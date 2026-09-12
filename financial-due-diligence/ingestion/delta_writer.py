"""Writes ingested EDGAR records to Databricks Delta tables."""

import logging
from datetime import date
from typing import Optional

from databricks import sql

from config import Settings

logger = logging.getLogger(__name__)

_RAW_FACTS_TABLE = "edgar_raw_facts"
_CHECKPOINT_TABLE = "ingestion_checkpoint"

_CREATE_RAW_FACTS_DDL = """
CREATE TABLE IF NOT EXISTS {catalog}.{schema}.{table} (
    ticker          STRING        NOT NULL,
    cik             STRING        NOT NULL,
    company_name    STRING,
    filing_type     STRING        NOT NULL,
    period_of_report STRING       NOT NULL,
    filed_date      STRING        NOT NULL,
    fiscal_year     INT,
    fiscal_quarter  INT,
    concept         STRING        NOT NULL,
    xbrl_concept    STRING,
    value           DOUBLE,
    unit            STRING,
    ingested_at     STRING        NOT NULL
)
USING DELTA
"""

_CREATE_CHECKPOINT_DDL = """
CREATE TABLE IF NOT EXISTS {catalog}.{schema}.{table} (
    cik             STRING        NOT NULL,
    last_filed_date STRING        NOT NULL,
    updated_at      TIMESTAMP     NOT NULL
)
USING DELTA
"""

_UPSERT_CHECKPOINT_SQL = """
MERGE INTO {catalog}.{schema}.{table} AS target
USING (SELECT '{cik}' AS cik, '{filed_date}' AS last_filed_date, current_timestamp() AS updated_at) AS source
ON target.cik = source.cik
WHEN MATCHED THEN UPDATE SET
    last_filed_date = source.last_filed_date,
    updated_at = source.updated_at
WHEN NOT MATCHED THEN INSERT (cik, last_filed_date, updated_at)
    VALUES (source.cik, source.last_filed_date, source.updated_at)
"""

_INSERT_FACTS_SQL = """
INSERT INTO {catalog}.{schema}.{table}
(ticker, cik, company_name, filing_type, period_of_report, filed_date,
 fiscal_year, fiscal_quarter, concept, xbrl_concept, value, unit, ingested_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class DeltaWriter:
    """Manages writes to Databricks Delta tables for the ingestion pipeline."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection = sql.connect(
            server_hostname=settings.databricks_host,
            http_path=settings.databricks_http_path,
            access_token=settings.databricks_token,
        )

    def ensure_tables_exist(self) -> None:
        """Create raw facts and checkpoint Delta tables if they do not already exist."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                _CREATE_RAW_FACTS_DDL.format(
                    catalog=self._settings.databricks_catalog,
                    schema=self._settings.databricks_schema_bronze,
                    table=_RAW_FACTS_TABLE,
                )
            )
            cursor.execute(
                _CREATE_CHECKPOINT_DDL.format(
                    catalog=self._settings.databricks_catalog,
                    schema=self._settings.databricks_schema_bronze,
                    table=_CHECKPOINT_TABLE,
                )
            )
        logger.info("Delta tables verified/created")

    def get_checkpoint(self, cik: str) -> Optional[date]:
        """Return the last successfully ingested filed_date for a given CIK.

        Args:
            cik: Zero-padded 10-digit CIK string.

        Returns:
            Most recent filed_date ingested, or None if this CIK has never been ingested.
        """
        sql_stmt = (
            f"SELECT last_filed_date FROM "
            f"{self._settings.databricks_catalog}.{self._settings.databricks_schema_bronze}.{_CHECKPOINT_TABLE} "
            f"WHERE cik = '{cik}'"
        )
        with self._connection.cursor() as cursor:
            cursor.execute(sql_stmt)
            row = cursor.fetchone()

        if row is None:
            return None

        from datetime import datetime

        return datetime.strptime(row[0], "%Y-%m-%d").date()

    def upsert_checkpoint(self, cik: str, filed_date: date) -> None:
        """Update (or insert) the ingestion checkpoint for a CIK.

        Args:
            cik: Zero-padded 10-digit CIK string.
            filed_date: The most recent filed_date successfully ingested.
        """
        sql_stmt = _UPSERT_CHECKPOINT_SQL.format(
            catalog=self._settings.databricks_catalog,
            schema=self._settings.databricks_schema_bronze,
            table=_CHECKPOINT_TABLE,
            cik=cik,
            filed_date=filed_date.isoformat(),
        )
        with self._connection.cursor() as cursor:
            cursor.execute(sql_stmt)
        logger.debug("Checkpoint updated for CIK %s → %s", cik, filed_date)

    def write_records(self, records: list[dict], table: str = _RAW_FACTS_TABLE) -> None:
        """Bulk-insert filing records into a Delta table.

        Args:
            records: List of canonical filing record dicts from EdgarClient.extract_filings.
            table: Target table name within the bronze schema.
        """
        if not records:
            return

        sql_stmt = _INSERT_FACTS_SQL.format(
            catalog=self._settings.databricks_catalog,
            schema=self._settings.databricks_schema_bronze,
            table=table,
        )
        rows = [
            (
                r["ticker"],
                r["cik"],
                r["company_name"],
                r["filing_type"],
                r["period_of_report"],
                r["filed_date"],
                r["fiscal_year"],
                r["fiscal_quarter"],
                r["concept"],
                r["xbrl_concept"],
                r["value"],
                r["unit"],
                r["ingested_at"],
            )
            for r in records
        ]

        with self._connection.cursor() as cursor:
            cursor.executemany(sql_stmt, rows)

        logger.info("Wrote %d records to %s", len(records), table)

    def close(self) -> None:
        """Close the Databricks connection."""
        self._connection.close()
