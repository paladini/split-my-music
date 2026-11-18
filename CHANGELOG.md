# Changelog

All notable changes are documented here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Security
- Raised minimum versions of runtime and test dependencies (`fastapi` 0.165, `uvicorn` 0.54, `python-multipart` 0.0.34, `jinja2` 3.1.6, `soundfile` 0.14, `audioread` 3.1, `pytest` 9.2) to pick up upstream security fixes.
- Upgraded all GitHub Actions to their current major versions (Node.js 24 runtime): `actions/checkout` v7, `actions/setup-python` v7, `docker/setup-buildx-action` v4, `docker/setup-qemu-action` v4, `docker/login-action` v4, `docker/metadata-action` v6, `docker/build-push-action` v7, `softprops/action-gh-release` v3, `peter-evans/dockerhub-description` v5.

### Changed
- GPU image now uses `nvidia/cuda:13.5.0-cudnn-runtime-ubuntu22.04` with PyTorch `cu132` wheels. This matches `onnxruntime-gpu` >= 1.32, which is built for CUDA 13. **Hosts need an NVIDIA driver 580 or newer**, and Maxwell, Pascal and Volta GPUs are no longer supported by CUDA 13.
- Test client dependency switched from `httpx` to `httpx2`, because Starlette 1.10 deprecates `httpx` for `starlette.testclient`.
- Dependabot now groups minor and patch updates and ignores Python base-image minor bumps, since `onnxruntime` has no Python 3.15 wheels yet.

## [1.0.0] - 2026-11-17

### Added
- Web interface: drag-and-drop upload, three plain-English goals, track selection, WAV/FLAC/MP3 output, advanced model picker, real stage progress, in-page players, per-file and ZIP downloads.
- Isolated `python-audio-separator` engine adapter and a curated catalog of six models (only `UVR-MDX-NET-Inst_HQ_3` has been executed in tests).
- Background job queue with concurrency and queue limits, disk-space guard, restart recovery, safe retention cleanup.
- Input validation with `ffprobe`, filename sanitization, streaming upload size limit, safe file serving.
- Docker CPU image and NVIDIA GPU override, health check, persistent model and result volumes, TrueNAS templates.
- English and Brazilian Portuguese documentation, CI and release pipelines.

### Known limitations
- GPU image and Docker images were validated only with `docker compose config` before release; see the README.
