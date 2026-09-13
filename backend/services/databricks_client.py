"""
Databricks workspace API helpers.
Carried over and extended from ads_automation/databricks_api.py.

In Databricks Apps, DATABRICKS_HOST and DATABRICKS_TOKEN are injected as env vars.
Falls back to settings values for local dev / REST calls.
"""
import base64
import os
import requests
from backend.config import settings


def _headers() -> dict:
    token = settings.databricks_token
    if not token:
        raise RuntimeError(
            "DATABRICKS_TOKEN not set. Add it to .env for local dev."
        )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def is_databricks_app() -> bool:
    """True when running inside a Databricks App (env vars injected)."""
    return settings.is_databricks_app


# ─────────────────────────────────────────────────────────────────────────────
# Workspace — notebooks
# ─────────────────────────────────────────────────────────────────────────────

def save_notebook(path: str, content: str) -> dict:
    """Push a SOURCE-format SQL notebook to Databricks workspace."""
    host = settings.databricks_host
    headers = _headers()

    # Ensure parent directory exists
    parent = "/".join(path.rstrip("/").split("/")[:-1])
    if parent:
        requests.post(
            f"{host}/api/2.0/workspace/mkdirs",
            headers=headers,
            json={"path": parent},
            timeout=15,
        )

    payload = {
        "path": path,
        "format": "SOURCE",
        "language": "SQL",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "overwrite": True,
    }
    resp = requests.post(
        f"{host}/api/2.0/workspace/import",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json() if resp.text.strip() else {}


def get_notebook_url(path: str) -> str:
    """Return a clickable Databricks workspace URL for the given notebook path."""
    return f"{settings.databricks_host}/#workspace{path}"


def get_current_user() -> str:
    """Return the userName of the authenticated user via SCIM API."""
    host = settings.databricks_host
    resp = requests.get(
        f"{host}/api/2.0/preview/scim/v2/Me",
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("userName", "")


# ─────────────────────────────────────────────────────────────────────────────
# Volume — file upload
# ─────────────────────────────────────────────────────────────────────────────

def upload_to_volume(local_path: str, volume_path: str) -> str:
    """
    Upload a local file to a UC Volume via Files API.
    Returns the volume path on success.
    """
    host = settings.databricks_host
    url = f"{host}/api/2.0/fs/files{volume_path}"
    headers = {"Authorization": f"Bearer {settings.databricks_token}"}

    with open(local_path, "rb") as fh:
        resp = requests.put(url, headers=headers, data=fh, timeout=60)
    resp.raise_for_status()
    return volume_path
