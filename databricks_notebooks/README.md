# RWE ADS Automation — Databricks Native Notebooks

Fully Databricks-native. No local installs. No VS Code. No GitHub needed to run.

---

## Notebooks

| File | Purpose |
|------|---------|
| `00_ADS_Orchestrator.py` | Main notebook — fill widgets → Run All → done |

---

## How to import into Databricks

1. Go to **Databricks Workspace → your folder**
2. Click **Import** → upload `00_ADS_Orchestrator.py`
3. Or: **Repos → Add Repo** → point to `dBoss0/rwe_ads_platform` → navigate to `databricks_notebooks/`

---

## How each user runs a study

1. Open `00_ADS_Orchestrator`
2. Fill the **widgets** at the top:
   - `Study Title` — full study name
   - `Study Window` — e.g. "January 2016 to December 2022"
   - `Output Folder` — where notebooks are saved (default: `/Shared/ads_automation/studies`)
   - `Inclusion Criteria` — JSON array of strings
   - `Exclusion Criteria` — JSON array of strings
   - `Code Lists` — JSON array of `{condition, coding_system, codes:[...]}` objects
3. Click **Run All**
4. Genie Agent generates the attrition SQL (30–90 seconds)
5. SQL is executed live — waterfall counts printed
6. Study notebook auto-created at `output_folder/{study_title}_attrition`
7. Click the red **Open Study Notebook** button at the bottom

---

## Output per study

Each run creates:
```
/Shared/ads_automation/studies/
└── {study_title}_attrition          ← self-contained study notebook
    ├── Study metadata (title, window, criteria)
    ├── Genie explanation text
    ├── Full attrition SQL (Genie-generated)
    ├── spark.sql() execution
    └── Attrition waterfall with patient counts
```

---

## Code Lists JSON format

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

Connected to: `Hospital Patient Clinical and Billing Data`  
Space ID: `01f1ad05e9a811de88b3f1c49399c3c1`  
Workspace: `dbc-db3d8a4e-f2cf.cloud.databricks.com`
