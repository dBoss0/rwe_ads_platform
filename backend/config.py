"""
Application configuration — zero external dependencies.

Uses plain os.environ so it works in Databricks Apps (no PyPI access)
and locally (values loaded from .env via the app entry point).
"""
import os


def _load_dotenv() -> None:
    """Load .env file when running locally. Silently skipped if not found."""
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(override=False)
    except ImportError:
        # python-dotenv not installed (Databricks Apps) — env vars already injected
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.isfile(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()


class Settings:
    # ── Databricks ────────────────────────────────────────────────────────────
    databricks_host: str = os.environ.get(
        "DATABRICKS_HOST", "https://dbc-db3d8a4e-f2cf.cloud.databricks.com"
    ).rstrip("/")
    databricks_token: str = os.environ.get("DATABRICKS_TOKEN", "")

    # ── Model Serving endpoints ───────────────────────────────────────────────
    claude_endpoint: str = os.environ.get("CLAUDE_ENDPOINT", "databricks-gpt-5-5")
    gpt_endpoint: str    = os.environ.get("GPT_ENDPOINT",    "databricks-gpt-5-5")

    # ── PHD Catalog (READ ONLY) ───────────────────────────────────────────────
    phd_catalog: str = os.environ.get("PHD_CATALOG", "rhealth_premier_phd")
    phd_schema: str = os.environ.get("PHD_SCHEMA", "bronze_native_premier_phd")

    # ── Scratch Catalog (READ/WRITE) ──────────────────────────────────────────
    meta_catalog: str = os.environ.get("META_CATALOG", "rhealth-catalog-poc")
    meta_schema: str = os.environ.get(
        "META_SCHEMA", "scratch_mtech_ga_dbx_prphd_ads_automation_poc"
    )

    # ── Volume paths ──────────────────────────────────────────────────────────
    protocol_volume: str = os.environ.get(
        "PROTOCOL_VOLUME",
        "/Volumes/rhealth-catalog-poc/scratch_mtech_ga_dbx_prphd_ads_automation_poc/ads_automation",
    )

    # ── Notebook workspace root ───────────────────────────────────────────────
    notebook_workspace_root: str = os.environ.get(
        "NOTEBOOK_WORKSPACE_ROOT", "/Shared/ads_automation"
    )

    # ── SQL Warehouse ─────────────────────────────────────────────────────────
    warehouse_id: str = os.environ.get("DATABRICKS_WAREHOUSE_ID", "9525c51c721e3ac7")

    @property
    def meta_fqn_sql(self) -> str:
        return f"`{self.meta_catalog}`.{self.meta_schema}"

    @property
    def is_databricks_app(self) -> bool:
        return bool(self.databricks_host and self.databricks_token)

    @property
    def phd_fqn(self) -> str:
        return f"{self.phd_catalog}.{self.phd_schema}"

    @property
    def claude_endpoint_url(self) -> str:
        return f"{self.databricks_host}/serving-endpoints/{self.claude_endpoint}/invocations"

    @property
    def gpt_endpoint_url(self) -> str:
        return f"{self.databricks_host}/serving-endpoints/{self.gpt_endpoint}/invocations"


settings = Settings()
