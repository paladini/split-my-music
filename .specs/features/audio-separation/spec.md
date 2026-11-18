# Audio Separation Specification

## Problem Statement

People who want to extract vocals, backing music, or individual instruments from audio files using AI models currently face command-line tools, complex dependency/CUDA setups, and confusing technical model catalogs. Split My Music solves this with a clean, self-hosted web application backed by `python-audio-separator` that turns complex audio separation into a reliable, three-step local experience.

## Goals

- [x] Allow any user to upload an audio file, select a plain-English goal, monitor separation stages, listen in-browser, and download tracks individually or as a ZIP archive.
- [x] Enforce explicit, user-friendly error handling for invalid/corrupted files, oversized inputs, low disk space, model download failures, OOM/device failures, and server restarts.
- [x] Expose only curated, validated models and exact output tracks each model can produce, with persistent caching and clear CPU/GPU hardware guidance.
- [x] Provide clean, port-safe CPU and NVIDIA GPU Docker configurations and bilingual (EN / PT-BR) documentation.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| YouTube / URL downloading | Keeps v1 focused on local file reliability and self-hosted copyright clarity |
| Arbitrary unverified model URLs | Prevents runtime failures and mismatched stem labels |
| Multi-user auth / accounts | Intended for personal, LAN, and homelab self-hosting behind user-managed reverse proxy if exposed |

---

## User Stories

### P1: Simple Goal-Based Audio Separation, Playback & Download ⭐ MVP

**User Story**: As an everyday user, I want to drag and drop a song, choose to split vocals & music or instruments, listen to the result on the page, and download the tracks or a ZIP bundle without knowing anything about AI models.

**Why P1**: Core product value proposition.

**Acceptance Criteria**:

1. WHEN user opens the web interface THEN system SHALL display an accessible upload dropzone, plain-English goal cards (`Vocals & Music`, `Vocals, Drums, Bass & Other`, `Full Band (6 Tracks)`), track toggles matching the active model's actual outputs, output format selector (`WAV`, `FLAC`, `MP3`), and current processing device badge (`CPU` or `NVIDIA GPU`).
2. WHEN user uploads a supported audio file (`.mp3`, `.wav`, `.flac`, `.m4a`, `.aac`, `.ogg`, `.opus`) within size and duration limits THEN system SHALL stream the upload to disk without loading the entire file in memory, inspect it with `ffprobe`, queue the job (`202 Accepted`), and return a job ID.
3. WHEN a job runs THEN system SHALL update real stage transitions (`queued` → `preparing` → `downloading_model` if uncached → `separating` → `exporting` → `completed`) without fabricating fake percentage progress.
4. WHEN separation completes THEN system SHALL render an in-page audio player card for each generated track (pausing other tracks when one plays), individual download links, and a single ZIP bundle download.
5. WHEN input audio is mono or has a non-default sample rate (e.g., 48 kHz) THEN system SHALL preserve valid mono/stereo layout and sample rate without failing or corrupting timing.

**Independent Test**: Upload a 3-second 48 kHz mono WAV and a 3-second 44.1 kHz stereo MP3, run separation with the default model, play outputs in browser, and verify downloaded tracks and ZIP contents.

---

### P1: Reliability, Error Handling & Restart Recovery ⭐ MVP

**User Story**: As a self-hoster or user, I want clear explanations and recovery actions when something goes wrong (bad file, full disk, download failure, OOM, restart) and protection against concurrent overload.

**Why P1**: Reliability and trust are core principles of the project.

**Acceptance Criteria**:

1. WHEN user uploads an empty file, unsupported extension, renamed non-audio binary, or audio exceeding configured duration/size limits THEN system SHALL reject the request with an explicit user-friendly message and actionable suggestion, without exposing stack traces.
2. WHEN free disk space is below the configured threshold THEN system SHALL refuse new jobs before consuming disk (`507 Insufficient Storage`).
3. WHEN concurrent jobs reach `MAX_CONCURRENT_JOBS` THEN system SHALL queue additional jobs up to `MAX_QUEUE_SIZE` and return `429 Too Many Requests` (`SERVER_BUSY`) if the queue is full.
4. WHEN the server restarts while a job is in an active/queued state THEN startup recovery SHALL mark that job as `failed` with code `INTERRUPTED_BY_RESTART`, clean up temporary input/work directories, and present a clear retry prompt if polled.
5. WHEN model download fails, GPU/RAM runs out of memory, or expected output files are missing/empty THEN system SHALL log technical details server-side, clean partial temporary files, and return a structured `AppError` with recovery advice.

**Independent Test**: Automated unit/integration suite simulating corrupted uploads, low disk space, full queue, simulated restart manifest, download exception, OOM exception, and path-traversal requests.

---

### P2: Advanced Model Selection, Output Formats & Persistent Cache Visibility

**User Story**: As an advanced user, I want to pick among curated validated models, choose lossless (`WAV`, `FLAC`) or compressed (`MP3`) output, and see whether a model is already cached or how large its first download will be.

**Why P2**: Empowers power users while keeping the default path zero-jargon.

**Acceptance Criteria**:

1. WHEN user opens Advanced Settings THEN system SHALL list curated models with architecture, download size in MB, local cache status (`Cached locally` vs `Downloads on first run`), and hardware recommendation (`Fast on CPU & GPU` vs `GPU recommended`).
2. WHEN user switches models THEN system SHALL dynamically update the selectable output tracks so only outputs the chosen model can produce are shown.
3. WHEN user selects `WAV`, `FLAC`, or `MP3` THEN system SHALL export separated tracks in that exact format and reflect the format in file metadata and downloads.

**Independent Test**: Switch between `UVR MDX-Net Inst HQ 3`, `HTDemucs v4 (4-Track)`, `HTDemucs v4 6-Track`, and `BS-RoFormer` in UI and API; verify output toggles update dynamically and invalid stem combinations are rejected with HTTP 400.

---

### P3: CPU & NVIDIA GPU Docker Deployment and Bilingual Docs

**User Story**: As a homelab/NAS operator, I want straightforward Docker Compose configurations for CPU and NVIDIA GPU plus accurate EN/PT-BR documentation so I can persist models/results safely without port conflicts.

**Why P3**: Enables effortless self-hosting.

**Acceptance Criteria**:

1. WHEN operator runs `docker compose up -d` THEN system SHALL start only the CPU service on port 7860 with persistent volumes for `/data/models` and `/data/jobs` and a working `/health` check.
2. WHEN operator runs `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build` THEN Compose SHALL replace the CPU service in place with the NVIDIA CUDA build on port 7860 without starting two containers on the same port.
3. WHEN documentation is published THEN `README.md` (EN) and `README_PT-BR.md` (PT-BR) SHALL include real screenshots, verified limits, model licenses/credits, LAN vs public exposure security guidance, and honest hardware limitations.

**Independent Test**: Validate `docker compose config` on both CPU and GPU overlay files; inspect `Dockerfile`, `Dockerfile.gpu`, `README.md`, and `README_PT-BR.md`.

---

## Edge Cases

- WHEN filename contains `../`, null bytes, or shell metacharacters THEN system SHALL sanitize display names and never pass unsanitized strings to a shell (`shell=False`).
- WHEN multi-channel (>2 channels, e.g., 5.1) audio is uploaded THEN system SHALL downmix to stereo prior to inference instead of crashing in channel-expecting models.
- WHEN retention cleanup runs THEN system SHALL delete only expired completed/failed jobs and never delete active or queued jobs.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| SEP-01 | P1: Simple Separation — Goal UI & Device Badge | Verified | ✅ Verified |
| SEP-02 | P1: Simple Separation — Streaming Upload & `ffprobe` Validation | Verified | ✅ Verified |
| SEP-03 | P1: Simple Separation — Real Stage Progress Tracking | Verified | ✅ Verified |
| SEP-04 | P1: Simple Separation — In-Page Player, Individual & ZIP Download | Verified | ✅ Verified |
| SEP-05 | P1: Simple Separation — Mono/Stereo & Sample Rate Preservation | Verified | ✅ Verified |
| SEP-06 | P1: Reliability — Input Validation & Safe Error Messages | Verified | ✅ Verified |
| SEP-07 | P1: Reliability — Disk Space Guard & Concurrency Queue | Verified | ✅ Verified |
| SEP-08 | P1: Reliability — Startup Restart Recovery & Retention Cleanup | Verified | ✅ Verified |
| SEP-09 | P1: Reliability — Path Traversal & Secure File Serving | Verified | ✅ Verified |
| SEP-10 | P2: Advanced — Curated Model Catalog & Cache Visibility | Verified | ✅ Verified |
| SEP-11 | P2: Advanced — Lossless (`WAV`, `FLAC`) & `MP3` Output Formats | Verified | ✅ Verified |
| SEP-12 | P3: Deployment — CPU/GPU Docker & Bilingual Docs | Verified | ✅ Verified (CPU Docker built & smoke-tested; GPU Compose validated) |

**Coverage:** 12 total, 12 mapped (SEP-12: CPU Docker built & smoke-tested; NVIDIA GPU Compose config-validated only)

---

## Success Criteria

- [x] All unit and integration tests pass via `pytest`, including real CPU separation with `UVR-MDX-NET-Inst_HQ_3.onnx`.
- [x] Live web UI walkthrough completes upload → processing → audio playback → ZIP download without console/server errors, and screenshots are captured.
- [x] Both CPU and NVIDIA GPU Compose configurations pass `docker compose config`, and the CPU Docker image (`paladini/split-my-music:latest`) passes container build and `/health` + `/api/config` smoke tests.

