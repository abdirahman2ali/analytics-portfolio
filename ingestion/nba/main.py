import os
import time
from datetime import date
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

from nba_ingestion.scraper import get_season_stats
from nba_ingestion.transformer import prepare_for_db, season_label
from nba_ingestion.loader import ensure_schema, ensure_table, write_to_db, get_last_loaded_year, get_loaded_seasons

if not os.getenv("DATABRICKS_RUNTIME_VERSION"):
    load_dotenv(Path(__file__).parent.parent.parent.parent / ".claude" / ".env")
    load_dotenv()

START_YEAR = 1950
TABLE_NAME = "player_season_totals"
REQUEST_DELAY = 6       # seconds between successful requests
RETRY_DELAY = 120       # seconds to wait after a 429 before retrying
MAX_RETRIES = 3


def last_complete_season_year() -> int:
    """Return the end year of the last fully completed NBA season.

    NBA Finals end in June. Stats are finalized on Basketball Reference
    by July, so any run in July or later safely captures a complete season.

    Examples:
        Called in July 2026  → returns 2026 (2025-26 season complete)
        Called in March 2026 → returns 2025 (2025-26 still in progress)
    """
    today = date.today()
    return today.year if today.month >= 7 else today.year - 1


def fetch_with_retry(year: int) -> pd.DataFrame:
    """Fetch season stats with retry logic on 429 rate-limit responses."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return get_season_stats(year)
        except Exception as e:
            if "429" in str(e) and attempt < MAX_RETRIES:
                print(f"rate limited — waiting {RETRY_DELAY}s (attempt {attempt}/{MAX_RETRIES})... ", end="", flush=True)
                time.sleep(RETRY_DELAY)
            else:
                raise


def run(start_year=None, end_year: int = None, table_name: str = TABLE_NAME):
    ensure_schema()
    ensure_table(table_name)

    if end_year is None:
        end_year = last_complete_season_year()

    if start_year is None:
        last_loaded = get_last_loaded_year(table_name)
        start_year = START_YEAR if last_loaded is None else last_loaded + 1

    if start_year > end_year:
        print("Already up to date.")
        return

    loaded_seasons = get_loaded_seasons(table_name)
    successful = 0
    failed = []

    for year in range(start_year, end_year + 1):
        label = season_label(year)
        if label in loaded_seasons:
            print(f"Skipping {label} — already loaded")
            continue
        try:
            print(f"Fetching {label} season... ", end="", flush=True)
            df = fetch_with_retry(year)

            if df.empty:
                print("no data")
                failed.append(year)
                continue

            df_db = prepare_for_db(df, year)
            write_to_db(df_db, table_name)
            print(f"{len(df):,} players saved")
            successful += 1

        except Exception as e:
            print(f"error: {e}")
            failed.append(year)

        finally:
            time.sleep(REQUEST_DELAY)

    total = end_year - start_year + 1
    print(f"\nDone. {successful}/{total} seasons loaded.")
    if failed:
        print(f"Failed seasons: {failed}")


if __name__ == "__main__":
    import sys
    start = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run(start_year=start)
