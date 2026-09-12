"""Environment configuration for the financial due diligence ingestion pipeline."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Typed settings loaded from environment variables."""

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
        """Load settings from environment, raising ValueError for any missing required var."""
        required = {
            "DATABRICKS_HOST": os.getenv("DATABRICKS_HOST"),
            "DATABRICKS_HTTP_PATH": os.getenv("DATABRICKS_HTTP_PATH"),
            "DATABRICKS_TOKEN": os.getenv("DATABRICKS_TOKEN"),
            "DATABRICKS_CATALOG": os.getenv("DATABRICKS_CATALOG"),
            "EDGAR_USER_AGENT": os.getenv("EDGAR_USER_AGENT"),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(
            databricks_host=required["DATABRICKS_HOST"],  # type: ignore[arg-type]
            databricks_http_path=required["DATABRICKS_HTTP_PATH"],  # type: ignore[arg-type]
            databricks_token=required["DATABRICKS_TOKEN"],  # type: ignore[arg-type]
            databricks_catalog=required["DATABRICKS_CATALOG"],  # type: ignore[arg-type]
            databricks_schema_bronze=os.getenv("DATABRICKS_SCHEMA_BRONZE", "bronze"),
            databricks_schema_silver=os.getenv("DATABRICKS_SCHEMA_SILVER", "silver"),
            databricks_schema_gold=os.getenv("DATABRICKS_SCHEMA_GOLD", "gold"),
            edgar_user_agent=required["EDGAR_USER_AGENT"],  # type: ignore[arg-type]
        )
