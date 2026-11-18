# Audio Separation Validation

**Date**: 2026-11-17
**Spec**: `.specs/features/audio-separation/spec.md`

## Test run

- Gate: `pytest -v` (unit + integration + real model, CPU, Windows, Python 3.12.10)
- See "Final result" at the bottom for counts.

## Verified (automated)

| Req | Evidence |
| --- | --- |
| SEP-02 | `test_api_routes` (streaming upload, extension/empty/corrupt/oversize rejection), `test_media_and_security` |
| SEP-03 | `test_engine_unit` stage callbacks; live UI showed real stages |
| SEP-04 | `test_api_routes` (play/download/zip), `test_real_separation`, live browser |
| SEP-05 | `test_real_separation`: 48 kHz mono WAV -> FLAC stays mono/48 kHz; 44.1 kHz stereo MP3 -> WAV stays stereo/44.1 kHz; 5.1 downmixed (`test_media_and_security`) |
| SEP-06 | error mapping tests (download failure, OOM, missing output, unexpected exception without leaked detail) |
| SEP-07 | `test_jobs_and_recovery`: queue full -> 429, low disk -> 507 |
| SEP-08 | restart recovery -> `INTERRUPTED_BY_RESTART`; retention cleanup spares active jobs |
| SEP-09 | path traversal / foreign filename / bad job id -> 404 |
| SEP-10, SEP-11 | catalog tests; outputs offered only per model; WAV/FLAC/MP3 export |
| SEP-01 | Live UI walkthrough via Chrome DevTools (desktop) with real screenshots |

## Verified manually (live browser)

Page load, goal/format/advanced controls rendering, file selection, stage progress, results with audio players, Download buttons and ZIP link, no server errors in log. The file was injected into the file input with a script because the browser tool blocks uploads from outside its workspace roots.

## Not verified (honest limits)

- **NVIDIA GPU**: no GPU on the dev host. `Dockerfile.gpu` and `docker-compose.gpu.yml` only checked with `docker compose config`.
- **Docker images (CPU and GPU) were never built or run**: the Docker daemon was not running.
- **Only `UVR-MDX-NET-Inst_HQ_3` was executed.** Kim Vocal 2, Karaoke 2, HTDemucs 4/6 stems and BS-RoFormer are configured from upstream metadata but not run.
- Mobile layout, keyboard-only walkthrough, screen reader and contrast were not audited with tools (CSS follows WCAG-minded choices only).
- Real music, long files, and performance/quality comparisons were not tested or measured (tests use synthetic tones).
- Browser subagent hit a quota limit; UI was checked directly with the DevTools MCP instead.
- Audio players show 0:00 until played (`preload="none"`).

## Final result

- `pytest -v`: **25 passed** (23 non-real + 2 real-model CPU), 0 failed, 0 skipped.
- `docker compose config` OK for CPU and CPU+GPU override (single service, port 7860).
