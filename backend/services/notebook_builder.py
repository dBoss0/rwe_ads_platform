"""
Notebook builder service.
Carried over and cleaned up from ads_automation/notebook_generator.py.

Generates a Databricks SOURCE-format SQL notebook from structured attrition steps.
Temporary tables are session-scoped (CREATE OR REPLACE TEMPORARY TABLE).
"""
import re
from typing import List, Optional, Tuple, Dict
import pandas as pd

from backend.config import settings
from backend.models.attrition import StepInput, CodeList, StepSQL
from backend.services.sql_generator import (
    generate_step_sql,
    generate_waterfall_sql,
    generate_final_summary_sql,
)

CELL_SEP = "\n-- COMMAND ----------\n"
HEADER   = "-- Databricks notebook source"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_STOP = {
    "the","a","an","is","are","of","for","or","and","at","as",
    "to","in","with","by","on","per","from","be","that","this",
    "have","has","been","such","its","it","not","do","does",
}

_SHORT_NAMES = [
    (["age", "18"],            "age_18_plus"),
    (["age", "21"],            "age_21_plus"),
    (["age", "65"],            "age_65_plus"),
    (["90",  "hospital"],      "hosp_90d"),
    (["90",  "contribut"],     "hosp_90d"),
    (["180", "contribut"],     "hosp_180d"),
    (["gender"],               "known_gender"),
    (["sex"],                  "known_gender"),
    (["publish", "cv"],        "publish_cv"),
    (["comparative", "valid"], "publish_cv"),
    (["cost", "zero"],         "positive_cost"),
    (["cost", "negative"],     "positive_cost"),
    (["missing"],              "complete_data"),
    (["inpatient"],            "inpatient_only"),
    (["outpatient"],           "outpatient_only"),
    (["los"],                  "los_filter"),
    (["length", "stay"],       "los_filter"),
    (["drg"],                  "drg_filter"),
]


def _step_table_name(n: int, description: str) -> str:
    d = description.lower()
    for keywords, short_name in _SHORT_NAMES:
        if all(kw in d for kw in keywords):
            return f"step{n}_{short_name}"
    words = re.findall(r"[a-z]+", d)
    meaningful = [w for w in words if w not in _STOP and len(w) > 2][:3]
    slug = "_".join(meaningful)[:30].rstrip("_")
    return f"step{n}_{slug or 'filter'}"


def make_temp_table_name(condition: str, coding_system: str) -> str:
    c = re.sub(r"[^a-z0-9]+", "_", condition.lower()).strip("_")
    s = re.sub(r"[^a-z0-9]+", "_", coding_system.lower()).strip("_")
    return f"tmp__{c}__{s}"


def _md_cell(text: str) -> str:
    lines = text.strip().splitlines()
    return "\n".join(f"-- MAGIC {ln}" if ln.strip() else "-- MAGIC " for ln in lines)


def _esc(s: str) -> str:
    return s.replace("'", "''")


def _extract_study_window(description: str) -> str:
    years = re.findall(r"\b(20\d{2})\b", description)
    if len(years) >= 2:
        return f"{years[0]}-01-01 to {years[-1]}-12-31"
    return ""


def _codelist_sql(condition: str, coding_system: str, codes: list) -> str:
    tbl = make_temp_table_name(condition, coding_system)
    has_desc = any(c.description for c in codes)
    if has_desc:
        vals = ",\n  ".join(
            f"('{_esc(c.code)}', '{_esc(c.description or '')}')"
            for c in codes if c.code.strip()
        )
        schema = "AS t(code, description)"
    else:
        vals = ",\n  ".join(
            f"('{_esc(c.code)}')" for c in codes if c.code.strip()
        )
        schema = "AS t(code)"
    return (
        f"-- Condition: {condition} | System: {coding_system}\n"
        f"CREATE OR REPLACE TEMPORARY TABLE {tbl} AS\n"
        f"SELECT * FROM VALUES\n  {vals}\n{schema};\n\n"
        f"SELECT COUNT(*) AS codes FROM {tbl};"
    )


def _build_code_table_mapping(code_lists: List[CodeList]) -> Dict:
    mapping: Dict = {}
    for cl in code_lists:
        tbl  = make_temp_table_name(cl.condition, cl.coding_system)
        norm = cl.coding_system.upper().replace(" ", "-")
        if "PCS" in norm or ("ICD" in norm and "CM" not in norm):
            t = "icd_proc"
        elif "CM" in norm:
            t = "icd_diag"
        elif "CPT" in norm or "HCPCS" in norm:
            t = "cpt"
        elif "DRG" in norm:
            t = "drg"
        else:
            t = "other"
        mapping.setdefault(cl.condition, {}).setdefault(t, []).append(tbl)
    return mapping


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def build_notebook(
    title: str,
    steps: List[StepInput],
    code_lists: Optional[List[CodeList]] = None,
    study_window: str = "",
) -> Tuple[str, List[StepSQL]]:
    """
    Build a complete Databricks SQL notebook for the attrition waterfall.

    Returns:
        (notebook_source_sql, list_of_StepSQL)
    """
    cells: List[str] = []
    step_sqls: List[StepSQL] = []

    # ── Header ────────────────────────────────────────────────────────────────
    cells.append(_md_cell(
        f"%md\n"
        f"# {title}\n\n"
        f"**Attrition Cohort Notebook** | RWE ADS Automation Platform  \n"
        f"Data Source: Premier PHD (PINC AI™ Healthcare Database)  \n"
        f"Catalog: `{settings.phd_fqn}`\n\n"
        "---\n\n"
        "**Run All Cells** to execute the full attrition pipeline.  \n"
        "Each step reads from the previous step's temp table.  \n"
        "Counts are shown after every step."
    ))

    # ── Code list temp tables ─────────────────────────────────────────────────
    code_table_mapping: Dict = {}
    code_table_names: List[str] = []

    if code_lists:
        cells.append(_md_cell(
            "%md\n---\n## Code List Temp Tables\n"
            "One table per condition × coding system."
        ))
        for cl in code_lists:
            if cl.codes:
                cells.append(_codelist_sql(cl.condition, cl.coding_system, cl.codes))

        code_table_mapping = _build_code_table_mapping(code_lists)
        for cond_map in code_table_mapping.values():
            for tbls in cond_map.values():
                code_table_names.extend(tbls)

    # ── Attrition steps ───────────────────────────────────────────────────────
    cells.append(_md_cell(
        "%md\n---\n## Attrition Steps\n"
        "Inclusion criteria first, then exclusion. Each step filters from the prior cohort."
    ))

    # Sort: inclusion first, then exclusion (preserve order within each group)
    inc_steps = [s for s in steps if s.step_type == "inclusion"]
    exc_steps = [s for s in steps if s.step_type != "inclusion"]
    ordered_steps = inc_steps + exc_steps

    step_records: List[Tuple] = []
    prev_table = ""

    for idx, step in enumerate(ordered_steps):
        n    = idx + 1
        tbl  = "step1_surgery_index" if n == 1 else _step_table_name(n, step.description)
        win  = study_window or (_extract_study_window(step.description) if n == 1 else "")

        sql, generated_by = generate_step_sql(
            step_num=n,
            step_type=step.step_type,
            description=step.description,
            prev_table=prev_table,
            target_table=tbl,
            code_table_mapping=code_table_mapping if n == 1 else None,
            code_table_names=code_table_names,
            study_window=win,
        )

        label = "INC" if step.step_type == "inclusion" else "EXC"
        cells.append(_md_cell(
            f"%md\n---\n## STEP {n} ({label}) — {step.description}"
        ))
        cells.append(sql)

        step_sqls.append(StepSQL(
            step_num=n,
            step_type=step.step_type,
            description=step.description,
            target_table=tbl,
            sql=sql,
            generated_by=generated_by,
        ))
        step_records.append((n, step.step_type, step.description, tbl))
        prev_table = tbl

    # ── Waterfall ─────────────────────────────────────────────────────────────
    if step_records:
        cells.append(_md_cell(
            "%md\n---\n## Attrition Waterfall\n"
            "Encounters and patients retained at each step, with drop counts."
        ))
        cells.append(generate_waterfall_sql(step_records))

    # ── Final summary ─────────────────────────────────────────────────────────
    if prev_table:
        cells.append(_md_cell(
            "%md\n---\n## Final Cohort Summary\n"
            "Demographics, utilization, and cost."
        ))
        cells.append(generate_final_summary_sql(prev_table))

    notebook_sql = HEADER + "\n" + CELL_SEP.join(cells)
    return notebook_sql, step_sqls
