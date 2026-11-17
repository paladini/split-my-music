"""File-backed background job manager with concurrency control, restart recovery, and cleanup."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import re
import shutil
import threading
import time
from typing import Any, Callable
import uuid
import zipfile

from src.config import Settings
from src.core.catalog import TRACK_DEFINITIONS, ModelSpec, get_output_format, is_model_cached
from src.core.engine import AudioSeparatorEngine
from src.core.errors import AppError
from src.core.media import AudioMetadata, prepare_audio_for_engine

logger = logging.getLogger(__name__)

ACTIVE_STATUSES: frozenset[str] = frozenset(
    {"queued", "preparing", "downloading_model", "separating", "exporting"}
)
_JOB_ID_PATTERN = re.compile(r"^[a-f0-9]{12}$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


class JobManager:
    """Manages separation jobs, queue limits, disk checks, recovery, ZIP packaging, and retention."""

    def __init__(
        self,
        settings: Settings,
        engine: AudioSeparatorEngine | None = None,
        disk_usage_fn: Callable[[Path], Any] | None = None,
    ) -> None:
        self.settings = settings
        self.engine = engine or AudioSeparatorEngine(
            model_cache_dir=settings.model_cache_dir,
            chunk_duration_seconds=settings.chunk_duration_seconds,
        )
        self._disk_usage_fn = disk_usage_fn or shutil.disk_usage

        self.settings.model_cache_dir.mkdir(parents=True, exist_ok=True)
        self.settings.jobs_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._manifest_lock = threading.Lock()
        self._reserved_ids: set[str] = set()
        self._queued_ids: set[str] = set()
        self._active_ids: set[str] = set()
        self._executor = ThreadPoolExecutor(
            max_workers=settings.max_concurrent_jobs,
            thread_name_prefix="split-worker",
        )
        self._shutdown = False

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the background worker pool cleanly."""
        self._shutdown = True
        self._executor.shutdown(wait=wait)

    def get_queue_counts(self) -> dict[str, int]:
        """Return current active and queued job counts."""
        with self._lock:
            return {
                "active_jobs": len(self._active_ids),
                "queued_jobs": len(self._queued_ids),
            }

    def check_capacity_and_disk(self, model_spec: ModelSpec) -> None:
        """Fail fast when the server queue is full or free disk space is insufficient."""
        max_in_flight = self.settings.max_concurrent_jobs + self.settings.max_queue_size
        with self._lock:
            in_flight = len(self._active_ids) + len(self._queued_ids) + len(self._reserved_ids)
        if in_flight >= max_in_flight:
            raise AppError(
                code="SERVER_BUSY",
                user_message="The server already has the maximum number of songs queued.",
                suggestion="Wait for a running separation to finish and try again in a moment.",
                status_code=429,
            )

        needs_download = not is_model_cached(model_spec, self.settings.model_cache_dir)
        required_mb = self.settings.min_free_disk_mb + (
            model_spec.download_size_mb if needs_download else 0
        )
        required_bytes = required_mb * 1024 * 1024

        for path_label, target_dir in (
            ("jobs storage", self.settings.jobs_dir),
            ("model cache storage", self.settings.model_cache_dir),
        ):
            target_dir.mkdir(parents=True, exist_ok=True)
            usage = self._disk_usage_fn(target_dir)
            if usage.free < required_bytes:
                free_mb = int(usage.free // (1024 * 1024))
                raise AppError(
                    code="INSUFFICIENT_DISK_SPACE",
                    user_message=(
                        f"Not enough free disk space on {path_label} "
                        f"({free_mb} MB available, at least {required_mb} MB needed)."
                    ),
                    suggestion="Free up disk space or clear old jobs before starting a new separation.",
                    status_code=507,
                )

    def allocate_upload_slot(self, model_spec: ModelSpec, ext: str) -> tuple[str, Path, Path]:
        """Validate capacity and disk, reserve a slot, and create isolated job folders."""
        max_in_flight = self.settings.max_concurrent_jobs + self.settings.max_queue_size
        with self._lock:
            in_flight = len(self._active_ids) + len(self._queued_ids) + len(self._reserved_ids)
            if in_flight >= max_in_flight:
                raise AppError(
                    code="SERVER_BUSY",
                    user_message="The server already has the maximum number of songs queued.",
                    suggestion="Wait for a running separation to finish and try again in a moment.",
                    status_code=429,
                )
            job_id = uuid.uuid4().hex[:12]
            self._reserved_ids.add(job_id)

        try:
            needs_download = not is_model_cached(model_spec, self.settings.model_cache_dir)
            required_mb = self.settings.min_free_disk_mb + (
                model_spec.download_size_mb if needs_download else 0
            )
            required_bytes = required_mb * 1024 * 1024

            for path_label, target_dir in (
                ("jobs storage", self.settings.jobs_dir),
                ("model cache storage", self.settings.model_cache_dir),
            ):
                target_dir.mkdir(parents=True, exist_ok=True)
                usage = self._disk_usage_fn(target_dir)
                if usage.free < required_bytes:
                    free_mb = int(usage.free // (1024 * 1024))
                    raise AppError(
                        code="INSUFFICIENT_DISK_SPACE",
                        user_message=(
                            f"Not enough free disk space on {path_label} "
                            f"({free_mb} MB available, at least {required_mb} MB needed)."
                        ),
                        suggestion="Free up disk space or clear old jobs before starting a new separation.",
                        status_code=507,
                    )

            job_dir = self.settings.jobs_dir / job_id
            (job_dir / "input").mkdir(parents=True, exist_ok=True)
            (job_dir / "work").mkdir(parents=True, exist_ok=True)
            (job_dir / "output").mkdir(parents=True, exist_ok=True)
            input_path = job_dir / "input" / f"upload{ext}"
            return job_id, job_dir, input_path
        except Exception:
            self.release_upload_slot(job_id, self.settings.jobs_dir / job_id)
            raise

    def release_upload_slot(self, job_id: str, job_dir: Path | None = None) -> None:
        """Release a reserved upload slot and remove partial job folders on validation failure."""
        with self._lock:
            self._reserved_ids.discard(job_id)
        if job_dir is not None and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)

    def _validate_job_id(self, job_id: str) -> Path:
        if not _JOB_ID_PATTERN.match(job_id or ""):
            raise AppError(
                code="JOB_NOT_FOUND",
                user_message="That separation job could not be found.",
                suggestion="Start a new separation from the home page.",
                status_code=404,
            )
        job_dir = self.settings.jobs_dir / job_id
        manifest_path = job_dir / "job.json"
        if not manifest_path.is_file():
            raise AppError(
                code="JOB_NOT_FOUND",
                user_message="That separation job no longer exists or has expired.",
                suggestion="Upload your audio file again to start a new separation.",
                status_code=404,
            )
        return job_dir

    def _write_manifest(self, job_dir: Path, data: dict[str, Any]) -> None:
        manifest_path = job_dir / "job.json"
        tmp_path = job_dir / f"job.{threading.get_ident()}.tmp"
        with self._manifest_lock:
            tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(tmp_path, manifest_path)

    def _read_manifest(self, job_dir: Path) -> dict[str, Any]:
        manifest_path = job_dir / "job.json"
        with self._manifest_lock:
            return json.loads(manifest_path.read_text(encoding="utf-8"))

    def enqueue_job(
        self,
        *,
        job_id: str,
        job_dir: Path,
        input_path: Path,
        safe_base_name: str,
        original_filename: str,
        model_spec: ModelSpec,
        selected_outputs: list[str],
        output_format: str,
        metadata: AudioMetadata,
    ) -> dict[str, Any]:
        """Persist initial queued manifest and schedule background separation."""
        now_iso = _utc_now_iso()
        format_spec = get_output_format(output_format)
        cached_before = is_model_cached(model_spec, self.settings.model_cache_dir)

        manifest: dict[str, Any] = {
            "id": job_id,
            "status": "queued",
            "stage": "queued",
            "stage_message": "Queued for processing...",
            "created_at": now_iso,
            "updated_at": now_iso,
            "completed_at": None,
            "elapsed_seconds": None,
            "original_filename": original_filename,
            "safe_base_name": safe_base_name,
            "model": {
                "id": model_spec.id,
                "name": model_spec.name,
                "architecture": model_spec.architecture,
                "download_size_mb": model_spec.download_size_mb,
                "cached_before_run": cached_before,
            },
            "selected_outputs": list(selected_outputs),
            "output_format": format_spec.id,
            "input_metadata": {
                "duration_seconds": metadata.duration_seconds,
                "sample_rate": metadata.sample_rate,
                "channels": metadata.channels,
                "codec_name": metadata.codec_name,
            },
            "files": [],
            "zip_filename": None,
            "error": None,
        }
        self._write_manifest(job_dir, manifest)

        with self._lock:
            self._reserved_ids.discard(job_id)
            self._queued_ids.add(job_id)

        self._executor.submit(
            self._run_job,
            job_id,
            job_dir,
            input_path,
            safe_base_name,
            model_spec,
            list(selected_outputs),
            format_spec.id,
            metadata,
        )
        return manifest

    def _update_stage(self, job_dir: Path, stage: str, message: str) -> None:
        data = self._read_manifest(job_dir)
        data["status"] = stage
        data["stage"] = stage
        data["stage_message"] = message
        data["updated_at"] = _utc_now_iso()
        self._write_manifest(job_dir, data)

    def _run_job(
        self,
        job_id: str,
        job_dir: Path,
        input_path: Path,
        safe_base_name: str,
        model_spec: ModelSpec,
        selected_outputs: list[str],
        output_format: str,
        metadata: AudioMetadata,
    ) -> None:
        started_monotonic = time.monotonic()
        with self._lock:
            self._queued_ids.discard(job_id)
            self._active_ids.add(job_id)

        work_dir = job_dir / "work"
        output_dir = job_dir / "output"
        input_dir = job_dir / "input"
        format_spec = get_output_format(output_format)

        try:
            self._update_stage(job_dir, "preparing", "Preparing audio stream...")
            prepared_input = prepare_audio_for_engine(input_path, work_dir, metadata)

            produced = self.engine.run_separation(
                model_spec=model_spec,
                input_path=prepared_input,
                work_dir=work_dir,
                output_dir=output_dir,
                safe_base_name=safe_base_name,
                selected_outputs=selected_outputs,
                output_format=format_spec.id,
                input_metadata=metadata,
                stage_callback=lambda stage, msg: self._update_stage(job_dir, stage, msg),
            )

            zip_filename = f"{safe_base_name}_split_my_music.zip"
            zip_path = output_dir / zip_filename
            with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                for track_key in selected_outputs:
                    track_path = produced[track_key]
                    zf.write(track_path, arcname=track_path.name)

            if not zip_path.is_file() or zip_path.stat().st_size <= 0:
                raise AppError(
                    code="EXPORT_FAILED",
                    user_message="Could not package the separated tracks into a ZIP archive.",
                    suggestion="Download the individual tracks or try running the separation again.",
                    status_code=500,
                )

            files_payload = []
            for track_key in selected_outputs:
                track_path = produced[track_key]
                track_def = TRACK_DEFINITIONS[track_key]
                files_payload.append(
                    {
                        "id": track_key,
                        "label": track_def.label,
                        "description": track_def.description,
                        "filename": track_path.name,
                        "size_bytes": track_path.stat().st_size,
                        "format": format_spec.id,
                        "format_label": format_spec.short_label,
                        "lossless": format_spec.lossless,
                    }
                )

            elapsed = round(time.monotonic() - started_monotonic, 2)
            now_iso = _utc_now_iso()
            data = self._read_manifest(job_dir)
            data["status"] = "completed"
            data["stage"] = "completed"
            data["stage_message"] = "Separation completed."
            data["updated_at"] = now_iso
            data["completed_at"] = now_iso
            data["elapsed_seconds"] = elapsed
            data["files"] = files_payload
            data["zip_filename"] = zip_filename
            data["error"] = None
            self._write_manifest(job_dir, data)
        except AppError as exc:
            logger.warning("Job %s failed with AppError %s: %s", job_id, exc.code, exc.user_message)
            self._mark_job_failed(job_dir, output_dir, exc.to_dict(), started_monotonic)
        except Exception:
            logger.exception("Unexpected error during job %s", job_id)
            self._mark_job_failed(
                job_dir,
                output_dir,
                {
                    "code": "PROCESSING_FAILED",
                    "message": "An unexpected error occurred while separating this audio file.",
                    "suggestion": "Try again, choose another audio file, or switch to the default model.",
                },
                started_monotonic,
            )
        finally:
            shutil.rmtree(input_dir, ignore_errors=True)
            shutil.rmtree(work_dir, ignore_errors=True)
            with self._lock:
                self._active_ids.discard(job_id)
                self._queued_ids.discard(job_id)

    def _mark_job_failed(
        self,
        job_dir: Path,
        output_dir: Path,
        error_dict: dict[str, str],
        started_monotonic: float,
    ) -> None:
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            data = self._read_manifest(job_dir)
        except Exception:
            data = {"id": job_dir.name, "created_at": _utc_now_iso()}
        data["status"] = "failed"
        data["stage"] = "failed"
        data["stage_message"] = error_dict.get("message", "Separation failed.")
        data["updated_at"] = _utc_now_iso()
        data["elapsed_seconds"] = round(time.monotonic() - started_monotonic, 2)
        data["files"] = []
        data["zip_filename"] = None
        data["error"] = error_dict
        self._write_manifest(job_dir, data)

    def get_job(self, job_id: str) -> dict[str, Any]:
        """Load and return the current manifest for a job."""
        job_dir = self._validate_job_id(job_id)
        return self._read_manifest(job_dir)

    def resolve_output_file(self, job_id: str, filename: str) -> tuple[Path, str]:
        """Resolve a verified output file path owned by a completed job."""
        job_dir = self._validate_job_id(job_id)
        manifest = self._read_manifest(job_dir)
        if manifest.get("status") != "completed":
            raise AppError(
                code="JOB_NOT_READY",
                user_message="Separated files are not ready yet.",
                suggestion="Wait for separation to finish before downloading.",
                status_code=409,
            )

        allowed_names = {item["filename"]: item for item in manifest.get("files") or []}
        if filename not in allowed_names:
            raise AppError(
                code="FILE_NOT_FOUND",
                user_message="Requested audio track was not found for this job.",
                suggestion="Refresh the results page or start a new separation.",
                status_code=404,
            )

        output_dir = (job_dir / "output").resolve()
        candidate = (output_dir / filename).resolve()
        if not candidate.is_relative_to(output_dir) or not candidate.is_file():
            raise AppError(
                code="FILE_NOT_FOUND",
                user_message="Requested audio track is no longer available on disk.",
                suggestion="Run the separation again to regenerate the track.",
                status_code=404,
            )

        fmt = get_output_format(allowed_names[filename].get("format", manifest.get("output_format", "wav")))
        return candidate, fmt.mime_type

    def resolve_zip_file(self, job_id: str) -> tuple[Path, str]:
        """Resolve the ZIP archive path for a completed job."""
        job_dir = self._validate_job_id(job_id)
        manifest = self._read_manifest(job_dir)
        if manifest.get("status") != "completed":
            raise AppError(
                code="JOB_NOT_READY",
                user_message="The ZIP archive is not ready yet.",
                suggestion="Wait until processing finishes.",
                status_code=409,
            )

        zip_filename = manifest.get("zip_filename")
        if not zip_filename:
            raise AppError(
                code="EXPORT_FAILED",
                user_message="ZIP package is unavailable for this job.",
                suggestion="Download the individual audio tracks instead.",
                status_code=500,
            )

        output_dir = (job_dir / "output").resolve()
        candidate = (output_dir / zip_filename).resolve()
        if not candidate.is_relative_to(output_dir) or not candidate.is_file():
            raise AppError(
                code="EXPORT_FAILED",
                user_message="The ZIP package could not be found on disk.",
                suggestion="Download individual tracks or run the separation again.",
                status_code=500,
            )
        return candidate, zip_filename

    def delete_job(self, job_id: str) -> None:
        """Delete a non-active job directory immediately upon user request."""
        job_dir = self._validate_job_id(job_id)
        with self._lock:
            if job_id in self._active_ids or job_id in self._queued_ids:
                raise AppError(
                    code="JOB_ACTIVE",
                    user_message="Cannot delete a separation while it is queued or running.",
                    suggestion="Wait for processing to finish before removing this job.",
                    status_code=409,
                )
        shutil.rmtree(job_dir, ignore_errors=True)

    def recover_interrupted_jobs(self) -> int:
        """Mark any jobs left in active/queued states prior to a server restart as failed."""
        recovered = 0
        if not self.settings.jobs_dir.exists():
            return 0

        for child in self.settings.jobs_dir.iterdir():
            if not child.is_dir():
                continue
            manifest_path = child / "job.json"
            if not manifest_path.is_file():
                continue
            try:
                data = self._read_manifest(child)
            except Exception:
                continue

            if data.get("status") in ACTIVE_STATUSES:
                shutil.rmtree(child / "input", ignore_errors=True)
                shutil.rmtree(child / "work", ignore_errors=True)
                data["status"] = "failed"
                data["stage"] = "failed"
                data["stage_message"] = "Separation was interrupted by a server restart."
                data["updated_at"] = _utc_now_iso()
                data["error"] = {
                    "code": "INTERRUPTED_BY_RESTART",
                    "message": "This separation was interrupted because the server restarted while it was running.",
                    "suggestion": "Upload your audio file and start the separation again.",
                }
                self._write_manifest(child, data)
                recovered += 1

        if recovered:
            logger.warning("Recovered %d interrupted job(s) after server restart.", recovered)
        return recovered

    def cleanup_expired_jobs(self) -> int:
        """Remove finished jobs past retention age or exceeding max_stored_jobs safely."""
        if not self.settings.jobs_dir.exists():
            return 0

        cutoff = _utc_now() - timedelta(hours=self.settings.retention_hours)
        terminal_jobs: list[tuple[datetime, Path]] = []
        removed = 0

        with self._lock:
            protected_ids = set(self._active_ids) | set(self._queued_ids) | set(self._reserved_ids)

        for child in self.settings.jobs_dir.iterdir():
            if not child.is_dir() or child.name in protected_ids:
                continue
            manifest_path = child / "job.json"
            if not manifest_path.is_file():
                continue
            try:
                data = self._read_manifest(child)
            except Exception:
                continue

            if data.get("status") in ACTIVE_STATUSES:
                continue

            timestamp = (
                _parse_iso(data.get("updated_at"))
                or _parse_iso(data.get("created_at"))
                or datetime.fromtimestamp(manifest_path.stat().st_mtime, tz=timezone.utc)
            )
            if timestamp < cutoff:
                shutil.rmtree(child, ignore_errors=True)
                removed += 1
            else:
                terminal_jobs.append((timestamp, child))

        if len(terminal_jobs) > self.settings.max_stored_jobs:
            terminal_jobs.sort(key=lambda pair: pair[0])
            excess = len(terminal_jobs) - self.settings.max_stored_jobs
            for _, old_dir in terminal_jobs[:excess]:
                shutil.rmtree(old_dir, ignore_errors=True)
                removed += 1

        return removed
