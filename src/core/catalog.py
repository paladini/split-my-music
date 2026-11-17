"""Curated separation goals, validated AI models, tracks, and output formats."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.errors import AppError


@dataclass(frozen=True)
class TrackDefinition:
    """User-facing audio track metadata mapped to python-audio-separator stem labels."""

    id: str
    label: str
    description: str
    engine_stem_name: str


@dataclass(frozen=True)
class SeparationGoal:
    """Plain-English separation goal shown in the primary interface."""

    id: str
    label: str
    description: str
    default_model_id: str


@dataclass(frozen=True)
class ModelSpec:
    """Curated, tested model supported by the application."""

    id: str
    model_filename: str
    name: str
    goal: str
    architecture: str
    outputs: tuple[str, ...]
    download_size_mb: int
    required_files: tuple[str, ...]
    recommended_device: str
    cpu_friendly: bool
    description: str
    license_note: str


@dataclass(frozen=True)
class OutputFormatSpec:
    """Audio export format supported by Split My Music."""

    id: str
    label: str
    short_label: str
    extension: str
    mime_type: str
    lossless: bool
    description: str


TRACK_DEFINITIONS: dict[str, TrackDefinition] = {
    "vocals": TrackDefinition(
        id="vocals",
        label="Vocals",
        description="Lead singing voice",
        engine_stem_name="Vocals",
    ),
    "music": TrackDefinition(
        id="music",
        label="Music",
        description="Instrumental backing track without vocals",
        engine_stem_name="Instrumental",
    ),
    "drums": TrackDefinition(
        id="drums",
        label="Drums",
        description="Percussion and drum kit",
        engine_stem_name="Drums",
    ),
    "bass": TrackDefinition(
        id="bass",
        label="Bass",
        description="Bass guitar and low-end groove",
        engine_stem_name="Bass",
    ),
    "guitar": TrackDefinition(
        id="guitar",
        label="Guitar",
        description="Electric and acoustic guitars",
        engine_stem_name="Guitar",
    ),
    "piano": TrackDefinition(
        id="piano",
        label="Piano",
        description="Piano and keyboard parts",
        engine_stem_name="Piano",
    ),
    "other": TrackDefinition(
        id="other",
        label="Other Instruments",
        description="Remaining melodies, synths, and textures",
        engine_stem_name="Other",
    ),
}

SEPARATION_GOALS: dict[str, SeparationGoal] = {
    "vocals_music": SeparationGoal(
        id="vocals_music",
        label="Vocals & Music",
        description="Split the singing voice from the instrumental backing track.",
        default_model_id="uvr_mdx_inst_hq_3",
    ),
    "four_instruments": SeparationGoal(
        id="four_instruments",
        label="Vocals, Drums, Bass & Other",
        description="Separate a song into 4 distinct instrument tracks.",
        default_model_id="htdemucs_4s",
    ),
    "six_instruments": SeparationGoal(
        id="six_instruments",
        label="Full Band (6 Tracks)",
        description="Split into vocals, drums, bass, guitar, piano, and other instruments.",
        default_model_id="htdemucs_6s",
    ),
}

CURATED_MODELS: dict[str, ModelSpec] = {
    "uvr_mdx_inst_hq_3": ModelSpec(
        id="uvr_mdx_inst_hq_3",
        model_filename="UVR-MDX-NET-Inst_HQ_3.onnx",
        name="UVR MDX-Net Inst HQ 3 (Balanced Default)",
        goal="vocals_music",
        architecture="MDX-Net (ONNX)",
        outputs=("vocals", "music"),
        download_size_mb=64,
        required_files=("UVR-MDX-NET-Inst_HQ_3.onnx",),
        recommended_device="cpu_or_gpu",
        cpu_friendly=True,
        description="Fast, reliable separation for vocals and backing music on both CPU and NVIDIA GPU.",
        license_note="MIT (Ultimate Vocal Remover / Anjok07)",
    ),
    "kim_vocal_2": ModelSpec(
        id="kim_vocal_2",
        model_filename="Kim_Vocal_2.onnx",
        name="Kim Vocal 2 (Vocal Clarity)",
        goal="vocals_music",
        architecture="MDX-Net (ONNX)",
        outputs=("vocals", "music"),
        download_size_mb=64,
        required_files=("Kim_Vocal_2.onnx",),
        recommended_device="cpu_or_gpu",
        cpu_friendly=True,
        description="Tuned for crisp vocal extraction with reduced instrumental bleed.",
        license_note="MIT (KimberleyJSN / UVR)",
    ),
    "uvr_karaoke_2": ModelSpec(
        id="uvr_karaoke_2",
        model_filename="UVR_MDXNET_KARA_2.onnx",
        name="UVR Karaoke 2 (Keep Backing Vocals)",
        goal="vocals_music",
        architecture="MDX-Net (ONNX)",
        outputs=("vocals", "music"),
        download_size_mb=50,
        required_files=("UVR_MDXNET_KARA_2.onnx",),
        recommended_device="cpu_or_gpu",
        cpu_friendly=True,
        description="Focuses on lead vocals while leaving backing harmonies in the music track.",
        license_note="MIT (Ultimate Vocal Remover / Anjok07)",
    ),
    "htdemucs_4s": ModelSpec(
        id="htdemucs_4s",
        model_filename="htdemucs.yaml",
        name="HTDemucs v4 (4-Track Instruments)",
        goal="four_instruments",
        architecture="Demucs v4 (PyTorch)",
        outputs=("vocals", "drums", "bass", "other"),
        download_size_mb=80,
        required_files=("htdemucs.yaml", "955717e8-8726e21a.th"),
        recommended_device="cpu_or_gpu",
        cpu_friendly=True,
        description="Meta AI Hybrid Transformer Demucs separating vocals, drums, bass, and other instruments.",
        license_note="MIT (Meta AI Research / Demucs)",
    ),
    "htdemucs_6s": ModelSpec(
        id="htdemucs_6s",
        model_filename="htdemucs_6s.yaml",
        name="HTDemucs v4 6-Track (+ Guitar & Piano)",
        goal="six_instruments",
        architecture="Demucs v4 (PyTorch)",
        outputs=("vocals", "drums", "bass", "guitar", "piano", "other"),
        download_size_mb=53,
        required_files=("htdemucs_6s.yaml", "5c90dfd2-34c22ccb.th"),
        recommended_device="cpu_or_gpu",
        cpu_friendly=True,
        description="6-track instrument separation adding guitar and piano (note: guitar and piano may occasionally bleed).",
        license_note="MIT (Meta AI Research / Demucs)",
    ),
    "bs_roformer_1297": ModelSpec(
        id="bs_roformer_1297",
        model_filename="model_bs_roformer_ep_317_sdr_12.9755.ckpt",
        name="BS-RoFormer Viperx 1297 (Studio Quality — GPU Recommended)",
        goal="vocals_music",
        architecture="BS-RoFormer (MDXC PyTorch)",
        outputs=("vocals", "music"),
        download_size_mb=610,
        required_files=(
            "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
            "model_bs_roformer_ep_317_sdr_12.9755.yaml",
        ),
        recommended_device="gpu_recommended",
        cpu_friendly=False,
        description="High-accuracy vocal/music model (~610 MB download); very slow without an NVIDIA GPU.",
        license_note="MIT (ViperX / lucidrains / UVR)",
    ),
}

OUTPUT_FORMATS: dict[str, OutputFormatSpec] = {
    "wav": OutputFormatSpec(
        id="wav",
        label="WAV (Lossless Uncompressed)",
        short_label="WAV · Lossless",
        extension=".wav",
        mime_type="audio/wav",
        lossless=True,
        description="Uncompressed studio-quality audio preserving exact waveform fidelity.",
    ),
    "flac": OutputFormatSpec(
        id="flac",
        label="FLAC (Lossless Compressed)",
        short_label="FLAC · Lossless",
        extension=".flac",
        mime_type="audio/flac",
        lossless=True,
        description="Lossless audio at roughly half the file size of WAV.",
    ),
    "mp3": OutputFormatSpec(
        id="mp3",
        label="MP3 (320 kbps High Quality)",
        short_label="MP3 · 320 kbps",
        extension=".mp3",
        mime_type="audio/mpeg",
        lossless=False,
        description="Compact, universally compatible files ideal for quick sharing.",
    ),
}


def get_goal(goal_id: str) -> SeparationGoal:
    """Return a validated separation goal or raise AppError."""
    goal = SEPARATION_GOALS.get(goal_id)
    if goal is None:
        raise AppError(
            code="INVALID_GOAL",
            user_message=f"Separation option '{goal_id}' is not recognized.",
            suggestion="Choose Vocals & Music, 4-Track Instruments, or Full Band (6 Tracks).",
            status_code=400,
        )
    return goal


def get_model(model_id: str) -> ModelSpec:
    """Return a curated model specification or raise AppError."""
    model = CURATED_MODELS.get(model_id)
    if model is None:
        raise AppError(
            code="UNSUPPORTED_MODEL",
            user_message=f"Model '{model_id}' is not in the supported Split My Music catalog.",
            suggestion="Select one of the verified models in Advanced Settings or reset to the default model.",
            status_code=400,
        )
    return model


def get_output_format(format_id: str) -> OutputFormatSpec:
    """Return a validated output format specification or raise AppError."""
    fmt = OUTPUT_FORMATS.get((format_id or "").strip().lower())
    if fmt is None:
        raise AppError(
            code="INVALID_OUTPUT_FORMAT",
            user_message=f"Output format '{format_id}' is not supported.",
            suggestion="Choose WAV (lossless), FLAC (lossless), or MP3.",
            status_code=400,
        )
    return fmt


def resolve_model_and_outputs(
    goal_id: str | None,
    model_id: str | None,
    requested_outputs: list[str] | None,
) -> tuple[ModelSpec, list[str]]:
    """Resolve the effective curated model and validate requested outputs against its capabilities."""
    if model_id and model_id.strip():
        model = get_model(model_id.strip())
    else:
        goal = get_goal((goal_id or "vocals_music").strip())
        model = get_model(goal.default_model_id)

    if not requested_outputs:
        selected = list(model.outputs)
    else:
        seen: set[str] = set()
        selected = []
        for raw in requested_outputs:
            key = raw.strip().lower()
            if not key or key in seen:
                continue
            if key not in model.outputs:
                allowed = ", ".join(TRACK_DEFINITIONS[o].label for o in model.outputs)
                raise AppError(
                    code="INVALID_OUTPUT_SELECTION",
                    user_message=(
                        f"'{model.name}' cannot export '{raw}'. "
                        f"It only produces: {allowed}."
                    ),
                    suggestion="Select only tracks supported by the chosen separation option or switch models.",
                    status_code=400,
                )
            seen.add(key)
            selected.append(key)

    if not selected:
        selected = list(model.outputs)

    return model, selected


def is_model_cached(model_spec: ModelSpec, model_cache_dir: Path) -> bool:
    """Check whether every required weight/config file for a curated model is cached and non-empty."""
    if not model_cache_dir.exists():
        return False
    for filename in model_spec.required_files:
        candidate = model_cache_dir / filename
        if not candidate.is_file():
            return False
        try:
            if candidate.stat().st_size <= 0:
                return False
        except OSError:
            return False
    return True


def list_public_catalog(model_cache_dir: Path) -> dict[str, object]:
    """Serialize goals, models with cache status, tracks, and output formats for the frontend."""
    goals_payload = [
        {
            "id": goal.id,
            "label": goal.label,
            "description": goal.description,
            "default_model_id": goal.default_model_id,
            "outputs": list(CURATED_MODELS[goal.default_model_id].outputs),
        }
        for goal in SEPARATION_GOALS.values()
    ]

    models_payload = []
    for model in CURATED_MODELS.values():
        cached = is_model_cached(model, model_cache_dir)
        models_payload.append(
            {
                "id": model.id,
                "name": model.name,
                "goal": model.goal,
                "architecture": model.architecture,
                "outputs": list(model.outputs),
                "download_size_mb": model.download_size_mb,
                "recommended_device": model.recommended_device,
                "cpu_friendly": model.cpu_friendly,
                "description": model.description,
                "license_note": model.license_note,
                "cached": cached,
                "cache_status": "Cached locally" if cached else f"Downloads ~{model.download_size_mb} MB on first use",
            }
        )

    tracks_payload = {
        track.id: {
            "id": track.id,
            "label": track.label,
            "description": track.description,
        }
        for track in TRACK_DEFINITIONS.values()
    }

    formats_payload = [
        {
            "id": fmt.id,
            "label": fmt.label,
            "short_label": fmt.short_label,
            "extension": fmt.extension,
            "lossless": fmt.lossless,
            "description": fmt.description,
        }
        for fmt in OUTPUT_FORMATS.values()
    ]

    return {
        "goals": goals_payload,
        "models": models_payload,
        "tracks": tracks_payload,
        "output_formats": formats_payload,
    }
