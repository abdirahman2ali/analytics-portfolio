"""Writes ingested EDGAR records to Databricks Delta tables."""

import logging
from datetime import date, datetime
from typing import Optional

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


def _try_get_spark():
    """Return the active SparkSession when running on-cluster, else None."""
    try:
        from pyspark.sql import SparkSession  # type: ignore[import]
        return SparkSession.builder.getOrCreate()
    except Exception:
        return None


class DeltaWriter:
    """Manages writes to Databricks Delta tables for the ingestion pipeline."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._spark = _try_get_spark()
        if self._spark:
            logger.debug("On-cluster: using SparkSession for Delta writes")
            self._conn = None
        else:
            from databricks import sql
            self._conn = sql.connect(
                server_hostname=settings.databricks_host,
                http_path=settings.databricks_http_path,
                access_token=settings.databricks_token,
            )

    def ensure_tables_exist(self) -> None:
        """Create raw facts and checkpoint Delta tables if they do not already exist."""
        cat = self._settings.databricks_catalog
        sch = self._settings.databricks_schema_bronze
        raw_ddl = _CREATE_RAW_FACTS_DDL.format(catalog=cat, schema=sch, table=_RAW_FACTS_TABLE)
        chk_ddl = _CREATE_CHECKPOINT_DDL.format(catalog=cat, schema=sch, table=_CHECKPOINT_TABLE)
        if self._spark:
            self._spark.sql(raw_ddl)
            self._spark.sql(chk_ddl)
        else:
            with self._conn.cursor() as cursor:  # type: ignore[union-attr]
                cursor.execute(raw_ddl)
                cursor.execute(chk_ddl)
        logger.info("Delta tables verified/created")

    def get_checkpoint(self, cik: str) -> Optional[date]:
        """Return the last successfully ingested filed_date for a given CIK.

        Args:
            cik: Zero-padded 10-digit CIK string.

        Returns:
            Most recent filed_date ingested, or None if this CIK has never been ingested.
        """
        fqn = (
            f"{self._settings.databricks_catalog}"
            f".{self._settings.databricks_schema_bronze}"
            f".{_CHECKPOINT_TABLE}"
        )
        sql_stmt = f"SELECT last_filed_date FROM {fqn} WHERE cik = '{cik}'"
        if self._spark:
            row = self._spark.sql(sql_stmt).first()
            if row is None:
                return None
            return datetime.strptime(row["last_filed_date"], "%Y-%m-%d").date()
        else:
            with self._conn.cursor() as cursor:  # type: ignore[union-attr]
                cursor.execute(sql_stmt)
                row = cursor.fetchone()
            if row is None:
                return None
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
        if self._spark:
            self._spark.sql(sql_stmt)
        else:
            with self._conn.cursor() as cursor:  # type: ignore[union-attr]
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

        cat = self._settings.databricks_catalog
        sch = self._settings.databricks_schema_bronze
        fqn = f"{cat}.{sch}.{table}"

        if self._spark:
            from pyspark.sql.types import (  # type: ignore[import]
                DoubleType,
                IntegerType,
                StringType,
                StructField,
                StructType,
            )
            spark_schema = StructType([
                StructField("ticker", StringType(), nullable=False),
                StructField("cik", StringType(), nullable=False),
                StructField("company_name", StringType(), nullable=True),
                StructField("filing_type", StringType(), nullable=False),
                StructField("period_of_report", StringType(), nullable=False),
                StructField("filed_date", StringType(), nullable=False),
                StructField("fiscal_year", IntegerType(), nullable=True),
                StructField("fiscal_quarter", IntegerType(), nullable=True),
                StructField("concept", StringType(), nullable=False),
                StructField("xbrl_concept", StringType(), nullable=True),
                StructField("value", DoubleType(), nullable=True),
                StructField("unit", StringType(), nullable=True),
                StructField("ingested_at", StringType(), nullable=False),
            ])
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
                    float(r["value"]) if r["value"] is not None else None,
                    r["unit"],
                    r["ingested_at"],
                )
                for r in records
            ]
            df = self._spark.createDataFrame(rows, spark_schema)
            df.write.mode("append").saveAsTable(fqn)
        else:
            sql_stmt = _INSERT_FACTS_SQL.format(catalog=cat, schema=sch, table=table)
            rows_sql = [
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
            with self._conn.cursor() as cursor:  # type: ignore[union-attr]
                cursor.executemany(sql_stmt, rows_sql)

        logger.info("Wrote %d records to %s", len(records), fqn)

    def close(self) -> None:
        """Close the Databricks connection (no-op when using SparkSession)."""
        if self._conn:
            self._conn.close()
