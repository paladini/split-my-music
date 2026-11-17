"""Real end-to-end separation on CPU with UVR-MDX-NET-Inst_HQ_3.onnx.

Downloads ~64 MB on first run (cached in ./data/models afterwards).
Run:  pytest -m real_model
"""

from pathlib import Path
import shutil
import subprocess
import time
import zipfile

from fastapi.testclient import TestClient
import pytest

from src.api.routes import create_app
from src.config import Settings
from src.core.catalog import get_model, is_model_cached
from src.core.media import inspect_audio_file

pytestmark = [pytest.mark.real_model,
              pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")]

ROOT = Path(__file__).resolve().parents[2]


def _music(path: Path, channels: int, rate: int, seconds: float = 4.0):
    # Tone chords + a noisy pulse: enough content for the model to run on.
    expr = ("aevalsrc='0.3*sin(2*PI*220*t)+0.2*sin(2*PI*330*t)+0.2*sin(2*PI*440*t)"
            "*(0.5+0.5*sin(2*PI*3*t))+0.1*random(0)*lt(mod(t,0.5),0.05)':"
            f"s={rate}:d={seconds}")
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", expr, "-ac", str(channels),
                    "-ar", str(rate), str(path)], check=True, capture_output=True)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("real")
    settings = Settings(base_dir=ROOT, host="127.0.0.1", port=7860,
                        model_cache_dir=ROOT / "data" / "models", jobs_dir=tmp / "jobs",
                        max_upload_mb=50, max_duration_minutes=10, max_concurrent_jobs=1,
                        max_queue_size=2, min_free_disk_mb=100, retention_hours=24,
                        max_stored_jobs=10, chunk_duration_seconds=300, log_level="INFO")
    with TestClient(create_app(settings=settings)) as c:
        yield c


def _run(client, path: Path, fmt: str, mime: str, timeout=900):
    r = client.post("/api/jobs", files={"file": (path.name, path.read_bytes(), mime)},
                    data={"goal": "vocals_music", "output_format": fmt})
    assert r.status_code == 202, r.text
    jid = r.json()["id"]
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(f"/api/jobs/{jid}").json()
        if job["status"] in ("completed", "failed"):
            return job
        time.sleep(1)
    raise AssertionError("timeout")


def test_mono_48k_wav_to_flac_preserves_layout(client, tmp_path):
    src = tmp_path / "mono.wav"
    _music(src, 1, 48000)
    job = _run(client, src, "flac", "audio/wav")
    assert job["status"] == "completed", job.get("error")
    assert is_model_cached(get_model("uvr_mdx_inst_hq_3"), ROOT / "data" / "models")
    assert {f["id"] for f in job["files"]} == {"vocals", "music"}
    for f in job["files"]:
        out = tmp_path / f["filename"]
        out.write_bytes(client.get(f["stream_url"]).content)
        meta = inspect_audio_file(out, 600)
        assert (meta.channels, meta.sample_rate) == (1, 48000)
        assert 3.5 < meta.duration_seconds < 4.6
    z = tmp_path / "all.zip"
    z.write_bytes(client.get(job["zip_url"]).content)
    assert len(zipfile.ZipFile(z).namelist()) == 2


def test_stereo_44k_mp3_to_wav_and_single_track(client, tmp_path):
    src = tmp_path / "stereo.mp3"
    _music(src, 2, 44100)
    r = client.post("/api/jobs", files={"file": (src.name, src.read_bytes(), "audio/mpeg")},
                    data={"goal": "vocals_music", "outputs": "music", "output_format": "wav"})
    jid = r.json()["id"]
    for _ in range(900):
        job = client.get(f"/api/jobs/{jid}").json()
        if job["status"] in ("completed", "failed"):
            break
        time.sleep(1)
    assert job["status"] == "completed", job.get("error")
    assert [f["id"] for f in job["files"]] == ["music"]
    out = tmp_path / "music.wav"
    out.write_bytes(client.get(job["files"][0]["stream_url"]).content)
    meta = inspect_audio_file(out, 600)
    assert (meta.channels, meta.sample_rate) == (2, 44100)
