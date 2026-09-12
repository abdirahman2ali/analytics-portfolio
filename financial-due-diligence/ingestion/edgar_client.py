"""SEC EDGAR XBRL API wrapper with rate limiting."""

import logging
import time
from datetime import date, datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

CONCEPT_MAP: dict[str, str] = {
    "Revenues": "revenue",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "GrossProfit": "gross_profit",
    "OperatingIncomeLoss": "ebit",
    "NetIncomeLoss": "net_income",
    "NetCashProvidedByUsedInOperatingActivities": "ocf",
    "PaymentsToAcquirePropertyPlantAndEquipment": "capex",
    "Assets": "total_assets",
    "Liabilities": "total_liabilities",
    "StockholdersEquity": "total_equity",
    "LongTermDebt": "long_term_debt",
    "ShortTermBorrowings": "short_term_debt",
    "InterestExpense": "interest_expense",
    "EarningsPerShareBasic": "eps_basic",
}

_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/{cik}.json"
_MAX_REQUESTS_PER_SECOND = 10
_MIN_INTERVAL = 1.0 / _MAX_REQUESTS_PER_SECOND


class EdgarClient:
    """Wraps the SEC EDGAR company facts API with rate limiting."""

    def __init__(self, user_agent: str) -> None:
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": user_agent})
        self._last_request_time: float = 0.0

    def _rate_limit(self) -> None:
        """Sleep as needed to stay at or below 10 requests per second."""
        elapsed = time.monotonic() - self._last_request_time
        wait = _MIN_INTERVAL - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_time = time.monotonic()

    def get_company_facts(self, cik: str) -> dict:
        """Fetch raw XBRL company facts JSON for a given CIK.

        Args:
            cik: Zero-padded 10-digit CIK string, e.g. '0000320193'.

        Returns:
            Parsed JSON response from the EDGAR company facts endpoint.
        """
        self._rate_limit()
        url = _COMPANY_FACTS_URL.format(cik=cik)
        response = self._session.get(url, timeout=30)
        response.raise_for_status()
        logger.debug("Fetched company facts for CIK %s", cik)
        return response.json()  # type: ignore[no-any-return]

    def extract_filings(
        self,
        facts: dict,
        ticker: str,
        company_name: str,
        cik: str,
        filing_types: Optional[list[str]] = None,
    ) -> list[dict]:
        """Flatten XBRL facts into canonical filing records.

        Args:
            facts: Raw JSON from get_company_facts.
            ticker: Equity ticker symbol.
            company_name: Human-readable company name.
            cik: Zero-padded CIK string.
            filing_types: Allowlist of SEC form types, defaults to ['10-K', '10-Q'].

        Returns:
            List of dicts, one per (concept, filing period) combination.
        """
        if filing_types is None:
            filing_types = ["10-K", "10-Q"]

        ingested_at = datetime.now(timezone.utc).isoformat()
        records: list[dict] = []
        us_gaap = facts.get("facts", {}).get("us-gaap", {})

        for xbrl_concept, canonical_name in CONCEPT_MAP.items():
            concept_data = us_gaap.get(xbrl_concept, {})
            if not concept_data:
                continue

            for unit_type, entries in concept_data.get("units", {}).items():
                for entry in entries:
                    form = entry.get("form", "")
                    if form not in filing_types:
                        continue

                    period_of_report = entry.get("end", "")
                    filed_date_str = entry.get("filed", "")
                    if not period_of_report or not filed_date_str:
                        continue

                    filed_date = _parse_date(filed_date_str)
                    if filed_date is None:
                        continue

                    fiscal_year, fiscal_quarter = _derive_fiscal_period(
                        period_of_report, form
                    )

                    records.append(
                        {
                            "ticker": ticker,
                            "cik": cik,
                            "company_name": company_name,
                            "filing_type": form,
                            "period_of_report": period_of_report,
                            "filed_date": filed_date_str,
                            "fiscal_year": fiscal_year,
                            "fiscal_quarter": fiscal_quarter,
                            "concept": canonical_name,
                            "xbrl_concept": xbrl_concept,
                            "value": entry.get("val"),
                            "unit": unit_type,
                            "ingested_at": ingested_at,
                        }
                    )

        logger.info(
            "Extracted %d records for %s (%s)", len(records), ticker, cik
        )
        return records


def _parse_date(date_str: str) -> Optional[date]:
    """Parse YYYY-MM-DD string to a date object, returning None on failure."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def _derive_fiscal_period(period_of_report: str, form: str) -> tuple[int, Optional[int]]:
    """Derive fiscal year and quarter from the period end date and form type.

    Args:
        period_of_report: Period end date in YYYY-MM-DD format.
        form: SEC form type ('10-K' or '10-Q').

    Returns:
        Tuple of (fiscal_year, fiscal_quarter). fiscal_quarter is None for 10-K.
    """
    try:
        end_date = datetime.strptime(period_of_report, "%Y-%m-%d").date()
    except ValueError:
        return 0, None

    fiscal_year = end_date.year
    if form == "10-K":
        return fiscal_year, None

    month = end_date.month
    if month <= 3:
        fiscal_quarter = 1
    elif month <= 6:
        fiscal_quarter = 2
    elif month <= 9:
        fiscal_quarter = 3
    else:
        fiscal_quarter = 4

    return fiscal_year, fiscal_quarter
