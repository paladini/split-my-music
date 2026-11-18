# Changelog

All notable changes are documented here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
