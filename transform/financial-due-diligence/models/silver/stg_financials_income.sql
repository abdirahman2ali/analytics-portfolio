{{ config(materialized='table') }}

-- Pivots income statement concept rows into columns.
-- Grain: ticker + period_of_report + filing_type

with source as (

    select * from {{ ref('brz_edgar_income_statement') }}

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

        cast(max(case when concept = 'revenue' then value end) as decimal(20, 4)) as revenue,
        cast(max(case when concept = 'gross_profit' then value end) as decimal(20, 4)) as gross_profit,
        cast(max(case when concept = 'ebit' then value end) as decimal(20, 4)) as ebit,
        cast(max(case when concept = 'net_income' then value end) as decimal(20, 4)) as net_income,
        cast(max(case when concept = 'eps_basic' then value end) as decimal(20, 4)) as eps_basic,
        cast(max(case when concept = 'interest_expense' then value end) as decimal(20, 4)) as interest_expense,

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

)

select * from pivoted
