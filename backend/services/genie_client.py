"""
genie_client.py — Databricks Genie MCP bridge.

Calls the Genie One MCP Server tools programmatically:
  genie_ask             → start a conversation, send criteria prompt
  genie_poll_response   → wait until Genie finishes generating SQL
  genie_get_query_result→ retrieve the SQL text + result rows

MCP endpoint: https://<host>/api/2.0/mcp/genie
Auth:         Bearer token (same DATABRICKS_TOKEN used everywhere)

The output is identical to typing the same prompt in the Genie UI —
same space, same data connection, same model, same instructions.
"""
import json
import logging
import time
from typing import Optional

import requests

from backend.config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Genie Space ID — from the room URL:
# /genie/rooms/01f1ad05e9a811de88b3f1c49399c3c1/chats/...
GENIE_SPACE_ID = "01f1ad05e9a811de88b3f1c49399c3c1"

MCP_URL        = f"{settings.databricks_host}/api/2.0/mcp/genie"
GENIE_BASE_URL = f"{settings.databricks_host}/api/2.0/genie/spaces/{GENIE_SPACE_ID}"

POLL_INTERVAL_SEC = 3
MAX_WAIT_SEC      = 300   # 5 minutes max


# ─────────────────────────────────────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.databricks_token}",
        "Content-Type":  "application/json",
    }


def _mcp_call(tool: str, arguments: dict) -> dict:
    """
    Call a Genie MCP tool via JSON-RPC 2.0.
    Returns the parsed result dict or raises on failure.
    """
    payload = {
        "jsonrpc": "2.0",
        "id":      1,
        "method":  "tools/call",
        "params":  {
            "name":      tool,
            "arguments": arguments,
        },
    }
    resp = requests.post(MCP_URL, headers=_headers(), json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"MCP error from {tool}: {data['error']}")

    # result.content is a list of content blocks; text block holds the payload
    content_blocks = data.get("result", {}).get("content", [])
    for block in content_blocks:
        if block.get("type") == "text":
            try:
                return json.loads(block["text"])
            except json.JSONDecodeError:
                return {"raw": block["text"]}
    return data.get("result", {})


# ─────────────────────────────────────────────────────────────────────────────
# Genie REST helpers (direct API — more reliable for polling)
# ─────────────────────────────────────────────────────────────────────────────

def _genie_post(path: str, body: dict) -> dict:
    url  = f"{GENIE_BASE_URL}{path}"
    resp = requests.post(url, headers=_headers(), json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _genie_get(path: str) -> dict:
    url  = f"{GENIE_BASE_URL}{path}"
    resp = requests.get(url, headers=_headers(), timeout=60)
    resp.raise_for_status()
    return resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def genie_ask(prompt: str, conversation_id: str = "") -> dict:
    """
    Send a prompt to Genie (starts a new conversation or continues one).

    Returns:
        {
          "conversation_id": "...",
          "message_id": "...",
          "status": "EXECUTING_QUERY" | "COMPLETED" | ...
        }
    """
    if conversation_id:
        # Continue existing conversation
        body = {"content": prompt}
        data = _genie_post(f"/conversations/{conversation_id}/messages", body)
    else:
        # Start a brand-new conversation
        body = {"content": prompt}
        data = _genie_post("/start-conversation", body)

    return {
        "conversation_id": data.get("conversation_id", conversation_id),
        "message_id":      data.get("message_id") or data.get("id", ""),
        "status":          data.get("status", "PENDING"),
    }


def genie_poll_response(conversation_id: str, message_id: str) -> dict:
    """
    Poll until Genie finishes generating SQL.
    Blocks for up to MAX_WAIT_SEC seconds.

    Returns the final message dict when status == COMPLETED.
    Raises TimeoutError if Genie takes too long.
    """
    waited = 0
    while waited < MAX_WAIT_SEC:
        data   = _genie_get(f"/conversations/{conversation_id}/messages/{message_id}")
        status = data.get("status", "PENDING")
        logger.info("Genie status: %s (waited %ds)", status, waited)

        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            if status != "COMPLETED":
                raise RuntimeError(f"Genie response ended with status: {status}")
            return data

        time.sleep(POLL_INTERVAL_SEC)
        waited += POLL_INTERVAL_SEC

    raise TimeoutError(f"Genie did not respond within {MAX_WAIT_SEC}s.")


def genie_get_sql(conversation_id: str, message_id: str) -> Optional[str]:
    """
    Retrieve the SQL that Genie generated for the given message.

    Returns the SQL string, or None if Genie produced no query
    (e.g. it answered in plain text without running SQL).
    """
    try:
        data = _genie_get(
            f"/conversations/{conversation_id}/messages/{message_id}/query-result"
        )
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None   # Genie answered in text, no SQL query
        raise

    # statement_response holds the executed SQL
    stmt = data.get("statement_response", {})
    sql  = stmt.get("statement", "")
    return sql.strip() or None


def genie_get_rows(conversation_id: str, message_id: str) -> tuple[list, list]:
    """
    Retrieve the result rows Genie fetched.

    Returns:
        columns: list of column name strings
        rows:    list of row dicts
    """
    try:
        data = _genie_get(
            f"/conversations/{conversation_id}/messages/{message_id}/query-result"
        )
    except requests.HTTPError:
        return [], []

    stmt    = data.get("statement_response", {})
    manifest = stmt.get("manifest", {})
    columns  = [
        c["name"]
        for c in manifest.get("schema", {}).get("columns", [])
    ]
    raw_rows = stmt.get("result", {}).get("data_array", [])
    rows     = [dict(zip(columns, row)) for row in raw_rows]
    return columns, rows


# ─────────────────────────────────────────────────────────────────────────────
# High-level: ask Genie → wait → return SQL + summary text
# ─────────────────────────────────────────────────────────────────────────────

def ask_genie_for_attrition(
    title: str,
    inclusion_criteria: list[str],
    exclusion_criteria: list[str],
    code_lists: list[dict] | None = None,
    study_window: str = "",
) -> dict:
    """
    Full round-trip: format criteria → ask Genie → poll → return SQL.

    Args:
        title:               Study title
        inclusion_criteria:  List of inclusion criterion descriptions
        exclusion_criteria:  List of exclusion criterion descriptions
        code_lists:          List of {"condition", "coding_system", "codes": [...]} dicts
        study_window:        Study date range string

    Returns:
        {
          "sql":             "<full SQL Genie generated>",
          "conversation_id": "...",
          "message_id":      "...",
          "columns":         [...],
          "rows":            [...],
          "summary":         "<Genie's explanation text>",
        }
    """
    prompt = _build_attrition_prompt(
        title, inclusion_criteria, exclusion_criteria, code_lists, study_window
    )
    logger.info("Sending attrition prompt to Genie (%d chars)", len(prompt))

    # Step 1: Ask
    ask_result = genie_ask(prompt)
    conv_id    = ask_result["conversation_id"]
    msg_id     = ask_result["message_id"]
    logger.info("Genie conversation started: conv=%s msg=%s", conv_id, msg_id)

    # Step 2: Poll
    final_msg  = genie_poll_response(conv_id, msg_id)
    summary    = _extract_summary_text(final_msg)

    # Step 3: Get SQL
    sql     = genie_get_sql(conv_id, msg_id)
    columns, rows = genie_get_rows(conv_id, msg_id)

    return {
        "sql":             sql or "",
        "conversation_id": conv_id,
        "message_id":      msg_id,
        "columns":         columns,
        "rows":            rows,
        "summary":         summary,
        "genie_url": (
            f"{settings.databricks_host}/genie/rooms/{GENIE_SPACE_ID}"
            f"/chats/{conv_id}"
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_attrition_prompt(
    title: str,
    inclusion_criteria: list[str],
    exclusion_criteria: list[str],
    code_lists: list[dict] | None,
    study_window: str,
) -> str:
    lines = [
        f"Cohort Attrition SQL for: {title}",
        "",
    ]

    if study_window:
        lines += [f"Study window: {study_window}", ""]

    lines += ["Inclusion Criteria:"]
    for i, c in enumerate(inclusion_criteria, 1):
        lines.append(f"  {i}. {c}")

    lines += ["", "Exclusion Criteria:"]
    for i, c in enumerate(exclusion_criteria, 1):
        lines.append(f"  {i}. {c}")

    if code_lists:
        lines += ["", "Procedure / Diagnosis Code Lists:"]
        for cl in code_lists:
            cond   = cl.get("condition", "")
            sys    = cl.get("coding_system", "")
            codes  = cl.get("codes", [])
            code_strs = [
                (c["code"] if isinstance(c, dict) else str(c))
                for c in codes
            ]
            lines.append(f"  {cond} ({sys}): {', '.join(code_strs[:30])}")
            if len(code_strs) > 30:
                lines.append(f"    ... and {len(code_strs) - 30} more codes")

    lines += [
        "",
        "Please generate the full step-by-step attrition SQL pipeline.",
        "Show patient count at each step.",
        "Use the procedure/diagnosis codes listed above.",
        "Return only SQL — one CREATE OR REPLACE TEMPORARY TABLE per step.",
    ]

    return "\n".join(lines)


def _extract_summary_text(message: dict) -> str:
    """Pull the human-readable explanation from Genie's message."""
    # Genie messages have an 'attachments' list with type=text for explanations
    for att in message.get("attachments", []):
        if att.get("type") == "text":
            return att.get("content", "")
    # Fallback: top-level content field
    return message.get("content", "")
