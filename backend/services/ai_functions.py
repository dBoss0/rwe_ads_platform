"""
Databricks AI Functions bridge.

Wraps all Databricks AI Functions via the SQL Statement API so they can be
called from FastAPI (which runs as a Databricks App, not inside a notebook).

Functions used:
  ai_parse_document  — extract text/tables/layout from PDF, DOCX, PPT, images
  ai_extract         — structured field extraction with JSON schema (v2.1)
  ai_classify        — multi-label text classification with confidence + rationale
  ai_query           — call any Model Serving endpoint with structured responseFormat
  ai_summarize       — generate a short summary of text
  ai_gen             — general-purpose text generation

All calls route through the Databricks SQL Statement API (warehouse ID from config).
Returns Python dicts / lists — no Spark DataFrames exposed to callers.
"""
import json
import logging
import requests
from typing import Any, Optional

from backend.config import settings

logger = logging.getLogger(__name__)

# Pulled from settings so it never drifts from config
WAREHOUSE_ID: str = settings.warehouse_id


# ─────────────────────────────────────────────────────────────────────────────
# SQL Statement API runner
# ─────────────────────────────────────────────────────────────────────────────

def _run_sql(statement: str, timeout: int = 60) -> list[dict]:
    """
    Execute a SQL statement via the Databricks SQL Statement API.
    Returns a list of row dicts.
    """
    host  = settings.databricks_host
    token = settings.databricks_token
    if not host or not token:
        logger.warning("Databricks not configured — SQL statement skipped.")
        return []

    payload = {
        "statement":      statement,
        "warehouse_id":   WAREHOUSE_ID,
        "wait_timeout":   f"{timeout}s",
        "on_wait_timeout": "CANCEL",
    }
    resp = requests.post(
        f"{host}/api/2.0/sql/statements",
        headers={
            "Authorization":  f"Bearer {token}",
            "Content-Type":   "application/json",
        },
        json=payload,
        timeout=timeout + 10,
    )
    if not resp.ok:
        logger.error("SQL Statement API error %d: %s", resp.status_code, resp.text[:400])
        return []

    data = resp.json()
    state = data.get("status", {}).get("state")
    if state != "SUCCEEDED":
        logger.error("SQL statement state: %s — %s", state, data.get("status", {}).get("error", {}).get("message", ""))
        return []

    columns = [
        c["name"]
        for c in data.get("manifest", {}).get("schema", {}).get("columns", [])
    ]
    rows = data.get("result", {}).get("data_array", [])
    return [dict(zip(columns, row)) for row in rows]


def _first_cell(rows: list[dict], col: str = None) -> Any:
    """Return the first cell from a single-row, single-column result."""
    if not rows:
        return None
    row = rows[0]
    if col:
        return row.get(col)
    return next(iter(row.values()), None)


# ─────────────────────────────────────────────────────────────────────────────
# ai_parse_document
# ─────────────────────────────────────────────────────────────────────────────

def ai_parse_document(volume_path: str) -> Optional[dict]:
    """
    Parse a document (PDF, DOCX, PPT, image) from a UC Volume.

    ai_parse_document takes BINARY content via READ_FILES — not a path string.
    Returns the VARIANT result as a Python dict.

    Args:
        volume_path: UC Volume path, e.g. /Volumes/catalog/schema/vol/file.docx
    """
    # Derive the directory and filename for READ_FILES
    # READ_FILES returns one row per file with a `content` BINARY column
    sql = f"""
    SELECT
        ai_parse_document(
            content,
            map('version', '2.0')
        ) AS parsed_doc
    FROM READ_FILES(
        '{volume_path}',
        format => 'binaryFile'
    )
    LIMIT 1
    """
    rows = _run_sql(sql, timeout=120)
    if not rows:
        return None

    raw = _first_cell(rows, "parsed_doc")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw_text": raw}
    return raw


def extract_text_from_parsed_doc(parsed_doc: dict) -> str:
    """
    Flatten ai_parse_document output into a single text string.
    Handles both v2.0 VARIANT structure and plain text fallbacks.
    """
    if not parsed_doc:
        return ""

    # v2.0 structure: {"documents": [{"pages": [{"elements": [{"type":"text","content":"..."}]}]}]}
    lines = []
    try:
        for doc in parsed_doc.get("documents", []):
            for page in doc.get("pages", []):
                for element in page.get("elements", []):
                    if element.get("type") in ("text", "table", "heading"):
                        lines.append(element.get("content", ""))
    except (AttributeError, TypeError):
        pass

    if not lines:
        # Fallback: try top-level text field
        lines = [str(parsed_doc.get("raw_text", parsed_doc))]

    return "\n".join(l for l in lines if l.strip())


# ─────────────────────────────────────────────────────────────────────────────
# ai_extract (v2.1)
# ─────────────────────────────────────────────────────────────────────────────

def ai_extract(text: str, schema: dict) -> Optional[dict]:
    """
    Extract structured fields from text using ai_extract v2.1.

    Args:
        text:   Protocol text (or section) to extract from
        schema: Dict of field definitions, e.g.:
                {"title": {"type": "string", "description": "Study title"},
                 "study_window": {"type": "string"}}

    Returns:
        Dict of extracted fields, or None on failure.
    """
    schema_json = json.dumps(schema).replace("'", "\\'")
    text_escaped = text.replace("'", "\\'")[:30_000]  # 30k char limit for inline SQL

    sql = f"""
    SELECT ai_extract(
        '{text_escaped}',
        '{schema_json}',
        options => map('version', '2.1', 'mode', 'precision')
    ) AS extracted
    """
    rows = _run_sql(sql, timeout=60)
    if not rows:
        return None

    raw = _first_cell(rows, "extracted")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw


# ─────────────────────────────────────────────────────────────────────────────
# ai_classify (v2.1)
# ─────────────────────────────────────────────────────────────────────────────

CRITERION_TYPES = [
    "procedure_code",
    "diagnosis_code",
    "age",
    "gender",
    "date_range",
    "lookback",
    "comorbidity",
    "data_quality",
    "inpatient_outpatient",
    "other",
]


def ai_classify_criterion(criterion_text: str) -> str:
    """
    Classify an attrition criterion into its PHD table type using ai_classify v2.1.

    Returns the best-matching label from CRITERION_TYPES.
    """
    labels_json = json.dumps(CRITERION_TYPES)
    text_escaped = criterion_text.replace("'", "\\'")[:2000]
    instructions = (
        "Classify this clinical attrition criterion by which Premier PHD table "
        "would be used to implement it in SQL. "
        "procedure_code=paticd_proc/patcpt, diagnosis_code=paticd_diag, "
        "age=pat.age, gender=pat.gender, date_range=pat.admit_date, "
        "inpatient_outpatient=pat.i_o_ind, data_quality=pat.publish_type/costs."
    )

    sql = f"""
    SELECT ai_classify(
        '{text_escaped}',
        '{labels_json}',
        map(
            'version', '2.1',
            'instructions', '{instructions}',
            'enableConfidenceScores', 'true'
        )
    ) AS classification
    """
    rows = _run_sql(sql, timeout=30)
    if not rows:
        return "other"

    raw = _first_cell(rows, "classification")
    try:
        if isinstance(raw, str):
            raw = json.loads(raw)
        # v2.1 format: {"response": [{"value": "label", "confidence_score": 0.97}]}
        responses = raw.get("response", [])
        if responses:
            return responses[0].get("value", "other")
    except (json.JSONDecodeError, AttributeError, IndexError):
        pass
    return "other"


def ai_classify_batch(criterion_texts: list[str]) -> list[str]:
    """
    Classify multiple criteria in a single SQL query using a VALUES table.
    More efficient than calling ai_classify_criterion per item.
    """
    if not criterion_texts:
        return []

    labels_json = json.dumps(CRITERION_TYPES).replace("'", "\\'")
    instructions = (
        "Classify this clinical attrition criterion by which Premier PHD table "
        "would be used to implement it in SQL."
    )

    # Build a VALUES table
    vals = ", ".join(
        f"({i}, '{t[:500].replace(chr(39), chr(39)+chr(39))}')"
        for i, t in enumerate(criterion_texts)
    )

    sql = f"""
    WITH criteria AS (
        SELECT * FROM VALUES {vals} AS t(idx, criterion_text)
    )
    SELECT
        idx,
        ai_classify(
            criterion_text,
            '{labels_json}',
            map('version', '2.1', 'instructions', '{instructions}')
        ) AS classification
    FROM criteria
    ORDER BY idx
    """
    rows = _run_sql(sql, timeout=60)

    results = ["other"] * len(criterion_texts)
    for row in rows:
        idx = int(row.get("idx", 0))
        raw = row.get("classification", {})
        try:
            if isinstance(raw, str):
                raw = json.loads(raw)
            responses = raw.get("response", [])
            if responses:
                results[idx] = responses[0].get("value", "other")
        except (json.JSONDecodeError, AttributeError, IndexError):
            pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# ai_query (with responseFormat)
# ─────────────────────────────────────────────────────────────────────────────

def ai_query(
    endpoint: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    response_format: Optional[str] = None,
    max_tokens: int = 8000,
) -> Optional[str]:
    """
    Call a Databricks Model Serving endpoint via ai_query SQL function.

    When system_prompt is provided the call uses the messages-array form so
    the system role is sent correctly (Claude respects it for tone + format).

    Args:
        endpoint:        Endpoint name, e.g. 'databricks-claude-opus-5'
        prompt:          User-role prompt string
        system_prompt:   Optional system-role instruction
        response_format: Optional STRUCT schema string for structured output
        max_tokens:      Max response tokens

    Returns:
        Response text (string), or None on failure.
    """
    p_esc = prompt.replace("'", "\\'")[:50_000]

    if system_prompt:
        # Prepend system instructions into the single prompt string —
        # compatible with all warehouse DBR versions (no named_struct/array needed)
        s_esc = system_prompt.replace("'", "\\'")[:15_000]
        combined = f"{s_esc}\\n\\n---\\n\\n{p_esc}"
        sql = f"""
        SELECT ai_query(
            '{endpoint}',
            '{combined}',
            modelParameters => named_struct('max_tokens', {max_tokens})
        ) AS response
        """
    elif response_format:
        sql = f"""
        SELECT ai_query(
            '{endpoint}',
            '{p_esc}',
            responseFormat => '{response_format}',
            modelParameters => named_struct('max_tokens', {max_tokens})
        ) AS response
        """
    else:
        sql = f"""
        SELECT ai_query(
            '{endpoint}',
            '{p_esc}',
            modelParameters => named_struct('max_tokens', {max_tokens})
        ) AS response
        """

    rows = _run_sql(sql, timeout=120)
    raw  = _first_cell(rows, "response")

    # ai_query may return a STRUCT-like dict with a 'content' key
    if isinstance(raw, dict):
        return raw.get("content") or raw.get("text") or json.dumps(raw)
    return raw


# ─────────────────────────────────────────────────────────────────────────────
# ai_summarize
# ─────────────────────────────────────────────────────────────────────────────

def ai_summarize(text: str, max_words: int = 150) -> Optional[str]:
    """
    Summarize protocol text using ai_summarize.
    Returns a short summary for display in the UI.
    """
    text_escaped = text.replace("'", "\\'")[:20_000]
    sql = f"SELECT ai_summarize('{text_escaped}', {max_words}) AS summary"
    rows = _run_sql(sql, timeout=30)
    return _first_cell(rows, "summary")


# ─────────────────────────────────────────────────────────────────────────────
# ai_gen
# ─────────────────────────────────────────────────────────────────────────────

def ai_gen(prompt: str) -> Optional[str]:
    """General-purpose text generation via ai_gen."""
    prompt_escaped = prompt.replace("'", "\\'")[:10_000]
    sql = f"SELECT ai_gen('{prompt_escaped}') AS result"
    rows = _run_sql(sql, timeout=30)
    return _first_cell(rows, "result")
