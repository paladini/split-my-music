"""Unit tests for configuration loading and curated catalog invariants."""

from pathlib import Path
import pytest

from src.config import Settings, load_settings
from src.core.catalog import (
    CURATED_MODELS,
    OUTPUT_FORMATS,
    SEPARATION_GOALS,
    TRACK_DEFINITIONS,
    get_goal,
    get_model,
    get_output_format,
    is_model_cached,
    list_public_catalog,
    resolve_model_and_outputs,
)
from src.core.errors import AppError


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


def test_app_error_to_dict():
    err = AppError(
        code="INVALID_FILE_FORMAT",
        user_message="Unsupported file.",
        suggestion="Upload MP3 or WAV.",
        status_code=400,
    )
    assert err.status_code == 400
    assert err.to_dict() == {
        "code": "INVALID_FILE_FORMAT",
        "message": "Unsupported file.",
        "suggestion": "Upload MP3 or WAV.",
    }


def test_catalog_goals_models_and_tracks_are_consistent():
    assert "vocals_music" in SEPARATION_GOALS
    assert "four_instruments" in SEPARATION_GOALS
    assert "six_instruments" in SEPARATION_GOALS

    for goal_id, goal in SEPARATION_GOALS.items():
        assert goal.default_model_id in CURATED_MODELS
        default_model = CURATED_MODELS[goal.default_model_id]
        assert default_model.goal == goal_id

    for model in CURATED_MODELS.values():
        assert model.goal in SEPARATION_GOALS
        assert len(model.outputs) >= 2
        assert len(model.required_files) >= 1
        assert model.download_size_mb > 0
        for output_key in model.outputs:
            assert output_key in TRACK_DEFINITIONS
            assert "stem" not in TRACK_DEFINITIONS[output_key].label.lower()

    assert "wav" in OUTPUT_FORMATS and OUTPUT_FORMATS["wav"].lossless is True
    assert "flac" in OUTPUT_FORMATS and OUTPUT_FORMATS["flac"].lossless is True
    assert "mp3" in OUTPUT_FORMATS and OUTPUT_FORMATS["mp3"].lossless is False


def test_resolve_model_and_outputs_validates_strictly():
    model, outputs = resolve_model_and_outputs(
        goal_id="vocals_music",
        model_id=None,
        requested_outputs=None,
    )
    assert model.id == "uvr_mdx_inst_hq_3"
    assert outputs == ["vocals", "music"]

    model2, outputs2 = resolve_model_and_outputs(
        goal_id="four_instruments",
        model_id=None,
        requested_outputs=["drums", "vocals", "drums"],
    )
    assert model2.id == "htdemucs_4s"
    assert outputs2 == ["drums", "vocals"]

    with pytest.raises(AppError) as exc_info:
        resolve_model_and_outputs(
            goal_id="vocals_music",
            model_id="uvr_mdx_inst_hq_3",
            requested_outputs=["drums"],
        )
    assert exc_info.value.code == "INVALID_OUTPUT_SELECTION"

    with pytest.raises(AppError) as bad_model:
        get_model("nonexistent-model")
    assert bad_model.value.code == "UNSUPPORTED_MODEL"

    with pytest.raises(AppError) as bad_goal:
        get_goal("nonexistent-goal")
    assert bad_goal.value.code == "INVALID_GOAL"

    with pytest.raises(AppError) as bad_fmt:
        get_output_format("wma")
    assert bad_fmt.value.code == "INVALID_OUTPUT_FORMAT"


def test_is_model_cached_checks_all_required_nonempty_files(tmp_path):
    model = get_model("htdemucs_4s")
    assert is_model_cached(model, tmp_path) is False

    # Partial download (missing .th) or 0-byte file must count as uncached
    (tmp_path / "htdemucs.yaml").write_text("yaml", encoding="utf-8")
    (tmp_path / "955717e8-8726e21a.th").write_bytes(b"")
    assert is_model_cached(model, tmp_path) is False

    (tmp_path / "955717e8-8726e21a.th").write_bytes(b"weights")
    assert is_model_cached(model, tmp_path) is True

    public = list_public_catalog(tmp_path)
    ht_entry = next(m for m in public["models"] if m["id"] == "htdemucs_4s")
    assert ht_entry["cached"] is True
