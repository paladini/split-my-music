"""Unit tests for configuration loading and curated catalog invariants."""

from pathlib import Path

from src.config import Settings, load_settings


def test_load_settings_defaults(monkeypatch, tmp_path):
    for var in (
        "SPLIT_HOST",
        "SPLIT_PORT",
        "SPLIT_MODEL_CACHE_DIR",
        "SPLIT_JOBS_DIR",
        "SPLIT_MAX_UPLOAD_MB",
        "SPLIT_MAX_DURATION_MINUTES",
        "SPLIT_MAX_CONCURRENT_JOBS",
        "SPLIT_MAX_QUEUE_SIZE",
        "SPLIT_MIN_FREE_DISK_MB",
        "SPLIT_RETENTION_HOURS",
        "SPLIT_MAX_STORED_JOBS",
        "SPLIT_CHUNK_DURATION_SECONDS",
        "SPLIT_LOG_LEVEL",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = load_settings(base_dir=tmp_path)

    assert isinstance(settings, Settings)
    assert settings.host == "0.0.0.0"
    assert settings.port == 7860
    assert settings.model_cache_dir == tmp_path / "data" / "models"
    assert settings.jobs_dir == tmp_path / "data" / "jobs"
    assert settings.max_upload_mb == 200
    assert settings.max_duration_minutes == 20
    assert settings.max_concurrent_jobs == 1
    assert settings.max_queue_size == 5
    assert settings.min_free_disk_mb == 500
    assert settings.retention_hours == 24
    assert settings.max_stored_jobs == 20
    assert settings.chunk_duration_seconds == 300
    assert settings.log_level == "INFO"


def test_load_settings_env_overrides(monkeypatch, tmp_path):
    custom_models = tmp_path / "custom_models"
    custom_jobs = tmp_path / "custom_jobs"

    monkeypatch.setenv("SPLIT_HOST", "127.0.0.1")
    monkeypatch.setenv("SPLIT_PORT", "8080")
    monkeypatch.setenv("SPLIT_MODEL_CACHE_DIR", str(custom_models))
    monkeypatch.setenv("SPLIT_JOBS_DIR", str(custom_jobs))
    monkeypatch.setenv("SPLIT_MAX_UPLOAD_MB", "150")
    monkeypatch.setenv("SPLIT_MAX_DURATION_MINUTES", "15")
    monkeypatch.setenv("SPLIT_MAX_CONCURRENT_JOBS", "2")
    monkeypatch.setenv("SPLIT_MAX_QUEUE_SIZE", "8")
    monkeypatch.setenv("SPLIT_MIN_FREE_DISK_MB", "1024")
    monkeypatch.setenv("SPLIT_RETENTION_HOURS", "12")
    monkeypatch.setenv("SPLIT_MAX_STORED_JOBS", "50")
    monkeypatch.setenv("SPLIT_CHUNK_DURATION_SECONDS", "180")
    monkeypatch.setenv("SPLIT_LOG_LEVEL", "debug")

    settings = load_settings(base_dir=tmp_path)

    assert settings.host == "127.0.0.1"
    assert settings.port == 8080
    assert settings.model_cache_dir == custom_models
    assert settings.jobs_dir == custom_jobs
    assert settings.max_upload_mb == 150
    assert settings.max_duration_minutes == 15
    assert settings.max_concurrent_jobs == 2
    assert settings.max_queue_size == 8
    assert settings.min_free_disk_mb == 1024
    assert settings.retention_hours == 12
    assert settings.max_stored_jobs == 50
    assert settings.chunk_duration_seconds == 180
    assert settings.log_level == "DEBUG"
    assert settings.max_upload_bytes == 150 * 1024 * 1024
    assert settings.max_duration_seconds == 15 * 60


def test_load_settings_enforces_safe_minimums(monkeypatch, tmp_path):
    monkeypatch.setenv("SPLIT_MAX_CONCURRENT_JOBS", "0")
    monkeypatch.setenv("SPLIT_MAX_QUEUE_SIZE", "0")
    monkeypatch.setenv("SPLIT_MAX_UPLOAD_MB", "0")

    settings = load_settings(base_dir=tmp_path)

    assert settings.max_concurrent_jobs >= 1
    assert settings.max_queue_size >= 1
    assert settings.max_upload_mb >= 1
