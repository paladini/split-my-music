# Testing Strategy & Verification Matrix

## Test Layers & Coverage Matrix

| Code Layer | Location | Required Test Type | Parallel-Safe | Notes |
| ---------- | -------- | ------------------ | ------------- | ----- |
| Config & Curated Catalog | `src/config.py`, `src/core/catalog.py` | `unit` | Yes | Pure functions & data invariants |
| Error Hierarchy | `src/core/errors.py` | `unit` | Yes | Tested alongside media, engine, and API |
| Media Inspection & Sanitization | `src/core/media.py` | `unit` | Yes | Uses `ffmpeg`-generated test fixtures in `tmp_path` |
| Engine Adapter | `src/core/engine.py` | `unit` + `integration` | No (model download/RAM) | Unit tests mock `Separator`; real test exercises `UVR-MDX-NET-Inst_HQ_3.onnx` on CPU |
| Job Manager & Recovery | `src/core/jobs.py` | `integration` | No (shared threadpool/tmp dirs) | Tests queue concurrency, disk guard, restart recovery, ZIP, retention |
| FastAPI Routes & Security | `src/api/routes.py` | `integration` | Yes (isolated `tmp_path` app state) | Uses FastAPI `TestClient` |
| Web Frontend & User Flow | `templates/index.html`, `static/` | `e2e` (live browser walkthrough) | No | Verified against live Uvicorn server with real screenshots |

## Gate Check Commands

- **Quick gate:** `.\.venv\Scripts\python.exe -m pytest tests/unit -v`
- **Full gate:** `.\.venv\Scripts\python.exe -m pytest tests/unit tests/integration -m "not real_model" -v`
- **Build gate (all tests including real model separation):** `.\.venv\Scripts\python.exe -m pytest -v`
- **Docker Compose validation:** `docker compose -f docker-compose.yml config` and `docker compose -f docker-compose.yml -f docker-compose.gpu.yml config`
