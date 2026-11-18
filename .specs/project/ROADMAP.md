# Roadmap

**Current Milestone:** Milestone 1 — Core Self-Hosted Separation Platform
**Status:** Complete

---

## Milestone 1: Core Self-Hosted Separation Platform

**Goal:** Deliver a complete, tested, self-hosted audio separation web application powered by `python-audio-separator`, ready for CPU and NVIDIA GPU Docker deployment.
**Target:** v1.0.0 Open Source Release

### Features

**Audio Separation (`audio-separation`)** - COMPLETE (CPU app + CPU Docker container verified; NVIDIA GPU Compose validated, physical GPU runtime unverified)

- Curated goal-based model catalog (`UVR-MDX-NET-Inst_HQ_3.onnx`, `Kim_Vocal_2.onnx`, `UVR_MDXNET_KARA_2.onnx`, `htdemucs.yaml`, `htdemucs_6s.yaml`, `model_bs_roformer_ep_317_sdr_12.9755.ckpt`)
- Audio validation (`ffprobe`), mono/stereo & multi-channel normalization, sample-rate preservation
- Background job queue, restart recovery, retention cleanup, and ZIP export
- Refined responsive & accessible web UI (upload, stage tracker, audio players, downloads)
- CPU & NVIDIA GPU Docker + Compose override + bilingual documentation

---

## Future Considerations

- Optional directory watch / batch folder processing for homelab workflows
- Waveform scrubbing preview inside the browser player
- Custom model registry extension via local config file for power users

