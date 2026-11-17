"""Unit tests for media validation, filename sanitization, and audio normalization."""

import shutil
import subprocess
from pathlib import Path

import pytest

from src.core.errors import AppError
from src.core.media import (
    finalize_output_audio,
    inspect_audio_file,
    prepare_audio_for_engine,
    sanitize_display_name,
    validate_extension,
)


def _ffmpeg_generate(dest: Path, *, channels: int = 2, sample_rate: int = 44100, duration: float = 1.5) -> Path:
    cmd = [
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
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return dest


def test_sanitize_display_name_strips_paths_and_unsafe_chars():
    assert sanitize_display_name("../../etc/passwd.mp3") == "passwd"
    assert sanitize_display_name(r"C:\Users\me\My Song (Live)!!.wav") == "My_Song_Live"
    assert sanitize_display_name("...///...") == "audio_track"
    assert len(sanitize_display_name("a" * 150 + ".mp3")) <= 80


def test_validate_extension_accepts_and_rejects_correctly():
    assert validate_extension("track.MP3") == ".mp3"
    assert validate_extension("song.flac") == ".flac"
    assert validate_extension("voice.opus") == ".opus"

    for bad in ("script.exe", "notes.txt", "no_extension", "image.png"):
        with pytest.raises(AppError) as exc:
            validate_extension(bad)
        assert exc.value.code == "INVALID_FILE_FORMAT"


def test_inspect_audio_file_rejects_empty_and_corrupted_files(tmp_path):
    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(AppError) as empty_err:
        inspect_audio_file(empty, max_duration_seconds=1200)
    assert empty_err.value.code == "EMPTY_FILE"

    fake = tmp_path / "fake.mp3"
    fake.write_text("not really an audio stream at all", encoding="utf-8")
    with pytest.raises(AppError) as fake_err:
        inspect_audio_file(fake, max_duration_seconds=1200)
    assert fake_err.value.code == "INVALID_AUDIO_FILE"


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg/ffprobe required")
def test_inspect_audio_file_reads_mono_stereo_and_enforces_duration_limit(tmp_path):
    mono_48k = _ffmpeg_generate(tmp_path / "mono48.wav", channels=1, sample_rate=48000, duration=1.5)
    meta_mono = inspect_audio_file(mono_48k, max_duration_seconds=10)
    assert meta_mono.channels == 1
    assert meta_mono.sample_rate == 48000
    assert 1.3 <= meta_mono.duration_seconds <= 1.7

    stereo_44k = _ffmpeg_generate(tmp_path / "stereo44.mp3", channels=2, sample_rate=44100, duration=2.5)
    meta_stereo = inspect_audio_file(stereo_44k, max_duration_seconds=10)
    assert meta_stereo.channels == 2
    assert meta_stereo.sample_rate == 44100

    with pytest.raises(AppError) as too_long:
        inspect_audio_file(stereo_44k, max_duration_seconds=1)
    assert too_long.value.code == "AUDIO_TOO_LONG"


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg/ffprobe required")
def test_prepare_audio_downmixes_multichannel_and_finalize_preserves_mono_and_samplerate(tmp_path):
    surround = _ffmpeg_generate(tmp_path / "surround.wav", channels=6, sample_rate=48000, duration=1.2)
    meta_surround = inspect_audio_file(surround, max_duration_seconds=60)
    assert meta_surround.channels == 6

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    prepared = prepare_audio_for_engine(surround, work_dir, meta_surround)
    prepared_meta = inspect_audio_file(prepared, max_duration_seconds=60)
    assert prepared_meta.channels == 2

    # Simulate 44.1kHz stereo raw stem from engine being finalized back to 48kHz mono FLAC & MP3
    raw_stem = _ffmpeg_generate(work_dir / "raw_vocals.wav", channels=2, sample_rate=44100, duration=1.2)

    mono_flac = finalize_output_audio(
        source_path=raw_stem,
        dest_path=tmp_path / "out_vocals.flac",
        target_channels=1,
        target_sample_rate=48000,
        output_format="flac",
    )
    mono_meta = inspect_audio_file(mono_flac, max_duration_seconds=60)
    assert mono_meta.channels == 1
    assert mono_meta.sample_rate == 48000

    mp3_96k_clamped = finalize_output_audio(
        source_path=raw_stem,
        dest_path=tmp_path / "out_vocals.mp3",
        target_channels=2,
        target_sample_rate=96000,
        output_format="mp3",
    )
    mp3_meta = inspect_audio_file(mp3_96k_clamped, max_duration_seconds=60)
    assert mp3_meta.channels == 2
    assert mp3_meta.sample_rate == 48000
