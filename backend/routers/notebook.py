"""Notebook save and download endpoints."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from backend.services.databricks_client import save_notebook, get_notebook_url

router = APIRouter(tags=["notebook"])


class SaveRequest(BaseModel):
    workspace_path: str
    notebook_sql: str


@router.post("/save")
async def save_to_workspace(req: SaveRequest):
    """Save a generated notebook to the Databricks workspace."""
    try:
        save_notebook(req.workspace_path, req.notebook_sql)
        url = get_notebook_url(req.workspace_path)
        return {"workspace_url": url, "status": "saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/download", response_class=PlainTextResponse)
async def download_notebook(req: SaveRequest):
    """Return the notebook SQL as a plain text file download."""
    return PlainTextResponse(
        content=req.notebook_sql,
        headers={
            "Content-Disposition": f'attachment; filename="attrition_notebook.sql"'
        },
    )
