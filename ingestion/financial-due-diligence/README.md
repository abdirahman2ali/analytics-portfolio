# Financial Due Diligence Pipeline

End-to-end pipeline that ingests SEC EDGAR XBRL data for all S&P 500 companies, transforms it through bronze/silver/gold dbt layers on Databricks, and produces a composite financial health score with letter grade and red/yellow flag overlays for investment due diligence.

## Architecture

```
SEC EDGAR API
    │
    ▼
sp500_fetcher.py          ← pulls S&P 500 tickers + CIKs (Wikipedia + EDGAR)
edgar_client.py           ← fetches XBRL company facts (rate-limited, 10 req/s)
delta_writer.py           ← writes to Databricks Delta, tracks incremental checkpoint
    │
    ▼
Delta Table: edgar_raw_facts
    │
    ▼
dbt bronze layer
  brz_edgar_submissions       ← full raw facts (all concepts)
  brz_edgar_income_statement  ← revenue, gross profit, EBIT, net income, EPS
  brz_edgar_balance_sheet     ← assets, liabilities, equity, debt
  brz_edgar_cash_flow         ← OCF, CapEx
    │
    ▼
dbt silver layer
  stg_financials_income       ← pivoted income statement (concept rows → columns)
  stg_financials_balance      ← pivoted balance sheet
  stg_financials_cashflow     ← pivoted cash flow, FCF derived (OCF - CapEx)
  int_financials_combined     ← wide table: all metrics joined + GICS sector
    │
    ▼
dbt gold layer
  fct_financial_metrics       ← computed ratios, growth rates, trend directions
  fct_peer_group_benchmarks   ← p20/p40/p60/p80 percentiles by GICS sector
  fct_metric_scores           ← 0-100 score per metric based on sector percentile rank
  fct_company_scores          ← composite score, letter grade, peer rank, flags
```

## Setup

### Requirements

- Python 3.11+
- dbt-databricks 1.7+
- A Databricks workspace with Unity Catalog enabled

### Python (ingestion)

```bash
cd financial-due-diligence/ingestion
pip install -r requirements.txt
```

### Environment variables

Copy `.env.example` to `.env` and fill in all values:

| Variable | Description | Example |
|---|---|---|
| `DATABRICKS_HOST` | Workspace hostname | `adb-1234.azuredatabricks.net` |
| `DATABRICKS_HTTP_PATH` | SQL warehouse HTTP path | `/sql/1.0/warehouses/abc123` |
| `DATABRICKS_TOKEN` | Personal access token | `dapiXXX...` |
| `DATABRICKS_CATALOG` | Unity Catalog target | `main` |
| `DATABRICKS_SCHEMA_BRONZE` | Bronze schema name | `bronze` |
| `DATABRICKS_SCHEMA_SILVER` | Silver schema name | `silver` |
| `DATABRICKS_SCHEMA_GOLD` | Gold schema name | `gold` |
| `EDGAR_USER_AGENT` | Required by EDGAR fair-use policy | `username project email@example.com` |

### dbt profiles

Copy `dbt/profiles.yml` to `~/.dbt/profiles.yml` (or keep it in the project directory and set `DBT_PROFILES_DIR`). It reads from the same env vars above — no edits needed.

## Running the pipeline

### 1. Ingestion

```bash
cd financial-due-diligence/ingestion
python edgar_ingestion.py
```

Fetches XBRL facts for all S&P 500 companies from EDGAR and writes new records to `edgar_raw_facts`. Incremental: only filings newer than the last checkpoint are processed on subsequent runs.

### 2. dbt

```bash
cd financial-due-diligence/dbt
dbt deps                          # install dbt_utils package
dbt seed                          # load sp500_companies.csv
dbt build --select bronze+        # build all layers + run tests
```

Run a single layer:

```bash
dbt run --select bronze           # bronze models only
dbt run --select silver           # silver models only
dbt run --select gold             # gold models only
dbt test                          # run all tests
```

## Deploying the Databricks job

```bash
databricks jobs create --json @financial-due-diligence/databricks/job_config.yml --profile abdirahman_portfolio
```

The job runs Mon-Fri at 07:00 UTC and executes two tasks in sequence:
1. `edgar_ingestion` — Python ingestion script
2. `dbt_run` — `dbt build --select bronze+ --fail-fast`

Update the `PLACEHOLDER_EMAIL` in `databricks/job_config.yml` with a real email before deploying.

## Data dictionary — `fct_company_scores`

| Column | Type | Description |
|---|---|---|
| `ticker` | string | Equity ticker symbol |
| `company_name` | string | Company legal name |
| `sector` | string | GICS sector |
| `period_of_report` | date | End of reporting period |
| `filing_type` | string | 10-K or 10-Q |
| `composite_score` | decimal | Weighted score 0-100 |
| `grade` | string | Letter grade: A+, A, B+, B, C+, C, D, F |
| `peer_rank` | int | Rank within GICS sector for this period (1 = best) |
| `flags` | array<string> | Red (🔴) and yellow (🟡) absolute flag labels |
| `revenue_growth_yoy_score` | decimal | Score for YoY revenue growth (0-100) |
| `revenue_cagr_3yr_score` | decimal | Score for 3-year revenue CAGR (0-100) |
| `gross_margin_score` | decimal | Score for gross margin (0-100) |
| `ebitda_margin_score` | decimal | Score for EBITDA margin (0-100) |
| `fcf_margin_score` | decimal | Score for FCF margin (0-100) |
| `fcf_conversion_score` | decimal | Score for FCF / net income conversion (0-100) |
| `debt_to_ebitda_score` | decimal | Score for debt leverage (lower debt = higher score) |
| `current_ratio_score` | decimal | Score for asset/liability coverage (0-100) |
| `interest_coverage_score` | decimal | Score for EBIT / interest expense (0-100) |
| `revenue_consistency_score` | decimal | Score for revenue stability (lower CV = higher score) |
| `revenue_growth_yoy` | decimal | Raw YoY revenue growth rate |
| `gross_margin` | decimal | Raw gross margin ratio |
| `ebitda_margin` | decimal | Raw EBITDA margin ratio |
| `fcf_margin` | decimal | Raw FCF margin ratio |
| `fcf_conversion` | decimal | Raw FCF / net income |
| `debt_to_ebitda` | decimal | Raw debt / EBITDA |
| `gross_margin_trend` | string | improving / stable / declining (trailing 3 quarters) |
| `ebitda_margin_trend` | string | improving / stable / declining |
| `revenue_growth_trend` | string | improving / stable / declining |

### Flag definitions

| Flag | Severity | Trigger |
|---|---|---|
| `fcf_negative` | 🔴 | FCF < 0 for 2+ consecutive quarters |
| `debt_overload` | 🔴 | debt_to_ebitda > 5x |
| `interest_coverage_weak` | 🔴 | interest_coverage < 2x |
| `negative_equity` | 🔴 | total_equity < 0 |
| `margin_compression` | 🟡 | Gross margin declining 3 consecutive quarters |
| `revenue_deceleration` | 🟡 | Revenue growth declining 3 consecutive quarters |
| `earnings_quality_risk` | 🟡 | fcf_conversion < 0.6 |
| `revenue_inconsistency` | 🟡 | Revenue coefficient of variation > 0.3 |
