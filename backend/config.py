"""
Application configuration.

In Databricks Apps, DATABRICKS_HOST and DATABRICKS_TOKEN are injected
automatically. All other values can be set via environment variables or
a local .env file (never committed — see .gitignore).
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Databricks ────────────────────────────────────────────────────────────
    databricks_host: str = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
    databricks_token: str = os.environ.get("DATABRICKS_TOKEN", "")

    # ── Model Serving endpoints ───────────────────────────────────────────────
    claude_endpoint: str = os.environ.get("CLAUDE_ENDPOINT", "databricks-claude-opus-5")
    gpt_endpoint: str = os.environ.get("GPT_ENDPOINT", "databricks-gpt-55")

    # ── PHD Catalog (READ ONLY) ───────────────────────────────────────────────
    phd_catalog: str = os.environ.get("PHD_CATALOG", "rhealth_premier_phd")
    phd_schema: str = os.environ.get("PHD_SCHEMA", "bronze_native_premier_phd")

    # ── Scratch Catalog (READ/WRITE) ──────────────────────────────────────────
    # All uploads, exports, and generated results go here.
    # Catalog name contains hyphens — backtick-quote in SQL: `rhealth-catalog-poc`
    meta_catalog: str = os.environ.get("META_CATALOG", "rhealth-catalog-poc")
    meta_schema: str = os.environ.get(
        "META_SCHEMA", "scratch_mtech_ga_dbx_prphd_ads_automation_poc"
    )

    # ── Volume paths (under the scratch catalog) ───────────────────────────────
    protocol_volume: str = os.environ.get(
        "PROTOCOL_VOLUME",
        "/Volumes/rhealth-catalog-poc/scratch_mtech_ga_dbx_prphd_ads_automation_poc/ads_automation",
    )

    # ── Runtime flags ─────────────────────────────────────────────────────────
    # ── Notebook workspace root ───────────────────────────────────────────────
    # All generated SQL notebooks land here.
    # /Shared/ads_automation/ is accessible to all team members regardless
    # of who runs the Databricks App.
    notebook_workspace_root: str = os.environ.get(
        "NOTEBOOK_WORKSPACE_ROOT", "/Shared/ads_automation"
    )

    @property
    def meta_fqn_sql(self) -> str:
        """
        Fully-qualified scratch catalog.schema with backtick quoting.
        Catalogs with hyphens must be quoted in Databricks SQL:
          `rhealth-catalog-poc`.scratch_mtech_ga_dbx_prphd_ads_automation_poc
        """
        return f"`{self.meta_catalog}`.{self.meta_schema}"

    @property
    def is_databricks_app(self) -> bool:
        """True when running inside a Databricks App."""
        return bool(self.databricks_host and self.databricks_token)

    @property
    def phd_fqn(self) -> str:
        """Fully-qualified PHD schema: catalog.schema"""
        return f"{self.phd_catalog}.{self.phd_schema}"

    @property
    def claude_endpoint_url(self) -> str:
        return (
            f"{self.databricks_host}"
            f"/serving-endpoints/{self.claude_endpoint}/invocations"
        )

    @property
    def gpt_endpoint_url(self) -> str:
        return (
            f"{self.databricks_host}"
            f"/serving-endpoints/{self.gpt_endpoint}/invocations"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
