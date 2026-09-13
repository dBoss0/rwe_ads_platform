"""Health check endpoints."""
from fastapi import APIRouter
from backend.config import settings
from backend.services.databricks_client import get_current_user

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """
    Returns connectivity status and user identity.
    React frontend calls this on mount to detect Databricks context.
    """
    user = ""
    if settings.databricks_token:
        try:
            user = get_current_user()
        except Exception:
            pass

    return {
        "status": "ok",
        "databricks_connected": bool(settings.databricks_token),
        "is_databricks_app": settings.is_databricks_app,
        "user": user,
        "version": "2.0.0",
        "phd_catalog": settings.phd_fqn,
        "claude_endpoint": settings.claude_endpoint,
    }
