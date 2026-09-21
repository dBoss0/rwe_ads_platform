# Databricks notebook source
# ════════════════════════════════════════════════════════════════════════════
# RWE ADS Automation Platform — Orchestrator
# Fully Databricks-native.  No local installs.  No VS Code.
#
# HOW TO USE:
#   1. Fill the widgets at the top of this notebook
#   2. Click "Run All"
#   3. Genie Agent generates the attrition SQL
#   4. SQL is executed live — waterfall counts printed
#   5. A study-specific notebook is auto-created in your workspace
#   6. Click the links at the bottom to open notebook or Genie chat
#
# EACH USER / EACH STUDY → runs this once → gets their own output notebook
# ════════════════════════════════════════════════════════════════════════════

# COMMAND ----------

# MAGIC %md
# MAGIC # 🏥 RWE ADS Automation Platform
# MAGIC ### Cohort Attrition · Powered by Genie Agent
# MAGIC ---
# MAGIC **Instructions**
# MAGIC 1. Fill the widgets above (study title, criteria, codes)
# MAGIC 2. Click **Run All**
# MAGIC 3. Genie generates SQL → executed live → notebook auto-created
# MAGIC
# MAGIC > Each run creates a separate study notebook under `/Shared/ads_automation/studies/`

# COMMAND ----------

# ── Widgets — fill these before running ──────────────────────────────────────
dbutils.widgets.removeAll()

dbutils.widgets.text(
    "study_title",
    "Bariatric Surgery Comparative Effectiveness Study",
    "Study Title"
)
dbutils.widgets.text(
    "study_window",
    "January 2016 to December 2022",
    "Study Window"
)
dbutils.widgets.text(
    "output_folder",
    "/Shared/ads_automation/studies",
    "Output Folder (workspace path)"
)
# Paste criteria as a JSON array of strings
dbutils.widgets.text(
    "inclusion_criteria",
    '["Inpatient admission with primary ICD-10-PCS procedure code for surgery of interest between Jan 2016 and Dec 2022", "Age 18 years or older at index admission", "Hospital contributes data for at least 90 days post-discharge", "Known gender (M or F)", "Publish type = Comparative Valid (CV)"]',
    "Inclusion Criteria (JSON array)"
)
dbutils.widgets.text(
    "exclusion_criteria",
    '["Zero or negative episode/supply/inpatient room and board costs", "Missing data (patients with missing data will not be included)"]',
    "Exclusion Criteria (JSON array)"
)
# Code lists: list of {condition, coding_system, codes:[...]}
dbutils.widgets.text(
    "code_lists",
    '[{"condition": "RYGB", "coding_system": "ICD-10-PCS", "codes": ["0D160ZA","0D160Z3","0D160Z4"]}, {"condition": "Sleeve Gastrectomy", "coding_system": "ICD-10-PCS", "codes": ["0DB64Z3","0DB60Z3"]}, {"condition": "BPD Duodenal Switch", "coding_system": "ICD-10-PCS", "codes": ["0D194ZA","0D190ZA"]}]',
    "Code Lists (JSON)"
)

print("Widgets ready. Proceed to next cell.")

# COMMAND ----------

# ── Read widget inputs ────────────────────────────────────────────────────────
import json, re, requests, time, base64

STUDY_TITLE    = dbutils.widgets.get("study_title").strip()
STUDY_WINDOW   = dbutils.widgets.get("study_window").strip()
OUTPUT_FOLDER  = dbutils.widgets.get("output_folder").strip().rstrip("/")
INCLUSION      = json.loads(dbutils.widgets.get("inclusion_criteria"))
EXCLUSION      = json.loads(dbutils.widgets.get("exclusion_criteria"))
CODE_LISTS     = json.loads(dbutils.widgets.get("code_lists"))

GENIE_SPACE_ID = "01f1ad05e9a811de88b3f1c49399c3c1"

# Databricks context — host and token from notebook session (no secrets needed)
ctx   = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
TOKEN = ctx.apiToken().get()
HOST  = f"https://{ctx.browserHostName().get()}"

GENIE_BASE = f"{HOST}/api/2.0/genie/spaces/{GENIE_SPACE_ID}"
WS_BASE    = f"{HOST}/api/2.0/workspace"
HEADERS    = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

print(f"Host         : {HOST}")
print(f"Study        : {STUDY_TITLE}")
print(f"Window       : {STUDY_WINDOW}")
print(f"Inclusion    : {len(INCLUSION)} steps")
print(f"Exclusion    : {len(EXCLUSION)} steps")
print(f"Code groups  : {len(CODE_LISTS)}")
print(f"Output folder: {OUTPUT_FOLDER}")

# COMMAND ----------

# MAGIC %md ### Step 1 — Build Prompt & Send to Genie Agent

# COMMAND ----------

# ── Build attrition prompt ────────────────────────────────────────────────────
def build_prompt():
    lines = [f"Cohort Attrition SQL for: {STUDY_TITLE}", ""]
    if STUDY_WINDOW:
        lines += [f"Study window: {STUDY_WINDOW}", ""]

    lines += ["Inclusion Criteria:"]
    for i, c in enumerate(INCLUSION, 1):
        lines.append(f"  {i}. {c}")

    lines += ["", "Exclusion Criteria:"]
    for i, c in enumerate(EXCLUSION, 1):
        lines.append(f"  {i}. {c}")

    if CODE_LISTS:
        lines += ["", "Procedure / Diagnosis Code Lists:"]
        for cl in CODE_LISTS:
            codes = cl.get("codes", [])
            codes_str = ", ".join(str(c) for c in codes[:40])
            extra = f" ... +{len(codes)-40} more" if len(codes) > 40 else ""
            lines.append(f"  {cl['condition']} ({cl['coding_system']}): {codes_str}{extra}")

    lines += [
        "",
        "Requirements:",
        "  - Generate the full step-by-step attrition SQL pipeline",
        "  - Use CREATE OR REPLACE TEMPORARY TABLE for each step",
        "  - Step 1 = index procedure identification using the codes above",
        "  - Each subsequent step filters from the previous temp table",
        "  - End each step with SELECT COUNT(*) to show patient count",
        "  - Use Premier PHD tables: pat, paticd_proc, paticd_diag, patcpt, prov_enrollment",
    ]
    return "\n".join(lines)

PROMPT = build_prompt()
print(f"Prompt built — {len(PROMPT)} characters")
print("-" * 60)
print(PROMPT[:500] + "..." if len(PROMPT) > 500 else PROMPT)

# COMMAND ----------

# ── Send to Genie Agent ───────────────────────────────────────────────────────
resp = requests.post(
    f"{GENIE_BASE}/start-conversation",
    headers=HEADERS,
    json={"content": PROMPT},
    timeout=60
)
resp.raise_for_status()

data    = resp.json()
CONV_ID = data["conversation_id"]
MSG_ID  = data["message_id"]

GENIE_LINK = f"{HOST}/genie/rooms/{GENIE_SPACE_ID}/chats/{CONV_ID}"

print("✓ Genie conversation started")
print(f"  conversation_id : {CONV_ID}")
print(f"  message_id      : {MSG_ID}")
print(f"  Genie URL       : {GENIE_LINK}")

# COMMAND ----------

# MAGIC %md ### Step 2 — Wait for Genie to Generate SQL

# COMMAND ----------

# ── Poll until COMPLETED ──────────────────────────────────────────────────────
MAX_WAIT_SEC  = 300
POLL_INTERVAL = 5
GENIE_MSG     = None

print("Polling Genie (up to 5 minutes)...")
print(f"{'Elapsed':>8}   Status")
print("-" * 30)

for elapsed in range(0, MAX_WAIT_SEC, POLL_INTERVAL):
    r      = requests.get(
        f"{GENIE_BASE}/conversations/{CONV_ID}/messages/{MSG_ID}",
        headers=HEADERS, timeout=30
    )
    r.raise_for_status()
    status = r.json().get("status", "PENDING")
    print(f"  {elapsed:>4}s   {status}")

    if status == "COMPLETED":
        GENIE_MSG = r.json()
        print("\n✓ Genie finished")
        break
    elif status in ("FAILED", "CANCELLED"):
        raise RuntimeError(f"Genie ended with status: {status}. Check Genie space.")

    time.sleep(POLL_INTERVAL)
else:
    raise TimeoutError("Genie did not respond within 5 minutes. Try again.")

# COMMAND ----------

# MAGIC %md ### Step 3 — Extract SQL from Genie Response

# COMMAND ----------

# ── Extract SQL ───────────────────────────────────────────────────────────────
GENERATED_SQL = ""
EXPLANATION   = ""

# Get explanation / narrative text from Genie attachments
for att in (GENIE_MSG or {}).get("attachments", []):
    if att.get("type") == "text":
        EXPLANATION = att.get("content", "")
        break

# Primary: get SQL from query-result endpoint
try:
    r = requests.get(
        f"{GENIE_BASE}/conversations/{CONV_ID}/messages/{MSG_ID}/query-result",
        headers=HEADERS, timeout=30
    )
    if r.status_code == 200:
        stmt         = r.json().get("statement_response", {})
        GENERATED_SQL = stmt.get("statement", "").strip()
except Exception as e:
    print(f"query-result not available: {e}")

# Fallback: extract ```sql ... ``` block from explanation text
if not GENERATED_SQL and EXPLANATION:
    m = re.search(r"```sql\n(.*?)```", EXPLANATION, re.DOTALL | re.IGNORECASE)
    if m:
        GENERATED_SQL = m.group(1).strip()
        print("SQL extracted from explanation text (fallback).")

# Show results
print("=" * 70)
print("GENIE EXPLANATION:")
print(EXPLANATION or "(none)")
print("=" * 70)
print("GENERATED SQL:")
print(GENERATED_SQL if GENERATED_SQL else "(No SQL extracted — see Genie link below)")
print("=" * 70)
print(f"Genie conversation: {GENIE_LINK}")

# COMMAND ----------

# MAGIC %md ### Step 4 — Execute SQL & Show Attrition Waterfall

# COMMAND ----------

# ── Execute SQL ───────────────────────────────────────────────────────────────
if not GENERATED_SQL:
    print("No SQL to execute.")
    print(f"Open Genie to view the full response: {GENIE_LINK}")
else:
    print(f"Executing SQL ({len(GENERATED_SQL)} chars)...")
    try:
        result_df = spark.sql(GENERATED_SQL)
        display(result_df)
    except Exception as e:
        print(f"SQL execution error: {e}")
        print("Tip: Open Genie and ask it to fix the error.")
        print(f"Genie: {GENIE_LINK}")

# COMMAND ----------

# ── Attrition Waterfall ───────────────────────────────────────────────────────
if GENERATED_SQL:
    tables = re.findall(
        r"CREATE\s+OR\s+REPLACE\s+TEMPORARY\s+TABLE\s+(\w+)",
        GENERATED_SQL, re.IGNORECASE
    )

    if tables:
        print(f"\n{'':=<60}")
        print(f"  ATTRITION WATERFALL — {STUDY_TITLE}")
        print(f"{'':=<60}")
        print(f"  {'Step':<42} {'N Patients':>12}  {'Drop':>10}")
        print(f"  {'-'*42} {'-'*12}  {'-'*10}")

        prev_count = None
        for i, tbl in enumerate(tables, 1):
            try:
                cnt  = spark.sql(f"SELECT COUNT(*) AS n FROM {tbl}").collect()[0]["n"]
                drop = f"−{prev_count - cnt:,}" if prev_count is not None else "—"
                print(f"  {i}. {tbl:<40} {cnt:>12,}  {drop:>10}")
                prev_count = cnt
            except Exception as e:
                print(f"  {i}. {tbl:<40} (unavailable: {e})")

        print(f"{'':=<60}")
        print(f"  Final cohort: {prev_count:,} patients" if prev_count else "")
    else:
        print("No temp tables detected in SQL — check the generated SQL above.")

# COMMAND ----------

# MAGIC %md ### Step 5 — Auto-Create Study Notebook

# COMMAND ----------

# ── Build and push study-specific notebook ────────────────────────────────────
safe_title = re.sub(r"[^a-zA-Z0-9]", "_", STUDY_TITLE).strip("_")[:60]
NB_PATH    = f"{OUTPUT_FOLDER}/{safe_title}_attrition"

# Escape SQL for embedding inside Python string
sql_escaped = (GENERATED_SQL or "# No SQL generated — re-run orchestrator") \
    .replace("\\", "\\\\").replace('"', '\\"')

nb_source = f'''# Databricks notebook source
# ════════════════════════════════════════════════════════
# {STUDY_TITLE}
# Auto-generated by RWE ADS Automation Platform
# Genie conversation: {GENIE_LINK}
# ════════════════════════════════════════════════════════

# COMMAND ----------

# MAGIC %md
# MAGIC # {STUDY_TITLE}
# MAGIC **Study window:** {STUDY_WINDOW}
# MAGIC **Generated by:** RWE ADS Automation Platform (Genie Agent)
# MAGIC **Genie conversation:** [{GENIE_LINK}]({GENIE_LINK})

# COMMAND ----------

# Study metadata
STUDY_TITLE  = """{STUDY_TITLE}"""
STUDY_WINDOW = """{STUDY_WINDOW}"""
GENIE_LINK   = """{GENIE_LINK}"""

INCLUSION_CRITERIA = {json.dumps(INCLUSION, indent=2)}

EXCLUSION_CRITERIA = {json.dumps(EXCLUSION, indent=2)}

CODE_LISTS = {json.dumps(CODE_LISTS, indent=2)}

print(f"Study  : {{STUDY_TITLE}}")
print(f"Window : {{STUDY_WINDOW}}")

# COMMAND ----------

# MAGIC %md ### Genie Explanation
# MAGIC
# MAGIC {EXPLANATION.replace(chr(10), chr(10) + "# MAGIC ") if EXPLANATION else "_No explanation captured._"}

# COMMAND ----------

# Attrition SQL — generated by Genie Agent
# Do not edit manually. Re-run the orchestrator to regenerate.

{GENERATED_SQL or "# No SQL was captured — re-run 00_ADS_Orchestrator"}

# COMMAND ----------

# Attrition Waterfall — patient counts at each step
import re

tables = re.findall(
    r"CREATE\\s+OR\\s+REPLACE\\s+TEMPORARY\\s+TABLE\\s+(\\w+)",
    """{sql_escaped}""",
    re.IGNORECASE
)

if tables:
    print(f"\\n{{\'=\'*60}}")
    print(f"  ATTRITION WATERFALL — {STUDY_TITLE}")
    print(f"{{\'=\'*60}}")
    prev = None
    for i, t in enumerate(tables, 1):
        try:
            cnt  = spark.sql(f"SELECT COUNT(*) AS n FROM {{t}}").collect()[0]["n"]
            drop = f"−{{prev - cnt:,}}" if prev else "—"
            print(f"  {{i}}. {{t:<40}} {{cnt:>12,}}  {{drop}}")
            prev = cnt
        except Exception as e:
            print(f"  {{i}}. {{t:<40}} (unavailable: {{e}})")
    if prev:
        print(f"\\n  Final cohort: {{prev:,}} patients")
else:
    print("No temp tables found. Check the SQL cell above.")
'''

# Ensure output folder exists
requests.post(f"{HOST}/api/2.0/workspace/mkdirs", headers=HEADERS,
              json={"path": OUTPUT_FOLDER})

# Push notebook
encoded = base64.b64encode(nb_source.encode("utf-8")).decode("ascii")
r = requests.post(
    f"{WS_BASE}/import",
    headers=HEADERS,
    json={
        "path":      NB_PATH,
        "format":    "SOURCE",
        "language":  "PYTHON",
        "content":   encoded,
        "overwrite": True,
    }
)
r.raise_for_status()

NB_URL = f"{HOST}/#workspace{NB_PATH}"
print(f"✓ Study notebook created: {NB_PATH}")

# COMMAND ----------

# MAGIC %md ### ✅ Done

# COMMAND ----------

# ── Summary + clickable links ─────────────────────────────────────────────────
displayHTML(f"""
<div style="font-family:Inter,sans-serif;padding:24px;background:#f9f8f6;
            border-radius:12px;border-left:5px solid #eb1700;max-width:700px;">
  <div style="font-size:0.65rem;font-weight:800;letter-spacing:0.2em;
              text-transform:uppercase;color:#eb1700;margin-bottom:12px;">
    ADS Automation Complete
  </div>
  <div style="font-size:1.2rem;font-weight:700;color:#1a1410;margin-bottom:6px;">
    {STUDY_TITLE}
  </div>
  <div style="font-size:0.85rem;color:#81766f;margin-bottom:20px;">
    {len(INCLUSION)} inclusion steps &nbsp;·&nbsp;
    {len(EXCLUSION)} exclusion steps &nbsp;·&nbsp;
    {len(CODE_LISTS)} code groups &nbsp;·&nbsp;
    {STUDY_WINDOW}
  </div>
  <div style="display:flex;gap:12px;flex-wrap:wrap;">
    <a href="{NB_URL}" target="_blank"
       style="background:#eb1700;color:#fff;padding:10px 20px;border-radius:6px;
              text-decoration:none;font-weight:700;font-size:0.85rem;">
      📓 Open Study Notebook →
    </a>
    <a href="{GENIE_LINK}" target="_blank"
       style="background:#0f68b2;color:#fff;padding:10px 20px;border-radius:6px;
              text-decoration:none;font-weight:700;font-size:0.85rem;">
      🤖 Open in Genie →
    </a>
  </div>
  <div style="margin-top:16px;font-size:0.72rem;color:#a39992;">
    Notebook path: {NB_PATH}
  </div>
</div>
""")
