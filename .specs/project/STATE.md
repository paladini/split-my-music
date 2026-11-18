# State

**Last Updated:** 2026-11-17T21:46:00-03:00
**Current Work:** Milestone 1 (`audio-separation`) — Complete & Releasing v1.0.0

---

## Recent Decisions (Last 60 days)

### AD-001: Curated Catalog & Isolated `python-audio-separator` Adapter (2026-11-17)

**Decision:** Isolate all `audio_separator` imports and model mappings in `src/core/engine.py` and expose only a curated, verified catalog in `src/core/catalog.py`.
**Reason:** Different UVR/Demucs/RoFormer models emit incompatible stem names, require different file artifacts (`.onnx`, `.yaml` + `.th`, `.ckpt` + `.yaml`), and vary wildly in RAM/VRAM usage.
**Trade-off:** Users cannot select arbitrary unverified models from the full 100+ upstream list in v1.
**Impact:** Guarantees every displayed output track (`vocals`, `music`, `drums`, `bass`, `guitar`, `piano`, `other`) actually exists for the selected model and prevents runtime mismatches.

### AD-002: File-Backed Job Persistence & Single-Worker Concurrency Queue (2026-11-17)

**Decision:** Persist job manifests (`job.json`) under per-job directories inside `SPLIT_JOBS_DIR` and process jobs via a bounded `ThreadPoolExecutor` (default `max_concurrent_jobs=1`, `max_queue_size=5`) with startup recovery.
**Reason:** Avoids heavy external broker dependencies (Redis/Celery) for homelab/NAS deployments while preventing RAM/VRAM exhaustion from concurrent separations and clearly marking interrupted jobs after restarts.
**Trade-off:** Single-process worker model is vertical-scaling only.
**Impact:** Lightweight Docker footprint and clean restart resilience (`INTERRUPTED_BY_RESTART`).

### AD-003: Validated File Endpoints Instead of Public Static Output Directory (2026-11-17)

**Decision:** Serve separated tracks and ZIP archives exclusively through `/api/jobs/{job_id}/files/{filename}` and `/api/jobs/{job_id}/zip` with strict manifest lookup and `is_relative_to` path validation, instead of mounting the entire output tree via `StaticFiles`.
**Reason:** Prevents accidental directory browsing, path traversal, or cross-job leakage while supporting both inline streaming playback and attachment downloads.
**Trade-off:** Requires API route handling for media responses (`FileResponse` handles HTTP Range requests for `<audio>` seeking).
**Impact:** Stronger self-hosting privacy and clean job lifecycle cleanup.

### AD-004: Compose Override Pattern for CPU vs NVIDIA GPU (2026-11-17)

**Decision:** Define a single `split-my-music` service in `docker-compose.yml` (CPU) and replace it in place via `docker-compose.gpu.yml` (`docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build`).
**Reason:** Putting both CPU and GPU services in one Compose file caused users to accidentally launch both containers bound to port `7860` simultaneously (lesson observed in `voice-separator-demucs`).
**Trade-off:** GPU users pass two `-f` flags.
**Impact:** Eliminates port `7860` collision by design.

---

## Active Blockers

### B-001: No Local NVIDIA GPU on Development Host

**Discovered:** 2026-11-17
**Impact:** Cannot execute live CUDA GPU inference on this host (Docker Desktop daemon was later started, allowing full CPU Docker build & smoke testing).
**Workaround:** Built and smoke-tested CPU Docker image locally (`paladini/split-my-music:latest`); validated `Dockerfile.gpu` and `docker-compose.gpu.yml` via `docker compose config` and wired GPU build into GitHub Actions.
**Resolution:** Document clearly in README and release notes that CPU + CPU Docker were verified live while NVIDIA GPU execution requires testing on an NVIDIA GPU host.

---

## Lessons Learned

### L-001: Windows Python Alias Resolution

**Context:** Running bare `python` on this Windows host resolves to the Microsoft Store App Execution Alias rather than Python 3.12.
**Problem:** `python --version` fails with exit code 1.
**Solution:** Create `.venv` explicitly using `py -3.12 -m venv .venv` and invoke `.\.venv\Scripts\python.exe`.
**Prevents:** Environment confusion during automated script and pytest execution.

### L-002: Missing `audioread` Transitive Dependency in `audio-separator==0.48.0`

**Context:** `librosa>=1.0.1` dropped `audioread` as a hard dependency, while `audio_separator.separator.uvr_lib_v5.spec_utils` still imports `audioread`.
**Problem:** Importing `Separator` fails with `ModuleNotFoundError: No module named 'audioread'`.
**Solution:** Pin `audioread>=3.0.1` explicitly in `requirements.txt`.
**Prevents:** Runtime import crash on fresh installs and Docker builds.

### L-003: Compiling `diffq` in Linux Docker Builds

**Context:** Building `Dockerfile` on `python:3.12-slim` (Linux x86_64) failed initially when building the wheel for `diffq` (dependency of `audio-separator`).
**Problem:** `diffq` has no prebuilt Linux Python 3.12 wheel and requires a C/C++ toolchain.
**Solution:** Use a multi-stage Docker build with `build-essential` in the builder stage (`Dockerfile` and `Dockerfile.gpu`) and copy `/opt/venv` into the slim runtime stage.
**Prevents:** Bloated runtime images and Linux pip build failures.

---

## Quick Tasks Completed

| # | Description | Date | Commit | Status |
| - | ----------- | ---- | ------ | ------ |

---

## Deferred Ideas

- Batch folder watcher for automated library splitting — Captured during: Project Init
- Interactive waveform scrubbing canvas — Captured during: Project Init

---

## Todos

- [x] Execute Phase 2–7 implementation and verify all unit, integration, and real CPU E2E tests.
- [x] Build and smoke-test CPU Docker image (`paladini/split-my-music:latest`).
- [x] Publish GitHub repository, CI/CD pipelines, Docker Hub image, and v1.0.0 release.

---

## Preferences

**Model Guidance Shown:** 2026-11-17
