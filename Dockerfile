FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1
# diffq has no Linux wheel and must be compiled.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY requirements.txt .
# CPU-only PyTorch + torchvision together: avoids pulling mismatched CUDA torchvision wheels.
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    SPLIT_HOST=0.0.0.0 \
    SPLIT_PORT=7860 \
    SPLIT_MODEL_CACHE_DIR=/data/models \
    SPLIT_JOBS_DIR=/data/jobs \
    TORCH_HOME=/data/models/torch

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY main.py ./
COPY src ./src
COPY static ./static
COPY templates ./templates

RUN mkdir -p /data/models /data/jobs
VOLUME ["/data/models", "/data/jobs"]
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/health', timeout=8)" || exit 1

CMD ["python", "main.py"]
