# Contributing to Split My Music

Thanks for helping! This project values **simplicity**, **honesty about what is tested**, and a friendly interface for people who know nothing about AI models.

## Ground rules

- Keep the main flow simple. Prefer fewer options over more.
- Plain English in the UI. Avoid jargon; do not use "stem" as primary UI wording.
- Do not claim support, speed or quality that was not verified.
- Never run shell commands built from user data. Never trust user file names.
- Only `src/core/engine.py` may import `audio_separator`.

## Setup

Python 3.12 and FFmpeg are required.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

## Tests

```bash
pytest -m "not real_model"   # fast
pytest -m real_model         # downloads ~64 MB, runs the default model on CPU
```

Add tests with every change. Bug fixes should include a test that fails before the fix.

## Adding a model

1. Confirm the file names and stems in `python-audio-separator`'s model list.
2. Add it to `src/core/catalog.py` with only the outputs it truly produces, its real download size and required files.
3. **Run it** on a real file and record the result in your PR. Untested models must be marked as such in the README.
4. Check the model's license and add credits.

## Pull requests

- Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`...).
- Update `CHANGELOG.md` for user-visible changes.
- Be kind. See the [Code of Conduct](CODE_OF_CONDUCT.md).
