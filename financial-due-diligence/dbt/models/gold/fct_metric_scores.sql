{{
    config(
        materialized='incremental',
        unique_key=['ticker', 'period_of_report', 'filing_type'],
        file_format='delta',
        incremental_strategy='merge'
    )
}}

-- Maps each company's within-sector percentile rank to a 0-100 score per metric.
-- Score bands: top 10% → 90-100, 10-25% → 75-89, 25-50% → 50-74, 50-75% → 25-49, bottom 25% → 0-24.
-- Grain: ticker + period_of_report + filing_type

with metrics as (

    select * from {{ ref('fct_financial_metrics') }}

    {% if is_incremental() %}
        where filed_date > (select max(filed_date) from {{ this }})
    {% endif %}

),

ranked as (

    select
        *,

        -- higher is better metrics
        percent_rank() over (
            partition by gics_sector, filing_type, period_of_report
            order by revenue_growth_yoy asc nulls last
        ) as revenue_growth_yoy_pct,

        percent_rank() over (
            partition by gics_sector, filing_type, period_of_report
            order by revenue_cagr_3yr asc nulls last
        ) as revenue_cagr_3yr_pct,

        percent_rank() over (
            partition by gics_sector, filing_type, period_of_report
            order by gross_margin asc nulls last
        ) as gross_margin_pct,

        percent_rank() over (
            partition by gics_sector, filing_type, period_of_report
            order by ebitda_margin asc nulls last
        ) as ebitda_margin_pct,

        percent_rank() over (
            partition by gics_sector, filing_type, period_of_report
            order by fcf_margin asc nulls last
        ) as fcf_margin_pct,

        percent_rank() over (
            partition by gics_sector, filing_type, period_of_report
            order by fcf_conversion asc nulls last
        ) as fcf_conversion_pct,

        -- lower is better: invert by ordering desc
        percent_rank() over (
            partition by gics_sector, filing_type, period_of_report
            order by debt_to_ebitda desc nulls last
        ) as debt_to_ebitda_pct,

        percent_rank() over (
            partition by gics_sector, filing_type, period_of_report
            order by current_ratio asc nulls last
        ) as current_ratio_pct,

        percent_rank() over (
            partition by gics_sector, filing_type, period_of_report
            order by interest_coverage asc nulls last
        ) as interest_coverage_pct,

        -- lower CV = more consistent = better: invert
        percent_rank() over (
            partition by gics_sector, filing_type, period_of_report
            order by revenue_consistency desc nulls last
        ) as revenue_consistency_pct,

        -- peer rank within sector (by composite will be applied in fct_company_scores)
        row_number() over (
            partition by gics_sector, filing_type, period_of_report
            order by gross_margin desc nulls last
        ) as gross_margin_peer_rank

    from metrics

),

scored as (

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

        revenue_growth_yoy,
        revenue_cagr_3yr,
        gross_margin,
        ebitda_margin,
        net_income_margin,
        fcf_margin,
        fcf_conversion,
        debt_to_ebitda,
        current_ratio,
        interest_coverage,
        revenue_consistency,
        gross_margin_trend,
        ebitda_margin_trend,
        revenue_growth_trend,
        fcf,
        total_equity,
        revenue,

        {{ _score_metric('revenue_growth_yoy_pct') }}   as revenue_growth_yoy_score,
        {{ _score_metric('revenue_cagr_3yr_pct') }}     as revenue_cagr_3yr_score,
        {{ _score_metric('gross_margin_pct') }}         as gross_margin_score,
        {{ _score_metric('ebitda_margin_pct') }}        as ebitda_margin_score,
        {{ _score_metric('fcf_margin_pct') }}           as fcf_margin_score,
        {{ _score_metric('fcf_conversion_pct') }}       as fcf_conversion_score,
        {{ _score_metric('debt_to_ebitda_pct') }}       as debt_to_ebitda_score,
        {{ _score_metric('current_ratio_pct') }}        as current_ratio_score,
        {{ _score_metric('interest_coverage_pct') }}    as interest_coverage_score,
        {{ _score_metric('revenue_consistency_pct') }}  as revenue_consistency_score

    from ranked

)

select * from scored

{% macro _score_metric(pct_col) %}
    case
        when {{ pct_col }} >= 0.90 then 90 + round(({{ pct_col }} - 0.90) / 0.10 * 10)
        when {{ pct_col }} >= 0.75 then 75 + round(({{ pct_col }} - 0.75) / 0.15 * 14)
        when {{ pct_col }} >= 0.50 then 50 + round(({{ pct_col }} - 0.50) / 0.25 * 24)
        when {{ pct_col }} >= 0.25 then 25 + round(({{ pct_col }} - 0.25) / 0.25 * 24)
        else round({{ pct_col }} / 0.25 * 24)
    end
{% endmacro %}
