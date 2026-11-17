"""Audio file validation, filename sanitization, and format normalization utilities."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf

from src.core.errors import AppError

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus"}
)

_MP3_SAMPLE_RATES = (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000)
_TRANSCODE_BEFORE_ENGINE_EXTS = frozenset({".aac", ".m4a", ".opus"})


@dataclass(frozen=True)
class AudioMetadata:
    """Verified audio stream metadata extracted from an uploaded file."""

    duration_seconds: float
    sample_rate: int
    channels: int
    codec_name: str
    format_name: str


def check_ffmpeg_available() -> bool:
    """Return True if both ffmpeg and ffprobe executables are discoverable on PATH."""
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def sanitize_display_name(filename: str) -> str:
    """Sanitize a user-supplied filename into a safe, readable base name without path traversal."""
    normalized = (filename or "").replace("\\", "/")
    basename = normalized.split("/")[-1]
    stem = Path(basename).stem
    cleaned = re.sub(r"[^A-Za-z0-9\-_ ]+", "_", stem)
    cleaned = re.sub(r"[\s_]+", "_", cleaned)
    cleaned = cleaned.strip("._- ")
    if not cleaned:
        return "audio_track"
    return cleaned[:80]


def validate_extension(filename: str) -> str:
    """Validate and return the lowercase extension of an uploaded audio filename."""
    normalized = (filename or "").replace("\\", "/")
    basename = normalized.split("/")[-1]
    ext = Path(basename).suffix.lower()
    if not ext or ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(ext.lstrip(".").upper() for ext in SUPPORTED_EXTENSIONS))
        raise AppError(
            code="INVALID_FILE_FORMAT",
            user_message=f"Unsupported file format '{ext or 'unknown'}'.",
            suggestion=f"Upload an audio file in one of the supported formats: {supported}.",
            status_code=400,
        )
    return ext


def _nearest_mp3_sample_rate(sample_rate: int) -> int:
    if sample_rate in _MP3_SAMPLE_RATES:
        return sample_rate
    return min(_MP3_SAMPLE_RATES, key=lambda rate: abs(rate - sample_rate))


def _parse_float(value: object) -> float | None:
    if value is None or value == "N/A":
        return None
    try:
        parsed = float(value)
        return parsed if parsed > 0 else None
    except (TypeError, ValueError):
        return None


def inspect_audio_file(file_path: Path, max_duration_seconds: int) -> AudioMetadata:
    """Validate that an uploaded file contains a valid, non-empty audio stream within limits."""
    if not file_path.is_file():
        raise AppError(
            code="INVALID_AUDIO_FILE",
            user_message="The uploaded audio file could not be read on the server.",
            suggestion="Please upload the file again.",
            status_code=400,
        )

    if file_path.stat().st_size <= 0:
        raise AppError(
            code="EMPTY_FILE",
            user_message="The uploaded file is empty (0 bytes).",
            suggestion="Select a valid non-empty audio file from your device.",
            status_code=400,
        )

    if shutil.which("ffprobe") is None:
        return _inspect_with_soundfile_fallback(file_path, max_duration_seconds)

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_name,sample_rate,channels,duration:format=duration,format_name",
        "-of",
        "json",
        str(file_path),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        logger.warning("ffprobe timed out inspecting %s", file_path)
        raise AppError(
            code="INVALID_AUDIO_FILE",
            user_message="Reading audio metadata took too long; the file may be damaged.",
            suggestion="Try re-exporting the audio file as WAV or MP3 and uploading it again.",
            status_code=400,
        ) from exc

    if proc.returncode != 0:
        logger.warning("ffprobe rejected %s: %s", file_path, proc.stderr.strip())
        raise AppError(
            code="INVALID_AUDIO_FILE",
            user_message="This file does not appear to be a valid or readable audio track.",
            suggestion="Check that the file plays normally on your device, or convert it to WAV or MP3.",
            status_code=400,
        )

    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise AppError(
            code="INVALID_AUDIO_FILE",
            user_message="Could not read audio stream information from this file.",
            suggestion="Choose a valid MP3, WAV, FLAC, M4A, AAC, or OGG file.",
            status_code=400,
        ) from exc

    streams = payload.get("streams") or []
    if not streams:
        raise AppError(
            code="INVALID_AUDIO_FILE",
            user_message="No audio track was found inside this file.",
            suggestion="Make sure you uploaded a real audio file rather than a document or empty container.",
            status_code=400,
        )

    stream = streams[0]
    fmt = payload.get("format") or {}

    try:
        sample_rate = int(stream.get("sample_rate") or 0)
        channels = int(stream.get("channels") or 0)
    except (TypeError, ValueError):
        sample_rate = 0
        channels = 0

    duration = _parse_float(stream.get("duration")) or _parse_float(fmt.get("duration"))
    if duration is None:
        try:
            info = sf.info(str(file_path))
            duration = float(info.duration) if info.duration > 0 else None
            if sample_rate <= 0:
                sample_rate = int(info.samplerate)
            if channels <= 0:
                channels = int(info.channels)
        except Exception:
            duration = None

    if sample_rate <= 0 or channels <= 0 or duration is None or duration <= 0.05:
        raise AppError(
            code="INVALID_AUDIO_FILE",
            user_message="The audio file appears corrupted or too short to process.",
            suggestion="Select a valid audio file at least 1 second long.",
            status_code=400,
        )

    if duration > max_duration_seconds:
        max_minutes = max(1, max_duration_seconds // 60)
        raise AppError(
            code="AUDIO_TOO_LONG",
            user_message=(
                f"This audio file is {duration / 60:.1f} minutes long, exceeding the "
                f"{max_minutes}-minute server limit."
            ),
            suggestion="Trim the audio file or increase SPLIT_MAX_DURATION_MINUTES in server configuration.",
            status_code=400,
        )

    return AudioMetadata(
        duration_seconds=round(duration, 3),
        sample_rate=sample_rate,
        channels=channels,
        codec_name=str(stream.get("codec_name") or "unknown"),
        format_name=str(fmt.get("format_name") or "unknown"),
    )


def _inspect_with_soundfile_fallback(file_path: Path, max_duration_seconds: int) -> AudioMetadata:
    try:
        info = sf.info(str(file_path))
    except Exception as exc:
        raise AppError(
            code="INVALID_AUDIO_FILE",
            user_message="Could not read audio metadata (ffprobe is unavailable and file could not be decoded).",
            suggestion="Ensure FFmpeg is installed or upload an uncompressed WAV/FLAC file.",
            status_code=400,
        ) from exc

    if info.samplerate <= 0 or info.channels <= 0 or info.duration <= 0.05:
        raise AppError(
            code="INVALID_AUDIO_FILE",
            user_message="The audio file appears empty or corrupted.",
            suggestion="Choose a valid audio file at least 1 second long.",
            status_code=400,
        )
    if info.duration > max_duration_seconds:
        max_minutes = max(1, max_duration_seconds // 60)
        raise AppError(
            code="AUDIO_TOO_LONG",
            user_message=f"Audio duration exceeds the {max_minutes}-minute limit.",
            suggestion="Trim the track or adjust SPLIT_MAX_DURATION_MINUTES.",
            status_code=400,
        )
    return AudioMetadata(
        duration_seconds=round(float(info.duration), 3),
        sample_rate=int(info.samplerate),
        channels=int(info.channels),
        codec_name=str(info.subtype or "unknown"),
        format_name=str(info.format or "unknown"),
    )


def prepare_audio_for_engine(input_path: Path, work_dir: Path, metadata: AudioMetadata) -> Path:
    """Normalize >2 channel audio or AAC/M4A/OPUS containers into clean WAV prior to separation."""
    needs_downmix = metadata.channels > 2
    needs_container_decode = input_path.suffix.lower() in _TRANSCODE_BEFORE_ENGINE_EXTS

    if not needs_downmix and not needs_container_decode:
        return input_path

    if shutil.which("ffmpeg") is None:
        raise AppError(
            code="PROCESSING_FAILED",
            user_message="FFmpeg is required to decode this audio format, but it was not found on the server.",
            suggestion="Install FFmpeg on the host or use the official Docker image.",
            status_code=500,
        )

    target_channels = 2 if metadata.channels >= 2 else 1
    prepared_path = work_dir / "prepared_input.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        str(target_channels),
        "-codec:a",
        "pcm_s16le",
        str(prepared_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, shell=False, timeout=300)
    if proc.returncode != 0 or not prepared_path.is_file() or prepared_path.stat().st_size <= 0:
        logger.error("FFmpeg pre-normalization failed for %s: %s", input_path, proc.stderr.strip())
        raise AppError(
            code="INVALID_AUDIO_FILE",
            user_message="Failed to decode the uploaded audio stream for processing.",
            suggestion="Try converting the file to WAV or MP3 before uploading.",
            status_code=400,
        )
    return prepared_path


def finalize_output_audio(
    source_path: Path,
    dest_path: Path,
    target_channels: int,
    target_sample_rate: int,
    output_format: str,
) -> Path:
    """Export a separated audio file with accurate channel layout, sample rate, and target format."""
    if not source_path.is_file() or source_path.stat().st_size <= 0:
        raise AppError(
            code="EXPORT_FAILED",
            user_message="A separated audio track could not be written to disk.",
            suggestion="Check available disk space and try running the separation again.",
            status_code=500,
        )

    fmt = output_format.strip().lower()
    channels = 1 if target_channels == 1 else 2
    sample_rate = target_sample_rate if 8000 <= target_sample_rate <= 192000 else 44100
    if fmt == "mp3":
        sample_rate = _nearest_mp3_sample_rate(sample_rate)

    if shutil.which("ffmpeg") is None:
        if source_path.resolve() != dest_path.resolve():
            shutil.copy2(source_path, dest_path)
        return dest_path

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
    ]
    if fmt == "wav":
        cmd.extend(["-codec:a", "pcm_s16le"])
    elif fmt == "flac":
        cmd.extend(["-codec:a", "flac"])
    elif fmt == "mp3":
        cmd.extend(["-codec:a", "libmp3lame", "-b:a", "320k"])
    else:
        raise AppError(
            code="INVALID_OUTPUT_FORMAT",
            user_message=f"Unsupported export format '{output_format}'.",
            suggestion="Select WAV, FLAC, or MP3.",
            status_code=400,
        )

    cmd.append(str(dest_path))
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, shell=False, timeout=300)
    if proc.returncode != 0 or not dest_path.is_file() or dest_path.stat().st_size <= 0:
        logger.error("FFmpeg output export failed (%s -> %s): %s", source_path, dest_path, proc.stderr.strip())
        raise AppError(
            code="EXPORT_FAILED",
            user_message="Could not export the separated audio track into the requested format.",
            suggestion="Try exporting as WAV or check that enough disk space is available.",
            status_code=500,
        )

    return dest_path
