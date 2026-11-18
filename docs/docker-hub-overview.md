# Split My Music

Self-hosted web application that separates **vocals, music, drums, bass, guitar, and piano** from your audio files using open-source AI models via [`python-audio-separator`](https://github.com/nomadkaraoke/python-audio-separator). Everything runs locally on your own server — no external audio uploads.

Source code, documentation, and issue tracker: <https://github.com/paladini/split-my-music>

## Quick Start (CPU — Tested & Ready)

```bash
docker run -d \
  --name split-my-music \
  -p 7860:7860 \
  -v split-models:/data/models \
  -v split-jobs:/data/jobs \
  --restart unless-stopped \
  paladini/split-my-music:latest
```

Open `http://localhost:7860`. Models download once on first use (~50–80 MB for default models) and persist in `/data/models`.

## NVIDIA GPU

Requires an NVIDIA GPU, recent NVIDIA host driver, and the NVIDIA Container Toolkit:

```bash
docker run -d \
  --name split-my-music \
  --gpus all \
  -p 7860:7860 \
  -v split-models:/data/models \
  -v split-jobs:/data/jobs \
  --restart unless-stopped \
  paladini/split-my-music:gpu
```

> **Note:** The CPU image was built and smoke-tested locally; the GPU image is built via CI/CD from `Dockerfile.gpu` and has not yet been executed on physical NVIDIA hardware by the author. Apple Silicon, AMD, and Intel GPUs are not accelerated inside these Linux containers.

## Available Tags

| Tag | Variant | Architecture |
| --- | --- | --- |
| `latest`, `cpu`, `1.0.0`, `1.0` | CPU (`Dockerfile`) | `linux/amd64` |
| `gpu`, `1.0.0-gpu`, `1.0-gpu` | NVIDIA CUDA 12.6 (`Dockerfile.gpu`) | `linux/amd64` |

## Configuration

- `SPLIT_MAX_UPLOAD_MB` (`200`)
- `SPLIT_MAX_DURATION_MINUTES` (`20`)
- `SPLIT_MAX_CONCURRENT_JOBS` (`1`)
- `SPLIT_MAX_QUEUE_SIZE` (`5`)
- `SPLIT_MIN_FREE_DISK_MB` (`500`)
- `SPLIT_RETENTION_HOURS` (`24`)
- `SPLIT_MAX_STORED_JOBS` (`20`)
- `SPLIT_LOG_LEVEL` (`INFO`)

Health check endpoint: `GET /health`

## Security

Split My Music ships without login/authentication and is intended for local machines, home LANs, and homelabs. Do not expose it directly to the public internet without placing it behind an authenticated HTTPS reverse proxy.

## License

MIT License for Split My Music application code. Model weights are downloaded at runtime and retain their upstream licenses; see `THIRD_PARTY.md` in the repository.
