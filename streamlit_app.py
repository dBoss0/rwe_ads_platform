"""
streamlit_app.py  –  J&J MedTech  |  RWE ADS Automation Platform
Run:  streamlit run streamlit_app.py --server.port 8000 --server.address 0.0.0.0
"""

import re
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from backend.config import settings
from backend.services.parser import parse_protocol
from backend.services.notebook_builder import build_notebook, make_temp_table_name
from backend.services.databricks_client import (
    save_notebook, get_notebook_url, get_current_user, is_databricks_app,
)
from backend.models.attrition import StepInput, CodeList, CodeEntry


# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Code Automation | J&J MedTech",
    layout="wide",
    page_icon=None,
)
# ─────────────────────────────────────────────────────────────────────────────

_LOGO_WEB_URL = (
    "https://play-lh.googleusercontent.com/"
    "goJEGZ2I1rekFkK_Os2Hq6tgG_Iz07Wy6CyW2ti-Tn-j9_SiFVfAoQ6qKZKRJT-O_znd4tgvOgWK_8uHxWcBOQ"
)
_DBX_HOST = settings.databricks_host

JNJ_RED      = "#eb1700"
JNJ_MAROON   = "#9e0000"
JNJ_GRAY_01  = "#f5f4f2"
JNJ_GRAY_02  = "#eae8e5"
JNJ_GRAY_03  = "#d5cfc9"
JNJ_GRAY_05  = "#a39992"
JNJ_GRAY_06  = "#81766f"
JNJ_GRAY_08  = "#1a1410"
JNJ_BLUE_03  = "#0f68b2"
JNJ_GREEN_03 = "#328714"
JNJ_ORANGE   = "#ff6017"

CODING_SYSTEMS = [
    "ICD-9 CM", "ICD-9 PCS",
    "ICD-10 CM", "ICD-10 PCS",
    "CPT-4", "CPT-5",
    "HCPCS", "DRG", "NDC",
]
CODING_SYSTEM_STYLE = {
    "ICD-9 CM":   ("#7c3aed", "rgba(124,58,237,0.07)"),
    "ICD-9 PCS":  ("#6d28d9", "rgba(109,40,217,0.07)"),
    "ICD-10 CM":  ("#0f68b2", "rgba(15,104,178,0.08)"),
    "ICD-10 PCS": ("#1d4ed8", "rgba(29,78,216,0.08)"),
    "CPT-4":      ("#328714", "rgba(50,135,20,0.07)"),
    "CPT-5":      ("#15803d", "rgba(21,128,61,0.07)"),
    "HCPCS":      ("#0891b2", "rgba(8,145,178,0.07)"),
    "DRG":        ("#ea580c", "rgba(234,88,12,0.07)"),
    "NDC":        ("#eb1700", "rgba(235,23,0,0.07)"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def parse_codes_input(raw: str) -> list:
    parts = re.split(r"[\n,;\t]+", raw)
    return [p.strip().upper() for p in parts if p.strip()]


def guess_coding_system(sheet_name: str, sample_codes: list) -> str | None:
    n = sheet_name.lower()
    if "icd-10" in n or "icd10" in n:
        return "ICD-10 PCS" if "pcs" in n else "ICD-10 CM"
    if "icd-9" in n or "icd9" in n:
        return "ICD-9 PCS" if "pcs" in n else "ICD-9 CM"
    if "cpt" in n:  return "CPT-4"
    if "hcpcs" in n: return "HCPCS"
    if "drg" in n:  return "DRG"
    if "ndc" in n:  return "NDC"
    icd10_re = re.compile(r"^[A-Z]\d{2}", re.IGNORECASE)
    ndc_re   = re.compile(r"^\d{10,11}$")
    if sample_codes:
        n_codes = max(len(sample_codes), 1)
        if sum(1 for c in sample_codes if icd10_re.match(str(c))) / n_codes > 0.6:
            return "ICD-10 CM"
        if sum(1 for c in sample_codes if ndc_re.match(str(c))) / n_codes > 0.6:
            return "NDC"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Roboto+Mono:wght@400;500;600&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}
html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background-color: {JNJ_GRAY_01};
    color: {JNJ_GRAY_08};
    -webkit-font-smoothing: antialiased;
}}
.stApp {{ background-color: {JNJ_GRAY_01}; }}
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{ padding: 0 !important; max-width: 100% !important; }}
[data-testid="stAppViewContainer"] {{ padding: 0 clamp(0.75rem, 2.5vw, 2rem); }}

.jnj-inner {{
    width: 100%; max-width: min(1180px, 100%);
    margin-left: auto; margin-right: auto;
    padding-left: clamp(1rem, 3.5vw, 2.75rem);
    padding-right: clamp(1rem, 3.5vw, 2.75rem);
}}

/* NAV */
.jnj-nav {{
    background: #ffffff; border-bottom: 3px solid {JNJ_RED};
    position: sticky; top: 0; z-index: 999;
    box-shadow: 0 2px 16px rgba(0,0,0,0.07);
}}
.jnj-nav-inner {{
    display: flex; align-items: center; justify-content: space-between;
    padding-top: clamp(0.6rem,1.5vw,1rem); padding-bottom: clamp(0.6rem,1.5vw,1rem);
}}
.jnj-logo-wrap {{ display: flex; align-items: center; gap: clamp(10px,2vw,18px); flex-shrink: 0; }}
.jnj-logo-divider {{ width:1px; height:clamp(20px,3vw,30px); background:{JNJ_GRAY_03}; flex-shrink:0; }}
.jnj-logo-text {{ font-size:clamp(0.78rem,1.2vw,0.92rem); font-weight:700; color:{JNJ_GRAY_08}; letter-spacing:0.01em; line-height:1.2; }}
.jnj-logo-sub {{ font-size:clamp(0.55rem,0.8vw,0.65rem); font-weight:500; color:{JNJ_GRAY_05}; letter-spacing:0.06em; text-transform:uppercase; display:block; margin-top:2px; }}
.jnj-nav-right {{ display:flex; align-items:center; gap:clamp(0.75rem,2vw,2rem); flex-shrink:0; }}
.jnj-nav-tag {{ font-size:clamp(0.58rem,0.9vw,0.72rem); font-weight:600; letter-spacing:0.1em; text-transform:uppercase; color:{JNJ_GRAY_05}; }}
.jnj-nav-version {{ font-size:clamp(0.55rem,0.8vw,0.65rem); font-family:'Roboto Mono',monospace; color:{JNJ_GRAY_06}; background:{JNJ_GRAY_02}; padding:3px 10px; border-radius:100px; }}

/* HERO */
.jnj-hero {{
    background: linear-gradient(135deg,{JNJ_GRAY_08} 0%,#231c18 60%,#1a0f0a 100%);
    padding: clamp(2.5rem,6vw,5rem) 0 clamp(2rem,5vw,4rem) 0;
    position: relative; overflow: hidden;
}}
.jnj-hero::before {{ content:''; position:absolute; top:0; left:0; width:clamp(4px,0.5vw,7px); height:100%; background:linear-gradient(180deg,{JNJ_RED} 0%,{JNJ_MAROON} 100%); }}
.jnj-hero::after {{ content:''; position:absolute; inset:0; background-image:radial-gradient(circle,rgba(255,255,255,0.04) 1px,transparent 1px); background-size:28px 28px; pointer-events:none; }}
.jnj-hero-inner {{ position:relative; z-index:1; }}
.jnj-hero-eyebrow {{ font-size:clamp(0.55rem,1vw,0.68rem); font-weight:700; letter-spacing:0.28em; text-transform:uppercase; color:{JNJ_RED}; margin-bottom:clamp(0.6rem,1.5vw,1.1rem); }}
.jnj-hero-title {{ font-size:clamp(2.2rem,5.5vw,4.25rem); font-weight:900; color:#ffffff; line-height:1.03; letter-spacing:-0.04em; }}
.jnj-hero-title span {{ color:{JNJ_RED}; }}
.jnj-hero-stats {{ display:flex; gap:clamp(1.5rem,4vw,3rem); margin-top:clamp(1.75rem,4vw,2.75rem); padding-top:clamp(1.25rem,3vw,2rem); border-top:1px solid rgba(255,255,255,0.09); flex-wrap:wrap; }}
.jnj-hero-stat-num {{ font-size:clamp(1.6rem,3.5vw,2.4rem); font-weight:900; color:#ffffff; line-height:1; margin-bottom:0.2rem; letter-spacing:-0.02em; }}
.jnj-hero-stat-num span {{ color:{JNJ_RED}; }}
.jnj-hero-stat-label {{ font-size:clamp(0.58rem,0.9vw,0.7rem); font-weight:600; letter-spacing:0.12em; text-transform:uppercase; color:{JNJ_GRAY_05}; }}

/* CONTENT */
.jnj-content {{ padding-top:clamp(1.75rem,4vw,3rem); padding-bottom:clamp(1.75rem,4vw,3rem); }}

/* SECTION HEADERS */
.jnj-section-header {{ display:flex; align-items:center; gap:clamp(0.65rem,1.5vw,1rem); margin-bottom:clamp(1rem,2vw,1.5rem); margin-top:clamp(1.75rem,4vw,2.75rem); }}
.jnj-step-num {{ width:clamp(28px,4vw,38px); height:clamp(28px,4vw,38px); min-width:clamp(28px,4vw,38px); background:{JNJ_RED}; color:#fff; font-size:clamp(0.65rem,1vw,0.82rem); font-weight:800; border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0; box-shadow:0 3px 10px rgba(235,23,0,0.3); }}
.jnj-section-title {{ font-size:clamp(1rem,2vw,1.25rem); font-weight:700; color:{JNJ_GRAY_08}; letter-spacing:-0.015em; line-height:1.2; }}
.jnj-section-title span {{ display:block; font-size:clamp(0.7rem,1.2vw,0.8rem); font-weight:400; color:{JNJ_GRAY_05}; letter-spacing:0.01em; margin-top:2px; }}

/* CARDS */
.jnj-card {{ background:#ffffff; border:1px solid {JNJ_GRAY_02}; border-radius:10px; padding:clamp(1.25rem,3vw,2rem); margin-bottom:1.25rem; box-shadow:0 1px 6px rgba(0,0,0,0.045),0 4px 16px rgba(0,0,0,0.03); }}

/* META STRIP */
.jnj-meta-strip {{ background:#ffffff; border:1px solid {JNJ_GRAY_02}; border-left:4px solid {JNJ_RED}; border-radius:0 10px 10px 0; padding:clamp(0.75rem,2vw,1.1rem) clamp(1rem,2.5vw,1.6rem); display:flex; gap:clamp(1rem,4vw,3rem); align-items:center; margin-bottom:clamp(1rem,2.5vw,1.6rem); flex-wrap:wrap; }}
.jnj-meta-item {{ display:flex; flex-direction:column; gap:3px; min-width:0; }}
.jnj-meta-label {{ font-size:clamp(0.55rem,0.85vw,0.62rem); font-weight:700; letter-spacing:0.18em; text-transform:uppercase; color:{JNJ_GRAY_05}; white-space:nowrap; }}
.jnj-meta-value {{ font-size:clamp(0.8rem,1.5vw,0.95rem); font-weight:600; color:{JNJ_GRAY_08}; overflow:hidden; text-overflow:ellipsis; }}
.jnj-meta-divider {{ width:1px; height:34px; background:{JNJ_GRAY_02}; flex-shrink:0; }}

/* HINTS */
.jnj-hints {{ display:flex; gap:0.4rem; flex-wrap:wrap; margin-bottom:clamp(0.75rem,2vw,1.1rem); }}
.jnj-hint {{ font-size:clamp(0.62rem,1vw,0.72rem); font-weight:500; color:{JNJ_GRAY_06}; background:{JNJ_GRAY_01}; border:1px solid {JNJ_GRAY_02}; border-radius:4px; padding:0.25rem clamp(0.5rem,1.2vw,0.8rem); white-space:nowrap; }}

/* DATA EDITOR */
[data-testid="stDataEditor"] {{ border:1px solid {JNJ_GRAY_02} !important; border-radius:10px !important; overflow:hidden; box-shadow:0 1px 6px rgba(0,0,0,0.04); }}

/* UPLOAD ZONE */
[data-testid="stFileUploader"] {{ background:#ffffff !important; border:2px dashed {JNJ_GRAY_03} !important; border-radius:10px !important; padding:clamp(1rem,3vw,1.75rem) !important; }}
[data-testid="stFileUploader"]:hover {{ border-color:{JNJ_RED} !important; box-shadow:0 0 0 4px rgba(235,23,0,0.07) !important; }}

/* BUTTONS */
.stButton > button[kind="primary"] {{ background:{JNJ_RED} !important; color:#ffffff !important; border:none !important; border-radius:6px !important; font-family:'Inter',sans-serif !important; font-weight:700 !important; font-size:clamp(0.78rem,1.2vw,0.9rem) !important; padding:0.625rem clamp(1.25rem,2.5vw,1.875rem) !important; letter-spacing:0.025em !important; box-shadow:0 2px 10px rgba(235,23,0,0.28) !important; }}
.stButton > button[kind="primary"]:hover {{ background:{JNJ_MAROON} !important; transform:translateY(-1px) !important; }}
.stButton > button[kind="secondary"] {{ background:#ffffff !important; color:{JNJ_GRAY_08} !important; border:1px solid {JNJ_GRAY_03} !important; border-radius:6px !important; font-family:'Inter',sans-serif !important; font-weight:600 !important; }}
.stButton > button[kind="secondary"]:hover {{ border-color:{JNJ_GRAY_06} !important; background:{JNJ_GRAY_01} !important; }}

/* TEXT INPUT */
.stTextInput > div > div > input {{ background:#ffffff !important; border:1px solid {JNJ_GRAY_03} !important; border-radius:6px !important; color:{JNJ_GRAY_08} !important; font-family:'Roboto Mono',monospace !important; font-size:clamp(0.76rem,1.1vw,0.84rem) !important; }}
.stTextInput > div > div > input:focus {{ border-color:{JNJ_RED} !important; box-shadow:0 0 0 3px rgba(235,23,0,0.1) !important; }}

/* STEP PREVIEW ROWS */
.jnj-step-row {{ display:flex; align-items:flex-start; gap:clamp(0.6rem,1.5vw,0.9rem); padding:clamp(0.7rem,1.5vw,1rem) clamp(0.75rem,1.5vw,1.1rem); border-bottom:1px solid {JNJ_GRAY_01}; }}
.jnj-step-row:last-child {{ border-bottom:none; }}
.jnj-step-index {{ font-family:'Roboto Mono',monospace; font-size:clamp(0.6rem,0.9vw,0.68rem); font-weight:600; color:{JNJ_GRAY_05}; min-width:22px; text-align:right; flex-shrink:0; }}
.jnj-badge {{ font-size:clamp(0.55rem,0.85vw,0.62rem); font-weight:800; letter-spacing:0.12em; text-transform:uppercase; border-radius:4px; padding:2px 8px; white-space:nowrap; flex-shrink:0; }}
.jnj-badge-inc {{ background:rgba(15,104,178,0.09); color:{JNJ_BLUE_03}; border:1px solid rgba(15,104,178,0.22); }}
.jnj-badge-exc {{ background:rgba(235,23,0,0.07); color:{JNJ_RED}; border:1px solid rgba(235,23,0,0.2); }}
.jnj-step-text {{ font-size:clamp(0.8rem,1.3vw,0.9rem); color:{JNJ_GRAY_08}; line-height:1.58; }}

/* BANNERS */
.jnj-success {{ background:rgba(50,135,20,0.06); border:1px solid rgba(50,135,20,0.22); border-left:4px solid {JNJ_GREEN_03}; border-radius:0 8px 8px 0; padding:clamp(0.75rem,2vw,1.1rem) clamp(1rem,2vw,1.4rem); color:#1e5c0a; font-size:clamp(0.78rem,1.2vw,0.875rem); font-weight:500; margin-bottom:1.5rem; line-height:1.5; }}
.jnj-error {{ background:rgba(235,23,0,0.05); border-left:4px solid {JNJ_RED}; border-radius:0 8px 8px 0; padding:clamp(0.75rem,2vw,1.1rem) clamp(1rem,2vw,1.4rem); color:{JNJ_MAROON}; font-size:clamp(0.78rem,1.2vw,0.875rem); margin-bottom:1rem; }}
.jnj-info {{ background:rgba(15,104,178,0.05); border-left:4px solid {JNJ_BLUE_03}; border-radius:0 8px 8px 0; padding:clamp(0.75rem,2vw,1.1rem) clamp(1rem,2vw,1.4rem); color:#0a3d6b; font-size:clamp(0.78rem,1.2vw,0.875rem); margin-bottom:1rem; }}

/* STAT ROW */
.jnj-stat-row {{ display:flex; gap:1px; background:{JNJ_GRAY_02}; border:1px solid {JNJ_GRAY_02}; border-radius:10px; overflow:hidden; margin-bottom:1.5rem; }}
.jnj-stat-cell {{ flex:1; background:#ffffff; padding:clamp(1rem,2vw,1.4rem) clamp(1.1rem,2.5vw,1.75rem); display:flex; flex-direction:column; gap:4px; }}
.jnj-stat-cell-label {{ font-size:clamp(0.58rem,0.9vw,0.65rem); font-weight:700; letter-spacing:0.16em; text-transform:uppercase; color:{JNJ_GRAY_05}; white-space:nowrap; }}
.jnj-stat-cell-value {{ font-size:clamp(1.4rem,3vw,1.9rem); font-weight:900; color:{JNJ_GRAY_08}; line-height:1; letter-spacing:-0.02em; }}
.jnj-stat-cell-value.red {{ color:{JNJ_RED}; }}
.jnj-stat-cell-value.blue {{ color:{JNJ_BLUE_03}; }}

/* SIDEBAR */
[data-testid="stSidebar"] {{ background:#ffffff !important; border-right:1px solid {JNJ_GRAY_02} !important; }}
[data-testid="stSidebar"] .block-container {{ padding:clamp(1.25rem,3vw,1.75rem) clamp(1rem,2.5vw,1.4rem) !important; max-width:100% !important; }}
.sidebar-brand {{ padding-bottom:1.25rem; border-bottom:2px solid {JNJ_RED}; margin-bottom:1.5rem; }}
.sidebar-brand-name {{ font-size:clamp(0.65rem,1vw,0.72rem); font-weight:800; letter-spacing:0.16em; text-transform:uppercase; color:{JNJ_RED}; }}
.sidebar-brand-sub {{ font-size:clamp(0.58rem,0.9vw,0.65rem); color:{JNJ_GRAY_05}; margin-top:3px; font-weight:400; }}
.sidebar-section-label {{ font-size:clamp(0.55rem,0.85vw,0.62rem); font-weight:800; letter-spacing:0.16em; text-transform:uppercase; color:{JNJ_GRAY_05}; margin-bottom:0.5rem; margin-top:1.5rem; }}
.sidebar-stat {{ display:flex; justify-content:space-between; align-items:center; padding:0.6rem 0.8rem; border-radius:6px; margin-bottom:4px; font-size:clamp(0.76rem,1.1vw,0.84rem); font-weight:500; }}
.sidebar-stat.total {{ background:{JNJ_GRAY_01}; color:{JNJ_GRAY_08}; }}
.sidebar-stat.inc {{ background:rgba(15,104,178,0.07); color:{JNJ_BLUE_03}; }}
.sidebar-stat.exc {{ background:rgba(235,23,0,0.06); color:{JNJ_RED}; }}
.sidebar-stat-num {{ font-weight:800; font-size:1.05em; }}
.sidebar-divider {{ height:1px; background:{JNJ_GRAY_02}; margin:1.25rem 0; }}
.sidebar-output {{ background:{JNJ_GRAY_01}; border-radius:6px; padding:0.75rem 0.9rem; font-family:'Roboto Mono',monospace; font-size:clamp(0.6rem,0.9vw,0.68rem); color:{JNJ_GREEN_03}; word-break:break-all; line-height:1.5; }}

/* AI PIPELINE STATUS */
.pipeline-panel {{ background:linear-gradient(135deg,#0f1923 0%,#162032 100%); border:1px solid rgba(105,208,255,0.15); border-radius:12px; padding:1.1rem 1.4rem; margin-bottom:1.25rem; }}
.pipeline-label {{ font-size:0.6rem; font-weight:800; letter-spacing:0.2em; text-transform:uppercase; color:#69d0ff; margin-bottom:0.85rem; }}
.pipeline-stages {{ display:flex; gap:4px; align-items:center; flex-wrap:wrap; }}
.stage-box {{ display:flex; flex-direction:column; align-items:center; gap:3px; min-width:80px; }}
.stage-circle {{ width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:700; }}
.stage-name {{ font-size:0.6rem; font-weight:700; text-align:center; white-space:nowrap; }}
.stage-fn {{ font-size:0.5rem; font-family:'Roboto Mono',monospace; text-align:center; white-space:nowrap; }}
.stage-connector {{ width:20px; height:1px; }}

/* TABS */
.stTabs [data-baseweb="tab-list"] {{ gap:0.25rem; background:transparent; border-bottom:2px solid {JNJ_GRAY_02}; padding:0; margin-bottom:clamp(1.25rem,3vw,1.875rem); }}
.stTabs [data-baseweb="tab"] {{ background:transparent; border-radius:0; color:{JNJ_GRAY_05}; font-family:'Inter',sans-serif; font-size:clamp(0.78rem,1.2vw,0.875rem); font-weight:500; padding:0.65rem clamp(0.9rem,2vw,1.5rem) 0.75rem; border:none; border-bottom:3px solid transparent; margin-bottom:-2px; }}
.stTabs [aria-selected="true"] {{ background:transparent !important; color:{JNJ_RED} !important; font-weight:700 !important; border-bottom:3px solid {JNJ_RED} !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ display:none; }}
.stTabs [data-baseweb="tab-border"] {{ display:none; }}

/* CODE LISTS */
.cl-condition-card {{ background:#ffffff; border:1px solid {JNJ_GRAY_02}; border-radius:10px; padding:clamp(1rem,2.5vw,1.5rem); margin-bottom:0.75rem; box-shadow:0 1px 6px rgba(0,0,0,0.04); }}
.cl-condition-header {{ display:flex; align-items:baseline; gap:0.75rem; margin-bottom:0.85rem; }}
.cl-condition-name {{ font-size:clamp(0.95rem,1.8vw,1.1rem); font-weight:700; color:{JNJ_GRAY_08}; letter-spacing:-0.01em; }}
.cl-condition-total {{ font-size:0.7rem; font-weight:500; color:{JNJ_GRAY_05}; font-family:'Roboto Mono',monospace; }}
.cl-badges-row {{ display:flex; flex-wrap:wrap; gap:0.5rem; }}
.cl-sys-badge {{ display:flex; align-items:center; gap:0.4rem; border:1.5px solid; border-radius:6px; padding:0.3rem 0.75rem; font-size:0.7rem; font-weight:600; }}
.cl-sys-name {{ font-weight:700; letter-spacing:0.04em; }}
.cl-sys-count {{ opacity:0.75; font-weight:500; }}
.cl-sys-tmp {{ font-family:'Roboto Mono',monospace; font-size:0.62rem; opacity:0.65; border-left:1px solid currentColor; padding-left:0.4rem; margin-left:0.1rem; }}

/* FOOTER */
.jnj-footer {{ margin-top:clamp(2.5rem,6vw,4.5rem); padding:clamp(1.1rem,2.5vw,1.6rem) 0; border-top:1px solid {JNJ_GRAY_02}; }}
.jnj-footer-inner {{ display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.75rem; }}
.jnj-footer-left {{ font-size:clamp(0.65rem,1vw,0.73rem); color:{JNJ_GRAY_05}; line-height:1.5; }}
.jnj-footer-left strong {{ color:{JNJ_RED}; }}
.jnj-footer-right {{ font-family:'Roboto Mono',monospace; font-size:clamp(0.58rem,0.9vw,0.65rem); color:{JNJ_GRAY_05}; }}

::-webkit-scrollbar {{ width:5px; height:5px; }}
::-webkit-scrollbar-track {{ background:{JNJ_GRAY_01}; }}
::-webkit-scrollbar-thumb {{ background:{JNJ_GRAY_03}; border-radius:4px; }}
::selection {{ background:rgba(235,23,0,0.12); color:{JNJ_GRAY_08}; }}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────
for key, default in [
    ("steps_df",            None),
    ("title",               ""),
    ("data_sources",        []),
    ("study_window",        ""),
    ("parse_method",        ""),
    ("parse_summary",       ""),
    ("notebook_path",       None),
    ("input_mode",          None),
    ("codelists_df",        None),
    ("selected_conditions", None),
    ("dbx_notebook_url",    None),
    ("dbx_notebook_sql",    None),
    ("nb_path_override",    None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ─────────────────────────────────────────────────────────────────────────────
# NAV BAR
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="jnj-nav">
  <div class="jnj-inner jnj-nav-inner">
    <div class="jnj-logo-wrap">
        <img src="{_LOGO_WEB_URL}" style="height:clamp(36px,5vw,54px);width:auto;display:block;" alt="J&amp;J">
        <div class="jnj-logo-divider"></div>
        <div>
            <div class="jnj-logo-text">MedTech</div>
            <span class="jnj-logo-sub">Agentic AI Platform</span>
        </div>
    </div>
    <div class="jnj-nav-right">
        <span class="jnj-nav-tag">Code Automation</span>
        <span class="jnj-nav-version">v2.0.0</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div class="sidebar-brand">
        <img src="{_LOGO_WEB_URL}" style="height:38px;width:auto;margin-bottom:10px;display:block;" alt="J&amp;J">
        <div class="sidebar-brand-name">Code Automation</div>
        <div class="sidebar-brand-sub">Protocol Intelligence Platform</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("New Protocol", type="secondary", use_container_width=True):
        for k in ["steps_df", "title", "data_sources", "study_window", "parse_method",
                  "parse_summary", "notebook_path", "input_mode", "codelists_df",
                  "selected_conditions", "dbx_notebook_url", "dbx_notebook_sql", "nb_path_override"]:
            st.session_state[k] = None if k not in ("data_sources",) else []
        st.session_state.title = ""
        st.session_state.study_window = ""
        st.rerun()

    if st.session_state.steps_df is not None:
        df = st.session_state.steps_df
        inc   = int((df["step_type"] == "inclusion").sum())
        exc   = int((df["step_type"] == "exclusion").sum())
        total = len(df)
        st.markdown('<div class="sidebar-section-label">Step Summary</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="sidebar-stat total"><span>Total Steps</span><span class="sidebar-stat-num">{total}</span></div>
        <div class="sidebar-stat inc"><span>Inclusion</span><span class="sidebar-stat-num">{inc}</span></div>
        <div class="sidebar-stat exc"><span>Exclusion</span><span class="sidebar-stat-num">{exc}</span></div>
        """, unsafe_allow_html=True)

    if st.session_state.notebook_path:
        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-section-label">Last Output</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sidebar-output">{st.session_state.notebook_path}</div>', unsafe_allow_html=True)
        if st.session_state.dbx_notebook_url:
            st.markdown(
                f'<div class="sidebar-output" style="margin-top:6px;">'
                f'<a href="{st.session_state.dbx_notebook_url}" target="_blank" style="color:{JNJ_GREEN_03};">'
                f'Open in Databricks →</a></div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-label">Databricks Connection</div>', unsafe_allow_html=True)
    if is_databricks_app():
        st.markdown(
            '<div class="sidebar-output" style="color:#328714;">Connected via Databricks App</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="font-size:0.72rem;color:{JNJ_GRAY_05};line-height:1.5;padding:0.4rem 0;">'
            f'Deploy to Databricks Apps to enable full AI pipeline.</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div style="font-size:0.6rem;color:{JNJ_GRAY_05};margin-top:2rem;padding-top:1rem;'
        f'border-top:1px solid {JNJ_GRAY_02};line-height:1.5;">Agentic AI Platform · Internal Use Only</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# HERO BAND
# ─────────────────────────────────────────────────────────────────────────────
df_now      = st.session_state.steps_df
inc_count   = int((df_now["step_type"] == "inclusion").sum()) if df_now is not None else 0
exc_count   = int((df_now["step_type"] == "exclusion").sum()) if df_now is not None else 0
total_count = len(df_now) if df_now is not None else 0

st.markdown(f"""
<div class="jnj-hero">
  <div class="jnj-inner jnj-hero-inner">
    <div class="jnj-hero-eyebrow">J&amp;J MedTech &nbsp;·&nbsp; Agentic AI Platform</div>
    <div class="jnj-hero-title">Code <span>Automation</span></div>
    <div class="jnj-hero-stats">
      <div class="jnj-hero-stat">
        <div class="jnj-hero-stat-num">{total_count}<span>.</span></div>
        <div class="jnj-hero-stat-label">Total Steps</div>
      </div>
      <div class="jnj-hero-stat">
        <div class="jnj-hero-stat-num">{inc_count}<span>.</span></div>
        <div class="jnj-hero-stat-label">Inclusion</div>
      </div>
      <div class="jnj-hero-stat">
        <div class="jnj-hero-stat-num">{exc_count}<span>.</span></div>
        <div class="jnj-hero-stat-label">Exclusion</div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# CONTENT
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="jnj-inner jnj-content">', unsafe_allow_html=True)


# ── STEP 1: PROTOCOL INPUT ────────────────────────────────────────────────────
st.markdown("""
<div class="jnj-section-header" style="margin-top:0;">
  <div class="jnj-step-num">1</div>
  <div class="jnj-section-title">Protocol Input
    <span>Upload a .docx / .pdf file, paste text, or enter steps manually</span>
  </div>
</div>
""", unsafe_allow_html=True)

tab_upload, tab_text, tab_manual = st.tabs([
    "  Upload Protocol  ",
    "  Paste Text  ",
    "  Enter Manually  ",
])

# ── TAB: UPLOAD ───────────────────────────────────────────────────────────────
with tab_upload:
    uploaded = st.file_uploader("", type=["docx", "pdf"], label_visibility="collapsed")
    if uploaded and st.session_state.steps_df is None:
        file_suffix = Path(uploaded.name).suffix.lower()

        # PDF requires Databricks; give a clear message instead of a cryptic error
        if file_suffix == ".pdf" and not is_databricks_app():
            st.markdown(
                '<div class="jnj-info">'
                '<strong>PDF parsing requires Databricks deployment.</strong><br>'
                'Please copy the protocol text and use the <strong>Paste Text</strong> tab, '
                'or upload a <code>.docx</code> version of the protocol.'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            with tempfile.NamedTemporaryFile(suffix=file_suffix, delete=False) as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            with st.spinner("Parsing protocol with AI pipeline…"):
                try:
                    if is_databricks_app():
                        from backend.services.databricks_client import upload_to_volume
                        vol_path = f"{settings.protocol_volume}/{uploaded.name}"
                        upload_to_volume(tmp_path, vol_path)
                        result = parse_protocol(volume_path=vol_path)
                    else:
                        result = parse_protocol(local_file_path=tmp_path)

                    st.session_state.title         = result.title
                    st.session_state.data_sources  = result.data_sources
                    st.session_state.study_window  = result.study_window or ""
                    st.session_state.parse_method  = result.parse_method
                    st.session_state.parse_summary = result.summary or ""
                    st.session_state.input_mode    = "upload"
                    rows = [
                        {"step_type": s.step_type, "description": s.description}
                        for s in result.all_steps
                    ]
                    if result.warnings:
                        for w in result.warnings:
                            st.markdown(f'<div class="jnj-info">⚠ {w}</div>', unsafe_allow_html=True)
                    if not result.all_steps:
                        st.markdown(
                            '<div class="jnj-error"><strong>No criteria extracted.</strong> '
                            'Check warnings above. Try the Paste Text tab instead.</div>',
                            unsafe_allow_html=True,
                        )
                    st.session_state.steps_df = pd.DataFrame(rows, columns=["step_type", "description"])
                    st.rerun()
                except Exception as e:
                    st.markdown(f'<div class="jnj-error">{e}</div>', unsafe_allow_html=True)

# ── TAB: PASTE TEXT ───────────────────────────────────────────────────────────
with tab_text:
    st.markdown("""
    <div class="jnj-hints">
        <span class="jnj-hint">Paste full protocol text including inclusion/exclusion criteria</span>
        <span class="jnj-hint">Claude extracts and classifies all steps automatically</span>
    </div>
    """, unsafe_allow_html=True)

    raw_text = st.text_area(
        "Protocol text",
        placeholder="Paste your protocol text here…\n\nInclusion Criteria:\n• Age ≥ 18 years\n• ...\n\nExclusion Criteria:\n• ...",
        height=280,
        label_visibility="collapsed",
    )
    if st.button("Parse Protocol Text", type="primary", key="parse_text_btn"):
        if not raw_text.strip():
            st.warning("Paste some protocol text first.")
        else:
            with st.spinner("Extracting criteria with Claude…"):
                try:
                    result = parse_protocol(raw_text=raw_text.strip())
                    st.session_state.title        = result.title
                    st.session_state.data_sources = result.data_sources
                    st.session_state.study_window = result.study_window or ""
                    st.session_state.parse_method = result.parse_method
                    st.session_state.parse_summary = result.summary or ""
                    st.session_state.input_mode   = "text"
                    rows = [
                        {"step_type": s.step_type, "description": s.description}
                        for s in result.all_steps
                    ]
                    if result.warnings:
                        for w in result.warnings:
                            st.markdown(f'<div class="jnj-info">⚠ {w}</div>', unsafe_allow_html=True)
                    if not result.all_steps:
                        st.markdown(
                            '<div class="jnj-error"><strong>No criteria extracted.</strong> '
                            'Check warnings above — the model endpoint or warehouse may need attention.</div>',
                            unsafe_allow_html=True,
                        )
                    st.session_state.steps_df = pd.DataFrame(rows, columns=["step_type", "description"])
                    st.rerun()
                except Exception as e:
                    st.markdown(f'<div class="jnj-error">Parse error: {e}</div>', unsafe_allow_html=True)

# ── TAB: MANUAL ───────────────────────────────────────────────────────────────
with tab_manual:
    if st.session_state.input_mode != "manual":
        st.markdown("""
        <div class="jnj-hints">
            <span class="jnj-hint">Type your study title below</span>
            <span class="jnj-hint">Add each attrition step in the table</span>
            <span class="jnj-hint">Choose Inclusion or Exclusion per row</span>
        </div>
        """, unsafe_allow_html=True)
        manual_title = st.text_input("Study Title", placeholder="e.g. Comparative effectiveness of…", key="manual_title_input")
        manual_source = st.text_input("Data Source (optional)", placeholder="e.g. Premier Healthcare Database", key="manual_source_input")
        st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
        if st.button("Start Entering Steps", type="primary", key="manual_start"):
            if not manual_title.strip():
                st.warning("Please enter a study title.")
            else:
                st.session_state.title        = manual_title.strip()
                st.session_state.data_sources = [manual_source.strip()] if manual_source.strip() else []
                st.session_state.input_mode   = "manual"
                st.session_state.parse_method = "manual"
                st.session_state.steps_df     = pd.DataFrame(
                    [{"step_type": "inclusion", "description": ""}],
                    columns=["step_type", "description"],
                )
                st.rerun()
    else:
        st.markdown(
            f'<div style="font-size:0.78rem;color:{JNJ_GRAY_06};margin-bottom:0.75rem;">'
            f'Manual entry active &nbsp;·&nbsp; <strong style="color:{JNJ_GRAY_08};">{st.session_state.title}</strong></div>',
            unsafe_allow_html=True,
        )


# ── STEP 2: EDIT ATTRITION STEPS ─────────────────────────────────────────────
st.markdown("""
<div class="jnj-section-header" style="margin-top:2.5rem;">
  <div class="jnj-step-num">2</div>
  <div class="jnj-section-title">Edit Attrition Steps
    <span>Add, remove, or modify any step — changes flow directly into the notebook</span>
  </div>
</div>
""", unsafe_allow_html=True)

if st.session_state.steps_df is None:
    st.markdown(f"""
    <div style="background:#ffffff;border:1px dashed {JNJ_GRAY_03};border-radius:8px;
                padding:1.5rem 2rem;color:{JNJ_GRAY_05};font-size:0.875rem;text-align:center;">
        Upload a protocol or enter steps manually in Step 1 to begin editing.
    </div>
    """, unsafe_allow_html=True)

edited_df = None
if st.session_state.steps_df is not None:

    # AI pipeline status panel
    pm = st.session_state.parse_method
    if pm and pm != "manual":
        is_dbx = pm == "llm_databricks"
        stages = [
            ("doc",      "Document Extract",   "ai_parse_document",  True),
            ("extract",  "Field Extraction",   "ai_extract v2.1",    True),
            ("claude",   "Criteria Extract",   "Claude REST",        False),
            ("classify", "Type Classify",      "ai_classify_batch",  True),
            ("summarize","Protocol Summary",   "ai_summarize",       True),
        ]
        circles = ""
        for i, (key, label, fn, dbx_only) in enumerate(stages):
            ran = is_dbx or not dbx_only
            is_gate = key == "claude"
            bg  = ("rgba(235,23,0,0.3)" if is_gate else "rgba(50,135,20,0.25)") if ran else "rgba(255,255,255,0.05)"
            bdr = ("#eb1700" if is_gate else "#328714") if ran else "rgba(255,255,255,0.1)"
            clr = ("#ff6b6b" if is_gate else "#6dd67f") if ran else "rgba(255,255,255,0.2)"
            txt_clr = "#ffffff" if ran else "rgba(255,255,255,0.2)"
            fn_clr  = "#69d0ff" if ran else "rgba(255,255,255,0.1)"
            connector = f'<div class="stage-connector" style="background:{"rgba(105,208,255,0.3)" if ran else "rgba(255,255,255,0.1)"}"></div>' if i > 0 else ""
            circles += f"""
            {connector}
            <div class="stage-box">
              <div class="stage-circle" style="background:{bg};border:2px solid {bdr};color:{clr};">
                {"✓" if ran else "—"}
              </div>
              <div class="stage-name" style="color:{txt_clr};">{label}</div>
              <div class="stage-fn" style="color:{fn_clr};">{fn}</div>
            </div>"""
        st.markdown(f"""
        <div class="pipeline-panel">
          <div class="pipeline-label">AI Parse Pipeline</div>
          <div class="pipeline-stages">{circles}</div>
          {"" if is_dbx else f'<div style="font-size:0.65rem;color:rgba(255,255,255,0.4);margin-top:0.75rem;">Stages 1,2,4,5 require Databricks · Stage 3 (Claude) always runs</div>'}
        </div>
        """, unsafe_allow_html=True)

    # Summary banner
    if st.session_state.parse_summary:
        st.markdown(
            f'<div class="jnj-info"><strong style="font-size:0.65rem;letter-spacing:0.1em;text-transform:uppercase;">Protocol Summary</strong><br>{st.session_state.parse_summary}</div>',
            unsafe_allow_html=True,
        )

    # Meta strip
    sources_display = ", ".join(st.session_state.data_sources) if st.session_state.data_sources else "Not detected"
    parse_labels = {
        "llm_databricks": "AI Functions (full pipeline)",
        "llm_rest": "Claude REST (text)",
        "llm_rest_text": "Claude REST (pasted text)",
        "llm_rest_local": "Claude REST (local DOCX)",
        "manual": "Manual entry",
    }
    st.markdown(f"""
    <div class="jnj-meta-strip">
      <div class="jnj-meta-item">
        <span class="jnj-meta-label">Study Title</span>
        <span class="jnj-meta-value">{st.session_state.title}</span>
      </div>
      <div class="jnj-meta-divider"></div>
      <div class="jnj-meta-item">
        <span class="jnj-meta-label">Data Source</span>
        <span class="jnj-meta-value">{sources_display}</span>
      </div>
      <div class="jnj-meta-divider"></div>
      <div class="jnj-meta-item">
        <span class="jnj-meta-label">Parse Method</span>
        <span class="jnj-meta-value" style="font-size:0.78rem;color:{JNJ_GRAY_06};">{parse_labels.get(pm, pm)}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="jnj-hints">
        <span class="jnj-hint">Click any cell to edit text</span>
        <span class="jnj-hint">Dropdown → switch Inclusion / Exclusion</span>
        <span class="jnj-hint">Select row checkbox → Delete key to remove</span>
        <span class="jnj-hint">+ row button to add a step</span>
    </div>
    """, unsafe_allow_html=True)

    edited_df = st.data_editor(
        st.session_state.steps_df,
        column_config={
            "step_type": st.column_config.SelectboxColumn(
                label="Type", options=["inclusion", "exclusion"], required=True, width="small",
            ),
            "description": st.column_config.TextColumn(
                label="Step Description", width="large", required=True,
            ),
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=False,
        key="step_editor",
    )

    inc_live   = int((edited_df["step_type"] == "inclusion").sum())
    exc_live   = int((edited_df["step_type"] == "exclusion").sum())
    total_live = len(edited_df.dropna(subset=["description"]))

    st.markdown(f"""
    <div class="jnj-stat-row" style="margin-top:1rem;">
      <div class="jnj-stat-cell">
        <span class="jnj-stat-cell-label">Total Steps</span>
        <span class="jnj-stat-cell-value">{total_live}</span>
      </div>
      <div class="jnj-stat-cell">
        <span class="jnj-stat-cell-label">Inclusion</span>
        <span class="jnj-stat-cell-value blue">{inc_live}</span>
      </div>
      <div class="jnj-stat-cell">
        <span class="jnj-stat-cell-label">Exclusion</span>
        <span class="jnj-stat-cell-value red">{exc_live}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ── STEP 3: CODE LISTS ────────────────────────────────────────────────────────
if st.session_state.steps_df is not None:
    st.markdown("""
    <div class="jnj-section-header" style="margin-top:2.5rem;">
      <div class="jnj-step-num">3</div>
      <div class="jnj-section-title">Code Lists
        <span>Define ICD-9/10, CPT, HCPCS, DRG, NDC codes grouped by condition — feeds SQL generation</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    cl_tab_manual, cl_tab_excel = st.tabs(["  Manual Entry  ", "  Upload Excel  "])

    # Manual entry
    with cl_tab_manual:
        st.markdown("""
        <div class="jnj-hints">
            <span class="jnj-hint">One code group = one condition + one coding system</span>
            <span class="jnj-hint">Paste codes — comma, newline, or semicolon separated</span>
        </div>
        """, unsafe_allow_html=True)
        with st.form("cl_add_form", clear_on_submit=True):
            col_cond, col_sys = st.columns([2, 2])
            with col_cond:
                f_condition = st.text_input("Condition / Concept Name", placeholder="e.g. Malnutrition, NSCLC")
            with col_sys:
                f_coding_sys = st.selectbox("Coding System", CODING_SYSTEMS)
            f_codes_raw = st.text_area("Codes", placeholder="Paste codes here — one per line or comma separated\nE40\nE41\nE42", height=140)
            cl_submitted = st.form_submit_button("+ Add Code Group", type="primary")

        if cl_submitted:
            if not f_condition.strip():
                st.warning("Enter a condition name.")
            elif not f_codes_raw.strip():
                st.warning("Enter at least one code.")
            else:
                new_codes = parse_codes_input(f_codes_raw)
                new_rows = pd.DataFrame({"condition": f_condition.strip(), "coding_system": f_coding_sys, "code": new_codes, "description": ""})
                if st.session_state.codelists_df is None:
                    st.session_state.codelists_df = new_rows
                else:
                    st.session_state.codelists_df = pd.concat([st.session_state.codelists_df, new_rows], ignore_index=True)
                st.rerun()

    # Excel upload
    with cl_tab_excel:
        st.markdown("""
        <div class="jnj-hints">
            <span class="jnj-hint">Upload one or multiple Excel/CSV files</span>
            <span class="jnj-hint">Select a file, then a sheet — system suggests column mapping</span>
            <span class="jnj-hint">You confirm every mapping</span>
        </div>
        """, unsafe_allow_html=True)

        cl_excel_files = st.file_uploader("", type=["xlsx", "xls", "csv"], label_visibility="collapsed", key="cl_excel_uploader", accept_multiple_files=True)

        if cl_excel_files:
            file_names = [f.name for f in cl_excel_files]
            selected_fname = st.selectbox(f"{len(cl_excel_files)} file(s) — select one to map", file_names, key="cl_file_select")
            cl_excel_file = next(f for f in cl_excel_files if f.name == selected_fname)

            try:
                if cl_excel_file.name.lower().endswith(".csv"):
                    all_sheets = {"Sheet1": pd.read_csv(cl_excel_file, dtype=str)}
                else:
                    xl = pd.ExcelFile(cl_excel_file)
                    all_sheets = {s: xl.parse(s, dtype=str) for s in xl.sheet_names}
            except Exception as e:
                st.markdown(f'<div class="jnj-error">Could not read file: {e}</div>', unsafe_allow_html=True)
                all_sheets = {}

            if all_sheets:
                for sheet_name, df_raw in all_sheets.items():
                    df_sheet    = df_raw.dropna(how="all")
                    col_options = ["— not in this sheet —"] + list(df_sheet.columns.astype(str))
                    sample_codes = df_sheet.iloc[:, 0].dropna().astype(str).tolist()[:20]
                    guessed_sys  = guess_coding_system(sheet_name, sample_codes)
                    guessed_idx  = CODING_SYSTEMS.index(guessed_sys) if guessed_sys in CODING_SYSTEMS else 0

                    label = f"Sheet: {sheet_name}  ·  {len(df_sheet)} rows"
                    if guessed_sys:
                        label += f"  ·  Auto-detected: {guessed_sys}"

                    with st.expander(label, expanded=True):
                        st.dataframe(df_sheet.head(3), use_container_width=True)
                        mc1, mc2 = st.columns(2)
                        with mc1:
                            map_code_col = st.selectbox("Code column *", col_options, key=f"map_code_{sheet_name}")
                            map_desc_col = st.selectbox("Description column (optional)", col_options, key=f"map_desc_{sheet_name}")
                        with mc2:
                            map_cond_col    = st.selectbox("Condition column (if in file)", col_options, key=f"map_cond_col_{sheet_name}")
                            map_cond_manual = st.text_input("— or type condition name", placeholder="e.g. TKA", key=f"map_cond_txt_{sheet_name}")
                            map_sys_col     = st.selectbox("Coding system column (if mixed)", col_options, key=f"map_sys_col_{sheet_name}")
                            map_sys_manual  = st.selectbox("— or select one coding system", CODING_SYSTEMS, index=guessed_idx, key=f"map_sys_sel_{sheet_name}")

                        if st.button(f"Import — {sheet_name}", type="primary", key=f"cl_import_{sheet_name}"):
                            if map_code_col == "— not in this sheet —":
                                st.warning("Select the column that contains the codes.")
                            else:
                                code_mask = df_sheet[map_code_col].notna() & (df_sheet[map_code_col].astype(str).str.strip() != "")
                                df_valid  = df_sheet[code_mask].copy().reset_index(drop=True)
                                cond_vals = (df_valid[map_cond_col].fillna("Unknown").astype(str).str.strip() if map_cond_col != "— not in this sheet —" else pd.Series([map_cond_manual.strip() or sheet_name] * len(df_valid)))
                                sys_vals  = (df_valid[map_sys_col].fillna("").astype(str).str.strip() if map_sys_col != "— not in this sheet —" else pd.Series([map_sys_manual] * len(df_valid)))
                                desc_vals = (df_valid[map_desc_col].astype(str).str.strip() if map_desc_col != "— not in this sheet —" else pd.Series([""] * len(df_valid)))
                                raw_codes = df_valid[map_code_col].astype(str).str.strip().str.upper()

                                new_rows = pd.DataFrame({"condition": cond_vals.values, "coding_system": sys_vals.values, "code": raw_codes.values, "description": desc_vals.values})
                                new_rows = new_rows[new_rows["code"].str.len() > 0].reset_index(drop=True)

                                if st.session_state.codelists_df is None:
                                    st.session_state.codelists_df = new_rows
                                else:
                                    st.session_state.codelists_df = pd.concat([st.session_state.codelists_df, new_rows], ignore_index=True)

                                st.success(f"{len(new_rows)} codes imported from '{sheet_name}'.")
                                st.rerun()

    # Display existing code lists
    if st.session_state.codelists_df is not None and not st.session_state.codelists_df.empty:
        df_cl = st.session_state.codelists_df
        conditions = df_cl["condition"].unique()

        st.markdown(f"""
        <div style="margin-top:1.75rem;margin-bottom:0.75rem;font-size:0.68rem;font-weight:800;
                    letter-spacing:0.15em;text-transform:uppercase;color:{JNJ_GRAY_05};">
            {len(df_cl)} codes &nbsp;·&nbsp; {df_cl["condition"].nunique()} conditions
            &nbsp;·&nbsp; {df_cl["coding_system"].nunique()} coding systems
        </div>
        """, unsafe_allow_html=True)

        for cond in conditions:
            cond_df = df_cl[df_cl["condition"] == cond]
            systems  = cond_df["coding_system"].unique()
            badges_html = ""
            for sys in systems:
                count    = len(cond_df[cond_df["coding_system"] == sys])
                color, bg = CODING_SYSTEM_STYLE.get(sys, (JNJ_GRAY_05, JNJ_GRAY_01))
                tmp      = make_temp_table_name(cond, sys)
                badges_html += f"""
                <div class="cl-sys-badge" style="border-color:{color};color:{color};background:{bg};">
                    <span class="cl-sys-name">{sys}</span>
                    <span class="cl-sys-count">&nbsp;{count} codes</span>
                    <span class="cl-sys-tmp">{tmp}</span>
                </div>"""

            st.markdown(f"""
            <div class="cl-condition-card">
                <div class="cl-condition-header">
                    <span class="cl-condition-name">{cond}</span>
                    <span class="cl-condition-total">{len(cond_df)} codes total</span>
                </div>
                <div class="cl-badges-row">{badges_html}</div>
            </div>
            """, unsafe_allow_html=True)

            for sys in systems:
                sys_codes = cond_df[cond_df["coding_system"] == sys]["code"].tolist()
                color, _  = CODING_SYSTEM_STYLE.get(sys, (JNJ_GRAY_05, JNJ_GRAY_01))
                with st.expander(f"{sys}  ·  {len(sys_codes)} codes", expanded=False):
                    display_codes = "   ·   ".join(sys_codes[:60])
                    if len(sys_codes) > 60:
                        display_codes += f"   … +{len(sys_codes)-60} more"
                    st.markdown(f"""
                    <div style="font-family:'Roboto Mono',monospace;font-size:0.78rem;color:{JNJ_GRAY_08};line-height:1.9;padding:0.5rem 0;word-break:break-all;">
                        {display_codes}
                    </div>
                    """, unsafe_allow_html=True)
                    del_col, _ = st.columns([1, 5])
                    with del_col:
                        if st.button("Delete group", key=f"del_{cond}_{sys}".replace(" ", "_"), type="secondary"):
                            mask = ~((df_cl["condition"] == cond) & (df_cl["coding_system"] == sys))
                            st.session_state.codelists_df = df_cl[mask].reset_index(drop=True)
                            st.rerun()

        st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
        if st.button("Clear All Code Lists", key="cl_clear_all", type="secondary"):
            st.session_state.codelists_df = None
            st.session_state.selected_conditions = None
            st.rerun()

        # Category selector
        all_conds = sorted(df_cl["condition"].unique().tolist())
        if st.session_state.selected_conditions is None:
            st.session_state.selected_conditions = all_conds
        else:
            prev  = set(st.session_state.selected_conditions)
            known = [c for c in st.session_state.selected_conditions if c in all_conds]
            new   = [c for c in all_conds if c not in prev]
            st.session_state.selected_conditions = known + new

        st.markdown(f"""
        <div style="margin-top:1.5rem;margin-bottom:0.5rem;">
            <span style="font-size:0.68rem;font-weight:800;letter-spacing:0.15em;text-transform:uppercase;color:{JNJ_GRAY_05};">
                Procedure Categories for Notebook Generation
            </span>
            <span style="font-size:0.72rem;color:{JNJ_GRAY_06};margin-left:0.75rem;">
                Only selected categories will create temp tables and appear in Step 1 SQL
            </span>
        </div>
        """, unsafe_allow_html=True)

        selected_conds = st.multiselect("Select categories", options=all_conds, default=st.session_state.selected_conditions, key="condition_selector", label_visibility="collapsed")
        if selected_conds != st.session_state.selected_conditions:
            st.session_state.selected_conditions = selected_conds

        n_excl = len(all_conds) - len(selected_conds)
        if n_excl > 0:
            excl_names = [c for c in all_conds if c not in selected_conds]
            st.markdown(f'<div style="font-size:0.75rem;color:{JNJ_ORANGE};margin-top:0.3rem;">{n_excl} category excluded: {", ".join(excl_names)}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="font-size:0.75rem;color:{JNJ_GREEN_03};margin-top:0.3rem;">All {len(selected_conds)} categories selected.</div>', unsafe_allow_html=True)


# ── STEP 4: GENERATE NOTEBOOK ─────────────────────────────────────────────────
if st.session_state.steps_df is not None:

    st.markdown(f"""
    <div class="jnj-section-header" style="margin-top:2.5rem;">
      <div class="jnj-step-num">4</div>
      <div class="jnj-section-title">Generate Notebook
        <span>Generates a Databricks SQL attrition notebook and pushes it to <code>/Shared/ads_automation/</code></span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    safe_title = re.sub(r"[^a-zA-Z0-9]+", "_", st.session_state.title).strip("_")[:60] or "study"
    nb_default = st.session_state.nb_path_override or f"{settings.notebook_workspace_root}/{safe_title}_attrition"

    nb_path_input = st.text_input(
        "Databricks workspace path",
        value=nb_default,
        help="Full workspace path where the notebook will be saved.",
        key="nb_path_input",
    )
    if nb_path_input:
        st.session_state.nb_path_override = nb_path_input

    col_gen, col_dl = st.columns([2, 1])
    with col_gen:
        push_btn = st.button("Generate & Push to Databricks", type="primary", use_container_width=True)
    with col_dl:
        if st.session_state.dbx_notebook_sql:
            st.download_button(
                "Download SQL",
                data=st.session_state.dbx_notebook_sql,
                file_name=f"{safe_title}_attrition.sql",
                mime="text/plain",
                use_container_width=True,
            )

    if push_btn:
        src_df = edited_df if edited_df is not None else st.session_state.steps_df
        clean_df = (
            src_df
            .dropna(subset=["description"])
            .pipe(lambda d: d[d["description"].str.strip() != ""])
            .reset_index(drop=True)
        )

        if clean_df.empty:
            st.warning("No valid steps found. Add at least one attrition step.")
        else:
            # Build StepInput list
            step_inputs = [
                StepInput(
                    step_num=i + 1,
                    step_type=row["step_type"],
                    description=row["description"],
                    criterion_type=row.get("criterion_type", "primary"),
                )
                for i, (_, row) in enumerate(clean_df.iterrows())
            ]

            # Build CodeList list
            code_list_inputs = []
            active_cl = st.session_state.codelists_df
            if active_cl is not None and not active_cl.empty and st.session_state.selected_conditions:
                active_cl = active_cl[active_cl["condition"].isin(st.session_state.selected_conditions)]
                for (cond, sys), grp in active_cl.groupby(["condition", "coding_system"]):
                    entries = [CodeEntry(code=r["code"], description=r.get("description", "")) for _, r in grp.iterrows()]
                    code_list_inputs.append(CodeList(condition=cond, coding_system=sys, codes=entries))

            with st.spinner("Generating notebook…"):
                try:
                    notebook_sql, step_sqls = build_notebook(
                        title=st.session_state.title,
                        steps=step_inputs,
                        code_lists=code_list_inputs or None,
                        study_window=st.session_state.study_window or "",
                    )
                    st.session_state.dbx_notebook_sql = notebook_sql
                    st.session_state.steps_df = clean_df
                except Exception as e:
                    st.markdown(f'<div class="jnj-error">Notebook generation failed: {e}</div>', unsafe_allow_html=True)
                    notebook_sql = None

            if notebook_sql:
                nb_path = (st.session_state.nb_path_override or "").strip() or nb_default
                with st.spinner(f"Pushing to {nb_path}…"):
                    try:
                        save_notebook(nb_path, notebook_sql)
                        nb_url = get_notebook_url(nb_path)
                        st.session_state.dbx_notebook_url = nb_url
                        st.session_state.notebook_path    = nb_path

                        cl_count = len(st.session_state.codelists_df) if st.session_state.codelists_df is not None else 0
                        st.markdown(f"""
                        <div class="jnj-success">
                            ✓ Notebook pushed to Databricks &nbsp;·&nbsp; {len(clean_df)} steps &nbsp;·&nbsp; {cl_count} codes<br>
                            <a href="{nb_url}" target="_blank" style="color:#1e5c0a;font-weight:700;">{nb_path}</a>
                        </div>
                        """, unsafe_allow_html=True)

                    except Exception as e:
                        st.markdown(f'<div class="jnj-error">Push failed: {e}</div>', unsafe_allow_html=True)

                # Step preview
                rows_html = ""
                for i, (_, row) in enumerate(clean_df.iterrows(), 1):
                    t   = row["step_type"]
                    css = "inc" if t == "inclusion" else "exc"
                    lbl = "INC" if t == "inclusion" else "EXC"
                    desc = str(row["description"]).strip()
                    rows_html += (
                        f'<div class="jnj-step-row">'
                        f'<span class="jnj-step-index">{i:02d}</span>'
                        f'<span class="jnj-badge jnj-badge-{css}">{lbl}</span>'
                        f'<span class="jnj-step-text">{desc}</span>'
                        f'</div>'
                    )
                st.markdown(f"""
                <div class="jnj-card" style="padding:0;overflow:hidden;margin-top:1rem;">
                    <div style="padding:1rem 1.4rem;border-bottom:1px solid {JNJ_GRAY_02};font-size:0.68rem;font-weight:800;letter-spacing:0.14em;text-transform:uppercase;color:{JNJ_GRAY_05};">
                        Step Preview &nbsp;·&nbsp; {len(clean_df)} steps
                    </div>
                    {rows_html}
                </div>
                """, unsafe_allow_html=True)


st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="jnj-footer">
  <div class="jnj-inner jnj-footer-inner">
    <div class="jnj-footer-left">
        &copy; 2026 <strong>Johnson &amp; Johnson MedTech</strong> &nbsp;·&nbsp;
        Agentic AI Platform &nbsp;·&nbsp; Internal Use Only
    </div>
    <div class="jnj-footer-right">Code Automation v2.0.0</div>
  </div>
</div>
""", unsafe_allow_html=True)
