import os
import pandas as pd

CATALOG = "abdirahman_portfolio"
INGESTION_SCHEMA = "nba_raw"

TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{INGESTION_SCHEMA}.{{table_name}} (
    player_id STRING,
    player STRING,
    age DECIMAL(5,2),
    team STRING,
    pos STRING,
    g DECIMAL(5,1),
    fg DECIMAL(7,1),
    fga DECIMAL(7,1),
    fg_pct DECIMAL(5,3),
    ft DECIMAL(7,1),
    fta DECIMAL(7,1),
    ft_pct DECIMAL(5,3),
    ast DECIMAL(7,1),
    pf DECIMAL(7,1),
    pts DECIMAL(7,1),
    awards STRING,
    season STRING,
    trb DECIMAL(7,1),
    mp DECIMAL(7,1),
    gs DECIMAL(5,1),
    orb DECIMAL(7,1),
    drb DECIMAL(7,1),
    stl DECIMAL(7,1),
    blk DECIMAL(7,1),
    tov DECIMAL(7,1),
    three_p DECIMAL(7,1),
    three_pa DECIMAL(7,1),
    three_p_pct DECIMAL(5,3),
    two_p DECIMAL(7,1),
    two_pa DECIMAL(7,1),
    two_p_pct DECIMAL(5,3),
    efg_pct DECIMAL(5,3),
    trp_dbl INT,
    loaded_at TIMESTAMP
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
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{INGESTION_SCHEMA}")
    else:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {INGESTION_SCHEMA}")


def ensure_table(table_name: str = "player_season_totals") -> None:
    ddl = TABLE_DDL.format(table_name=table_name)
    if _is_databricks():
        _spark().sql(ddl)
    else:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)


def get_last_loaded_year(table_name: str = "player_season_totals"):
    query = f"SELECT MAX(CAST(LEFT(season, 4) AS INT) + 1) FROM {CATALOG}.{INGESTION_SCHEMA}.{table_name}"
    if _is_databricks():
        try:
            row = _spark().sql(query).collect()[0]
            return row[0]
        except Exception:
            return None
    else:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                row = cur.fetchone()
                return row[0] if row else None


def get_loaded_seasons(table_name: str = "player_season_totals") -> set[str]:
    query = f"SELECT DISTINCT season FROM {CATALOG}.{INGESTION_SCHEMA}.{table_name}"
    if _is_databricks():
        try:
            rows = _spark().sql(query).collect()
            return {r[0] for r in rows}
        except Exception:
            return set()
    else:
        try:
            with _get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    return {r[0] for r in cur.fetchall()}
        except Exception:
            return set()


def write_to_db(df: pd.DataFrame, table_name: str = "player_season_totals") -> None:
    df = df.copy()
    df["loaded_at"] = pd.Timestamp.now()

    if _is_databricks():
        spark_df = _spark().createDataFrame(df)
        spark_df.write.format("delta").mode("append").saveAsTable(f"{CATALOG}.{INGESTION_SCHEMA}.{table_name}")
    else:
        cols = list(df.columns)
        placeholders = ", ".join(["?" for _ in cols])
        col_list = ", ".join(cols)
        insert_sql = f"INSERT INTO {INGESTION_SCHEMA}.{table_name} ({col_list}) VALUES ({placeholders})"

        with _get_connection() as conn:
            with conn.cursor() as cur:
                chunk_size = 500
                records = df.where(pd.notnull(df), None).values.tolist()
                int_cols = {col: cols.index(col) for col in ("trp_dbl",) if col in cols}
                for rec in records:
                    for col, idx in int_cols.items():
                        if rec[idx] is not None:
                            rec[idx] = int(rec[idx])
                for i in range(0, len(records), chunk_size):
                    cur.executemany(insert_sql, records[i : i + chunk_size])
