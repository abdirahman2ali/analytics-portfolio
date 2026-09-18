{{ config(materialized='table') }}

-- Pivots cash flow concept rows into columns and derives FCF.
-- Grain: ticker + period_of_report + filing_type

with source as (

    select * from {{ ref('brz_edgar_cash_flow') }}

),

pivoted as (

    select
        ticker,
        cik,
        company_name,
        filing_type,
        period_of_report,
        filed_date,
        fiscal_year,
        fiscal_quarter,

        cast(max(case when concept = 'ocf' then value end) as decimal(20, 4)) as ocf,
        cast(max(case when concept = 'capex' then value end) as decimal(20, 4)) as capex,

        max(ingested_at) as ingested_at

    from source
    group by
        ticker,
        cik,
        company_name,
        filing_type,
        period_of_report,
        filed_date,
        fiscal_year,
        fiscal_quarter

),

with_fcf as (

    select
        *,
        -- CapEx is reported as a positive outflow in EDGAR; subtract to get FCF
        ocf - coalesce(capex, 0) as fcf

    from pivoted

)

select * from with_fcf
