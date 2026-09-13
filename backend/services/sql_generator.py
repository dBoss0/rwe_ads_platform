"""
SQL generation service.
Carried over from ads_automation/model_serving.py and hardened.

Generates Databricks SQL for each attrition step via Claude (Model Serving).
Falls back to a deterministic template if LLM call fails or is not configured.
"""
import logging
import requests
from typing import Dict, List, Optional

from backend.config import settings
from backend.prompts.sql_system_prompt import SQL_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# LLM caller
# ─────────────────────────────────────────────────────────────────────────────

def _call_llm(user_message: str, max_tokens: int = 8000) -> str:
    payload = {
        "messages": [
            {"role": "system", "content": SQL_SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        "max_tokens": max_tokens,
    }
    resp = requests.post(
        settings.claude_endpoint_url,
        headers={
            "Authorization": f"Bearer {settings.databricks_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "\n".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return content.strip()


def _clean_sql(raw: str) -> str:
    """Strip accidental markdown fences."""
    if "```" in raw:
        lines = [l for l in raw.splitlines() if not l.strip().startswith("```")]
        return "\n".join(lines).strip()
    return raw


# ─────────────────────────────────────────────────────────────────────────────
# Completeness validators
# ─────────────────────────────────────────────────────────────────────────────

def _is_step_complete(sql: str, step_num: int) -> bool:
    s = sql.upper()
    if not sql.rstrip().endswith(";"):
        return False
    if "CREATE OR REPLACE TEMPORARY TABLE" not in s:
        return False
    if step_num == 1:
        return all(r in s for r in ["ALL_MATCHES", "RANKED", "WHERE RN = 1", "COUNT(*)"])
    return "COUNT(*)" in s


def _is_waterfall_complete(sql: str) -> bool:
    s = sql.upper()
    return (
        sql.rstrip().endswith(";")
        and "WITH COUNTS AS" in s
        and "LAG(" in s
        and "ENC_DROPPED" in s
        and "PTS_DROPPED" in s
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 structured prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_step1_prompt(
    description: str,
    target_table: str,
    code_table_mapping: Dict,
    study_window: str,
) -> str:
    icd_entries, cpt_entries, diag_entries = [], [], []
    for cond, type_map in code_table_mapping.items():
        for sys_type, tables in type_map.items():
            for tbl in tables:
                if sys_type == "icd_proc":
                    icd_entries.append((cond, tbl))
                elif sys_type == "cpt":
                    cpt_entries.append((cond, tbl))
                elif sys_type == "icd_diag":
                    diag_entries.append((cond, tbl))

    def _alias(i, prefix):
        return f"{prefix}{i:02d}"

    win_filter = (
        f"WHERE p.admit_date BETWEEN '{study_window.split(' to ')[0]}' AND '{study_window.split(' to ')[1]}'"
        if " to " in study_window
        else "-- TODO: Add study window date filter"
    )

    icd_lines = "\n".join(f"  {_alias(i,'i')} → {tbl}  (condition='{cond}')" for i,(cond,tbl) in enumerate(icd_entries))
    cpt_lines = "\n".join(f"  {_alias(i,'c')} → {tbl}  (condition='{cond}')" for i,(cond,tbl) in enumerate(cpt_entries))

    parts = []
    if icd_entries:
        parts.append(f"ICD-10 PCS PROCEDURE TABLES:\n{icd_lines}")
    if cpt_entries:
        parts.append(f"CPT-4 TABLES:\n{cpt_lines}")

    union_parts = []
    if icd_entries:
        union_parts.append("    SELECT pat_key, surgery_category FROM icd_proc_match")
    if cpt_entries:
        union_parts.append("    SELECT pat_key, surgery_category FROM cpt_match")
    if diag_entries:
        union_parts.append("    SELECT pat_key, surgery_category FROM icd_diag_match")
    union_sql = "\n    UNION\n".join(union_parts)

    return f"""Generate the COMPLETE Step 1 SQL.

Target table : {target_table}
Description  : {description}
Study window : {study_window or 'not specified'}

{chr(10).join(parts)}

Required 4-CTE chain:
1. icd_proc_match  (from paticd_proc, icd_version=10, icd_pri_sec='P')
2. cpt_match       (from patcpt)
3. all_matches AS ({union_sql})
4. ranked AS (ROW_NUMBER OVER PARTITION BY medrec_key, surgery_category ORDER BY admit_date ASC, pat_key ASC)

Final SELECT: WHERE rn = 1
{win_filter}

End with:
SELECT surgery_category, COUNT(*) AS index_admissions, COUNT(DISTINCT medrec_key) AS unique_patients
FROM {target_table} GROUP BY surgery_category ORDER BY surgery_category;

Output COMPLETE SQL only. Do not truncate."""


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_step_sql(
    step_num: int,
    step_type: str,
    description: str,
    prev_table: str,
    target_table: str,
    code_table_mapping: Optional[Dict] = None,
    code_table_names: Optional[List[str]] = None,
    study_window: str = "",
) -> tuple[str, str]:
    """
    Generate SQL for a single attrition step.

    Returns: (sql_string, generated_by) where generated_by is 'llm' or 'fallback'
    """
    if not settings.databricks_token:
        return _fallback_sql(target_table, description, step_type, step_num, prev_table), "fallback"

    label = "INCLUSION" if step_type == "inclusion" else "EXCLUSION"
    max_tok = 16000 if step_num == 1 else 4000

    try:
        if step_num == 1 and code_table_mapping:
            prompt = _build_step1_prompt(description, target_table, code_table_mapping, study_window)
        else:
            tables_info = "\n".join(f"  - {t}" for t in (code_table_names or [])) or "  (none)"
            win_line = f"Study window: {study_window}" if study_window else ""
            prompt = f"""Generate SQL for this attrition step.

Step number  : {step_num}
Step type    : {label}
Description  : {description}
Source table : {prev_table}
Target table : {target_table}
{win_line}

Code list temp tables available:
{tables_info}

Requirements:
- Banner comment with ════ border
- CREATE OR REPLACE TEMPORARY TABLE {target_table} AS SELECT * FROM {prev_table} WHERE <condition>
- Appropriate count check SELECT at the end
- Return ONLY the complete SQL"""

        sql = _clean_sql(_call_llm(prompt, max_tokens=max_tok))

        if not _is_step_complete(sql, step_num):
            retry = f"Your previous response was incomplete. Generate the COMPLETE SQL again.\n\n{prompt}"
            sql = _clean_sql(_call_llm(retry, max_tokens=max_tok))

        if _is_step_complete(sql, step_num):
            return sql, "llm"

    except Exception as e:
        logger.error("LLM step SQL generation failed for step %d: %s", step_num, e)

    return _fallback_sql(target_table, description, step_type, step_num, prev_table), "fallback"


def generate_waterfall_sql(step_records: List[tuple]) -> str:
    """
    Generate the attrition waterfall CTE SQL.
    Always uses the deterministic Python generator (LLM unreliable for this template).
    """
    return _python_waterfall(step_records)


def generate_final_summary_sql(last_table: str) -> str:
    """Generate the final cohort summary SQL."""
    return _python_final_summary(last_table)


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic fallbacks
# ─────────────────────────────────────────────────────────────────────────────

def _fallback_sql(
    target_table: str,
    description: str,
    step_type: str,
    step_num: int,
    prev_table: str,
) -> str:
    label = "INCLUSION" if step_type == "inclusion" else "EXCLUSION"
    return (
        f"-- ════════════════════════════════════════════════════════════════════════════\n"
        f"-- STEP {step_num} ({label}) — {description}\n"
        f"-- TODO: LLM not configured — implement filter manually\n"
        f"-- ════════════════════════════════════════════════════════════════════════════\n\n"
        f"CREATE OR REPLACE TEMPORARY TABLE {target_table} AS\n"
        f"SELECT * FROM {prev_table or 'rhealth_premier_phd.bronze_native_premier_phd.pat'}\n"
        f"WHERE 1=1;  -- TODO: add filter for: {description}\n\n"
        f"SELECT COUNT(*) AS index_admissions, COUNT(DISTINCT medrec_key) AS unique_patients\n"
        f"FROM {target_table};"
    )


def _python_waterfall(step_records: List[tuple]) -> str:
    def _esc(s):
        return str(s).replace("'", "''")

    rows = []
    for i, (n, stype, desc, tbl) in enumerate(step_records):
        label = "EXC" if str(stype).lower() != "inclusion" else "INC"
        prefix = "EXCLUDE: " if label == "EXC" else ""
        safe_desc = _esc(f"{n}. {prefix}{str(desc)[:70]}")
        if i == 0:
            rows.append(
                f"    SELECT {n} AS n, '{label}' AS type,\n"
                f"           '{safe_desc}' AS step,\n"
                f"           COUNT(*) AS enc, COUNT(DISTINCT medrec_key) AS pts\n"
                f"    FROM {tbl}"
            )
        else:
            rows.append(
                f"    SELECT {n}, '{label}', '{safe_desc}',\n"
                f"           COUNT(*), COUNT(DISTINCT medrec_key)\n"
                f"    FROM {tbl}"
            )

    union_all = "\n\n    UNION ALL\n".join(rows)
    return (
        f"-- ════════════════════════════════════════════════════════════════════════════\n"
        f"-- ATTRITION WATERFALL\n"
        f"-- enc_dropped / pts_dropped = difference vs previous step\n"
        f"-- ════════════════════════════════════════════════════════════════════════════\n\n"
        f"WITH counts AS (\n\n{union_all}\n\n)\n\n"
        f"SELECT\n"
        f"    n                                        AS step_num,\n"
        f"    type                                     AS step_type,\n"
        f"    step                                     AS step_description,\n"
        f"    enc                                      AS enc_after,\n"
        f"    pts                                      AS pts_after,\n"
        f"    LAG(enc) OVER (ORDER BY n) - enc         AS enc_dropped,\n"
        f"    LAG(pts) OVER (ORDER BY n) - pts         AS pts_dropped\n"
        f"FROM counts\n"
        f"ORDER BY n;"
    )


def _python_final_summary(last_table: str) -> str:
    return (
        f"-- ════════════════════════════════════════════════════════════════════════════\n"
        f"-- FINAL COHORT SUMMARY\n"
        f"-- ════════════════════════════════════════════════════════════════════════════\n\n"
        f"SELECT\n"
        f"    surgery_category,\n"
        f"    COUNT(*)                                             AS index_admissions,\n"
        f"    COUNT(DISTINCT medrec_key)                           AS unique_patients,\n"
        f"    COUNT(DISTINCT prov_id)                              AS hospitals,\n"
        f"    ROUND(AVG(age),          1)                          AS mean_age,\n"
        f"    SUM(CASE WHEN gender  = 'F' THEN 1 ELSE 0 END)       AS female_n,\n"
        f"    SUM(CASE WHEN gender  = 'M' THEN 1 ELSE 0 END)       AS male_n,\n"
        f"    SUM(CASE WHEN i_o_ind = 'I' THEN 1 ELSE 0 END)       AS inpatient_n,\n"
        f"    SUM(CASE WHEN i_o_ind = 'O' THEN 1 ELSE 0 END)       AS outpatient_n,\n"
        f"    ROUND(AVG(los),          1)                          AS mean_los_days,\n"
        f"    ROUND(AVG(pat_cost),     0)                          AS mean_total_cost_usd,\n"
        f"    ROUND(AVG(pat_fix_cost), 0)                          AS mean_room_board_cost_usd,\n"
        f"    ROUND(AVG(pat_var_cost), 0)                          AS mean_variable_cost_usd,\n"
        f"    ROUND(AVG(pat_charges),  0)                          AS mean_billed_charges_usd\n"
        f"FROM {last_table}\n"
        f"GROUP BY surgery_category\n"
        f"ORDER BY surgery_category;"
    )
