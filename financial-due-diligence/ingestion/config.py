"""Environment configuration for the financial due diligence ingestion pipeline."""

import logging
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_SECRETS_SCOPE = "financial_due_diligence"


def _secret_or_env(secret_key: str, env_var: str) -> Optional[str]:
    """Try Databricks Secrets first (when running on-cluster), then fall back to env var."""
    try:
        from databricks.sdk.runtime import dbutils  # type: ignore[import]

        val = dbutils.secrets.get(scope=_SECRETS_SCOPE, key=secret_key)
        if val:
            logger.debug("Loaded %s from Databricks Secrets", secret_key)
            return val
    except Exception:
        pass
    return os.getenv(env_var)


@dataclass
class Settings:
    """Typed settings loaded from Databricks Secrets (on-cluster) or environment variables (local)."""

    databricks_host: str
    databricks_http_path: str
    databricks_token: str
    databricks_catalog: str
    databricks_schema_bronze: str
    databricks_schema_silver: str
    databricks_schema_gold: str
    edgar_user_agent: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings, raising ValueError for any missing required value."""
        required = {
            "databricks_token": _secret_or_env("databricks_token", "DATABRICKS_TOKEN"),
            "DATABRICKS_HOST": _secret_or_env("databricks_host", "DATABRICKS_HOST"),
            "DATABRICKS_HTTP_PATH": _secret_or_env("databricks_http_path", "DATABRICKS_HTTP_PATH"),
            "DATABRICKS_CATALOG": _secret_or_env("databricks_catalog", "DATABRICKS_CATALOG"),
            "EDGAR_USER_AGENT": _secret_or_env("edgar_user_agent", "EDGAR_USER_AGENT"),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"Missing required config (env var or Databricks Secret): {', '.join(missing)}")

        return cls(
            databricks_host=required["DATABRICKS_HOST"],  # type: ignore[arg-type]
            databricks_http_path=required["DATABRICKS_HTTP_PATH"],  # type: ignore[arg-type]
            databricks_token=required["databricks_token"],  # type: ignore[arg-type]
            databricks_catalog=required["DATABRICKS_CATALOG"],  # type: ignore[arg-type]
            databricks_schema_bronze=_secret_or_env("databricks_schema_bronze", "DATABRICKS_SCHEMA_BRONZE") or "bronze",
            databricks_schema_silver=_secret_or_env("databricks_schema_silver", "DATABRICKS_SCHEMA_SILVER") or "silver",
            databricks_schema_gold=_secret_or_env("databricks_schema_gold", "DATABRICKS_SCHEMA_GOLD") or "gold",
            edgar_user_agent=required["EDGAR_USER_AGENT"],  # type: ignore[arg-type]
        )
