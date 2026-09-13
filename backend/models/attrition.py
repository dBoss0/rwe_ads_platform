"""Pydantic models for attrition generation requests and responses."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class CodeEntry(BaseModel):
    code: str
    description: Optional[str] = ""


class CodeList(BaseModel):
    condition: str
    coding_system: str = Field(
        ..., description="ICD-10-PCS | ICD-10-CM | CPT | HCPCS | MS-DRG"
    )
    codes: List[CodeEntry]


class StepInput(BaseModel):
    step_num: int
    step_type: str = Field(..., description="inclusion | exclusion")
    description: str
    criterion_type: str


class NotebookRequest(BaseModel):
    title: str
    steps: List[StepInput]
    code_lists: Optional[List[CodeList]] = []
    study_window: Optional[str] = ""
    workspace_path: Optional[str] = Field(
        None,
        description="Databricks workspace path to save notebook (e.g. /Users/me/attrition)"
    )


class StepSQL(BaseModel):
    step_num: int
    step_type: str
    description: str
    target_table: str
    sql: str
    generated_by: str = Field(..., description="llm | fallback")


class NotebookResponse(BaseModel):
    title: str
    notebook_sql: str
    steps: List[StepSQL]
    workspace_url: Optional[str] = None
    warnings: List[str] = []
