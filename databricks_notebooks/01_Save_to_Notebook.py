# Databricks notebook source
# ════════════════════════════════════════════════════════════════════════════
# RWE ADS — Save Genie Conversation to Study Notebook
#
# USE THIS after you have finished chatting in the Genie Agent UI.
#
# WORKFLOW:
#   1. Chat in Genie UI until you're happy with the SQL and results
#   2. Copy the Conversation ID from the Genie URL:
#        https://.../genie/rooms/.../chats/ ▶ abc123xyz ◀
#   3. Fill the 3 widgets below
#   4. Click Run All
#   → A clean study notebook is created at your folder path
#
# For a NEW section (e.g. feasibility after attrition):
#   - Continue chatting in the SAME Genie conversation
#   - Change Notebook Name to the new section (e.g. 02_feasibility)
#   - Run All again → second notebook created in the same folder
# ════════════════════════════════════════════════════════════════════════════

# COMMAND ----------

# MAGIC %md
# MAGIC # 💾 Save Genie Conversation → Study Notebook
# MAGIC
# MAGIC **Step 1:** Finish chatting in the Genie Agent UI
# MAGIC
# MAGIC **Step 2:** Copy the Conversation ID from the Genie URL bar:
# MAGIC ```
# MAGIC https://...cloud.databricks.com/genie/rooms/.../chats/ ► COPY THIS ◄
# MAGIC ```
# MAGIC
# MAGIC **Step 3:** Fill the widgets below and click **Run All**
# MAGIC
# MAGIC | Widget | What to fill |
# MAGIC |--------|-------------|
# MAGIC | **Conversation ID** | Paste from Genie URL |
# MAGIC | **Study Title** | Display name for notebook headers |
# MAGIC | **Notebook Folder Path** | Full Databricks path, e.g. `/Shared/oncology/lung_cancer_2024` |
# MAGIC | **Notebook Name** | e.g. `01_attrition_pipeline` or `02_feasibility` |
# MAGIC | **Message ID** | Leave blank — auto-finds the latest SQL. Fill only if you want a specific message. |

# COMMAND ----------

# ── Widgets ───────────────────────────────────────────────────────────────────
dbutils.widgets.removeAll()

dbutils.widgets.text(
    "conversation_id",
    "",
    "Conversation ID  (from Genie URL — required)"
)
dbutils.widgets.text(
    "study_title",
    "My Study",
    "Study Title  (shown in notebook headers)"
)
dbutils.widgets.text(
    "folder_path",
    "",
    "Notebook Folder Path  (e.g. /Shared/oncology/lung_cancer_2024)"
)
dbutils.widgets.text(
    "notebook_name",
    "01_attrition_pipeline",
    "Notebook Name  (e.g. 01_attrition_pipeline, 02_feasibility)"
)
dbutils.widgets.text(
    "message_id",
    "",
    "Message ID  (optional — blank = auto-detect latest SQL from conversation)"
)
dbutils.widgets.text(
    "genie_space_id",
    "",
    "Genie Space ID  (from URL: /genie/rooms/ ► THIS PART ◄ /chats/...)"
)

print("Widgets ready.")

# COMMAND ----------

# ── Imports & auth ────────────────────────────────────────────────────────────
import json, re, requests, base64

CONV_ID        = dbutils.widgets.get("conversation_id").strip()
STUDY_TITLE    = dbutils.widgets.get("study_title").strip()
FOLDER_PATH    = dbutils.widgets.get("folder_path").strip().rstrip("/")
NB_NAME        = dbutils.widgets.get("notebook_name").strip()
MSG_ID_IN      = dbutils.widgets.get("message_id").strip()
GENIE_SPACE_ID = dbutils.widgets.get("genie_space_id").strip()

if not CONV_ID:
    raise ValueError("Conversation ID is required. Copy it from the Genie URL.")
if not FOLDER_PATH:
    raise ValueError("Notebook Folder Path is required. E.g. /Shared/oncology/my_study")
if not NB_NAME:
    raise ValueError("Notebook Name is required. E.g. 01_attrition_pipeline")
if not GENIE_SPACE_ID:
    raise ValueError("Genie Space ID is required. Copy it from /genie/rooms/ ► HERE ◄ /chats/...")

ctx     = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
TOKEN   = ctx.apiToken().get()
HOST    = f"https://{ctx.browserHostName().get()}"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

GENIE_BASE = f"{HOST}/api/2.0/genie/spaces/{GENIE_SPACE_ID}"
GENIE_LINK = f"{HOST}/genie/rooms/{GENIE_SPACE_ID}/chats/{CONV_ID}"
WS_BASE    = f"{HOST}/api/2.0/workspace"
NB_PATH    = f"{FOLDER_PATH}/{NB_NAME}"

print(f"Conversation  : {CONV_ID}")
print(f"Saving to     : {NB_PATH}")
print(f"Host          : {HOST}")

# COMMAND ----------

# MAGIC %md ### Step 1 — Find the right message in the conversation

# COMMAND ----------

# ── Find the latest message that has SQL ──────────────────────────────────────
TARGET_MSG_ID  = MSG_ID_IN   # use provided, or we'll find it
FOUND_SQL      = ""
FOUND_EXPLAIN  = ""

def get_message(msg_id: str) -> dict:
    r = requests.get(
        f"{GENIE_BASE}/conversations/{CONV_ID}/messages/{msg_id}",
        headers=HEADERS, timeout=30
    )
    r.raise_for_status()
    return r.json()

def get_sql_for_message(msg_id: str):
    """Try to get SQL from query-result endpoint."""
    try:
        r = requests.get(
            f"{GENIE_BASE}/conversations/{CONV_ID}/messages/{msg_id}/query-result",
            headers=HEADERS, timeout=30
        )
        if r.status_code == 200:
            stmt = r.json().get("statement_response", {})
            sql  = stmt.get("statement", "").strip()
            return sql or None
    except Exception:
        pass
    return None

def get_explanation(message: dict) -> str:
    """Pull explanation text from message attachments."""
    for att in message.get("attachments", []):
        if att.get("type") == "text":
            return att.get("content", "")
    return message.get("content", "")

# ── If message_id provided → use it directly ─────────────────────────────────
if TARGET_MSG_ID:
    print(f"Using provided message ID: {TARGET_MSG_ID}")
    msg           = get_message(TARGET_MSG_ID)
    FOUND_SQL     = get_sql_for_message(TARGET_MSG_ID) or ""
    FOUND_EXPLAIN = get_explanation(msg)

# ── Otherwise → list messages and find the latest one with SQL ───────────────
else:
    print("No message ID provided — scanning conversation for latest SQL...")
    try:
        r = requests.get(
            f"{GENIE_BASE}/conversations/{CONV_ID}/messages",
            headers=HEADERS, timeout=30
        )
        r.raise_for_status()
        messages = r.json().get("messages", []) or r.json().get("items", []) or []
    except Exception as e:
        print(f"Could not list messages ({e}). Trying conversation-level query-result...")
        messages = []

    # Walk messages newest-first, find one with SQL
    if messages:
        print(f"Found {len(messages)} messages. Scanning newest first...")
        completed = [
            m for m in messages
            if m.get("status") == "COMPLETED" and m.get("role") != "USER"
        ]
        for m in reversed(completed):
            mid = m.get("id") or m.get("message_id", "")
            if not mid:
                continue
            sql = get_sql_for_message(mid)
            if sql:
                TARGET_MSG_ID = mid
                FOUND_SQL     = sql
                FOUND_EXPLAIN = get_explanation(m)
                print(f"✓ SQL found in message: {mid}")
                break
        if not FOUND_SQL:
            print("No SQL found in any completed message.")
            print("Capturing explanation text from latest message instead.")
            if completed:
                m             = completed[-1]
                TARGET_MSG_ID = m.get("id") or m.get("message_id", "")
                FOUND_EXPLAIN = get_explanation(m)
    else:
        print("Message listing not available — using conversation-level fallback.")

print(f"\nSQL captured  : {'YES (' + str(len(FOUND_SQL)) + ' chars)' if FOUND_SQL else 'NO'}")
print(f"Explanation   : {'YES (' + str(len(FOUND_EXPLAIN)) + ' chars)' if FOUND_EXPLAIN else 'NO'}")

# COMMAND ----------

# MAGIC %md ### Step 2 — Execute SQL (preview in orchestrator)

# COMMAND ----------

# ── Run the SQL live so we can see the output here too ────────────────────────
STEP_TABLES = []

if FOUND_SQL:
    print(f"Executing SQL ({len(FOUND_SQL)} chars)...")
    try:
        df = spark.sql(FOUND_SQL)
        display(df)
    except Exception as e:
        print(f"SQL execution note: {e}")
        print("SQL will still be saved to the notebook — open it and run there.")

    STEP_TABLES = re.findall(
        r"CREATE\s+OR\s+REPLACE\s+TEMPORARY\s+TABLE\s+(\w+)",
        FOUND_SQL, re.IGNORECASE
    )
else:
    print("No SQL captured — notebook will contain explanation text only.")
    print(f"Open the Genie conversation to review: {GENIE_LINK}")

# COMMAND ----------

# ── Attrition waterfall ───────────────────────────────────────────────────────
if STEP_TABLES:
    print(f"\n{'':=<65}")
    print(f"  ATTRITION WATERFALL  —  {STUDY_TITLE}")
    print(f"  Section: {NB_NAME}")
    print(f"{'':=<65}")
    print(f"  {'Step':<44} {'N Patients':>12}  {'Drop':>10}")
    print(f"  {'-'*44} {'-'*12}  {'-'*10}")
    prev = None
    for i, tbl in enumerate(STEP_TABLES, 1):
        try:
            cnt  = spark.sql(f"SELECT COUNT(*) AS n FROM {tbl}").collect()[0]["n"]
            drop = f"−{prev - cnt:,}" if prev is not None else "—"
            print(f"  {i}. {tbl:<42} {cnt:>12,}  {drop:>10}")
            prev = cnt
        except Exception as e:
            print(f"  {i}. {tbl:<42} (error: {e})")
    print(f"{'':=<65}")
    if prev is not None:
        print(f"  Final cohort: {prev:,} patients")

# COMMAND ----------

# MAGIC %md ### Step 3 — Create the study notebook

# COMMAND ----------

# ── Ensure folder exists ──────────────────────────────────────────────────────
requests.post(
    f"{HOST}/api/2.0/workspace/mkdirs",
    headers=HEADERS,
    json={"path": FOLDER_PATH}
)
print(f"Folder ready: {FOLDER_PATH}")

# COMMAND ----------

# ── Build notebook content ────────────────────────────────────────────────────
sql_safe     = (FOUND_SQL or "# No SQL captured").replace("\\", "\\\\").replace('"""', "'''")
explain_safe = FOUND_EXPLAIN.replace(chr(10), "\n# MAGIC ") if FOUND_EXPLAIN else "_No explanation text captured._"

waterfall_cell = ""
if STEP_TABLES:
    waterfall_cell = f'''
# COMMAND ----------

# Attrition waterfall — counts every step
import re as _re

_sql    = """{sql_safe[:8000]}"""
_tables = _re.findall(
    r"CREATE\\s+OR\\s+REPLACE\\s+TEMPORARY\\s+TABLE\\s+(\\w+)",
    _sql, _re.IGNORECASE
)

if _tables:
    print(f"\\n{{\'=\'*65}}")
    print(f"  WATERFALL — {STUDY_TITLE} / {NB_NAME}")
    print(f"{{\'=\'*65}}")
    _prev = None
    for _i, _t in enumerate(_tables, 1):
        try:
            _cnt  = spark.sql(f"SELECT COUNT(*) AS n FROM {{_t}}").collect()[0]["n"]
            _drop = f"−{{_prev - _cnt:,}}" if _prev is not None else "—"
            print(f"  {{_i}}. {{_t:<42}} {{_cnt:>12,}}  {{_drop}}")
            _prev = _cnt
        except Exception as _e:
            print(f"  {{_i}}. {{_t:<42}} (error: {{_e}})")
    if _prev is not None:
        print(f"\\n  Final cohort: {{_prev:,}} patients")
else:
    print("No temp tables found. Check SQL above.")
'''

nb_source = f'''# Databricks notebook source
# ════════════════════════════════════════════════════════════════════════
# Study   : {STUDY_TITLE}
# Section : {NB_NAME}
# Source  : Genie conversation {CONV_ID}
# Genie   : {GENIE_LINK}
# ════════════════════════════════════════════════════════════════════════

# COMMAND ----------

# MAGIC %md
# MAGIC # {STUDY_TITLE}
# MAGIC ## {NB_NAME.replace("_", " ").title()}
# MAGIC
# MAGIC **Source:** Genie Agent conversation → saved to notebook
# MAGIC
# MAGIC **Genie conversation:** [{GENIE_LINK}]({GENIE_LINK})
# MAGIC
# MAGIC *Generated by RWE ADS Automation Platform*

# COMMAND ----------

# Notebook metadata
STUDY_TITLE   = """{STUDY_TITLE}"""
NB_SECTION    = """{NB_NAME}"""
GENIE_CONV_ID = """{CONV_ID}"""
GENIE_MSG_ID  = """{TARGET_MSG_ID}"""
GENIE_LINK    = """{GENIE_LINK}"""

# COMMAND ----------

# MAGIC %md ### Genie Explanation
# MAGIC
# MAGIC {explain_safe}

# COMMAND ----------

# SQL generated by Genie Agent
# To regenerate: open the Genie conversation link above and continue the chat,
# then run 01_Save_to_Notebook again with the same or updated Conversation ID.

{FOUND_SQL or "# No SQL was captured. Open the Genie link above to review."}
{waterfall_cell}
'''

# ── Push to workspace ─────────────────────────────────────────────────────────
encoded = base64.b64encode(nb_source.encode("utf-8")).decode("ascii")
r = requests.post(
    f"{HOST}/api/2.0/workspace/import",
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
FOLDER_URL = f"{HOST}/#workspace{FOLDER_PATH}"

print(f"✓ Notebook saved: {NB_PATH}")

# COMMAND ----------

# ── Summary card ──────────────────────────────────────────────────────────────
displayHTML(f"""
<div style="font-family:Inter,sans-serif;padding:28px 32px;background:#f9f8f6;
            border-radius:14px;border-left:6px solid #eb1700;max-width:740px;
            box-shadow:0 2px 12px rgba(0,0,0,0.07);">

  <div style="font-size:0.6rem;font-weight:800;letter-spacing:0.22em;
              text-transform:uppercase;color:#eb1700;margin-bottom:10px;">
    Saved to Notebook
  </div>

  <div style="font-size:1.25rem;font-weight:800;color:#1a1410;margin-bottom:4px;">
    {STUDY_TITLE}
  </div>
  <div style="font-size:0.95rem;font-weight:600;color:#eb1700;margin-bottom:16px;">
    {NB_NAME}
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

  <div style="background:#fff;border:1px solid #eae8e5;border-radius:8px;
              padding:14px 18px;font-size:0.78rem;color:#1a1410;line-height:2;">
    <div style="font-weight:800;letter-spacing:0.1em;text-transform:uppercase;
                font-size:0.6rem;color:#81766f;margin-bottom:8px;">
      Save Next Section (e.g. Feasibility, Subgroup, Device Analysis)
    </div>
    <div>1. Go back to <a href="{GENIE_LINK}" style="color:#0f68b2;">Genie</a>
         → continue the same conversation → ask your next question</div>
    <div>2. When done, come back here and set:</div>
    <div style="margin-left:16px;">
      · <strong>Conversation ID</strong> → same: <code style="background:#f5f4f2;
        padding:2px 6px;border-radius:3px;color:#eb1700;">{CONV_ID}</code><br/>
      · <strong>Notebook Name</strong> → next section, e.g.
        <code style="background:#f5f4f2;padding:2px 6px;border-radius:3px;">02_feasibility</code>
    </div>
    <div>3. Click <strong>Run All</strong></div>
  </div>

  <div style="margin-top:14px;font-size:0.68rem;color:#a39992;">
    SQL captured: {'Yes — ' + str(len(FOUND_SQL)) + ' chars, ' + str(len(STEP_TABLES)) + ' steps' if FOUND_SQL else 'No SQL — text only'}
    &nbsp;·&nbsp; Genie msg: {TARGET_MSG_ID or 'N/A'}
  </div>
</div>
""")
