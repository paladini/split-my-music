"""Integration tests for the FastAPI routes using a fake engine."""

from pathlib import Path
import shutil
import subprocess
import time
import zipfile

from fastapi.testclient import TestClient
import pytest

from src.api.routes import create_app
from src.config import Settings

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")


class _FakeEngine:
    def run_separation(self, *, model_spec, input_path, work_dir, output_dir, safe_base_name,
                       selected_outputs, output_format, input_metadata, stage_callback):
        stage_callback("separating", "Separating...")
        stage_callback("exporting", "Exporting...")
        out = {}
        for key in selected_outputs:
            p = output_dir / f"{safe_base_name}_{key}.{output_format}"
            p.write_bytes(b"audio-" + key.encode())
            out[key] = p
        return out


def _settings(tmp_path: Path, **kw) -> Settings:
    d = dict(base_dir=Path(__file__).resolve().parents[2], host="127.0.0.1", port=7860,
             model_cache_dir=tmp_path / "models", jobs_dir=tmp_path / "jobs", max_upload_mb=1,
             max_duration_minutes=10, max_concurrent_jobs=1, max_queue_size=3, min_free_disk_mb=0,
             retention_hours=24, max_stored_jobs=10, chunk_duration_seconds=300, log_level="INFO")
    d.update(kw)
    return Settings(**d)


def _wav(path: Path, seconds: float = 1.0) -> bytes:
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                    str(path)], check=True, capture_output=True)
    return path.read_bytes()


@pytest.fixture
def client(tmp_path):
    app = create_app(settings=_settings(tmp_path), engine=_FakeEngine())
    with TestClient(app) as c:
        yield c


def _wait(client, job_id):
    for _ in range(100):
        data = client.get(f"/api/jobs/{job_id}").json()
        if data["status"] in ("completed", "failed"):
            return data
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_health_config_and_index(client):
    h = client.get("/health").json()
    assert h["status"] == "healthy" and "device" in h
    cfg = client.get("/api/config").json()
    assert {g["id"] for g in cfg["goals"]} == {"vocals_music", "four_instruments", "six_instruments"}
    assert cfg["limits"]["max_upload_mb"] == 1
    page = client.get("/")
    assert page.status_code == 200


def test_full_flow_upload_poll_download_zip(client, tmp_path):
    data = _wav(tmp_path / "a.wav")
    r = client.post("/api/jobs", files={"file": ("my song.wav", data, "audio/wav")},
                    data={"goal": "vocals_music", "output_format": "wav"})
    assert r.status_code == 202, r.text
    job = _wait(client, r.json()["id"])
    assert job["status"] == "completed"
    assert [f["id"] for f in job["files"]] == ["vocals", "music"]
    f = job["files"][0]
    fr = client.get(f["stream_url"])
    assert fr.status_code == 200 and fr.content == b"audio-vocals"
    assert "attachment" in client.get(f["download_url"]).headers["content-disposition"]
    zr = client.get(job["zip_url"])
    assert zr.status_code == 200
    z = tmp_path / "out.zip"
    z.write_bytes(zr.content)
    assert len(zipfile.ZipFile(z).namelist()) == 2


def test_validation_errors(client, tmp_path):
    r = client.post("/api/jobs", files={"file": ("x.exe", b"abc", "application/octet-stream")})
    assert r.json()["error"]["code"] == "INVALID_FILE_FORMAT" and r.status_code == 400
    r = client.post("/api/jobs", files={"file": ("x.wav", b"", "audio/wav")})
    assert r.json()["error"]["code"] == "EMPTY_FILE"
    r = client.post("/api/jobs", files={"file": ("x.mp3", b"not audio at all", "audio/mpeg")})
    assert r.json()["error"]["code"] == "INVALID_AUDIO_FILE"
    r = client.post("/api/jobs", files={"file": ("x.wav", b"0" * (1024 * 1024 + 10), "audio/wav")})
    assert r.status_code == 413 and r.json()["error"]["code"] == "FILE_TOO_LARGE"
    good = _wav(tmp_path / "g.wav")
    r = client.post("/api/jobs", files={"file": ("g.wav", good, "audio/wav")},
                    data={"goal": "vocals_music", "outputs": "drums"})
    assert r.json()["error"]["code"] == "INVALID_OUTPUT_SELECTION"
    r = client.post("/api/jobs", files={"file": ("g.wav", good, "audio/wav")}, data={"model": "nope"})
    assert r.json()["error"]["code"] == "UNSUPPORTED_MODEL"
    # no leftover job folders from rejected uploads
    jobs = list((tmp_path / "jobs").iterdir())
    assert jobs == []


def test_path_traversal_and_unknown_jobs(client, tmp_path):
    data = _wav(tmp_path / "a.wav")
    job_id = client.post("/api/jobs", files={"file": ("a.wav", data, "audio/wav")}).json()["id"]
    _wait(client, job_id)
    assert client.get(f"/api/jobs/{job_id}/files/..%2Fjob.json").status_code == 404
    assert client.get(f"/api/jobs/{job_id}/files/job.json").status_code == 404
    assert client.get("/api/jobs/..%2F..%2Fetc/zip").status_code == 404
    assert client.get("/api/jobs/aaaaaaaaaaaa").status_code == 404
    assert client.delete(f"/api/jobs/{job_id}").status_code == 200
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
