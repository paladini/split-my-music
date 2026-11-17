"""Unit tests for the isolated python-audio-separator engine adapter."""

from pathlib import Path
import shutil
import subprocess

import pytest

from src.core.catalog import get_model
from src.core.engine import AudioSeparatorEngine, detect_hardware_info
from src.core.errors import AppError
from src.core.media import AudioMetadata


def _make_wav(path: Path, channels: int = 2, sample_rate: int = 44100, duration: float = 0.8) -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate={sample_rate}:duration={duration}",
            "-ac",
            str(channels),
            "-ar",
            str(sample_rate),
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


class _FakeSeparator:
    def __init__(self, *, model_file_dir, output_dir, output_format, chunk_duration, output_single_stem=None, **kwargs):
        self.model_file_dir = Path(model_file_dir)
        self.output_dir = Path(output_dir)
        self.output_format = output_format
        self.chunk_duration = chunk_duration
        self.output_single_stem = output_single_stem
        self.loaded_model = None

    def load_model(self, model_filename):
        self.loaded_model = model_filename
        (self.model_file_dir / model_filename).write_bytes(b"weights")

    def separate(self, audio_file_path, custom_output_names=None):
        results = []
        for stem_name, custom_base in (custom_output_names or {}).items():
            if self.output_single_stem and stem_name.lower() != self.output_single_stem.lower():
                continue
            if stem_name in ("Vocals", "Instrumental"):
                out_file = self.output_dir / f"{custom_base}.wav"
                _make_wav(out_file, channels=2, sample_rate=44100, duration=0.5)
                results.append(out_file.name)
        return results


def test_detect_hardware_info_returns_honest_structure():
    info = detect_hardware_info()
    data = info.to_dict()
    assert data["device_type"] in {"cpu", "cuda"}
    assert isinstance(data["device_label"], str) and data["device_label"]
    assert isinstance(data["onnx_providers"], list)
    assert isinstance(data["ffmpeg_available"], bool)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_engine_runs_stages_caches_model_and_exports_requested_outputs(tmp_path):
    cache_dir = tmp_path / "models"
    work_dir = tmp_path / "work"
    output_dir = tmp_path / "output"
    cache_dir.mkdir()
    work_dir.mkdir()
    output_dir.mkdir()

    input_wav = _make_wav(tmp_path / "song.wav", channels=1, sample_rate=48000, duration=0.5)
    meta = AudioMetadata(duration_seconds=0.5, sample_rate=48000, channels=1, codec_name="pcm_s16le", format_name="wav")

    stages = []
    captured_kwargs = {}

    def fake_factory(**kwargs):
        captured_kwargs.update(kwargs)
        return _FakeSeparator(**kwargs)

    engine = AudioSeparatorEngine(model_cache_dir=cache_dir, chunk_duration_seconds=300, separator_factory=fake_factory)
    outputs = engine.run_separation(
        model_spec=get_model("uvr_mdx_inst_hq_3"),
        input_path=input_wav,
        work_dir=work_dir,
        output_dir=output_dir,
        safe_base_name="my_song",
        selected_outputs=["vocals"],
        output_format="flac",
        input_metadata=meta,
        stage_callback=lambda stage, msg: stages.append((stage, msg)),
    )

    assert [s[0] for s in stages] == ["downloading_model", "separating", "exporting"]
    assert captured_kwargs["output_single_stem"] == "Vocals"
    assert list(outputs.keys()) == ["vocals"]
    assert outputs["vocals"].name == "my_song_vocals.flac"
    assert outputs["vocals"].is_file() and outputs["vocals"].stat().st_size > 0


def test_engine_maps_download_oom_and_missing_output_errors(tmp_path):
    cache_dir = tmp_path / "models"
    work_dir = tmp_path / "work"
    output_dir = tmp_path / "output"
    cache_dir.mkdir()
    work_dir.mkdir()
    output_dir.mkdir()
    input_wav = tmp_path / "dummy.wav"
    input_wav.write_bytes(b"RIFF")
    meta = AudioMetadata(duration_seconds=1.0, sample_rate=44100, channels=2, codec_name="pcm_s16le", format_name="wav")

    class _DownloadFailSep:
        def __init__(self, **_):
            pass

        def load_model(self, model_filename):
            # Leave a 0-byte partial file behind to verify cleanup
            (cache_dir / model_filename).write_bytes(b"")
            raise ConnectionError("Failed to download model file: timeout")

    engine_dl = AudioSeparatorEngine(model_cache_dir=cache_dir, separator_factory=lambda **kw: _DownloadFailSep(**kw))
    with pytest.raises(AppError) as dl_err:
        engine_dl.run_separation(
            model_spec=get_model("uvr_mdx_inst_hq_3"),
            input_path=input_wav,
            work_dir=work_dir,
            output_dir=output_dir,
            safe_base_name="song",
            selected_outputs=["vocals", "music"],
            output_format="wav",
            input_metadata=meta,
            stage_callback=lambda *_: None,
        )
    assert dl_err.value.code == "MODEL_DOWNLOAD_FAILED"
    assert not (cache_dir / "UVR-MDX-NET-Inst_HQ_3.onnx").exists()

    class _OomSep:
        def __init__(self, **_):
            pass

        def load_model(self, model_filename):
            (cache_dir / model_filename).write_bytes(b"ok")

        def separate(self, *_args, **_kwargs):
            raise RuntimeError("CUDA out of memory while allocating tensor")

    engine_oom = AudioSeparatorEngine(model_cache_dir=cache_dir, separator_factory=lambda **kw: _OomSep(**kw))
    with pytest.raises(AppError) as oom_err:
        engine_oom.run_separation(
            model_spec=get_model("uvr_mdx_inst_hq_3"),
            input_path=input_wav,
            work_dir=work_dir,
            output_dir=output_dir,
            safe_base_name="song",
            selected_outputs=["vocals"],
            output_format="wav",
            input_metadata=meta,
            stage_callback=lambda *_: None,
        )
    assert oom_err.value.code == "OUT_OF_MEMORY"

    class _EmptyOutputSep:
        def __init__(self, **_):
            pass

        def load_model(self, model_filename):
            (cache_dir / model_filename).write_bytes(b"ok")

        def separate(self, *_args, **_kwargs):
            return []

    engine_empty = AudioSeparatorEngine(model_cache_dir=cache_dir, separator_factory=lambda **kw: _EmptyOutputSep(**kw))
    with pytest.raises(AppError) as empty_err:
        engine_empty.run_separation(
            model_spec=get_model("uvr_mdx_inst_hq_3"),
            input_path=input_wav,
            work_dir=work_dir,
            output_dir=output_dir,
            safe_base_name="song",
            selected_outputs=["vocals"],
            output_format="wav",
            input_metadata=meta,
            stage_callback=lambda *_: None,
        )
    assert empty_err.value.code == "EXPORT_FAILED"
