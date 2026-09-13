"""PHD catalog schema endpoints."""
from fastapi import APIRouter, Query
from typing import List, Optional
from backend.models.catalog import SchemaResponse
from backend.services.schema_service import get_phd_schema, CORE_TABLES

router = APIRouter(tags=["catalog"])


@router.get("/schema", response_model=SchemaResponse)
async def get_schema(
    tables: Optional[List[str]] = Query(
        None,
        description="Table names to fetch. Defaults to core attrition tables.",
    )
):
    """
    Return PHD table/column metadata from the catalog.
    Data dictionary lives in the catalog — not hardcoded.
    """
    return get_phd_schema(tables or CORE_TABLES)


@router.get("/tables")
async def list_tables():
    """Return the list of core PHD tables used in attrition."""
    return {"tables": CORE_TABLES}
