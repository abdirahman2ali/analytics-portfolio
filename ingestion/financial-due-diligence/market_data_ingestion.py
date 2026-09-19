"""Fetches daily market data for S&P 500 constituents via yfinance and writes to Databricks.

Strategy:
  - Prices: yf.download() for all tickers in one batch call (rate-limit friendly).
  - Shares outstanding: per-ticker fast_info with 0.25s sleep and retry on rate limit.
  - Market cap: close_price × shares_outstanding (computed locally).
"""

import logging
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from config import Settings
from delta_writer import DeltaWriter
from sp500_fetcher import fetch_sp500_tickers

import yfinance as yf
from yfinance.exceptions import YFRateLimitError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

_MARKET_DATA_TABLE = "brz_market_data"
_SHARES_SLEEP_S = 0.25
_RATE_LIMIT_BACKOFF_S = [30, 60, 120]

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

_MERGE_MARKET_DATA_SPARK = """
MERGE INTO {fqn} AS target
USING _source_market AS source
ON  target.ticker     = source.ticker
AND target.price_date = source.price_date
WHEN MATCHED AND source.ingested_at >= target.ingested_at THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
"""


def _fetch_prices_batch(tickers: list[str]) -> dict[str, tuple[Optional[float], Optional[str]]]:
    """Download the latest available close price for all tickers in one batch call.

    Uses yf.download() which batches requests and has built-in retry logic,
    making it significantly more rate-limit friendly than per-ticker fast_info.

    Returns:
        Dict mapping ticker → (close_price, price_date_str).
    """
    logger.info("Downloading prices for %d tickers via yf.download()", len(tickers))
    try:
        df = yf.download(
            tickers=tickers,
            period="5d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception as exc:
        logger.error("Batch price download failed: %s", exc)
        return {}

    if df.empty:
        logger.warning("yf.download() returned empty DataFrame")
        return {}

    # Multi-ticker download returns MultiIndex columns: (field, ticker)
    # Single-ticker returns flat columns
    prices: dict[str, tuple[Optional[float], Optional[str]]] = {}
    if len(tickers) == 1:
        close_series = df["Close"] if "Close" in df.columns else None
        if close_series is not None and not close_series.dropna().empty:
            latest_idx = close_series.dropna().index[-1]
            prices[tickers[0]] = (
                float(close_series.dropna().iloc[-1]),
                latest_idx.strftime("%Y-%m-%d"),
            )
    else:
        try:
            close = df["Close"]
        except KeyError:
            logger.error("'Close' not in download result columns: %s", df.columns.tolist()[:10])
            return {}
        for ticker in tickers:
            if ticker not in close.columns:
                continue
            series = close[ticker].dropna()
            if series.empty:
                continue
            prices[ticker] = (float(series.iloc[-1]), series.index[-1].strftime("%Y-%m-%d"))

    logger.info("Prices retrieved for %d / %d tickers", len(prices), len(tickers))
    return prices


def _fetch_shares(ticker: str) -> Optional[float]:
    """Fetch shares outstanding via fast_info with sleep and retry on rate limit."""
    for attempt, backoff in enumerate([0] + _RATE_LIMIT_BACKOFF_S):
        if backoff:
            logger.warning("Rate limited on %s (attempt %d), waiting %ds", ticker, attempt, backoff)
            time.sleep(backoff)
        try:
            time.sleep(_SHARES_SLEEP_S)
            val = yf.Ticker(ticker).fast_info.shares
            return float(val) if val is not None else None
        except YFRateLimitError:
            continue
        except Exception as exc:
            logger.error("Failed to get shares for %s: %s", ticker, exc)
            return None
    logger.error("Exhausted retries for shares on %s", ticker)
    return None


def _build_records(
    tickers: list[str],
    prices: dict[str, tuple[Optional[float], Optional[str]]],
    ingested_at: str,
) -> tuple[list[dict], int]:
    """Combine price data with shares outstanding into records.

    Tickers with no price are skipped. Shares/market_cap may be null if fetch fails.
    """
    records: list[dict] = []
    errors = 0
    price_date_fallback = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for ticker in tickers:
        price_info = prices.get(ticker)
        if price_info is None:
            logger.warning("%s: no price data — skipping", ticker)
            errors += 1
            continue

        close_price, price_date = price_info
        shares = _fetch_shares(ticker)
        market_cap = (close_price * shares) if (close_price and shares) else None

        records.append({
            "ticker": ticker,
            "price_date": price_date or price_date_fallback,
            "close_price": close_price,
            "shares_outstanding": shares,
            "market_cap": market_cap,
            "ingested_at": ingested_at,
        })
        logger.info(
            "%s: price=%.2f shares=%s mktcap=%s",
            ticker,
            close_price or 0,
            f"{shares/1e9:.2f}B" if shares else "n/a",
            f"${market_cap/1e9:.1f}B" if market_cap else "n/a",
        )

    return records, errors


def _ensure_market_table(writer: DeltaWriter) -> None:
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
        writer._spark.sql(_MERGE_MARKET_DATA_SPARK.format(fqn=fqn))
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
    logger.info("Starting market data ingestion")

    settings = Settings.from_env()
    writer = DeltaWriter(settings)
    ingested_at = datetime.now(timezone.utc).isoformat()

    try:
        _ensure_market_table(writer)

        companies = fetch_sp500_tickers(settings.edgar_user_agent)
        tickers = [c.ticker for c in companies]
        logger.info("Processing %d tickers", len(tickers))

        prices = _fetch_prices_batch(tickers)
        records, errors = _build_records(tickers, prices, ingested_at)

        if records:
            _write_market_records(writer, records)

        logger.info(
            "Market data ingestion complete. Records written: %d. Errors: %d",
            len(records),
            errors,
        )
        if errors > 0:
            logger.warning("%d tickers had no price data and were skipped", errors)

    finally:
        writer.close()

    if len(records) == 0:
        logger.error("Zero records written — exiting with non-zero status")
        sys.exit(1)


if __name__ == "__main__":
    main()
