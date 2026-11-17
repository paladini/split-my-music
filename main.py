"""Split My Music entry point.

Run:  python main.py   (or: uvicorn main:app --host 0.0.0.0 --port 7860)
"""

from src.api.routes import create_app
from src.config import load_settings

app = create_app()

if __name__ == "__main__":
    import uvicorn

    s = load_settings()
    uvicorn.run(app, host=s.host, port=s.port, log_level=s.log_level.lower())
