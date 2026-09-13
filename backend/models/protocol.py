"""Pydantic models for protocol upload and parse responses."""
from pydantic import BaseModel, Field
from typing import List, Optional


class ParseRequest(BaseModel):
    volume_path: Optional[str] = Field(
        None, description="UC Volume path to uploaded protocol file"
    )
    raw_text: Optional[str] = Field(
        None, description="Pasted protocol text (alternative to file upload)"
    )


class AttritionStep(BaseModel):
    step_num: int
    step_type: str = Field(..., description="inclusion | exclusion")
    description: str
    criterion_type: str = Field(
        ...,
        description=(
            "procedure_code | diagnosis_code | age | gender | date_range | "
            "lookback | comorbidity | data_quality | other"
        ),
    )
    raw_text: str = Field(..., description="Original sentence from protocol")


class ParseResponse(BaseModel):
    title: str
    data_sources: List[str]
    study_window: Optional[str] = None
    inclusion_steps: List[AttritionStep]
    exclusion_steps: List[AttritionStep]
    all_steps: List[AttritionStep]
    parse_method: str = Field(
        ..., description="llm_databricks | llm_rest | regex_fallback"
    )
    warnings: List[str] = []
    summary: Optional[str] = None          # ai_summarize output (Databricks mode only)
