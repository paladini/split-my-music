"""FastAPI application: pages, JSON API, streaming uploads, and safe file serving."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import shutil
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src import __version__
from src.config import Settings, load_settings
from src.core.catalog import list_public_catalog, resolve_model_and_outputs, get_output_format
from src.core.engine import detect_hardware_info
from src.core.errors import AppError
from src.core.jobs import JobManager
from src.core.media import (
    inspect_audio_file,
    sanitize_display_name,
    validate_extension,
)

logger = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024


def _error_response(err: AppError) -> JSONResponse:
    return JSONResponse(status_code=err.status_code, content={"error": err.to_dict()})


def _job_payload(job: dict[str, Any]) -> dict[str, Any]:
    """Public view of a job manifest with URLs; omits internal paths."""
    job_id = job["id"]
    payload = {
        "id": job_id,
        "status": job.get("status"),
        "stage": job.get("stage"),
        "stage_message": job.get("stage_message"),
        "created_at": job.get("created_at"),
        "completed_at": job.get("completed_at"),
        "elapsed_seconds": job.get("elapsed_seconds"),
        "original_filename": job.get("original_filename"),
        "model": job.get("model"),
        "output_format": job.get("output_format"),
        "selected_outputs": job.get("selected_outputs", []),
        "input_metadata": job.get("input_metadata"),
        "error": job.get("error"),
        "files": [],
        "zip_url": None,
    }
    for f in job.get("files") or []:
        base = f"/api/jobs/{job_id}/files/{f['filename']}"
        payload["files"].append({**f, "stream_url": base, "download_url": f"{base}?download=1"})
    if job.get("zip_filename"):
        payload["zip_url"] = f"/api/jobs/{job_id}/zip"
    return payload


def create_app(settings: Settings | None = None, engine: Any | None = None) -> FastAPI:
    settings = settings or load_settings()
    logging.basicConfig(level=settings.log_level)
    manager = JobManager(settings=settings, engine=engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        manager.recover_interrupted_jobs()
        manager.cleanup_expired_jobs()
        yield
        manager.shutdown(wait=False)

    app = FastAPI(title="Split My Music", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None)
    app.state.manager = manager
    app.state.settings = settings

    static_dir = settings.base_dir / "static"
    templates = Jinja2Templates(directory=str(settings.base_dir / "templates"))
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.exception_handler(AppError)
    async def _app_error(_req: Request, exc: AppError):
        return _error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_req: Request, _exc: RequestValidationError):
        return _error_response(AppError(
            "INVALID_REQUEST", "The request was missing required information.",
            "Choose an audio file and try again.", 400))

    @app.exception_handler(Exception)
    async def _unexpected(_req: Request, exc: Exception):
        logger.exception("Unhandled server error: %s", exc)
        return _error_response(AppError(
            "SERVER_ERROR", "Something went wrong on the server.",
            "Please try again. If it keeps happening, check the server logs.", 500))

    @app.get("/")
    async def index(request: Request):
        return templates.TemplateResponse(request, "index.html", {"version": __version__})

    @app.get("/health")
    async def health():
        hw = detect_hardware_info()
        return {"status": "healthy", "version": __version__, "device": hw.device_label,
                "ffmpeg_available": hw.ffmpeg_available, **manager.get_queue_counts()}

    @app.get("/api/config")
    async def config():
        catalog = list_public_catalog(settings.model_cache_dir)
        return {
            **catalog,
            "hardware": detect_hardware_info().to_dict(),
            "limits": {
                "max_upload_mb": settings.max_upload_mb,
                "max_duration_minutes": settings.max_duration_minutes,
                "retention_hours": settings.retention_hours,
            },
        }

    @app.post("/api/jobs", status_code=202)
    async def create_job(
        file: UploadFile = File(...),
        goal: str = Form("vocals_music"),
        model: str = Form(""),
        outputs: str = Form(""),
        output_format: str = Form("wav"),
    ):
        filename = file.filename or ""
        ext = validate_extension(filename)
        fmt = get_output_format(output_format)
        requested = [o for o in outputs.split(",") if o.strip()] if outputs else None
        model_spec, selected = resolve_model_and_outputs(goal, model, requested)

        job_id, job_dir, input_path = manager.allocate_upload_slot(model_spec, ext)
        try:
            written = 0
            with input_path.open("wb") as out:
                while True:
                    chunk = await file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > settings.max_upload_bytes:
                        raise AppError(
                            "FILE_TOO_LARGE",
                            f"This file is larger than the {settings.max_upload_mb} MB limit.",
                            "Choose a smaller file or ask the server owner to raise SPLIT_MAX_UPLOAD_MB.",
                            413)
                    out.write(chunk)
            if written == 0:
                raise AppError("EMPTY_FILE", "The uploaded file is empty (0 bytes).",
                               "Select a valid non-empty audio file.", 400)
            metadata = inspect_audio_file(input_path, settings.max_duration_seconds)
            job = manager.enqueue_job(
                job_id=job_id, job_dir=job_dir, input_path=input_path,
                safe_base_name=sanitize_display_name(filename),
                original_filename=sanitize_display_name(filename) + ext,
                model_spec=model_spec, selected_outputs=selected,
                output_format=fmt.id, metadata=metadata)
        except BaseException:
            manager.release_upload_slot(job_id, job_dir)
            raise
        finally:
            await file.close()
        return _job_payload(job)

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str):
        return _job_payload(manager.get_job(job_id))

    @app.get("/api/jobs/{job_id}/files/{filename}")
    async def get_file(job_id: str, filename: str, download: int = 0):
        path, mime = manager.resolve_output_file(job_id, filename)
        return FileResponse(path, media_type=mime, filename=path.name,
                            content_disposition_type="attachment" if download else "inline")

    @app.get("/api/jobs/{job_id}/zip")
    async def get_zip(job_id: str):
        path, name = manager.resolve_zip_file(job_id)
        return FileResponse(path, media_type="application/zip", filename=name)

    @app.delete("/api/jobs/{job_id}")
    async def delete_job(job_id: str):
        manager.delete_job(job_id)
        return {"deleted": True}

    return app
