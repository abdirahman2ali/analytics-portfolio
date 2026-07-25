"""
Entry point for the toronto_parking_centrelines Databricks job task.

Fetches the Toronto Centreline (TCL) dataset from Toronto Open Data and loads
it into abdirahman_portfolio.toronto_parking_raw.street_centrelines. Run as a
spark_python_task alongside toronto_parking_ingestion before the dbt task.
"""
import logging
import os
import sys
from pathlib import Path

if not os.getenv("DATABRICKS_RUNTIME_VERSION"):
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[3] / ".claude" / ".env")
    load_dotenv()

from toronto_parking.centrelines import fetch_centrelines  # noqa: E402
from toronto_parking.loader import ensure_schema, ensure_centrelines_table, replace_centrelines  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    ensure_schema()
    ensure_centrelines_table()

    logger.info("Fetching Toronto Centreline dataset")
    df = fetch_centrelines()

    logger.info(f"Loading {len(df):,} street centroids into Databricks")
    count = replace_centrelines(df)

    logger.info(f"Done — {count:,} street names loaded")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error(f"Centrelines pipeline failed: {exc}", exc_info=True)
        sys.exit(1)
