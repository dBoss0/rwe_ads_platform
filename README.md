# RWE ADS Automation Platform

> **J&J MedTech × Mu Sigma** — Protocol Intelligence Platform  
> Automated attrition notebook generation for Real-World Evidence studies using Premier Healthcare Database.

---

## Architecture

```
React (TypeScript + Vite)          FastAPI (Python)           Databricks
─────────────────────           ──────────────────           ────────────
Step 1: Upload/Paste    ──────► /api/protocol/upload  ──────► ai_parse_document
Step 2: Edit Steps      ◄──────  (ParseResponse)       ◄──────  Claude REST
Step 3: Code Lists               /api/attrition/generate ────► LLM SQL generation
Step 4: Generate        ◄──────  (NotebookResponse)    ◄──────  Workspace push
```

**5-Stage Parse Pipeline:**
1. `ai_parse_document` — extract text from PDF/DOCX/PPT (Databricks)
2. `ai_extract v2.1` — pull title, study_window, data_source (Databricks)
3. Claude REST — extract inclusion/exclusion criteria as structured JSON (all modes)
4. `ai_classify_batch v2.1` — classify each criterion by PHD table type (Databricks)
5. `ai_summarize` — protocol summary for UI display (Databricks)

---

## Quick Start (local dev)

```bash
# 1. Clone
git clone https://github.com/dBoss0/rwe-ads-platform.git
cd rwe-ads-platform

# 2. Python env
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Environment
cp .env.example .env
# → Fill in DATABRICKS_HOST and DATABRICKS_TOKEN in .env

# 4. Build React frontend
cd frontend && npm install && npm run build && cd ..

# 5. Run
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# 6. Dev mode: run React dev server in parallel (uses Vite proxy)
cd frontend && npm run dev
```

Visit: `http://localhost:5173` (dev) or `http://localhost:8000` (prod build)

---

## Databricks Deploy

```bash
# 1. On VDI — pull latest
git pull origin master

# 2. Build frontend
bash scripts/build_frontend.sh

# 3. Deploy via Asset Bundle
databricks bundle deploy --target dev

# 4. Start the App in Databricks Apps console
```

Required `.env` variables:
| Variable              | Description                                          |
|-----------------------|------------------------------------------------------|
| `DATABRICKS_HOST`     | `https://dbc-db3d8a4e-f2cf.cloud.databricks.com`    |
| `DATABRICKS_TOKEN`    | Personal Access Token (never commit)                 |
| `CLAUDE_ENDPOINT`     | `databricks-claude-opus-5`                           |
| `PHD_CATALOG`         | `rhealth_premier_phd`                                |
| `PHD_SCHEMA`          | `bronze_native_premier_phd`                          |
| `META_CATALOG`        | Scratch catalog for metadata tables                  |
| `META_SCHEMA`         | Scratch schema                                       |
| `PROTOCOL_VOLUME`     | UC Volume path for protocol uploads                  |

---

## Project Structure

```
rwe_ads_platform/
├── app.py                        # uvicorn entry point
├── app.yaml                      # Databricks Apps config
├── databricks.yml                # Asset Bundle (CI/CD)
├── requirements.txt
├── .env.example
├── backend/
│   ├── main.py                   # FastAPI app
│   ├── config.py                 # Settings (env-driven)
│   ├── models/                   # Pydantic models
│   ├── routers/                  # API route handlers
│   ├── services/
│   │   ├── ai_functions.py       # Databricks AI Functions bridge
│   │   ├── parser.py             # 5-stage LLM protocol parser
│   │   ├── sql_generator.py      # Claude → attrition SQL
│   │   ├── notebook_builder.py   # Full notebook assembly
│   │   ├── databricks_client.py  # Workspace API helpers
│   │   └── schema_service.py     # PHD catalog schema (live, no hardcoding)
│   └── prompts/
│       └── sql_system_prompt.py  # SQL + Parser system prompts
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx
│       ├── api/client.ts         # FastAPI REST client
│       ├── store/useStore.ts     # Zustand state management
│       ├── components/
│       │   ├── layout/           # NavBar, Sidebar, HeroBand, Footer
│       │   └── steps/            # Step1Input, Step2Edit, Step3CodeLists, Step4Generate
│       └── styles/globals.css    # J&J design system
└── scripts/
    └── build_frontend.sh
```

---

## Parsing — Universal Protocol Support

The parser uses Claude to semantically extract criteria — **no fixed headings, no stop words**.

Handles:
- Any section naming (`Study Population`, `Eligibility Criteria`, `Patient Selection`, etc.)
- Any format (numbered lists, bullets, paragraphs, tables)
- Compound criteria split into atomic steps
- PDF, DOCX, PPT (via `ai_parse_document` in Databricks)
- Pasted text (Claude REST in all modes)

Criterion types classified by which PHD table implements them:
`procedure_code` · `diagnosis_code` · `age` · `gender` · `date_range` ·
`lookback` · `comorbidity` · `data_quality` · `inpatient_outpatient` · `other`

---

## Security

- `DATABRICKS_TOKEN` → **never committed**; loaded from `.env` (local) or Databricks Apps env injection
- PHD Delta tables are **never exposed in any output** — used only for SQL generation context
- No Mu Sigma branding in the deployed app
