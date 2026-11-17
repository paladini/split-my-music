"""Isolated wrapper around python-audio-separator and hardware acceleration detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.core.catalog import TRACK_DEFINITIONS, ModelSpec, get_output_format, is_model_cached
from src.core.errors import AppError
from src.core.media import AudioMetadata, check_ffmpeg_available, finalize_output_audio

logger = logging.getLogger(__name__)

StageCallback = Callable[[str, str], None]


@dataclass(frozen=True)
class HardwareInfo:
    """Verified compute environment reported by PyTorch, ONNX Runtime, and FFmpeg."""

    device_type: str
    device_label: str
    gpu_name: str | None
    onnx_providers: list[str]
    ffmpeg_available: bool

    def to_dict(self) -> dict[str, Any]:
        """Serialize hardware details for health/config responses."""
        return {
            "device_type": self.device_type,
            "device_label": self.device_label,
            "gpu_name": self.gpu_name,
            "onnx_providers": list(self.onnx_providers),
            "ffmpeg_available": self.ffmpeg_available,
        }


def detect_hardware_info() -> HardwareInfo:
    """Inspect available PyTorch CUDA and ONNX Runtime providers without fabricating acceleration."""
    gpu_name: str | None = None
    device_type = "cpu"
    device_label = "CPU"
    onnx_providers: list[str] = []

    try:
        import torch

        if torch.cuda.is_available():
            device_type = "cuda"
            try:
                gpu_name = torch.cuda.get_device_name(0)
                device_label = f"NVIDIA GPU ({gpu_name})"
            except Exception:
                device_label = "NVIDIA GPU (CUDA)"
    except Exception as exc:
        logger.debug("PyTorch CUDA inspection failed, defaulting to CPU: %s", exc)

    try:
        import onnxruntime as ort

        onnx_providers = list(ort.get_available_providers())
    except Exception as exc:
        logger.debug("ONNX Runtime provider inspection failed: %s", exc)

    return HardwareInfo(
        device_type=device_type,
        device_label=device_label,
        gpu_name=gpu_name,
        onnx_providers=onnx_providers,
        ffmpeg_available=check_ffmpeg_available(),
    )


def _clear_cuda_cache_quietly() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _cleanup_zero_byte_model_files(model_cache_dir: Path, required_files: tuple[str, ...]) -> None:
    for filename in required_files:
        candidate = model_cache_dir / filename
        try:
            if candidate.is_file() and candidate.stat().st_size <= 0:
                candidate.unlink()
        except OSError:
            pass


def _classify_load_error(exc: Exception, model_spec: ModelSpec) -> AppError:
    msg = str(exc).lower()
    if any(
        token in msg
        for token in (
            "out of memory",
            "cuda error",
            "cudnn",
            "cannot allocate",
            "cublas",
        )
    ) or isinstance(exc, MemoryError):
        return AppError(
            code="OUT_OF_MEMORY",
            user_message=f"Not enough memory to load '{model_spec.name}'.",
            suggestion="Try using the default lighter model (UVR MDX-Net Inst HQ 3) or close memory-heavy apps.",
            status_code=500,
        )

    if any(
        token in msg
        for token in (
            "download",
            "connection",
            "timed out",
            "timeout",
            "name resolution",
            "http",
            "ssl",
            "404",
            "checksum",
            "hash",
            "url",
        )
    ) or isinstance(exc, (ConnectionError, TimeoutError)):
        return AppError(
            code="MODEL_DOWNLOAD_FAILED",
            user_message=f"Could not download '{model_spec.name}' (~{model_spec.download_size_mb} MB).",
            suggestion="Verify your server has internet access to GitHub model releases and enough free disk space, then try again.",
            status_code=502,
        )

    if any(token in msg for token in ("cuda", "gpu", "driver", "onnxruntime", "provider")):
        return AppError(
            code="DEVICE_INCOMPATIBLE",
            user_message=f"Hardware acceleration error while loading '{model_spec.name}'.",
            suggestion="Check your GPU driver/CUDA container setup or try switching to another model.",
            status_code=500,
        )

    return AppError(
        code="MODEL_LOAD_FAILED",
        user_message=f"Failed to load AI model '{model_spec.name}'.",
        suggestion="Try again or switch to the default model (UVR MDX-Net Inst HQ 3).",
        status_code=500,
    )


def _classify_separation_error(exc: Exception, model_spec: ModelSpec) -> AppError:
    if isinstance(exc, AppError):
        return exc

    msg = str(exc).lower()
    exc_name = type(exc).__name__

    if exc_name == "InvalidAudioDataError":
        return AppError(
            code="INVALID_AUDIO_FILE",
            user_message="The audio data could not be decoded for separation.",
            suggestion="Check that the audio file plays cleanly, or convert it to WAV/MP3 and try again.",
            status_code=400,
        )

    if exc_name == "AudioExportError":
        return AppError(
            code="EXPORT_FAILED",
            user_message="Failed while writing one of the separated audio tracks.",
            suggestion="Verify disk space and try exporting in WAV format.",
            status_code=500,
        )

    if any(
        token in msg
        for token in (
            "out of memory",
            "cuda out of memory",
            "cannot allocate",
            "std::bad_alloc",
            "alloc",
        )
    ) or isinstance(exc, MemoryError):
        return AppError(
            code="OUT_OF_MEMORY",
            user_message="The server ran out of memory while separating this track.",
            suggestion="Try a shorter audio clip or switch to the lighter UVR MDX-Net Inst HQ 3 model.",
            status_code=500,
        )

    if any(token in msg for token in ("cuda", "cudnn", "cublas", "gpu", "driver")):
        return AppError(
            code="DEVICE_INCOMPATIBLE",
            user_message="A GPU processing error interrupted the separation.",
            suggestion="Ensure your NVIDIA driver and CUDA libraries match, or run the CPU container.",
            status_code=500,
        )

    return AppError(
        code="PROCESSING_FAILED",
        user_message=f"Audio separation did not finish cleanly with '{model_spec.name}'.",
        suggestion="Try again, pick a different audio file, or switch to UVR MDX-Net Inst HQ 3.",
        status_code=500,
    )


def _default_separator_factory(**kwargs: Any) -> Any:
    from audio_separator.separator import Separator

    return Separator(**kwargs)


class AudioSeparatorEngine:
    """Isolated engine adapter translating catalog choices into python-audio-separator calls."""

    def __init__(
        self,
        model_cache_dir: Path,
        chunk_duration_seconds: int = 300,
        separator_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.model_cache_dir = model_cache_dir
        self.chunk_duration_seconds = chunk_duration_seconds
        self._separator_factory = separator_factory or _default_separator_factory

    def _build_custom_output_names(self, model_spec: ModelSpec) -> dict[str, str]:
        mapping = {
            TRACK_DEFINITIONS[track_key].engine_stem_name: f"track_{track_key}"
            for track_key in model_spec.outputs
        }
        if model_spec.goal == "vocals_music":
            mapping["No_Vocals"] = "track_music"
            mapping["Other"] = "track_music"
        return mapping

    def _match_output_file(
        self,
        raw_paths: list[str],
        work_dir: Path,
        track_key: str,
    ) -> Path | None:
        expected_stem = f"track_{track_key}".lower()
        engine_label = f"({TRACK_DEFINITIONS[track_key].engine_stem_name})".lower()

        for raw in raw_paths:
            candidate = Path(raw)
            resolved = candidate if candidate.is_absolute() else (work_dir / candidate)
            if not resolved.is_file():
                continue
            stem_lower = resolved.stem.lower()
            if stem_lower == expected_stem or engine_label in stem_lower:
                return resolved
        return None

    def run_separation(
        self,
        *,
        model_spec: ModelSpec,
        input_path: Path,
        work_dir: Path,
        output_dir: Path,
        safe_base_name: str,
        selected_outputs: list[str],
        output_format: str,
        input_metadata: AudioMetadata,
        stage_callback: StageCallback,
    ) -> dict[str, Path]:
        """Run model loading, separation, and format export for a validated job."""
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)
        work_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        format_spec = get_output_format(output_format)
        hardware = detect_hardware_info()

        output_single_stem: str | None = None
        if len(selected_outputs) == 1:
            output_single_stem = TRACK_DEFINITIONS[selected_outputs[0]].engine_stem_name

        was_cached = is_model_cached(model_spec, self.model_cache_dir)
        if not was_cached:
            stage_callback(
                "downloading_model",
                f"Downloading {model_spec.name} (~{model_spec.download_size_mb} MB) for first use...",
            )

        try:
            separator = self._separator_factory(
                log_level=logging.INFO,
                model_file_dir=str(self.model_cache_dir),
                output_dir=str(work_dir),
                output_format="WAV",
                output_single_stem=output_single_stem,
                chunk_duration=self.chunk_duration_seconds,
                use_soundfile=False,
            )
        except FileNotFoundError as exc:
            logger.exception("Required binary missing during Separator initialization")
            raise AppError(
                code="PROCESSING_FAILED",
                user_message="FFmpeg was not found on the server.",
                suggestion="Install FFmpeg or run Split My Music inside Docker.",
                status_code=500,
            ) from exc
        except Exception as exc:
            logger.exception("Separator initialization failed")
            raise _classify_load_error(exc, model_spec) from exc

        try:
            separator.load_model(model_filename=model_spec.model_filename)
        except Exception as exc:
            logger.exception("Model load failed for %s", model_spec.model_filename)
            _cleanup_zero_byte_model_files(self.model_cache_dir, model_spec.required_files)
            _clear_cuda_cache_quietly()
            raise _classify_load_error(exc, model_spec) from exc

        stage_callback(
            "separating",
            f"Separating tracks with {model_spec.name} on {hardware.device_label}...",
        )

        custom_names = self._build_custom_output_names(model_spec)
        try:
            raw_files = separator.separate(str(input_path), custom_output_names=custom_names)
        except Exception as exc:
            logger.exception("Separation failed for model %s", model_spec.model_filename)
            _clear_cuda_cache_quietly()
            raise _classify_separation_error(exc, model_spec) from exc
        finally:
            _clear_cuda_cache_quietly()

        if not raw_files:
            raise AppError(
                code="EXPORT_FAILED",
                user_message="Separation finished without producing any audio files.",
                suggestion="Verify the input audio is not silent or corrupted and try again.",
                status_code=500,
            )

        stage_callback(
            "exporting",
            f"Exporting {len(selected_outputs)} track(s) as {format_spec.id.upper()}...",
        )

        final_outputs: dict[str, Path] = {}
        for track_key in selected_outputs:
            source_file = self._match_output_file(list(raw_files), work_dir, track_key)
            if source_file is None or source_file.stat().st_size <= 0:
                logger.error(
                    "Expected output for track '%s' missing from engine output %s",
                    track_key,
                    raw_files,
                )
                raise AppError(
                    code="EXPORT_FAILED",
                    user_message=f"Could not export the '{TRACK_DEFINITIONS[track_key].label}' track.",
                    suggestion="Try running the separation again or switch to the default model.",
                    status_code=500,
                )

            dest_path = output_dir / f"{safe_base_name}_{track_key}{format_spec.extension}"
            final_outputs[track_key] = finalize_output_audio(
                source_path=source_file,
                dest_path=dest_path,
                target_channels=input_metadata.channels,
                target_sample_rate=input_metadata.sample_rate,
                output_format=format_spec.id,
            )

        return final_outputs
