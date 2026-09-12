"""Fetches the S&P 500 constituent list and maps tickers to SEC EDGAR CIKs."""

import logging
from dataclasses import dataclass

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_EDGAR_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


@dataclass
class CompanyInfo:
    """Represents one S&P 500 constituent with its EDGAR CIK."""

    ticker: str
    company_name: str
    gics_sector: str
    gics_sub_industry: str
    cik: str


def fetch_sp500_tickers(user_agent: str) -> list[CompanyInfo]:
    """Fetch S&P 500 constituents from Wikipedia and resolve CIKs from EDGAR.

    Args:
        user_agent: User-Agent string for SEC EDGAR requests.

    Returns:
        List of CompanyInfo for each constituent that has a resolvable CIK.
    """
    sp500_df = _fetch_wikipedia_table()
    cik_map = _fetch_edgar_cik_map(user_agent)

    companies: list[CompanyInfo] = []
    unresolved: list[str] = []

    for _, row in sp500_df.iterrows():
        ticker = str(row["Symbol"]).strip().replace(".", "-")
        cik = cik_map.get(ticker.upper())
        if cik is None:
            unresolved.append(ticker)
            continue

        companies.append(
            CompanyInfo(
                ticker=ticker,
                company_name=str(row.get("Security", "")),
                gics_sector=str(row.get("GICS Sector", "")),
                gics_sub_industry=str(row.get("GICS Sub-Industry", "")),
                cik=_pad_cik(cik),
            )
        )

    if unresolved:
        logger.warning(
            "Could not resolve CIKs for %d tickers: %s",
            len(unresolved),
            ", ".join(unresolved[:20]),
        )
    logger.info("Resolved %d S&P 500 companies with CIKs", len(companies))
    return companies


def _fetch_wikipedia_table() -> pd.DataFrame:
    """Pull the first S&P 500 table from Wikipedia."""
    tables = pd.read_html(_WIKIPEDIA_URL)
    df = tables[0]
    logger.info("Fetched %d rows from Wikipedia S&P 500 table", len(df))
    return df


def _fetch_edgar_cik_map(user_agent: str) -> dict[str, int]:
    """Download the full ticker→CIK mapping from SEC EDGAR in one request.

    Args:
        user_agent: User-Agent string required by EDGAR.

    Returns:
        Dict mapping uppercase ticker to integer CIK.
    """
    headers = {"User-Agent": user_agent}
    response = requests.get(_EDGAR_TICKERS_URL, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()

    cik_map: dict[str, int] = {}
    for entry in data.values():
        ticker = str(entry.get("ticker", "")).upper()
        cik = entry.get("cik_str")
        if ticker and cik is not None:
            cik_map[ticker] = int(cik)

    logger.info("Loaded %d ticker→CIK mappings from EDGAR", len(cik_map))
    return cik_map


def _pad_cik(cik: int) -> str:
    """Zero-pad a CIK integer to 10 digits as required by EDGAR URLs."""
    return str(cik).zfill(10)


def get_sample_companies() -> list[CompanyInfo]:
    """Return a small set of well-known companies for testing without network calls."""
    return [
        CompanyInfo("AAPL", "Apple Inc.", "Information Technology", "Technology Hardware, Storage & Peripherals", "0000320193"),
        CompanyInfo("MSFT", "Microsoft Corporation", "Information Technology", "Systems Software", "0000789019"),
        CompanyInfo("AMZN", "Amazon.com Inc.", "Consumer Discretionary", "Broadline Retail", "0001018724"),
        CompanyInfo("GOOGL", "Alphabet Inc.", "Communication Services", "Interactive Media & Services", "0001652044"),
        CompanyInfo("META", "Meta Platforms Inc.", "Communication Services", "Interactive Media & Services", "0001326801"),
        CompanyInfo("JPM", "JPMorgan Chase & Co.", "Financials", "Diversified Banks", "0000019617"),
        CompanyInfo("JNJ", "Johnson & Johnson", "Health Care", "Pharmaceuticals", "0000200406"),
        CompanyInfo("XOM", "Exxon Mobil Corporation", "Energy", "Integrated Oil & Gas", "0000034088"),
        CompanyInfo("WMT", "Walmart Inc.", "Consumer Staples", "Consumer Staples Merchandise Retail", "0000104169"),
        CompanyInfo("V", "Visa Inc.", "Financials", "Transaction & Payment Processing Services", "0001403161"),
    ]
