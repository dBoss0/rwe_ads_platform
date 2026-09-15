"""
Protocol Parser — LLM-based, universal, full AI Functions stack.

Parse pipeline (Databricks mode):
  Stage 1  ai_parse_document     → extract text from PDF/DOCX/PPT (binary READ_FILES)
  Stage 2  ai_extract v2.1       → pull title, study_window, data_sources
  Stage 3  ai_query (Claude)     → extract inclusion + exclusion criteria as JSON
  Stage 4  ai_classify v2.1      → classify each criterion by PHD table type (batch)
  Stage 5  ai_summarize          → short protocol summary for UI

Parse pipeline (REST/local dev mode):
  Stage 1  python-docx           → extract text from DOCX
  Stage 3  REST → Claude endpoint → same structured JSON extraction
  (Stages 2, 4, 5 skipped — no Databricks SQL available locally)

NO hardcoded stop words. NO fixed section headings.
Works for any protocol format, any section naming convention.
"""
import json
import re
import logging
from pathlib import Path
from typing import Optional

import requests

from backend.config import settings
from backend.models.protocol import ParseResponse, AttritionStep
from backend.prompts.sql_system_prompt import PARSER_SYSTEM_PROMPT

# AI Functions — used in Databricks mode
from backend.services.ai_functions import (
    ai_parse_document,
    extract_text_from_parsed_doc,
    ai_extract,
    ai_classify_batch,
    ai_summarize,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 extraction schema (ai_extract v2.1)
# ─────────────────────────────────────────────────────────────────────────────

_EXTRACT_SCHEMA = {
    "title": {
        "type": "string",
        "description": "Full clinical study or research project title",
    },
    "study_window": {
        "type": "string",
        "description": "Study date range, e.g. 'January 2018 to December 2022' or '2018-2022'",
    },
    "data_source": {
        "type": "string",
        "description": "Database name used, e.g. Premier Healthcare Database, Optum, IBM Marketscan",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def parse_protocol(
    volume_path: Optional[str] = None,
    raw_text: Optional[str] = None,
    local_file_path: Optional[str] = None,
) -> ParseResponse:
    """
    Parse a clinical protocol and return structured attrition steps.

    Args:
        volume_path:     UC Volume path — used in Databricks (full AI pipeline).
        raw_text:        Pasted protocol text — skips document extraction.
        local_file_path: Local DOCX path — for dev/local mode only.

    Returns:
        ParseResponse with all steps structured, typed, and classified.
    """
    warnings: list[str] = []
    parse_method = "llm_rest"
    protocol_text = ""
    summary = ""

    # ── Stage 1: Extract text ─────────────────────────────────────────────────
    if raw_text:
        protocol_text = raw_text.strip()
        parse_method = "llm_rest_text"

    elif volume_path and settings.is_databricks_app:
        parse_method = "llm_databricks"
        parsed_doc = ai_parse_document(volume_path)
        if parsed_doc:
            protocol_text = extract_text_from_parsed_doc(parsed_doc)
        if not protocol_text:
            warnings.append(
                f"ai_parse_document returned empty content for: {volume_path}. "
                "Verify the volume path and file format (PDF, DOCX, PPT supported)."
            )

    elif local_file_path:
        parse_method = "llm_rest_local"
        protocol_text = _local_extract_docx(local_file_path)
        warnings.append("Local file extraction (dev mode — limited to DOCX only).")

    else:
        raise ValueError(
            "Provide one of: volume_path (Databricks), raw_text, or local_file_path."
        )

    if not protocol_text:
        return _empty_response(["No text could be extracted from the protocol."])

    # ── Stage 2: Structured field extraction (Databricks only) ───────────────
    extracted_fields: dict = {}
    if parse_method == "llm_databricks":
        extracted_fields = ai_extract(protocol_text, _EXTRACT_SCHEMA) or {}

    # ── Stage 3: LLM criteria extraction (all modes) ─────────────────────────
    llm_result = _call_llm_parser(protocol_text)
    if not llm_result:
        warnings.append(
            "LLM parser returned no result. Check Model Serving endpoint configuration."
        )
        return _empty_response(warnings)

    # ── Stage 4: Batch classify criterion types (Databricks only) ────────────
    all_criteria = (
        llm_result.get("inclusion_criteria", [])
        + llm_result.get("exclusion_criteria", [])
    )
    if parse_method == "llm_databricks" and all_criteria:
        texts = [c.get("description", "") for c in all_criteria]
        classified_types = ai_classify_batch(texts)
        for c, ctype in zip(all_criteria, classified_types):
            # Override LLM's criterion_type with ai_classify result if available
            if ctype != "other":
                c["criterion_type"] = ctype

    # ── Stage 5: Summarize (Databricks only, non-blocking) ───────────────────
    if parse_method == "llm_databricks":
        try:
            summary = ai_summarize(protocol_text[:10_000], max_words=80) or ""
        except Exception:
            pass  # Summary is nice-to-have; don't fail the parse

    # ── Build response ────────────────────────────────────────────────────────
    # Merge ai_extract results into LLM result (prefer ai_extract for title/window)
    if extracted_fields.get("title"):
        llm_result["title"] = extracted_fields["title"]
    if extracted_fields.get("study_window"):
        llm_result["study_window"] = extracted_fields["study_window"]
    if extracted_fields.get("data_source") and not llm_result.get("data_sources"):
        llm_result["data_sources"] = [extracted_fields["data_source"]]

    return _build_response(llm_result, parse_method, warnings, summary)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Local text extraction (dev fallback — stdlib only, no python-docx)
# ─────────────────────────────────────────────────────────────────────────────

_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W = f"{{{_WORD_NS}}}"


def _local_extract_docx(file_path: str) -> str:
    """
    Extract plain text from a .docx or .pdf file without external dependencies.

    .docx  → unzip + parse word/document.xml with stdlib xml.etree.ElementTree.
             Handles paragraphs, headings, and table cells.
    .pdf   → not supported locally; user is prompted to paste text instead.
    """
    import zipfile
    from xml.etree import ElementTree as ET

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Protocol file not found: {path}")

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        raise ValueError(
            "PDF parsing requires Databricks deployment (ai_parse_document). "
            "Please paste the protocol text in the 'Paste Text' tab instead."
        )

    if suffix != ".docx":
        raise ValueError(
            f"Unsupported file type '{suffix}'. Upload a .docx file or use the Paste Text tab."
        )

    # ── Read word/document.xml from the ZIP ───────────────────────────────────
    lines: list[str] = []
    try:
        with zipfile.ZipFile(str(path), "r") as zf:
            xml_bytes = zf.read("word/document.xml")
    except KeyError:
        raise ValueError("Invalid .docx file — word/document.xml not found inside the archive.")

    root = ET.fromstring(xml_bytes)

    # Paragraphs (covers body text, headings, list items)
    for para in root.iter(f"{_W}p"):
        text = "".join(
            node.text or ""
            for node in para.iter(f"{_W}t")
        ).strip()
        if text:
            lines.append(text)

    # Table cells (inclusion/exclusion criteria are often in Word tables)
    for cell in root.iter(f"{_W}tc"):
        cell_lines: list[str] = []
        for para in cell.iter(f"{_W}p"):
            text = "".join(
                node.text or ""
                for node in para.iter(f"{_W}t")
            ).strip()
            if text:
                cell_lines.append(text)
        combined = " ".join(cell_lines).strip()
        if combined and combined not in lines:
            lines.append(combined)

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: LLM criteria extraction via REST
# ─────────────────────────────────────────────────────────────────────────────

def _call_llm_parser(protocol_text: str) -> Optional[dict]:
    """
    Call Claude via Model Serving REST API to extract structured criteria.
    Used in all parse modes (Databricks + local).
    """
    user_message = (
        "Extract ALL inclusion and exclusion criteria from the following clinical "
        "study protocol. Return ONLY valid JSON — no explanation, no markdown.\n\n"
        f"PROTOCOL TEXT:\n{protocol_text[:60_000]}"
    )

    payload = {
        "messages": [
            {"role": "system", "content": PARSER_SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        "max_tokens": 8000,
    }

    try:
        resp = requests.post(
            settings.claude_endpoint_url,
            headers={
                "Authorization": f"Bearer {settings.databricks_token}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Handle Databricks content-block format
        if isinstance(content, list):
            content = "\n".join(
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        return _extract_json(content.strip())

    except Exception as e:
        logger.error("LLM parser call failed: %s", e)
        return None


def _extract_json(raw: str) -> Optional[dict]:
    """Strip markdown fences and parse JSON from LLM response."""
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw.strip())
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    logger.error("Could not parse JSON from LLM: %s", raw[:300])
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Response builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_response(
    llm: dict,
    parse_method: str,
    warnings: list,
    summary: str = "",
) -> ParseResponse:
    inc_raw = llm.get("inclusion_criteria", [])
    exc_raw = llm.get("exclusion_criteria", [])

    inclusion_steps = [
        AttritionStep(
            step_num=i + 1,
            step_type="inclusion",
            description=c.get("description", ""),
            criterion_type=c.get("criterion_type", "other"),
            raw_text=c.get("raw_text", ""),
        )
        for i, c in enumerate(inc_raw)
    ]

    offset = len(inclusion_steps)
    exclusion_steps = [
        AttritionStep(
            step_num=offset + i + 1,
            step_type="exclusion",
            description=c.get("description", ""),
            criterion_type=c.get("criterion_type", "other"),
            raw_text=c.get("raw_text", ""),
        )
        for i, c in enumerate(exc_raw)
    ]

    warnings.extend(llm.get("warnings", []))

    return ParseResponse(
        title=llm.get("title", "Unknown Study"),
        data_sources=llm.get("data_sources", []),
        study_window=llm.get("study_window", ""),
        inclusion_steps=inclusion_steps,
        exclusion_steps=exclusion_steps,
        all_steps=inclusion_steps + exclusion_steps,
        parse_method=parse_method,
        warnings=warnings,
    )


def _empty_response(warnings: list) -> ParseResponse:
    return ParseResponse(
        title="Unknown Study",
        data_sources=[],
        inclusion_steps=[],
        exclusion_steps=[],
        all_steps=[],
        parse_method="error",
        warnings=warnings,
    )
