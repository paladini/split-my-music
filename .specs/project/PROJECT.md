# Split My Music

**Vision:** A lightweight, accessible, self-hosted web application that lets anyone split vocals, backing music, and individual instruments from audio files using AI models powered by `python-audio-separator`.
**For:** Everyday music listeners, singers, musicians, and homelab/NAS self-hosters who want private local audio separation without technical jargon.
**Solves:** Running modern open-source audio separation models requires CLI proficiency, manual Python/CUDA setup, and knowledge of obscure model filenames. Split My Music wraps `python-audio-separator` in a calm, goal-driven web interface with reliable background job management, persistent model caching, and reproducible CPU/GPU Docker deployments.

## Goals

- Enable a first-time user to upload an audio track, choose a plain-English goal (Vocals & Music, 4-Track Instruments, or 6-Track Full Band), listen in-browser, and download individual tracks or a ZIP archive in a single flow.
- Keep all `python-audio-separator` integration isolated in a dedicated adapter layer exposing only curated, validated models and accurate output choices.
- Handle invalid/corrupted files, missing disk space, download failures, memory pressure, and server restarts gracefully without exposing stack traces to end users.
- Provide clean, conflict-free CPU and NVIDIA GPU Docker Compose configurations with persistent model and job volumes.

## Tech Stack

**Core:**

- Framework: FastAPI + Jinja2
- Language: Python 3.12+
- Server: Uvicorn (ASGI)
- Frontend: Semantic HTML5, Vanilla CSS3 (modern custom properties & responsive grid), Vanilla ES6 JavaScript (zero heavy build pipeline)
- Storage: File-backed job manifest JSON + local persistent filesystem volumes (`/data/models`, `/data/jobs`)

**Key dependencies:** `audio-separator` (>=0.48.0), `ffmpeg`/`ffprobe` (system binary), `python-multipart`, `soundfile`, `httpx2`, `pytest`

## Scope

**v1 includes:**

- Local audio upload (MP3, WAV, FLAC, M4A, AAC, OGG, OPUS) with streaming size limit enforcement and `ffprobe` validation.
- Goal-driven separation (`Vocals & Music`, `Vocals, Drums, Bass & Other`, `Full Band 6-Track`) plus collapsible advanced model selector and lossless (`WAV`, `FLAC`) or lossy (`MP3`) output formats.
- Background job queue with concurrency cap, real stage tracking (`preparing`, `downloading_model`, `separating`, `exporting`), restart recovery, in-browser audio playback, and individual/ZIP downloads.
- Docker CPU (`Dockerfile` + `docker-compose.yml`), NVIDIA GPU override (`Dockerfile.gpu` + `docker-compose.gpu.yml`), health checks, and TrueNAS SCALE templates.
- Bilingual documentation (`README.md` + `README_PT-BR.md`), MIT license, and automated unit + integration + real-model CPU tests.

**Explicitly out of scope:**

- YouTube / remote URL downloading (excluded to keep v1 strictly focused on local file separation, reliability, and self-hosted legal clarity).
- Uncurated "load any arbitrary model URL" support (only validated catalog models are exposed).
- Multi-user authentication, billing, or multi-node distributed worker clusters.
- Claiming GPU acceleration for Apple Silicon / AMD / Intel inside Docker containers.

## Constraints

- Technical: Keep `D:\code\voice-separator-demucs` completely untouched; isolate `audio_separator` behind `src/core/engine.py`; never use "stem" as primary UI copy.
- Hardware/Verification: Host environment has Python 3.12, FFmpeg 9.0, and CPU only (no NVIDIA GPU; Docker Desktop daemon stopped during development). Real CPU separation will be verified end-to-end; GPU and Docker runtime builds must be documented honestly as structurally validated rather than GPU-executed if unavailable.
