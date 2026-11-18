# Third-party software and models

Split My Music's own code is MIT licensed. It does **not** ship any model weights; they are downloaded at runtime from the upstream hosts the first time a model is used. Each component keeps its own license. This list is a good-faith summary; verify licenses before redistributing anything.

| Component | Used for | License (per upstream) |
|---|---|---|
| [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator) | separation engine | MIT |
| [Ultimate Vocal Remover](https://github.com/Anjok07/ultimatevocalremovergui) (Anjok07, aufr33) | MDX-Net / VR models and code origin | MIT (upstream asks users of its models to credit UVR) |
| MDX-Net models (Kuielab, KimberleyJSN and others) | `UVR-MDX-NET-Inst_HQ_3`, `Kim_Vocal_2`, `UVR_MDXNET_KARA_2` | see each model's source |
| [Demucs](https://github.com/facebookresearch/demucs) (Meta AI Research) | `htdemucs`, `htdemucs_6s` | MIT |
| BS-RoFormer (lucidrains implementation, ViperX weights) | `model_bs_roformer_ep_317_sdr_12.9755` | see source; not run in tests |
| PyTorch, ONNX Runtime, librosa, FastAPI, Uvicorn | runtime | BSD / MIT / Apache-2.0 |
| FFmpeg | decoding and encoding | LGPL/GPL depending on build (installed from the OS package, not bundled) |

Model licenses for individual weight files may differ from the code licenses above. The notes in `src/core/catalog.py` are not legal advice.
