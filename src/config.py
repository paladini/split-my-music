"""Environment-driven application settings for Split My Music."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _read_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    return max(minimum, value)


def _read_path(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return Path(raw.strip()).expanduser()


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings loaded from environment variables."""

    base_dir: Path
    host: str
    port: int
    model_cache_dir: Path
    jobs_dir: Path
    max_upload_mb: int
    max_duration_minutes: int
    max_concurrent_jobs: int
    max_queue_size: int
    min_free_disk_mb: int
    retention_hours: int
    max_stored_jobs: int
    chunk_duration_seconds: int
    log_level: str

    @property
    def max_upload_bytes(self) -> int:
        """Return the maximum upload size in bytes."""
        return self.max_upload_mb * 1024 * 1024

    @property
    def max_duration_seconds(self) -> int:
        """Return the maximum audio duration in seconds."""
        return self.max_duration_minutes * 60


def load_settings(base_dir: Path | None = None) -> Settings:
    """Load application settings from environment variables."""
    root = (base_dir or PROJECT_ROOT).resolve()
    host = (os.getenv("SPLIT_HOST") or "0.0.0.0").strip() or "0.0.0.0"
    port = min(65535, _read_int("SPLIT_PORT", 7860, minimum=1))
    model_cache_dir = _read_path("SPLIT_MODEL_CACHE_DIR", root / "data" / "models")
    jobs_dir = _read_path("SPLIT_JOBS_DIR", root / "data" / "jobs")
    log_level = (os.getenv("SPLIT_LOG_LEVEL") or "INFO").strip().upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        log_level = "INFO"

    return Settings(
        base_dir=root,
        host=host,
        port=port,
        model_cache_dir=model_cache_dir,
        jobs_dir=jobs_dir,
        max_upload_mb=_read_int("SPLIT_MAX_UPLOAD_MB", 200, minimum=1),
        max_duration_minutes=_read_int("SPLIT_MAX_DURATION_MINUTES", 20, minimum=1),
        max_concurrent_jobs=_read_int("SPLIT_MAX_CONCURRENT_JOBS", 1, minimum=1),
        max_queue_size=_read_int("SPLIT_MAX_QUEUE_SIZE", 5, minimum=1),
        min_free_disk_mb=_read_int("SPLIT_MIN_FREE_DISK_MB", 500, minimum=0),
        retention_hours=_read_int("SPLIT_RETENTION_HOURS", 24, minimum=1),
        max_stored_jobs=_read_int("SPLIT_MAX_STORED_JOBS", 20, minimum=1),
        chunk_duration_seconds=_read_int("SPLIT_CHUNK_DURATION_SECONDS", 300, minimum=30),
        log_level=log_level,
    )
