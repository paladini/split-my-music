"""Integration tests for JobManager queue, persistence, restart recovery, ZIP, and cleanup."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import threading
import time
import zipfile

import pytest

from src.config import Settings
from src.core.catalog import get_model
from src.core.errors import AppError
from src.core.jobs import JobManager
from src.core.media import AudioMetadata


def _make_settings(tmp_path: Path, **overrides) -> Settings:
    defaults = dict(
        base_dir=tmp_path,
        host="127.0.0.1",
        port=7860,
        model_cache_dir=tmp_path / "models",
        jobs_dir=tmp_path / "jobs",
        max_upload_mb=50,
        max_duration_minutes=10,
        max_concurrent_jobs=1,
        max_queue_size=1,
        min_free_disk_mb=500,
        retention_hours=24,
        max_stored_jobs=5,
        chunk_duration_seconds=300,
        log_level="INFO",
    )
    defaults.update(overrides)
    return Settings(**defaults)


class _ControlledEngine:
    def __init__(self, delay_seconds: float = 0.0, fail_exc: Exception | None = None):
        self.delay_seconds = delay_seconds
        self.fail_exc = fail_exc
        self.started_event = threading.Event()
        self.release_event = threading.Event()
        if delay_seconds == 0.0:
            self.release_event.set()

    def run_separation(
        self,
        *,
        model_spec,
        input_path,
        work_dir,
        output_dir,
        safe_base_name,
        selected_outputs,
        output_format,
        input_metadata,
        stage_callback,
    ):
        self.started_event.set()
        stage_callback("separating", "Separating...")
        if self.delay_seconds > 0:
            self.release_event.wait(timeout=self.delay_seconds)
        if self.fail_exc:
            raise self.fail_exc
        stage_callback("exporting", "Exporting...")
        results = {}
        for key in selected_outputs:
            dest = output_dir / f"{safe_base_name}_{key}.{output_format}"
            dest.write_bytes(b"RIFFfakeaudio" + key.encode("utf-8"))
            results[key] = dest
        return results


def _dummy_input(manager: JobManager, filename: str = "track.wav"):
    job_id, job_dir, input_path = manager.allocate_upload_slot(get_model("uvr_mdx_inst_hq_3"), ".wav")
    input_path.write_bytes(b"RIFFdummydata")
    meta = AudioMetadata(duration_seconds=3.0, sample_rate=44100, channels=2, codec_name="pcm_s16le", format_name="wav")
    return job_id, job_dir, input_path, meta


def test_job_lifecycle_creates_zip_and_cleans_temp_dirs(tmp_path):
    settings = _make_settings(tmp_path)
    engine = _ControlledEngine()
    manager = JobManager(settings=settings, engine=engine)

    job_id, job_dir, input_path, meta = _dummy_input(manager)
    job = manager.enqueue_job(
        job_id=job_id,
        job_dir=job_dir,
        input_path=input_path,
        safe_base_name="demo_song",
        original_filename="demo song.wav",
        model_spec=get_model("uvr_mdx_inst_hq_3"),
        selected_outputs=["vocals", "music"],
        output_format="wav",
        metadata=meta,
    )
    assert job["status"] == "queued"

    deadline = time.time() + 5
    while time.time() < deadline:
        current = manager.get_job(job_id)
        if current["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    final = manager.get_job(job_id)
    assert final["status"] == "completed"
    assert len(final["files"]) == 2
    assert not (job_dir / "input").exists()
    assert not (job_dir / "work").exists()

    zip_path, zip_name = manager.resolve_zip_file(job_id)
    assert zip_name == "demo_song_split_my_music.zip"
    with zipfile.ZipFile(zip_path) as zf:
        assert sorted(zf.namelist()) == ["demo_song_music.wav", "demo_song_vocals.wav"]

    vocals_path, _ = manager.resolve_output_file(job_id, "demo_song_vocals.wav")
    assert vocals_path.is_file()
    manager.shutdown()


def test_concurrency_queue_limit_and_disk_space_guard(tmp_path):
    settings = _make_settings(tmp_path, max_concurrent_jobs=1, max_queue_size=1)
    engine = _ControlledEngine(delay_seconds=5.0)
    manager = JobManager(settings=settings, engine=engine)

    # Job 1 occupies the single active worker
    j1_id, j1_dir, j1_in, meta = _dummy_input(manager)
    manager.enqueue_job(
        job_id=j1_id,
        job_dir=j1_dir,
        input_path=j1_in,
        safe_base_name="song1",
        original_filename="song1.wav",
        model_spec=get_model("uvr_mdx_inst_hq_3"),
        selected_outputs=["vocals"],
        output_format="wav",
        metadata=meta,
    )
    assert engine.started_event.wait(timeout=3)

    # Job 2 enters the 1-slot queue
    j2_id, j2_dir, j2_in, _ = _dummy_input(manager)
    j2 = manager.enqueue_job(
        job_id=j2_id,
        job_dir=j2_dir,
        input_path=j2_in,
        safe_base_name="song2",
        original_filename="song2.wav",
        model_spec=get_model("uvr_mdx_inst_hq_3"),
        selected_outputs=["vocals"],
        output_format="wav",
        metadata=meta,
    )
    assert j2["status"] == "queued"

    # Job 3 overflows queue -> SERVER_BUSY (429)
    with pytest.raises(AppError) as busy_err:
        manager.check_capacity_and_disk(get_model("uvr_mdx_inst_hq_3"))
    assert busy_err.value.code == "SERVER_BUSY"
    assert busy_err.value.status_code == 429

    engine.release_event.set()
    manager.shutdown()

    # Low disk check -> INSUFFICIENT_DISK_SPACE (507)
    low_disk_usage = lambda _path: shutil._ntuple_diskusage(total=10**10, used=9**10, free=100 * 1024 * 1024)
    low_disk_manager = JobManager(
        settings=settings,
        engine=_ControlledEngine(),
        disk_usage_fn=low_disk_usage,
    )
    with pytest.raises(AppError) as disk_err:
        low_disk_manager.check_capacity_and_disk(get_model("uvr_mdx_inst_hq_3"))
    assert disk_err.value.code == "INSUFFICIENT_DISK_SPACE"
    assert disk_err.value.status_code == 507
    low_disk_manager.shutdown()


def test_startup_recovery_and_safe_retention_cleanup(tmp_path):
    settings = _make_settings(tmp_path, retention_hours=24, max_stored_jobs=2)
    jobs_dir = settings.jobs_dir
    jobs_dir.mkdir(parents=True)

    # 1) Interrupted job from previous crash/restart
    interrupted_dir = jobs_dir / "aaaa1111bbbb"
    (interrupted_dir / "input").mkdir(parents=True)
    (interrupted_dir / "work").mkdir(parents=True)
    (interrupted_dir / "output").mkdir(parents=True)
    (interrupted_dir / "input" / "upload.wav").write_bytes(b"tmp")
    (interrupted_dir / "job.json").write_text(
        json.dumps(
            {
                "id": "aaaa1111bbbb",
                "status": "separating",
                "stage": "separating",
                "stage_message": "Separating...",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "files": [],
            }
        ),
        encoding="utf-8",
    )

    # 2) Expired completed job (48h old)
    old_dir = jobs_dir / "cccc2222dddd"
    (old_dir / "output").mkdir(parents=True)
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    (old_dir / "job.json").write_text(
        json.dumps(
            {
                "id": "cccc2222dddd",
                "status": "completed",
                "stage": "completed",
                "created_at": old_ts,
                "updated_at": old_ts,
                "files": [],
            }
        ),
        encoding="utf-8",
    )

    # 3) Recent completed job
    fresh_dir = jobs_dir / "eeee3333ffff"
    (fresh_dir / "output").mkdir(parents=True)
    fresh_ts = datetime.now(timezone.utc).isoformat()
    (fresh_dir / "job.json").write_text(
        json.dumps(
            {
                "id": "eeee3333ffff",
                "status": "completed",
                "stage": "completed",
                "created_at": fresh_ts,
                "updated_at": fresh_ts,
                "files": [],
            }
        ),
        encoding="utf-8",
    )

    manager = JobManager(settings=settings, engine=_ControlledEngine())
    recovered = manager.recover_interrupted_jobs()
    assert recovered == 1

    interrupted = manager.get_job("aaaa1111bbbb")
    assert interrupted["status"] == "failed"
    assert interrupted["error"]["code"] == "INTERRUPTED_BY_RESTART"
    assert not (interrupted_dir / "input").exists()
    assert not (interrupted_dir / "work").exists()

    cleaned = manager.cleanup_expired_jobs()
    assert cleaned == 1
    assert not old_dir.exists()
    assert fresh_dir.exists()
    manager.shutdown()


def test_unexpected_engine_exception_does_not_leak_traceback(tmp_path):
    settings = _make_settings(tmp_path)
    engine = _ControlledEngine(fail_exc=RuntimeError("secret internal stack details C:\\secret\\path"))
    manager = JobManager(settings=settings, engine=engine)

    job_id, job_dir, input_path, meta = _dummy_input(manager)
    manager.enqueue_job(
        job_id=job_id,
        job_dir=job_dir,
        input_path=input_path,
        safe_base_name="secret_song",
        original_filename="secret.wav",
        model_spec=get_model("uvr_mdx_inst_hq_3"),
        selected_outputs=["vocals"],
        output_format="wav",
        metadata=meta,
    )

    deadline = time.time() + 5
    while time.time() < deadline:
        current = manager.get_job(job_id)
        if current["status"] == "failed":
            break
        time.sleep(0.05)

    failed = manager.get_job(job_id)
    assert failed["status"] == "failed"
    assert "secret" not in failed["error"]["message"].lower()
    assert failed["error"]["code"] == "PROCESSING_FAILED"
    manager.shutdown()
