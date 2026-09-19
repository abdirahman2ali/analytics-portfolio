{{ config(materialized='table') }}

-- Market multiples for S&P 500 constituents using LTM financials + latest market price.
-- Grain: one row per ticker (most recent LTM 10-Q snapshot joined to latest close price).
-- Note: EV excludes cash and cash equivalents (not available from EDGAR XBRL).

with financials as (

    select * from {{ ref('int_financials_combined') }}

),

ltm as (

    select
        ticker,
        cik,
        company_name,
        gics_sector,
        gics_sub_industry,
        period_of_report,
        filed_date,
        fiscal_year,
        fiscal_quarter,

        -- balance sheet: point-in-time (not summed)
        total_equity,
        coalesce(long_term_debt, 0) as long_term_debt,
        coalesce(short_term_debt, 0) as short_term_debt,

        -- LTM aggregates: 4-quarter rolling sum
        sum(net_income) over (
            partition by ticker, filing_type
            order by period_of_report
            rows between 3 preceding and current row
        ) as ltm_net_income,

        sum(ebit) over (
            partition by ticker, filing_type
            order by period_of_report
            rows between 3 preceding and current row
        ) as ltm_ebit,

        sum(fcf) over (
            partition by ticker, filing_type
            order by period_of_report
            rows between 3 preceding and current row
        ) as ltm_fcf,

        sum(revenue) over (
            partition by ticker, filing_type
            order by period_of_report
            rows between 3 preceding and current row
        ) as ltm_revenue,

        row_number() over (
            partition by ticker
            order by period_of_report desc
        ) as _rn

    from financials
    where filing_type = '10-Q'

),

latest_financials as (

    select * from ltm where _rn = 1

),

latest_market as (

    select
        ticker,
        price_date,
        close_price,
        shares_outstanding,
        market_cap,
        row_number() over (
            partition by ticker
            order by price_date desc
        ) as _rn

    from {{ ref('brz_market_data') }}

),

latest_market_deduped as (

    select * from latest_market where _rn = 1

),

joined as (

    select
        f.ticker,
        f.cik,
        f.company_name,
        f.gics_sector,
        f.gics_sub_industry,
        f.period_of_report   as ltm_period_end,
        f.filed_date,
        f.fiscal_year,
        f.fiscal_quarter,

        -- market data
        m.price_date,
        m.close_price,
        m.shares_outstanding,
        m.market_cap,

        -- LTM financials
        f.ltm_net_income,
        f.ltm_ebit,
        f.ltm_fcf,
        f.ltm_revenue,
        f.total_equity,
        f.long_term_debt,
        f.short_term_debt,

        -- enterprise value (excl. cash)
        m.market_cap + f.long_term_debt + f.short_term_debt as ev_approx,

        -- market multiples
        m.market_cap / nullif(f.ltm_net_income, 0)     as pe_ratio,
        m.market_cap / nullif(f.ltm_fcf, 0)            as p_fcf_ratio,
        m.market_cap / nullif(f.total_equity, 0)       as price_to_book,
        (m.market_cap + f.long_term_debt + f.short_term_debt)
            / nullif(f.ltm_ebit, 0)                    as ev_to_ebit

    from latest_financials as f
    inner join latest_market_deduped as m
        on f.ticker = m.ticker

)

select * from joined
