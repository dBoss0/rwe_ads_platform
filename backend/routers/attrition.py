"""Attrition step generation endpoints."""
from fastapi import APIRouter, HTTPException
from backend.models.attrition import NotebookRequest, NotebookResponse
from backend.services.notebook_builder import build_notebook

router = APIRouter(tags=["attrition"])


@router.post("/generate", response_model=NotebookResponse)
async def generate_attrition_notebook(request: NotebookRequest):
    """
    Generate a complete Databricks SQL attrition notebook.

    Input:
    - title: study title
    - steps: list of attrition steps (from /protocol/parse or manually edited)
    - code_lists: optional code lists (ICD, CPT, DRG)
    - study_window: optional date range string
    - workspace_path: optional Databricks path to save the notebook

    Output:
    - notebook_sql: full SOURCE-format SQL notebook
    - steps: per-step SQL with generated_by (llm | fallback)
    - workspace_url: clickable link if workspace_path was provided
    """
    try:
        notebook_sql, step_sqls = build_notebook(
            title=request.title,
            steps=request.steps,
            code_lists=request.code_lists or [],
            study_window=request.study_window or "",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Notebook generation failed: {e}")

    workspace_url = None

    if request.workspace_path:
        try:
            from backend.services.databricks_client import save_notebook, get_notebook_url
            save_notebook(request.workspace_path, notebook_sql)
            workspace_url = get_notebook_url(request.workspace_path)
        except Exception as e:
            # Non-fatal — return the notebook SQL even if save fails
            pass

    warnings = [
        f"Step {s.step_num} used fallback template (LLM unavailable)"
        for s in step_sqls
        if s.generated_by == "fallback"
    ]

    return NotebookResponse(
        title=request.title,
        notebook_sql=notebook_sql,
        steps=step_sqls,
        workspace_url=workspace_url,
        warnings=warnings,
    )
