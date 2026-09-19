"""Fetches daily market data for S&P 500 constituents via yfinance and writes to Databricks.

Pulls close price, shares outstanding, and market cap for every ticker in sp500_companies seed.
Writes to financial_due_diligence_bronze.brz_market_data using an idempotent MERGE on (ticker, price_date).
"""

import logging
import sys
from datetime import datetime, timezone

from config import Settings
from delta_writer import DeltaWriter
from sp500_fetcher import fetch_sp500_tickers

import yfinance as yf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

_MARKET_DATA_TABLE = "brz_market_data"

_CREATE_MARKET_DATA_DDL = """
CREATE TABLE IF NOT EXISTS {catalog}.{schema}.{table} (
    ticker              STRING        NOT NULL,
    price_date          DATE          NOT NULL,
    close_price         DOUBLE,
    shares_outstanding  DOUBLE,
    market_cap          DOUBLE,
    ingested_at         STRING        NOT NULL
)
USING DELTA
"""

_MERGE_MARKET_DATA_SQL = """
MERGE INTO {fqn} AS target
USING _source_market AS source
ON  target.ticker     = source.ticker
AND target.price_date = source.price_date
WHEN MATCHED AND source.ingested_at >= target.ingested_at THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
"""


def _fetch_market_records(tickers: list[str], ingested_at: str) -> tuple[list[dict], int]:
    """Download the latest trading-day close and shares outstanding for each ticker.

    Args:
        tickers: List of equity ticker symbols.
        ingested_at: ISO timestamp to stamp on every row.

    Returns:
        List of market data record dicts.
    """
    records: list[dict] = []
    errors = 0

    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).fast_info
            price = getattr(info, "last_price", None)
            shares = getattr(info, "shares", None)
            market_cap = (price * shares) if (price and shares) else None

            price_date_ts = getattr(info, "last_volume_dt", None)
            if price_date_ts:
                price_date = price_date_ts.strftime("%Y-%m-%d")
            else:
                price_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            records.append({
                "ticker": ticker,
                "price_date": price_date,
                "close_price": float(price) if price is not None else None,
                "shares_outstanding": float(shares) if shares is not None else None,
                "market_cap": float(market_cap) if market_cap is not None else None,
                "ingested_at": ingested_at,
            })
            logger.info("%s: price=%.2f shares=%s", ticker, price or 0, shares)

        except Exception as exc:
            logger.error("Failed to fetch %s: %s", ticker, exc, exc_info=True)
            errors += 1

    return records, errors


def _ensure_market_table(writer: DeltaWriter) -> None:
    """Create brz_market_data if it does not already exist."""
    cat = writer._settings.databricks_catalog
    sch = writer._settings.databricks_schema_bronze
    ddl = _CREATE_MARKET_DATA_DDL.format(catalog=cat, schema=sch, table=_MARKET_DATA_TABLE)
    if writer._spark:
        writer._spark.sql(ddl)
    else:
        with writer._conn.cursor() as cursor:
            cursor.execute(ddl)
    logger.info("Market data table verified/created")


def _write_market_records(writer: DeltaWriter, records: list[dict]) -> None:
    """Upsert market data records into brz_market_data."""
    if not records:
        return

    cat = writer._settings.databricks_catalog
    sch = writer._settings.databricks_schema_bronze
    fqn = f"{cat}.{sch}.{_MARKET_DATA_TABLE}"

    if writer._spark:
        from pyspark.sql.types import (  # type: ignore[import]
            DateType, DoubleType, StringType, StructField, StructType,
        )
        schema = StructType([
            StructField("ticker", StringType(), nullable=False),
            StructField("price_date", StringType(), nullable=False),
            StructField("close_price", DoubleType(), nullable=True),
            StructField("shares_outstanding", DoubleType(), nullable=True),
            StructField("market_cap", DoubleType(), nullable=True),
            StructField("ingested_at", StringType(), nullable=False),
        ])
        rows = [
            (r["ticker"], r["price_date"], r["close_price"],
             r["shares_outstanding"], r["market_cap"], r["ingested_at"])
            for r in records
        ]
        df = writer._spark.createDataFrame(rows, schema)
        df = df.withColumn("price_date", df["price_date"].cast(DateType()))
        df.createOrReplaceTempView("_source_market")
        writer._spark.sql(_MERGE_MARKET_DATA_SQL.format(fqn=fqn))
    else:
        merge_sql = f"""
            MERGE INTO {fqn} AS target
            USING (SELECT ? AS ticker, cast(? AS DATE) AS price_date,
                          ? AS close_price, ? AS shares_outstanding,
                          ? AS market_cap, ? AS ingested_at) AS source
            ON target.ticker = source.ticker AND target.price_date = source.price_date
            WHEN MATCHED AND source.ingested_at >= target.ingested_at THEN UPDATE SET *
            WHEN NOT MATCHED THEN INSERT *
        """
        with writer._conn.cursor() as cursor:
            for r in records:
                cursor.execute(merge_sql, (
                    r["ticker"], r["price_date"], r["close_price"],
                    r["shares_outstanding"], r["market_cap"], r["ingested_at"],
                ))

    logger.info("Upserted %d records into %s", len(records), fqn)


def main() -> None:
    """Fetch latest market data for all S&P 500 constituents and upsert into bronze."""
    logger.info("Starting market data ingestion")

    settings = Settings.from_env()
    writer = DeltaWriter(settings)
    ingested_at = datetime.now(timezone.utc).isoformat()

    try:
        _ensure_market_table(writer)

        companies = fetch_sp500_tickers(settings.edgar_user_agent)
        tickers = [c.ticker for c in companies]
        logger.info("Fetching market data for %d tickers", len(tickers))

        records, errors = _fetch_market_records(tickers, ingested_at)

        if records:
            _write_market_records(writer, records)

        logger.info(
            "Market data ingestion complete. Records written: %d. Errors: %d",
            len(records),
            errors,
        )

    finally:
        writer.close()

    if errors == len(tickers):
        logger.error("All tickers failed — exiting with non-zero status")
        sys.exit(1)


if __name__ == "__main__":
    main()
