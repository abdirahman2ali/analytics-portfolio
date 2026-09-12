select
    {{ dbt_utils.generate_surrogate_key(['cik', 'xbrl_concept', 'period_of_report', 'filing_type', 'filed_date']) }} as filing_id,
    ticker,
    cik,
    company_name,
    filing_type,
    cast(period_of_report as date) as period_of_report,
    cast(filed_date as date) as filed_date,
    cast(fiscal_year as int) as fiscal_year,
    cast(fiscal_quarter as int) as fiscal_quarter,
    concept,
    xbrl_concept,
    cast(value as double) as value,
    unit,
    ingested_at

from {{ source('edgar_raw', 'edgar_raw_facts') }}
