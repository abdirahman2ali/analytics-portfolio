{{
    config(
        materialized='incremental',
        unique_key=['ticker', 'period_of_report', 'filing_type'],
        file_format='delta',
        incremental_strategy='merge'
    )
}}

-- FCF components, ratios, growth, trends, and CapEx intensity.
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

        -- FCF components
        ocf,
        capex,
        fcf,
        revenue,
        net_income,

        -- trailing FCF values for growth and trend calculations
        lag(fcf, 4) over (partition by ticker, filing_type order by period_of_report) as fcf_4q_ago,
        lag(fcf, 12) over (partition by ticker, filing_type order by period_of_report) as fcf_12q_ago,

        -- trailing capex for intensity trend
        lag(capex / nullif(revenue, 0), 1) over (partition by ticker, filing_type order by period_of_report) as capex_intensity_1q_ago,
        lag(capex / nullif(revenue, 0), 2) over (partition by ticker, filing_type order by period_of_report) as capex_intensity_2q_ago,

        -- trailing fcf_margin for trend
        lag(fcf / nullif(revenue, 0), 1) over (partition by ticker, filing_type order by period_of_report) as fcf_margin_1q_ago,
        lag(fcf / nullif(revenue, 0), 2) over (partition by ticker, filing_type order by period_of_report) as fcf_margin_2q_ago,

        -- rolling 4-period sum for LTM FCF (valid for quarterly filings reporting period-specific CF)
        sum(fcf) over (
            partition by ticker, filing_type
            order by period_of_report
            rows between 3 preceding and current row
        ) as ltm_fcf,

        sum(ocf) over (
            partition by ticker, filing_type
            order by period_of_report
            rows between 3 preceding and current row
        ) as ltm_ocf,

        sum(capex) over (
            partition by ticker, filing_type
            order by period_of_report
            rows between 3 preceding and current row
        ) as ltm_capex

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

        -- FCF components
        ocf,
        capex,
        fcf,

        -- LTM aggregates (most useful for quarterly filings)
        ltm_fcf,
        ltm_ocf,
        ltm_capex,

        -- ratios
        fcf / nullif(revenue, 0) as fcf_margin,
        fcf / nullif(net_income, 0) as fcf_conversion,
        capex / nullif(revenue, 0) as capex_intensity,

        -- FCF growth
        (fcf - fcf_4q_ago) / nullif(abs(fcf_4q_ago), 0) as fcf_growth_yoy,
        power(fcf / nullif(fcf_12q_ago, 0), 1.0 / 3.0) - 1 as fcf_cagr_3yr,

        -- FCF margin trend (3-period direction)
        case
            when fcf / nullif(revenue, 0) > fcf_margin_1q_ago
             and fcf_margin_1q_ago > fcf_margin_2q_ago then 'improving'
            when fcf / nullif(revenue, 0) < fcf_margin_1q_ago
             and fcf_margin_1q_ago < fcf_margin_2q_ago then 'declining'
            else 'stable'
        end as fcf_margin_trend,

        -- CapEx intensity trend (3-period direction; lower intensity = better capital efficiency)
        case
            when capex / nullif(revenue, 0) < capex_intensity_1q_ago
             and capex_intensity_1q_ago < capex_intensity_2q_ago then 'improving'
            when capex / nullif(revenue, 0) > capex_intensity_1q_ago
             and capex_intensity_1q_ago > capex_intensity_2q_ago then 'worsening'
            else 'stable'
        end as capex_intensity_trend,

        -- raw values carried forward for peer benchmarking downstream
        revenue,
        net_income

    from windowed

)

select * from metrics
