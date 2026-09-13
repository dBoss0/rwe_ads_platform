"""Pydantic models for PHD catalog schema queries."""
from pydantic import BaseModel
from typing import List, Optional


class ColumnInfo(BaseModel):
    column_name: str
    data_type: str
    description: Optional[str] = ""
    valid_values: Optional[str] = ""
    is_join_key: bool = False


class TableInfo(BaseModel):
    table_name: str
    table_category: str = ""
    columns: List[ColumnInfo]


class SchemaResponse(BaseModel):
    catalog: str
    schema: str
    tables: List[TableInfo]
