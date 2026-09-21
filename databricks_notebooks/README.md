# RWE ADS Automation — Databricks Native Notebooks

Fully Databricks-native. No local installs. No VS Code. No GitHub needed to run.

---

## Notebooks

| File | Purpose |
|------|---------|
| `00_ADS_Orchestrator.py` | Import once — run for every study section. Multi-notebook aware. |

---

## How to import into Databricks

1. Go to **Databricks Workspace → your folder**
2. Click **Import** → upload `00_ADS_Orchestrator.py`
3. Or: **Repos → Add Repo** → `dBoss0/rwe_ads_platform` → open `databricks_notebooks/`

---

## Study folder structure (auto-created)

Every run creates or updates notebooks inside a study folder:

```
/Shared/ads_automation/studies/
└── Bariatric_Surgery_Study/
    ├── 01_attrition_pipeline        ← first run (no /new: command)
    ├── 02_feasibility_device_analysis  ← /new: feasibility device analysis
    ├── 03_subgroup_by_region        ← /new: subgroup by region
    └── 04_readmission_analysis      ← /new: readmission analysis
```

Each notebook is self-contained and re-runnable.

---

## First run — new study

1. Import `00_ADS_Orchestrator.py` into Databricks
2. Fill the widgets:

| Widget | Example value |
|--------|---------------|
| **Study Title** | `Bariatric Surgery Study` ← same across all runs |
| **Study Window** | `January 2016 to December 2022` |
| **Conversation ID** | *(leave blank)* |
| **Prompt** | `Generate the full attrition pipeline with patient counts` |
| **Inclusion Criteria** | JSON array (see below) |
| **Exclusion Criteria** | JSON array |
| **Code Lists** | JSON array (see below) |

3. Click **Run All**
4. Genie generates the SQL (30–90 seconds)
5. SQL executes live; attrition waterfall prints
6. Notebook auto-created at `…/01_attrition_pipeline`
7. **Copy the Conversation ID** shown in the red summary card

---

## Next generation — NEW notebook in same study

Use the `/new:` command in the Prompt widget to route the next generation to a new notebook:

```
/new: feasibility device analysis  →  How many patients had a bariatric device?
      Break down by device type and manufacturer.
```

**Syntax:**
```
/new: <notebook name>  →  <your actual question for Genie>
```

The text before `→` becomes the notebook filename. The text after is sent to Genie.

**Steps:**
1. Keep **Study Title** the same (saves to the same folder)
2. Paste the **Conversation ID** from the previous run (continues Genie context)
3. Set **Prompt** = `/new: <topic>  →  <question>`
4. Click **Run All**

This creates `02_feasibility_device_analysis` in the same study folder.

---

## Example: 4-notebook study

| Run | Prompt widget | Notebook created |
|-----|---------------|-----------------|
| 1 | `Generate the full attrition pipeline` | `01_attrition_pipeline` |
| 2 | `/new: feasibility device analysis  →  How many patients by device?` | `02_feasibility_device_analysis` |
| 3 | `/new: subgroup by region  →  Break down cohort by US census region` | `03_subgroup_by_region` |
| 4 | `/new: readmission analysis  →  90-day readmission rates by procedure type` | `04_readmission_analysis` |

---

## Continuing without a new notebook

If you omit `/new:`, the next run creates a new numbered notebook anyway (each run
increments the number). To explicitly continue a topic, just put the question directly:

```
Prompt: What is the payer mix breakdown for this cohort?
```

→ Creates `05_payer_mix_breakdown`

---

## Inclusion / Exclusion Criteria JSON

```json
[
  "Inpatient admission with primary ICD-10-PCS procedure for surgery of interest",
  "Age 18 or older at index admission",
  "Hospital contributes data for 90 days post-discharge",
  "Known gender",
  "Publish type = Comparative Valid (CV)"
]
```

---

## Code Lists JSON

```json
[
  {
    "condition": "RYGB",
    "coding_system": "ICD-10-PCS",
    "codes": ["0D160ZA", "0D160Z3", "0D160Z4"]
  },
  {
    "condition": "Sleeve Gastrectomy",
    "coding_system": "ICD-10-PCS",
    "codes": ["0DB64Z3", "0DB60Z3"]
  }
]
```

---

## Genie Space

Connected to: `Hospital Patient Clinical and Billing Data (Premier PHD)`  
Space ID: `01f1ad05e9a811de88b3f1c49399c3c1`  
Workspace: `dbc-db3d8a4e-f2cf.cloud.databricks.com`

---

## Security

- No PAT tokens are hardcoded — uses `dbutils.notebook.entry_point` (Databricks-managed identity)
- Delta table schema is used only for SQL generation — never displayed to users
- Output notebooks contain only: SQL code, waterfall counts, Genie conversation link
