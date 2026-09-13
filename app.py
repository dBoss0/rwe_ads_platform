"""
Databricks Apps entry point.

Databricks Apps runs this file directly:
  uvicorn app:app --host 0.0.0.0 --port $PORT

The FastAPI application lives in backend/main.py.
React frontend is built to frontend/dist/ and served as static files.
"""
from backend.main import app  # noqa: F401 — re-exported for uvicorn

__all__ = ["app"]
