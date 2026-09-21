# Databricks notebook source
# ════════════════════════════════════════════════════════════════════════════
# RWE ADS Automation Platform — Multi-Notebook Orchestrator
# Fully Databricks-native. No local installs. No VS Code.
#
# HOW TO USE — first run (new study):
#   1. Fill Study Title, Window, Inclusion, Exclusion, Code Lists widgets
#   2. Leave Conversation ID blank  →  starts a fresh Genie conversation
#   3. Prompt = "Generate the full attrition pipeline"
#   4. Click Run All
#   → Creates: /Shared/ads_automation/studies/{title}/01_attrition_pipeline
#
# HOW TO USE — next generation (same study, NEW notebook):
#   1. Keep Study Title the same (same folder)
#   2. Set Conversation ID = the printed CONV_ID from the previous run
#      (or leave blank to start a new Genie conversation)
#   3. Prompt = "/new: feasibility device analysis  →  How many patients
#      had a bariatric device? Break down by device type."
#      ↑ /new: triggers a new notebook named after the text after the colon
#   4. Click Run All
#   → Creates: /Shared/ads_automation/studies/{title}/02_feasibility_device_analysis
#
# COMMAND REFERENCE:
#   /new: <name>   →  save generation to a NEW notebook (next number in folder)
#   /append        →  add to existing latest notebook (default)
#   /summary       →  ask Genie to summarise the whole study so far
# ════════════════════════════════════════════════════════════════════════════

# COMMAND ----------

# MAGIC %md
# MAGIC # 🏥 RWE ADS Automation — Multi-Notebook Orchestrator
# MAGIC ### Each `/new:` command → new numbered notebook in your study folder
# MAGIC ---
# MAGIC | Widget | Required? | Purpose |
# MAGIC |--------|-----------|---------|
# MAGIC | **Study Title** | Always | Display name shown in notebook headers and waterfall |
# MAGIC | **Study Window** | Always | Date range sent to Genie (e.g. `January 2019 to December 2023`) |
# MAGIC | **Notebook Folder Path** | Optional | Full Databricks path where all study notebooks are saved, e.g. `/Shared/oncology/lung_cancer_2024`. Leave blank → auto-created under `/Shared/{Study Title}` |
# MAGIC | **Conversation ID** | Optional | Paste from a previous run to continue the same Genie conversation |
# MAGIC | **Prompt** | Always | What to ask Genie. Start with `/new: <topic>` to route to a new notebook |
# MAGIC | **Inclusion / Exclusion / Code Lists** | First run only | Study criteria — Genie remembers them via Conversation ID after the first run |

# COMMAND ----------

# ── Widgets ───────────────────────────────────────────────────────────────────
dbutils.widgets.removeAll()

dbutils.widgets.text(
    "study_title",
    "My Study Title",
    "Study Title  (display name — used in notebook headers and summary)"
)
dbutils.widgets.text(
    "study_window",
    "January 2019 to December 2023",
    "Study Window  (e.g. January 2019 to December 2023)"
)
dbutils.widgets.text(
    "conversation_id",
    "",
    "Genie Conversation ID  (blank = start new conversation)"
)

# ── Folder path ──────────────────────────────────────────────────────────────
# Full Databricks workspace path where all notebooks for this study are saved.
# Examples:  /Shared/oncology/lung_cancer_2024
#            /Users/jane.smith@company.com/studies/rheumatoid_arthritis
#            /Repos/my-team/rwe-studies/knee_replacement
# Leave blank → falls back to /Shared/{sanitized Study Title}
dbutils.widgets.text(
    "folder_path",
    "",
    "Notebook Folder Path  (full Databricks path — leave blank to auto-create under /Shared)"
)

dbutils.widgets.text(
    "prompt",
    "Generate the full step-by-step attrition pipeline with patient counts at every step.",
    "Prompt  —  Start with  /new: <topic>  to save to a new notebook in the study folder"
)

# ── These only matter on the first run ─────────────────────────────────────
# On subsequent runs Genie remembers the study context via conversation_id.
# Replace with your actual criteria from the study protocol.
dbutils.widgets.text(
    "inclusion_criteria",
    '["Describe inclusion criterion 1", "Describe inclusion criterion 2", "Describe inclusion criterion 3"]',
    "Inclusion Criteria  (JSON array of strings — first run only)"
)
dbutils.widgets.text(
    "exclusion_criteria",
    '["Describe exclusion criterion 1", "Describe exclusion criterion 2"]',
    "Exclusion Criteria  (JSON array of strings — first run only)"
)
dbutils.widgets.text(
    "code_lists",
    '[{"condition": "Condition Name", "coding_system": "ICD-10-PCS", "codes": ["CODE1", "CODE2"]}]',
    "Code Lists  (JSON array — first run only)"
)
dbutils.widgets.text(
    "genie_space_id",
    "",
    "Genie Space ID  (from URL: /genie/rooms/ ► THIS PART ◄ /chats/...)"
)

print("Widgets ready.")

# COMMAND ----------

# ── Imports & context ─────────────────────────────────────────────────────────
import json, re, requests, time, base64

STUDY_TITLE    = dbutils.widgets.get("study_title").strip()
STUDY_WINDOW   = dbutils.widgets.get("study_window").strip()
CONV_ID_IN     = dbutils.widgets.get("conversation_id").strip()
FOLDER_PATH    = dbutils.widgets.get("folder_path").strip().rstrip("/")
RAW_PROMPT     = dbutils.widgets.get("prompt").strip()
INCLUSION      = json.loads(dbutils.widgets.get("inclusion_criteria"))
EXCLUSION      = json.loads(dbutils.widgets.get("exclusion_criteria"))
CODE_LISTS     = json.loads(dbutils.widgets.get("code_lists"))
GENIE_SPACE_ID = dbutils.widgets.get("genie_space_id").strip()

ctx   = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
TOKEN = ctx.apiToken().get()
HOST  = f"https://{ctx.browserHostName().get()}"

GENIE_BASE = f"{HOST}/api/2.0/genie/spaces/{GENIE_SPACE_ID}"
WS_BASE    = f"{HOST}/api/2.0/workspace"
HEADERS    = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# ── Resolve study folder path ─────────────────────────────────────────────────
# If the user gave a path → use it directly.
# If blank → auto-create under /Shared using the study title.
if FOLDER_PATH:
    STUDY_PATH = FOLDER_PATH
else:
    safe_title = re.sub(r"[^a-zA-Z0-9]", "_", STUDY_TITLE).strip("_")[:60]
    STUDY_PATH = f"/Shared/{safe_title}"

print(f"Study title  : {STUDY_TITLE}")
print(f"Notebook folder : {STUDY_PATH}")
print(f"Host         : {HOST}")

# COMMAND ----------

# MAGIC %md ### Step 1 — Parse Command & Decide Notebook Routing

# COMMAND ----------

# ── Parse /new: command from prompt ──────────────────────────────────────────
CMD_NEW     = False
NB_TOPIC    = ""
CLEAN_PROMPT = RAW_PROMPT

# Detect /new: <name> at start of prompt (case-insensitive)
new_match = re.match(r"^/new:\s*(.+?)(?:\s{2,}|\n|→|->|$)(.*)", RAW_PROMPT, re.DOTALL | re.IGNORECASE)
if new_match:
    CMD_NEW      = True
    NB_TOPIC     = new_match.group(1).strip()
    CLEAN_PROMPT = new_match.group(2).strip() or NB_TOPIC  # rest of prompt, or topic as question
elif RAW_PROMPT.lower().startswith("/new"):
    CMD_NEW      = True
    NB_TOPIC     = re.sub(r"^/new[:\s]*", "", RAW_PROMPT, flags=re.IGNORECASE).strip()
    CLEAN_PROMPT = NB_TOPIC

print(f"Command      : {'NEW NOTEBOOK' if CMD_NEW else 'DEFAULT (new or append)'}")
print(f"Topic        : {NB_TOPIC or '(first run — attrition pipeline)'}")
print(f"Clean prompt : {CLEAN_PROMPT[:120]}...")

# COMMAND ----------

# ── Find next notebook number in study folder ─────────────────────────────────
def get_next_notebook_number(study_path: str) -> int:
    """List existing notebooks in the study folder and return next index."""
    try:
        r = requests.get(
            f"{WS_BASE}/list",
            headers=HEADERS,
            params={"path": study_path},
            timeout=15
        )
        if r.status_code == 404:
            return 1  # folder doesn't exist yet → first notebook
        r.raise_for_status()
        objects = r.json().get("objects", [])
        nums = []
        for obj in objects:
            m = re.match(r".*?/(\d+)_", obj.get("path", ""))
            if m:
                nums.append(int(m.group(1)))
        return max(nums) + 1 if nums else 1
    except Exception as e:
        print(f"Note: could not list folder ({e}). Defaulting to 01.")
        return 1

NB_NUM = get_next_notebook_number(STUDY_PATH)

# Build notebook name
if NB_TOPIC:
    safe_topic = re.sub(r"[^a-zA-Z0-9]", "_", NB_TOPIC).strip("_")[:50]
else:
    safe_topic = "attrition_pipeline"

NB_NAME = f"{NB_NUM:02d}_{safe_topic}"
NB_PATH = f"{STUDY_PATH}/{NB_NAME}"

print(f"Notebook     : {NB_PATH}")

# COMMAND ----------

# MAGIC %md ### Step 2 — Build Prompt & Ask Genie

# COMMAND ----------

# ── Build full Genie prompt ───────────────────────────────────────────────────
def build_first_run_prompt():
    """Full criteria prompt for the first conversation turn."""
    lines = [f"Study: {STUDY_TITLE}", ""]
    if STUDY_WINDOW:
        lines += [f"Study window: {STUDY_WINDOW}", ""]
    lines += ["Inclusion Criteria:"]
    for i, c in enumerate(INCLUSION, 1):
        lines.append(f"  {i}. {c}")
    lines += ["", "Exclusion Criteria:"]
    for i, c in enumerate(EXCLUSION, 1):
        lines.append(f"  {i}. {c}")
    if CODE_LISTS:
        lines += ["", "Code Lists:"]
        for cl in CODE_LISTS:
            codes_str = ", ".join(str(c) for c in cl.get("codes", [])[:40])
            extra     = f" (+{len(cl['codes'])-40} more)" if len(cl.get("codes",[])) > 40 else ""
            lines.append(f"  {cl['condition']} ({cl['coding_system']}): {codes_str}{extra}")
    lines += [
        "",
        CLEAN_PROMPT,
        "",
        "Requirements:",
        "  - CREATE OR REPLACE TEMPORARY TABLE per attrition step",
        "  - Step 1 = index procedure identification",
        "  - Each step filters from the previous temp table",
        "  - End with SELECT COUNT(*) at each step",
    ]
    return "\n".join(lines)

# Is this a continuation of an existing conversation?
IS_CONTINUATION = bool(CONV_ID_IN)

if IS_CONTINUATION:
    GENIE_PROMPT = CLEAN_PROMPT
    print(f"Continuing conversation: {CONV_ID_IN}")
else:
    GENIE_PROMPT = build_first_run_prompt()
    print("New conversation — full criteria prompt built.")

print(f"Prompt length: {len(GENIE_PROMPT)} chars")

# COMMAND ----------

# ── Call Genie ────────────────────────────────────────────────────────────────
if IS_CONTINUATION:
    # Send message in existing conversation
    resp = requests.post(
        f"{GENIE_BASE}/conversations/{CONV_ID_IN}/messages",
        headers=HEADERS,
        json={"content": GENIE_PROMPT},
        timeout=60
    )
else:
    # Start brand-new conversation
    resp = requests.post(
        f"{GENIE_BASE}/start-conversation",
        headers=HEADERS,
        json={"content": GENIE_PROMPT},
        timeout=60
    )

resp.raise_for_status()
data    = resp.json()
CONV_ID = data.get("conversation_id", CONV_ID_IN)
MSG_ID  = data.get("message_id") or data.get("id", "")

GENIE_LINK = f"{HOST}/genie/rooms/{GENIE_SPACE_ID}/chats/{CONV_ID}"

print(f"\n✓ Genie conversation active")
print(f"  conversation_id : {CONV_ID}")
print(f"  message_id      : {MSG_ID}")
print(f"  Genie URL       : {GENIE_LINK}")
print(f"\n  ⬇  Copy conversation_id for your NEXT run:")
print(f"  {CONV_ID}")

# COMMAND ----------

# MAGIC %md ### Step 3 — Wait for Genie

# COMMAND ----------

# ── Poll until COMPLETED ──────────────────────────────────────────────────────
MAX_WAIT  = 300
INTERVAL  = 5
GENIE_MSG = None

print(f"Polling Genie... (max {MAX_WAIT}s)")
print(f"{'Elapsed':>8}   Status")
print("-" * 28)

for elapsed in range(0, MAX_WAIT, INTERVAL):
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
        raise RuntimeError(f"Genie ended with: {status}")
    time.sleep(INTERVAL)
else:
    raise TimeoutError("Genie did not respond in 5 minutes.")

# COMMAND ----------

# MAGIC %md ### Step 4 — Extract SQL

# COMMAND ----------

# ── Extract SQL + explanation ─────────────────────────────────────────────────
EXPLANATION   = ""
GENERATED_SQL = ""

for att in (GENIE_MSG or {}).get("attachments", []):
    if att.get("type") == "text":
        EXPLANATION = att.get("content", "")
        break

# Primary: query-result endpoint
try:
    r = requests.get(
        f"{GENIE_BASE}/conversations/{CONV_ID}/messages/{MSG_ID}/query-result",
        headers=HEADERS, timeout=30
    )
    if r.status_code == 200:
        stmt          = r.json().get("statement_response", {})
        GENERATED_SQL = stmt.get("statement", "").strip()
except Exception as e:
    print(f"query-result: {e}")

# Fallback: SQL block inside explanation
if not GENERATED_SQL and EXPLANATION:
    m = re.search(r"```sql\n(.*?)```", EXPLANATION, re.DOTALL | re.IGNORECASE)
    if m:
        GENERATED_SQL = m.group(1).strip()
        print("SQL extracted from explanation text.")

print("=" * 70)
print("GENIE EXPLANATION:")
print(EXPLANATION or "(none)")
print("=" * 70)
print("GENERATED SQL (first 1000 chars):")
print((GENERATED_SQL or "(none)")[:1000])
print("=" * 70)

# COMMAND ----------

# MAGIC %md ### Step 5 — Execute SQL + Waterfall

# COMMAND ----------

# ── Run SQL ───────────────────────────────────────────────────────────────────
STEP_TABLES = []

if GENERATED_SQL:
    print(f"Executing SQL ({len(GENERATED_SQL)} chars)...")
    try:
        result_df = spark.sql(GENERATED_SQL)
        display(result_df)
    except Exception as e:
        print(f"SQL error: {e}")
        print(f"Open Genie to debug: {GENIE_LINK}")

    # Find temp tables for waterfall
    STEP_TABLES = re.findall(
        r"CREATE\s+OR\s+REPLACE\s+TEMPORARY\s+TABLE\s+(\w+)",
        GENERATED_SQL, re.IGNORECASE
    )
else:
    print("No SQL generated.")
    print(f"Full response in Genie: {GENIE_LINK}")

# COMMAND ----------

# ── Attrition Waterfall ───────────────────────────────────────────────────────
if STEP_TABLES:
    print(f"\n{'':=<62}")
    print(f"  ATTRITION WATERFALL — {STUDY_TITLE}")
    print(f"  Section: {NB_TOPIC or 'Attrition Pipeline'}")
    print(f"{'':=<62}")
    print(f"  {'Step':<42} {'N Patients':>12}  {'Drop':>10}")
    print(f"  {'-'*42} {'-'*12}  {'-'*10}")
    prev = None
    for i, tbl in enumerate(STEP_TABLES, 1):
        try:
            cnt  = spark.sql(f"SELECT COUNT(*) AS n FROM {tbl}").collect()[0]["n"]
            drop = f"−{prev - cnt:,}" if prev is not None else "—"
            print(f"  {i}. {tbl:<40} {cnt:>12,}  {drop:>10}")
            prev = cnt
        except Exception as e:
            print(f"  {i}. {tbl:<40} (error: {e})")
    print(f"{'':=<62}")
    if prev is not None:
        print(f"  Final cohort: {prev:,} patients")

# COMMAND ----------

# MAGIC %md ### Step 6 — Save to Notebook

# COMMAND ----------

# ── Ensure study folder exists ────────────────────────────────────────────────
requests.post(
    f"{WS_BASE}/mkdirs",
    headers=HEADERS,
    json={"path": STUDY_PATH}
)
print(f"Study folder: {STUDY_PATH}")

# COMMAND ----------

# ── Build and push the section notebook ──────────────────────────────────────
sql_safe = (GENERATED_SQL or "# No SQL generated").replace("\\", "\\\\").replace('"""', "'''")

waterfall_lines = ""
if STEP_TABLES:
    waterfall_lines = "\n".join(
        f'        ("{t}", {i}),' for i, t in enumerate(STEP_TABLES, 1)
    )

nb_source = f'''# Databricks notebook source
# ════════════════════════════════════════════════════════════════════════
# Study   : {STUDY_TITLE}
# Section : {NB_TOPIC or "Attrition Pipeline"}
# Notebook: {NB_NAME}
# Genie   : {GENIE_LINK}
# ════════════════════════════════════════════════════════════════════════

# COMMAND ----------

# MAGIC %md
# MAGIC # {STUDY_TITLE}
# MAGIC ## {NB_TOPIC or "Attrition Pipeline"}
# MAGIC **Study window:** {STUDY_WINDOW}
# MAGIC
# MAGIC **Genie conversation:** [{GENIE_LINK}]({GENIE_LINK})
# MAGIC
# MAGIC *Auto-generated by RWE ADS Automation Platform*

# COMMAND ----------

# Section metadata
STUDY_TITLE  = """{STUDY_TITLE}"""
STUDY_WINDOW = """{STUDY_WINDOW}"""
NB_SECTION   = """{NB_TOPIC or "Attrition Pipeline"}"""
GENIE_LINK   = """{GENIE_LINK}"""

# COMMAND ----------

# MAGIC %md ### Genie Explanation
# MAGIC
# MAGIC {EXPLANATION.replace(chr(10), chr(10) + "# MAGIC ") if EXPLANATION else "_No explanation text captured._"}

# COMMAND ----------

# Attrition SQL — generated by Genie Agent
# Re-run orchestrator to regenerate or continue conversation in Genie.

{GENERATED_SQL or "# No SQL was captured — re-run 00_ADS_Orchestrator"}

# COMMAND ----------

# Attrition Waterfall
import re as _re

_sql = """{sql_safe[:8000]}"""
_tables = _re.findall(
    r"CREATE\\s+OR\\s+REPLACE\\s+TEMPORARY\\s+TABLE\\s+(\\w+)",
    _sql, _re.IGNORECASE
)

if _tables:
    print(f"\\n{{\'=\'*60}}")
    print(f"  WATERFALL — {STUDY_TITLE} / {NB_TOPIC or 'Attrition'}")
    print(f"{{\'=\'*60}}")
    _prev = None
    for _i, _t in enumerate(_tables, 1):
        try:
            _cnt  = spark.sql(f"SELECT COUNT(*) AS n FROM {{_t}}").collect()[0]["n"]
            _drop = f"−{{_prev - _cnt:,}}" if _prev is not None else "—"
            print(f"  {{_i}}. {{_t:<40}} {{_cnt:>12,}}  {{_drop}}")
            _prev = _cnt
        except Exception as _e:
            print(f"  {{_i}}. {{_t:<40}} (error: {{_e}})")
    if _prev is not None:
        print(f"\\n  Final: {{_prev:,}} patients")
else:
    print("No temp tables in SQL. Check the SQL cell above.")
'''

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

NB_URL     = f"{HOST}/#workspace{NB_PATH}"
FOLDER_URL = f"{HOST}/#workspace{STUDY_PATH}"

print(f"✓ Notebook saved: {NB_PATH}")

# COMMAND ----------

# MAGIC %md ### ✅ Done

# COMMAND ----------

# ── Summary card ─────────────────────────────────────────────────────────────
displayHTML(f"""
<div style="font-family:Inter,sans-serif;padding:28px 32px;background:#f9f8f6;
            border-radius:14px;border-left:6px solid #eb1700;max-width:740px;
            box-shadow:0 2px 12px rgba(0,0,0,0.07);">

  <div style="font-size:0.6rem;font-weight:800;letter-spacing:0.22em;
              text-transform:uppercase;color:#eb1700;margin-bottom:10px;">
    ADS Automation Complete
  </div>

  <div style="font-size:1.25rem;font-weight:800;color:#1a1410;margin-bottom:4px;">
    {STUDY_TITLE}
  </div>
  <div style="font-size:0.95rem;font-weight:600;color:#eb1700;margin-bottom:12px;">
    {NB_TOPIC or "Attrition Pipeline"}
  </div>
  <div style="font-size:0.82rem;color:#81766f;margin-bottom:22px;
              font-family:'Roboto Mono',monospace;">
    {NB_NAME} &nbsp;·&nbsp; {len(STEP_TABLES)} steps &nbsp;·&nbsp; {STUDY_WINDOW}
  </div>

  <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px;">
    <a href="{NB_URL}" target="_blank"
       style="background:#eb1700;color:#fff;padding:10px 22px;border-radius:7px;
              text-decoration:none;font-weight:700;font-size:0.85rem;">
      📓 Open This Notebook →
    </a>
    <a href="{FOLDER_URL}" target="_blank"
       style="background:#1a1410;color:#fff;padding:10px 22px;border-radius:7px;
              text-decoration:none;font-weight:700;font-size:0.85rem;">
      📁 Open Study Folder →
    </a>
    <a href="{GENIE_LINK}" target="_blank"
       style="background:#0f68b2;color:#fff;padding:10px 22px;border-radius:7px;
              text-decoration:none;font-weight:700;font-size:0.85rem;">
      🤖 Continue in Genie →
    </a>
  </div>

  <div style="background:#ffffff;border:1px solid #eae8e5;border-radius:8px;
              padding:14px 18px;font-size:0.78rem;color:#1a1410;line-height:1.9;">
    <div style="font-weight:800;letter-spacing:0.1em;text-transform:uppercase;
                font-size:0.6rem;color:#81766f;margin-bottom:8px;">
      Next Generation → New Notebook
    </div>
    <div>1. Copy this conversation ID:</div>
    <div style="font-family:'Roboto Mono',monospace;background:#f5f4f2;
                padding:6px 10px;border-radius:4px;margin:6px 0 10px 0;
                color:#eb1700;font-weight:700;font-size:0.82rem;">
      {CONV_ID}
    </div>
    <div>2. Paste it in the <strong>Conversation ID</strong> widget</div>
    <div>3. Set <strong>Prompt</strong> to:
         <code style="background:#f5f4f2;padding:2px 6px;border-radius:3px;">
           /new: feasibility analysis  →  Your next question for Genie here
         </code>
    </div>
    <div>4. Click <strong>Run All</strong></div>
  </div>

  <div style="margin-top:14px;font-size:0.68rem;color:#a39992;">
    Folder: {STUDY_PATH}
  </div>
</div>
""")
