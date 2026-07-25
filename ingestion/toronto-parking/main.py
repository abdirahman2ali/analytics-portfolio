import argparse
import datetime
import logging
import os
import sys
import time
from pathlib import Path

if not os.getenv("DATABRICKS_RUNTIME_VERSION"):
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[3] / ".claude" / ".env")
    load_dotenv()

from toronto_parking.fetcher import fetch_available_years, fetch_year  # noqa: E402
from toronto_parking.loader import ensure_schema, ensure_table, _loaded_years, upsert_dataframe  # noqa: E402
from toronto_parking.transformer import prepare_for_db  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 30


def _run_year(year: int) -> dict:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"[{year}] Attempt {attempt}/{MAX_RETRIES}: fetching")
            df_raw = fetch_year(year)
            if df_raw is None or df_raw.empty:
                logger.warning(f"[{year}] No data returned — skipping")
                return {"year": year, "status": "skipped", "rows": 0}

            logger.info(f"[{year}] Fetched {len(df_raw):,} rows — transforming")
            df = prepare_for_db(df_raw)

            logger.info(f"[{year}] Inserting {len(df):,} rows")
            inserted = upsert_dataframe(df, year=year)
            logger.info(f"[{year}] Done: {inserted:,} rows inserted")
            return {"year": year, "status": "ok", "rows": inserted}

        except Exception as exc:
            if attempt < MAX_RETRIES:
                logger.warning(f"[{year}] Attempt {attempt} failed: {exc} — retrying in {RETRY_DELAY}s")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"[{year}] Failed after {MAX_RETRIES} attempts: {exc}")
                return {"year": year, "status": "error", "rows": 0, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", help="Comma-separated years to process, e.g. 2012,2013,2014")
    parser.add_argument("--full-refresh", action="store_true", help="Re-process all available years")
    args = parser.parse_args()

    available_years = fetch_available_years()
    if not available_years:
        logger.error("No years found in CKAN package — aborting")
        sys.exit(1)
    logger.info(f"Available years in CKAN: {available_years}")

    ensure_schema()
    ensure_table()

    if args.years:
        years_to_process = [int(y.strip()) for y in args.years.split(",")]
        logger.info(f"Explicit years requested: {years_to_process}")
    elif args.full_refresh:
        years_to_process = available_years
        logger.info(f"Full refresh: loading all {len(years_to_process)} available years")
    else:
        loaded_years = _loaded_years()
        logger.info(f"Already loaded years: {loaded_years or 'none'}")
        current_year = datetime.date.today().year
        if not loaded_years:
            years_to_process = available_years
            logger.info(f"First run: loading all {len(years_to_process)} available years")
        else:
            years_to_process = [current_year] if current_year in available_years else [max(available_years)]
            logger.info(f"Incremental run: processing year(s) {years_to_process}")

    results = [_run_year(yr) for yr in years_to_process]

    total_inserted = sum(r.get("rows", 0) for r in results)
    failed = [r["year"] for r in results if r["status"] == "error"]

    logger.info(f"Pipeline complete — {total_inserted:,} total rows inserted")
    if failed:
        logger.error(f"Failed years: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
