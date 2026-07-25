import logging

import pandas as pd

logger = logging.getLogger(__name__)

# Canonical column names as they appear in CKAN CSV files
_KNOWN_COLUMNS: list[str] = [
    "tag_number_masked",
    "date_of_infraction",
    "infraction_code",
    "infraction_description",
    "set_fine_amount",
    "time_of_infraction",
    "location1",
    "location2",
    "officer_tag_number",
    "province",
]


def prepare_for_db(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize a raw parking tickets DataFrame for DB load.

    Normalizes column names, casts types, and drops rows missing the partition key.
    """
    df = df.copy()

    # Normalize column names: lowercase, strip whitespace
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Keep only recognized columns that are present
    keep = [c for c in _KNOWN_COLUMNS if c in df.columns]
    missing = [c for c in _KNOWN_COLUMNS if c not in df.columns]
    if missing:
        logger.debug(f"Columns not found in source (will be skipped): {missing}")
    df = df[keep]

    # date_of_infraction: YYYYMMDD integer/string → Python date
    # A single null in the column causes pandas to read it as float64, making
    # valid dates like 20250101 appear as "20250101.0" after astype(str).
    # Split on "." to strip the decimal before parsing.
    if "date_of_infraction" in df.columns:
        df["date_of_infraction"] = pd.to_datetime(
            df["date_of_infraction"].astype(str).str.strip().str.split(".").str[0],
            format="%Y%m%d",
            errors="coerce",
        ).dt.date

    # time_of_infraction: store as zero-padded 4-char string (e.g. "0930")
    if "time_of_infraction" in df.columns:
        df["time_of_infraction"] = (
            pd.to_numeric(df["time_of_infraction"], errors="coerce")
            .fillna(0)
            .astype(int)
            .astype(str)
            .str.zfill(4)
        )

    if "infraction_code" in df.columns:
        df["infraction_code"] = pd.to_numeric(df["infraction_code"], errors="coerce")

    if "set_fine_amount" in df.columns:
        df["set_fine_amount"] = pd.to_numeric(df["set_fine_amount"], errors="coerce")

    if "infraction_description" in df.columns:
        df["infraction_description"] = df["infraction_description"].astype(str).str.strip()

    if "location1" in df.columns:
        df["location1"] = df["location1"].astype(str).str.strip().str.upper()

    if "location2" in df.columns:
        df["location2"] = df["location2"].astype(str).str.strip().str.upper()

    # Drop rows missing the partition key (required by partitioned table)
    before = len(df)
    df = df.dropna(subset=["date_of_infraction"])
    dropped = before - len(df)
    if dropped:
        logger.warning(f"Dropped {dropped:,} rows with null date_of_infraction")

    return df
