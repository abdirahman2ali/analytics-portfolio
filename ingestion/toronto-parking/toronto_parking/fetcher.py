import logging
import re
import zipfile
from io import BytesIO
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

CKAN_BASE_URL = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
PACKAGE_ID = "parking-tickets"
REQUEST_TIMEOUT = 120


def _get_package_resources() -> list[dict]:
    url = f"{CKAN_BASE_URL}/api/3/action/package_show"
    resp = requests.get(url, params={"id": PACKAGE_ID}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"CKAN API returned success=false for package {PACKAGE_ID}")
    return data["result"]["resources"]


def _extract_year(name: str) -> Optional[int]:
    match = re.search(r"\b(20\d{2})\b", name)
    return int(match.group(1)) if match else None


_ENCODINGS = ("utf-8", "utf-16", "latin-1", "cp1252")
# Older years (pre-2020) use Latin-1/CP1252; 2021 ZIP contains .txt files not .csv


def _read_csv_bytes(content: bytes) -> pd.DataFrame:
    """Try multiple encodings and quoting modes; return first successful parse.

    Two passes:
    1. Standard quoting — handles well-formed CSVs and UTF-16 files with bad rows.
    2. QUOTE_NONE — handles files with unclosed quotes (e.g. 2013) that cause
       the C parser to read until EOF looking for the closing quote.
    """
    import csv as _csv

    for quoting in (None, _csv.QUOTE_NONE):
        kwargs: dict = {"low_memory": False, "on_bad_lines": "skip"}
        if quoting is not None:
            kwargs["quoting"] = quoting
            kwargs["escapechar"] = "\\"
        for enc in _ENCODINGS:
            try:
                return pd.read_csv(BytesIO(content), encoding=enc, **kwargs)
            except UnicodeDecodeError:
                continue
            except Exception as exc:
                logger.debug(f"  encoding={enc} quoting={quoting} failed: {type(exc).__name__}: {exc}")
                continue
    raise ValueError("Could not decode CSV with any known encoding")


def _is_tabular(name: str) -> bool:
    """Return True for .csv, .txt, or numbered chunk extensions like .000, .001."""
    lower = name.lower()
    if lower.endswith((".csv", ".txt")):
        return True
    # Numbered split parts — e.g. Parking_Tags_Data_2021.000
    suffix = lower.rsplit(".", 1)[-1]
    return suffix.isdigit()


def _download_csv(resource: dict) -> pd.DataFrame:
    url = resource["url"]
    logger.info(f"Downloading from {url}")
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    content = resp.content

    fmt = resource.get("format", "").upper()
    if fmt == "ZIP" or url.lower().endswith(".zip"):
        with zipfile.ZipFile(BytesIO(content)) as zf:
            tabular = sorted(
                n for n in zf.namelist()
                if _is_tabular(n) and not n.startswith("__MACOSX")
            )
            if not tabular:
                raise ValueError(f"No tabular file found in ZIP: {url} — contents: {zf.namelist()}")
            if len(tabular) == 1:
                with zf.open(tabular[0]) as f:
                    return _read_csv_bytes(f.read())
            # Multiple parts — read and concatenate all chunks
            logger.info(f"ZIP contains {len(tabular)} parts — concatenating")
            parts = []
            for name in tabular:
                with zf.open(name) as f:
                    parts.append(_read_csv_bytes(f.read()))
            return pd.concat(parts, ignore_index=True)

    return _read_csv_bytes(content)


def fetch_available_years() -> list[int]:
    """Return all years available in the CKAN parking tickets package."""
    resources = _get_package_resources()
    years = []
    for r in resources:
        year = _extract_year(r.get("name", ""))
        if year:
            years.append(year)
    return sorted(set(years))


def fetch_year(year: int) -> Optional[pd.DataFrame]:
    """Download and return the parking tickets DataFrame for the given year.

    Some years have multiple CKAN resources (split ZIPs). All matching
    resources are downloaded and concatenated into a single DataFrame.
    """
    resources = _get_package_resources()
    targets = [r for r in resources if _extract_year(r.get("name", "")) == year]
    if not targets:
        logger.warning(f"No CKAN resource found for year {year}")
        return None

    if len(targets) == 1:
        logger.info(f"Fetching {year} parking tickets: {targets[0]['name']}")
        return _download_csv(targets[0])

    logger.info(f"Fetching {year} parking tickets: {len(targets)} resources — concatenating")
    parts = []
    for r in targets:
        logger.info(f"  → {r['name']}")
        parts.append(_download_csv(r))
    return pd.concat(parts, ignore_index=True)
