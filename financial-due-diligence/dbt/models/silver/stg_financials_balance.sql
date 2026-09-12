{{
    config(
        materialized='incremental',
        unique_key=['ticker', 'period_of_report', 'filing_type'],
        file_format='delta',
        incremental_strategy='merge'
    )
}}

-- Pivots balance sheet concept rows into columns.
-- One row per (ticker, period_of_report, filing_type).
-- Grain: ticker + period_of_report + filing_type

with source as (

    select * from {{ ref('brz_edgar_balance_sheet') }}

    {% if is_incremental() %}
        where filed_date > (select max(filed_date) from {{ this }})
    {% endif %}

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

        cast(max(case when concept = 'total_assets'     then value end) as decimal(20, 4)) as total_assets,
        cast(max(case when concept = 'total_liabilities' then value end) as decimal(20, 4)) as total_liabilities,
        cast(max(case when concept = 'total_equity'     then value end) as decimal(20, 4)) as total_equity,
        cast(max(case when concept = 'long_term_debt'   then value end) as decimal(20, 4)) as long_term_debt,
        cast(max(case when concept = 'short_term_debt'  then value end) as decimal(20, 4)) as short_term_debt,

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
