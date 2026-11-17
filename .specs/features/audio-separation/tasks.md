# Audio Separation Tasks

**Design**: `.specs/features/audio-separation/design.md`
**Status**: Approved

---

## Execution Plan

### Phase 1: Foundation (Sequential)
`T1` → `T2`

### Phase 2: Core Modules (Parallel OK)
```text
     ┌→ T3 [P] ─┐
T2 ──┼→ T4 [P] ─┼──→ T6
     └→ T5 [P] ─┘
```

### Phase 3: Integration, UI, Docker & Verification (Sequential)
`T6` → `T7` → `T8` → `T9` → `T10`

---

## Task Breakdown

### T1: Bootstrap Project Skeleton & Settings
**What**: Create package files, gitignore/gitattributes, MIT LICENSE, `requirements.txt`, `pytest.ini`, and `src/config.py` with unit tests.
**Where**: `src/config.py`, `requirements.txt`, `pytest.ini`, `LICENSE`, `.gitignore`, `.gitattributes`, `tests/unit/test_catalog_and_config.py`
**Depends on**: None
**Requirement**: SEP-07, SEP-12
**Done when**:
- [ ] `.venv` created on Python 3.12 with all dependencies installed
- [ ] Settings load defaults and environment variable overrides accurately
- [ ] Gate check passes: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_catalog_and_config.py -v`
**Tests**: unit
**Gate**: quick

---

### T2: Implement Structured Errors & Curated Model Catalog
**What**: Implement `AppError` hierarchy and curated goals/models/output-format catalog with strict validation helpers.
**Where**: `src/core/errors.py`, `src/core/catalog.py`, `tests/unit/test_catalog_and_config.py`
**Depends on**: T1
**Requirement**: SEP-06, SEP-10, SEP-11
**Done when**:
- [ ] All curated models map accurately to `python-audio-separator` filenames and canonical track keys
- [ ] Invalid model IDs or unsupported output selections raise `AppError`
- [ ] Gate check passes: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_catalog_and_config.py -v`
**Tests**: unit
**Gate**: quick

---

### T3: Implement Media Validation & Audio Format Normalization [P]
**What**: Implement filename sanitization, extension check, `ffprobe` stream inspection, multi-channel stereo downmix, and mono/stereo + sample-rate-preserving output finalization.
**Where**: `src/core/media.py`, `tests/unit/test_media_and_security.py`
**Depends on**: T2
**Requirement**: SEP-02, SEP-05, SEP-06, SEP-09
**Done when**:
- [ ] Invalid/corrupted/empty/oversized/too-long inputs raise structured `AppError`
- [ ] Mono (48 kHz), stereo (44.1 kHz), and 5.1 surround fixtures verified via `ffmpeg`/`ffprobe`
- [ ] Gate check passes: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_media_and_security.py -v`
**Tests**: unit
**Gate**: quick

---

### T4: Implement Isolated `python-audio-separator` Engine Adapter [P]
**What**: Wrap `audio_separator.separator.Separator`, hardware detection (`CPU` / `NVIDIA GPU`), cache status checks, stage callbacks, and failure mapping.
**Where**: `src/core/engine.py`, `tests/unit/test_engine_unit.py`
**Depends on**: T2
**Requirement**: SEP-03, SEP-06, SEP-10, SEP-11
**Done when**:
- [ ] Engine reports accurate hardware state and cache status
- [ ] Mocked unit tests verify stage transitions, single-stem optimization, and OOM/download/export errors
- [ ] Gate check passes: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_engine_unit.py -v`
**Tests**: unit
**Gate**: quick

---

### T5: Implement Job Queue, Persistence, Restart Recovery & Retention [P]
**What**: Build `JobManager` with atomic JSON manifests, concurrency control, disk-space checks, startup restart recovery, ZIP bundling, and safe expiration cleanup.
**Where**: `src/core/jobs.py`, `tests/integration/test_jobs_and_recovery.py`
**Depends on**: T2
**Requirement**: SEP-03, SEP-04, SEP-07, SEP-08
**Done when**:
- [ ] Concurrent jobs queue cleanly and reject overflow with `SERVER_BUSY`
- [ ] Startup recovery converts active/queued jobs to `INTERRUPTED_BY_RESTART`
- [ ] Expired jobs are cleaned without touching active jobs
- [ ] Gate check passes: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_jobs_and_recovery.py -v`
**Tests**: integration
**Gate**: full

---

### T6: Implement FastAPI App, Safe File Streaming & API Tests
**What**: Build `src/api/routes.py`, `src/api/__init__.py`, `main.py`, and API integration tests covering upload streaming, job polling, safe file/ZIP downloads, path traversal rejection, and error handlers.
**Where**: `src/api/routes.py`, `src/api/__init__.py`, `main.py`, `tests/integration/test_api_routes.py`
**Depends on**: T3, T4, T5
**Requirement**: SEP-01, SEP-02, SEP-04, SEP-06, SEP-09
**Done when**:
- [ ] Streaming upload enforces `MAX_UPLOAD_MB` without buffering entire file in memory
- [ ] File endpoint rejects path traversal and unowned filenames
- [ ] Gate check passes: `.\.venv\Scripts\python.exe -m pytest tests/unit tests/integration/test_api_routes.py tests/integration/test_jobs_and_recovery.py -v`
**Tests**: integration
**Gate**: full

---

### T7: Build Accessible Studio Frontend
**What**: Create `templates/index.html`, `static/css/style.css`, `static/js/app.js`, and `static/img/favicon.svg` with responsive layout, keyboard navigation, ARIA live regions, goal cards, dynamic track selection, advanced model panel, stage stepper, audio players, and error recovery controls.
**Where**: `templates/index.html`, `static/css/style.css`, `static/js/app.js`, `static/img/favicon.svg`
**Depends on**: T6
**Requirement**: SEP-01, SEP-03, SEP-04, SEP-10, SEP-11
**Done when**:
- [ ] Page renders cleanly with no "stem" jargon in primary controls
- [ ] Keyboard navigation and contrast comply with WCAG AA
- [ ] End-to-end browser verification passes with real screenshots captured
**Tests**: e2e (browser walkthrough)
**Gate**: full

---

### T8: Run Real CPU Model Separation Integration Tests
**What**: Implement and run `tests/integration/test_real_separation.py` exercising real `UVR-MDX-NET-Inst_HQ_3.onnx` separation on CPU for both mono 48 kHz and stereo 44.1 kHz audio files through the HTTP API, verifying WAV/FLAC outputs and ZIP archives.
**Where**: `tests/integration/test_real_separation.py`
**Depends on**: T6
**Requirement**: SEP-02, SEP-04, SEP-05, SEP-10, SEP-11
**Done when**:
- [ ] Real CPU model separation succeeds end-to-end and passes all assertions
- [ ] Gate check passes: `.\.venv\Scripts\python.exe -m pytest -v`
**Tests**: integration
**Gate**: build

---

### T9: Add Docker (CPU & NVIDIA GPU) & TrueNAS Configs
**What**: Create `Dockerfile`, `Dockerfile.gpu`, `.dockerignore`, `docker-compose.yml`, `docker-compose.gpu.yml`, and `deploy/truenas/` templates, and verify Compose YAML resolution.
**Where**: `Dockerfile`, `Dockerfile.gpu`, `.dockerignore`, `docker-compose.yml`, `docker-compose.gpu.yml`, `deploy/truenas/`
**Depends on**: T6
**Requirement**: SEP-12
**Done when**:
- [ ] `docker compose -f docker-compose.yml config` succeeds
- [ ] `docker compose -f docker-compose.yml -f docker-compose.gpu.yml config` succeeds with a single service on port 7860
**Tests**: none (config verification via `docker compose config`)
**Gate**: build

---

### T10: Create Bilingual Docs, Screenshots & Final Spec Validation
**What**: Capture real UI screenshots in `docs/screenshots/`, write `README.md` (EN) and `README_PT-BR.md` (PT-BR), and complete `.specs/features/audio-separation/validation.md`.
**Where**: `docs/screenshots/`, `README.md`, `README_PT-BR.md`, `.specs/features/audio-separation/validation.md`
**Depends on**: T7, T8, T9
**Requirement**: SEP-01 through SEP-12
**Done when**:
- [ ] Real screenshots embedded and verified in both READMEs
- [ ] All specs/tasks/validation updated and full test suite passes
**Tests**: build gate
**Gate**: build

---

## Pre-Approval Validation Checks

### Task Granularity Check
| Task | Scope | Status |
| ---- | ----- | ------ |
| T1 | Config + skeleton + tests | ✅ Granular |
| T2 | Errors + curated catalog + tests | ✅ Granular |
| T3 | Media inspection & normalization + tests | ✅ Granular |
| T4 | Isolated engine adapter + unit tests | ✅ Granular |
| T5 | Job manager & recovery + integration tests | ✅ Granular |
| T6 | FastAPI routes + API integration tests | ✅ Granular |
| T7 | Accessible Web UI | ✅ Granular |
| T8 | Real CPU model E2E integration test | ✅ Granular |
| T9 | Docker CPU/GPU & Compose configs | ✅ Granular |
| T10 | Bilingual docs, screenshots & validation | ✅ Granular |

### Diagram-Definition Cross-Check
| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | Start | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 [P] | ✅ Match |
| T4 | T2 | T2 → T4 [P] | ✅ Match |
| T5 | T2 | T2 → T5 [P] | ✅ Match |
| T6 | T3, T4, T5 | T3, T4, T5 → T6 | ✅ Match |
| T7 | T6 | T6 → T7 | ✅ Match |
| T8 | T6 | T7 → T8 (sequential execution order) | ✅ Match |
| T9 | T6 | T8 → T9 (sequential execution order) | ✅ Match |
| T10 | T7, T8, T9 | T9 → T10 | ✅ Match |

### Test Co-location Validation
| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1 | Config | unit | unit | ✅ OK |
| T2 | Catalog & Errors | unit | unit | ✅ OK |
| T3 | Media Inspection | unit | unit | ✅ OK |
| T4 | Engine Adapter | unit | unit | ✅ OK |
| T5 | Job Manager | integration | integration | ✅ OK |
| T6 | FastAPI Routes | integration | integration | ✅ OK |
| T7 | Frontend UI | e2e | e2e | ✅ OK |
| T8 | Real Model Separation | integration (build) | integration | ✅ OK |
| T9 | Docker Configs | none | none | ✅ OK |
| T10 | Docs & Validation | build gate | build gate | ✅ OK |
