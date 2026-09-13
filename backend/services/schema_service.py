"""
PHD schema service.

Queries the Premier PHD catalog via Databricks REST SQL API to return
table/column metadata. The data dictionary lives IN the catalog — we do
not hardcode it in Python files.

In Databricks Apps this uses the injected token automatically.
"""
import requests
from typing import List, Dict, Optional
from backend.config import settings
from backend.models.catalog import ColumnInfo, TableInfo, SchemaResponse


# Core PHD tables used in attrition (always load these)
CORE_TABLES = [
    "pat",
    "paticd_proc",
    "paticd_diag",
    "patcpt",
    "patbill",
    "prov_enrollment",
    "providers",
    "chgmstr",
    "hospchg",
    "icdcode",
    "cptcode",
]


def _run_sql(statement: str) -> List[Dict]:
    """Execute a SQL statement via Databricks SQL Statement API and return rows as dicts."""
    host = settings.databricks_host
    token = settings.databricks_token
    if not host or not token:
        return []

    payload = {
        "statement": statement,
        "warehouse_id": "9525c51c721e3ac7",
        "wait_timeout": "30s",
        "on_wait_timeout": "CANCEL",
    }
    resp = requests.post(
        f"{host}/api/2.0/sql/statements",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=45,
    )
    if not resp.ok:
        return []

    data = resp.json()
    if data.get("status", {}).get("state") != "SUCCEEDED":
        return []

    result = data.get("result", {})
    columns = [c["name"] for c in data.get("manifest", {}).get("schema", {}).get("columns", [])]
    rows = result.get("data_array", [])
    return [dict(zip(columns, row)) for row in rows]


def get_phd_schema(tables: Optional[List[str]] = None) -> SchemaResponse:
    """
    Return table + column metadata from the PHD catalog.
    Uses information_schema.columns — no hardcoded data dictionary.

    Args:
        tables: list of table names to fetch (default: CORE_TABLES)
    """
    target = tables or CORE_TABLES
    in_clause = ", ".join(f"'{t}'" for t in target)

    sql = f"""
    SELECT
        table_name,
        column_name,
        data_type,
        comment
    FROM {settings.phd_catalog}.information_schema.columns
    WHERE table_schema = '{settings.phd_schema}'
      AND table_name   IN ({in_clause})
    ORDER BY table_name, ordinal_position
    """

    rows = _run_sql(sql)

    # Group by table
    tables_map: Dict[str, List[ColumnInfo]] = {}
    for row in rows:
        tbl = row["table_name"]
        col = ColumnInfo(
            column_name=row["column_name"],
            data_type=row["data_type"],
            description=row.get("comment") or "",
        )
        tables_map.setdefault(tbl, []).append(col)

    table_list = [
        TableInfo(table_name=tbl, columns=cols)
        for tbl, cols in tables_map.items()
    ]

    return SchemaResponse(
        catalog=settings.phd_catalog,
        schema=settings.phd_schema,
        tables=table_list,
    )


def get_schema_as_prompt_context() -> str:
    """
    Return a compact string of PHD schema suitable for injection into LLM prompts.
    Used by the parser and SQL generator to ground responses in real column names.
    """
    schema = get_phd_schema()
    lines = []
    for tbl in schema.tables:
        col_names = ", ".join(c.column_name for c in tbl.columns)
        lines.append(f"{tbl.table_name}: {col_names}")
    return "\n".join(lines)
