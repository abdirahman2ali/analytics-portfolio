"""Main orchestration script for the SEC EDGAR financial due diligence pipeline.

Fetches S&P 500 company facts from EDGAR, applies incremental filtering via a
Delta checkpoint table, and writes new records to Databricks.
"""

import logging
import sys
from datetime import date

from config import Settings
from delta_writer import DeltaWriter
from edgar_client import EdgarClient
from sp500_fetcher import fetch_sp500_tickers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Run the full incremental ingestion pipeline."""
    logger.info("Starting EDGAR ingestion pipeline")

    settings = Settings.from_env()
    writer = DeltaWriter(settings)

    try:
        writer.ensure_tables_exist()

        companies = fetch_sp500_tickers(settings.edgar_user_agent)
        logger.info("Processing %d S&P 500 companies", len(companies))

        client = EdgarClient(settings.edgar_user_agent)
        total_written = 0
        errors = 0

        for company in companies:
            try:
                checkpoint: date | None = writer.get_checkpoint(company.cik)
                facts = client.get_company_facts(company.cik)
                records = client.extract_filings(
                    facts=facts,
                    ticker=company.ticker,
                    company_name=company.company_name,
                    cik=company.cik,
                    filing_types=["10-K", "10-Q"],
                )

                if checkpoint is not None:
                    from datetime import datetime

                    records = [
                        r
                        for r in records
                        if datetime.strptime(r["filed_date"], "%Y-%m-%d").date()
                        > checkpoint
                    ]

                if records:
                    writer.write_records(records)
                    latest_filed = max(r["filed_date"] for r in records)
                    from datetime import datetime

                    writer.upsert_checkpoint(
                        company.cik,
                        datetime.strptime(latest_filed, "%Y-%m-%d").date(),
                    )
                    total_written += len(records)
                    logger.info(
                        "%s: wrote %d new records (latest filed: %s)",
                        company.ticker,
                        len(records),
                        latest_filed,
                    )
                else:
                    logger.info("%s: no new records since checkpoint", company.ticker)

            except Exception as exc:
                logger.error(
                    "Failed to process %s (%s): %s",
                    company.ticker,
                    company.cik,
                    exc,
                    exc_info=True,
                )
                errors += 1

        logger.info(
            "Ingestion complete. Total records written: %d. Companies with errors: %d",
            total_written,
            errors,
        )

        if errors > 0:
            logger.warning(
                "%d companies failed — inspect logs above for details", errors
            )

    finally:
        writer.close()

    if errors == len(companies):
        logger.error("All companies failed — exiting with non-zero status")
        sys.exit(1)


if __name__ == "__main__":
    main()
