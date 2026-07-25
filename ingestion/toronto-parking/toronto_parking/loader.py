import logging
import os
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

CATALOG = "abdirahman_portfolio"
INGESTION_SCHEMA = "toronto_parking_raw"
RAW_TABLE = "parking_tickets_raw"
CENTRELINES_TABLE = "street_centrelines"
CHUNK_SIZE = 100_000

TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{INGESTION_SCHEMA}.{RAW_TABLE} (
    tag_number_masked      STRING,
    date_of_infraction     DATE,
    infraction_code        INT,
    infraction_description STRING,
    set_fine_amount        DECIMAL(10, 2),
    time_of_infraction     STRING,
    location1              STRING,
    location2              STRING,
    officer_tag_number     STRING,
    province               STRING,
    loaded_at              TIMESTAMP
)
USING DELTA
"""


CENTRELINES_DDL = f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{INGESTION_SCHEMA}.{CENTRELINES_TABLE} (
    lname      STRING,
    latitude   DOUBLE,
    longitude  DOUBLE,
    loaded_at  TIMESTAMP
)
USING DELTA
"""


def _is_databricks() -> bool:
    return "DATABRICKS_RUNTIME_VERSION" in os.environ


def _spark():
    from pyspark.sql import SparkSession
    return SparkSession.builder.getOrCreate()


def _get_connection():
    from databricks import sql as dbsql
    return dbsql.connect(
        server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    )


def ensure_schema() -> None:
    if _is_databricks():
        spark = _spark()
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{INGESTION_SCHEMA}")
    else:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{INGESTION_SCHEMA}")
    logger.info(f"Schema '{CATALOG}.{INGESTION_SCHEMA}' ensured")


def ensure_table() -> None:
    if _is_databricks():
        _spark().sql(TABLE_DDL)
    else:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(TABLE_DDL)
    logger.info(f"Table '{CATALOG}.{INGESTION_SCHEMA}.{RAW_TABLE}' ensured")


def _loaded_years() -> list[int]:
    query = f"SELECT DISTINCT YEAR(date_of_infraction) AS yr FROM {CATALOG}.{INGESTION_SCHEMA}.{RAW_TABLE} ORDER BY yr"
    try:
        if _is_databricks():
            rows = _spark().sql(query).collect()
            return [r[0] for r in rows]
        else:
            with _get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    return [r[0] for r in cur.fetchall()]
    except Exception:
        return []


def upsert_dataframe(df: pd.DataFrame, year: Optional[int] = None) -> int:
    """Delete existing rows for the year then insert the full year's data.

    Returns the number of rows inserted.
    """
    if df.empty:
        return 0

    df = df.copy()
    df["loaded_at"] = pd.Timestamp.now()

    full_table = f"{CATALOG}.{INGESTION_SCHEMA}.{RAW_TABLE}"

    if _is_databricks():
        spark = _spark()
        if year is not None:
            existing = spark.sql(
                f"SELECT COUNT(*) FROM {full_table} WHERE YEAR(date_of_infraction) = {year}"
            ).collect()[0][0]
            if existing > 0:
                logger.info(f"[{year}] Deleting {existing:,} existing rows")
                spark.sql(f"DELETE FROM {full_table} WHERE YEAR(date_of_infraction) = {year}")

        spark_df = spark.createDataFrame(df)
        spark_df.write.format("delta").mode("append").saveAsTable(full_table)
    else:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                if year is not None:
                    cur.execute(
                        f"SELECT COUNT(*) FROM {full_table} WHERE YEAR(date_of_infraction) = {year}"
                    )
                    existing = cur.fetchone()[0]
                    if existing > 0:
                        logger.info(f"[{year}] Deleting {existing:,} existing rows")
                        cur.execute(
                            f"DELETE FROM {full_table} WHERE YEAR(date_of_infraction) = {year}"
                        )

                cols = list(df.columns)
                placeholders = ", ".join(["?" for _ in cols])
                col_list = ", ".join(cols)
                insert_sql = f"INSERT INTO {full_table} ({col_list}) VALUES ({placeholders})"
                records = df.where(pd.notnull(df), None).values.tolist()
                for i in range(0, len(records), CHUNK_SIZE):
                    cur.executemany(insert_sql, records[i : i + CHUNK_SIZE])

    rows = len(df)
    logger.info(f"[{year}] Inserted {rows:,} rows")
    return rows


def ensure_centrelines_table() -> None:
    if _is_databricks():
        _spark().sql(CENTRELINES_DDL)
    else:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(CENTRELINES_DDL)
    logger.info(f"Table '{CATALOG}.{INGESTION_SCHEMA}.{CENTRELINES_TABLE}' ensured")


def replace_centrelines(df: pd.DataFrame) -> int:
    """Overwrite street_centrelines with a fresh geocoded dataset.

    Deletes all existing rows then inserts the new set. The table is small
    (~6-10k rows) so a full replace is cheaper than a merge.
    """
    if df.empty:
        logger.warning("No centreline rows to load — skipping")
        return 0

    df = df.copy()
    df["loaded_at"] = pd.Timestamp.now()

    full_table = f"{CATALOG}.{INGESTION_SCHEMA}.{CENTRELINES_TABLE}"

    if _is_databricks():
        spark = _spark()
        spark_df = spark.createDataFrame(df)
        spark_df.write.format("delta").mode("overwrite").saveAsTable(full_table)
    else:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {full_table}")
                cols = list(df.columns)
                placeholders = ", ".join(["?" for _ in cols])
                col_list = ", ".join(cols)
                insert_sql = f"INSERT INTO {full_table} ({col_list}) VALUES ({placeholders})"
                records = df.where(pd.notnull(df), None).values.tolist()
                for i in range(0, len(records), CHUNK_SIZE):
                    cur.executemany(insert_sql, records[i : i + CHUNK_SIZE])

    rows = len(df)
    logger.info(f"Centrelines loaded: {rows:,} street names")
    return rows
