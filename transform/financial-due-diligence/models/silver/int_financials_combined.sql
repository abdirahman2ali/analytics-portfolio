{{
    config(
        materialized='incremental',
        unique_key=['ticker', 'period_of_report', 'filing_type'],
        file_format='delta',
        incremental_strategy='merge'
    )
}}

-- Joins all three normalized staging models into one wide table.
-- Also joins to the sp500_companies seed to bring in GICS sector.
-- One row per (ticker, period_of_report, filing_type).
-- Grain: ticker + period_of_report + filing_type

with income as (

    select * from {{ ref('stg_financials_income') }}

    {% if is_incremental() %}
        where filed_date > (select max(filed_date) from {{ this }})
    {% endif %}

),

balance as (

    select * from {{ ref('stg_financials_balance') }}

),

cashflow as (

    select * from {{ ref('stg_financials_cashflow') }}

),

companies as (

    select
        ticker,
        gics_sector,
        gics_sub_industry

    from {{ ref('sp500_companies') }}

),

joined as (

    select
        i.ticker,
        i.cik,
        coalesce(i.company_name, c.ticker) as company_name,
        c.gics_sector,
        c.gics_sub_industry,
        i.filing_type,
        i.period_of_report,
        i.filed_date,
        i.fiscal_year,
        i.fiscal_quarter,

        -- income statement
        i.revenue,
        i.gross_profit,
        i.ebit,
        i.net_income,
        i.eps_basic,
        i.interest_expense,

        -- balance sheet
        b.total_assets,
        b.total_liabilities,
        b.total_equity,
        b.long_term_debt,
        b.short_term_debt,

        -- cash flow
        cf.ocf,
        cf.capex,
        cf.fcf,

        greatest(
            coalesce(i.ingested_at, '1970-01-01'),
            coalesce(b.ingested_at, '1970-01-01'),
            coalesce(cf.ingested_at, '1970-01-01')
        ) as ingested_at

    from income as i
    left join balance as b
        on i.ticker = b.ticker
        and i.period_of_report = b.period_of_report
        and i.filing_type = b.filing_type
    left join cashflow as cf
        on i.ticker = cf.ticker
        and i.period_of_report = cf.period_of_report
        and i.filing_type = cf.filing_type
    left join companies as c
        on i.ticker = c.ticker

)

select * from joined
