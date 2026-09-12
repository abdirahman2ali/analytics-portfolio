-- Assert that all composite scores in fct_company_scores fall within [0, 100].
-- Returns rows on failure; dbt treats any returned rows as a test failure.

select
    ticker,
    period_of_report,
    filing_type,
    composite_score

from {{ ref('fct_company_scores') }}

where
    composite_score < 0
    or composite_score > 100
