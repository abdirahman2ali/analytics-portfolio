{{
    config(
        materialized='incremental',
        unique_key=['ticker', 'period_of_report', 'filing_type'],
        file_format='delta',
        incremental_strategy='merge'
    )
}}

-- Computes all per-company-per-period financial metrics using window functions.
-- Grain: ticker + period_of_report + filing_type

with base as (

    select * from {{ ref('int_financials_combined') }}

    {% if is_incremental() %}
        where filed_date > (select max(filed_date) from {{ this }})
    {% endif %}

),

windowed as (

    select
        ticker,
        cik,
        company_name,
        gics_sector,
        gics_sub_industry,
        filing_type,
        period_of_report,
        filed_date,
        fiscal_year,
        fiscal_quarter,

        revenue,
        gross_profit,
        ebit,
        net_income,
        fcf,
        ocf,
        capex,
        total_assets,
        total_liabilities,
        total_equity,
        long_term_debt,
        short_term_debt,

        -- YoY growth uses 4-quarter lag for quarterly filings
        lag(revenue, 4) over (partition by ticker, filing_type order by period_of_report) as revenue_4q_ago,
        lag(revenue, 12) over (partition by ticker, filing_type order by period_of_report) as revenue_12q_ago,

        -- trailing 8 quarters for coefficient of variation
        avg(revenue) over (
            partition by ticker, filing_type
            order by period_of_report
            rows between 7 preceding and current row
        ) as revenue_trailing_8q_avg,

        stddev_samp(revenue) over (
            partition by ticker, filing_type
            order by period_of_report
            rows between 7 preceding and current row
        ) as revenue_trailing_8q_stddev,

        -- trailing 3 quarters for trend direction
        lag(gross_profit / nullif(revenue, 0), 1) over (partition by ticker, filing_type order by period_of_report) as gross_margin_1q_ago,
        lag(gross_profit / nullif(revenue, 0), 2) over (partition by ticker, filing_type order by period_of_report) as gross_margin_2q_ago,

        lag(ebit / nullif(revenue, 0), 1) over (partition by ticker, filing_type order by period_of_report) as ebitda_margin_1q_ago,
        lag(ebit / nullif(revenue, 0), 2) over (partition by ticker, filing_type order by period_of_report) as ebitda_margin_2q_ago,

        lag(
            (revenue - lag(revenue, 4) over (partition by ticker, filing_type order by period_of_report))
            / nullif(lag(revenue, 4) over (partition by ticker, filing_type order by period_of_report), 0),
            1
        ) over (partition by ticker, filing_type order by period_of_report) as rev_growth_1q_ago,

        lag(
            (revenue - lag(revenue, 4) over (partition by ticker, filing_type order by period_of_report))
            / nullif(lag(revenue, 4) over (partition by ticker, filing_type order by period_of_report), 0),
            2
        ) over (partition by ticker, filing_type order by period_of_report) as rev_growth_2q_ago

    from base

),

metrics as (

    select
        ticker,
        cik,
        company_name,
        gics_sector,
        gics_sub_industry,
        filing_type,
        period_of_report,
        filed_date,
        fiscal_year,
        fiscal_quarter,

        -- growth
        (revenue - revenue_4q_ago) / nullif(revenue_4q_ago, 0) as revenue_growth_yoy,
        power(revenue / nullif(revenue_12q_ago, 0), 1.0 / 3.0) - 1 as revenue_cagr_3yr,

        -- margins
        gross_profit / nullif(revenue, 0) as gross_margin,
        ebit / nullif(revenue, 0) as ebitda_margin,
        net_income / nullif(revenue, 0) as net_income_margin,
        fcf / nullif(revenue, 0) as fcf_margin,
        fcf / nullif(net_income, 0) as fcf_conversion,

        -- leverage & coverage
        (coalesce(long_term_debt, 0) + coalesce(short_term_debt, 0)) / nullif(ebit, 0) as debt_to_ebitda,
        total_assets / nullif(total_liabilities, 0) as current_ratio,
        ebit / nullif(interest_expense, 0) as interest_coverage,

        -- consistency: coefficient of variation (lower = more consistent)
        revenue_trailing_8q_stddev / nullif(revenue_trailing_8q_avg, 0) as revenue_consistency,

        -- trend direction (3-quarter slope) for gross_margin
        case
            when gross_profit / nullif(revenue, 0) > gross_margin_1q_ago
             and gross_margin_1q_ago > gross_margin_2q_ago then 'improving'
            when gross_profit / nullif(revenue, 0) < gross_margin_1q_ago
             and gross_margin_1q_ago < gross_margin_2q_ago then 'declining'
            else 'stable'
        end as gross_margin_trend,

        -- trend direction for ebitda_margin
        case
            when ebit / nullif(revenue, 0) > ebitda_margin_1q_ago
             and ebitda_margin_1q_ago > ebitda_margin_2q_ago then 'improving'
            when ebit / nullif(revenue, 0) < ebitda_margin_1q_ago
             and ebitda_margin_1q_ago < ebitda_margin_2q_ago then 'declining'
            else 'stable'
        end as ebitda_margin_trend,

        -- trend direction for revenue_growth
        case
            when (revenue - revenue_4q_ago) / nullif(revenue_4q_ago, 0) > rev_growth_1q_ago
             and rev_growth_1q_ago > rev_growth_2q_ago then 'improving'
            when (revenue - revenue_4q_ago) / nullif(revenue_4q_ago, 0) < rev_growth_1q_ago
             and rev_growth_1q_ago < rev_growth_2q_ago then 'declining'
            else 'stable'
        end as revenue_growth_trend,

        -- raw values carried forward for downstream scoring
        fcf,
        total_equity,
        revenue

    from windowed

)

select * from metrics
