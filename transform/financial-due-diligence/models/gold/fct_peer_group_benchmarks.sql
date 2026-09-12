{{
    config(
        materialized='incremental',
        unique_key=['gics_sector', 'period_of_report', 'filing_type'],
        file_format='delta',
        incremental_strategy='merge'
    )
}}

-- Computes p20/p40/p60/p80 percentiles and sector median per metric, per sector per period.
-- Grain: gics_sector + period_of_report + filing_type

with metrics as (

    select * from {{ ref('fct_financial_metrics') }}

    {% if is_incremental() %}
        where filed_date > (select max(filed_date) from {{ this }})
    {% endif %}

),

benchmarks as (

    select
        gics_sector,
        filing_type,
        period_of_report,

        -- revenue_growth_yoy
        percentile_cont(0.2) within group (order by revenue_growth_yoy) as revenue_growth_yoy_p20,
        percentile_cont(0.4) within group (order by revenue_growth_yoy) as revenue_growth_yoy_p40,
        percentile_cont(0.5) within group (order by revenue_growth_yoy) as revenue_growth_yoy_median,
        percentile_cont(0.6) within group (order by revenue_growth_yoy) as revenue_growth_yoy_p60,
        percentile_cont(0.8) within group (order by revenue_growth_yoy) as revenue_growth_yoy_p80,

        -- revenue_cagr_3yr
        percentile_cont(0.2) within group (order by revenue_cagr_3yr) as revenue_cagr_3yr_p20,
        percentile_cont(0.4) within group (order by revenue_cagr_3yr) as revenue_cagr_3yr_p40,
        percentile_cont(0.5) within group (order by revenue_cagr_3yr) as revenue_cagr_3yr_median,
        percentile_cont(0.6) within group (order by revenue_cagr_3yr) as revenue_cagr_3yr_p60,
        percentile_cont(0.8) within group (order by revenue_cagr_3yr) as revenue_cagr_3yr_p80,

        -- gross_margin
        percentile_cont(0.2) within group (order by gross_margin) as gross_margin_p20,
        percentile_cont(0.4) within group (order by gross_margin) as gross_margin_p40,
        percentile_cont(0.5) within group (order by gross_margin) as gross_margin_median,
        percentile_cont(0.6) within group (order by gross_margin) as gross_margin_p60,
        percentile_cont(0.8) within group (order by gross_margin) as gross_margin_p80,

        -- ebitda_margin
        percentile_cont(0.2) within group (order by ebitda_margin) as ebitda_margin_p20,
        percentile_cont(0.4) within group (order by ebitda_margin) as ebitda_margin_p40,
        percentile_cont(0.5) within group (order by ebitda_margin) as ebitda_margin_median,
        percentile_cont(0.6) within group (order by ebitda_margin) as ebitda_margin_p60,
        percentile_cont(0.8) within group (order by ebitda_margin) as ebitda_margin_p80,

        -- fcf_margin
        percentile_cont(0.2) within group (order by fcf_margin) as fcf_margin_p20,
        percentile_cont(0.4) within group (order by fcf_margin) as fcf_margin_p40,
        percentile_cont(0.5) within group (order by fcf_margin) as fcf_margin_median,
        percentile_cont(0.6) within group (order by fcf_margin) as fcf_margin_p60,
        percentile_cont(0.8) within group (order by fcf_margin) as fcf_margin_p80,

        -- fcf_conversion
        percentile_cont(0.2) within group (order by fcf_conversion) as fcf_conversion_p20,
        percentile_cont(0.4) within group (order by fcf_conversion) as fcf_conversion_p40,
        percentile_cont(0.5) within group (order by fcf_conversion) as fcf_conversion_median,
        percentile_cont(0.6) within group (order by fcf_conversion) as fcf_conversion_p60,
        percentile_cont(0.8) within group (order by fcf_conversion) as fcf_conversion_p80,

        -- debt_to_ebitda (lower is better — inverted in scoring)
        percentile_cont(0.2) within group (order by debt_to_ebitda) as debt_to_ebitda_p20,
        percentile_cont(0.4) within group (order by debt_to_ebitda) as debt_to_ebitda_p40,
        percentile_cont(0.5) within group (order by debt_to_ebitda) as debt_to_ebitda_median,
        percentile_cont(0.6) within group (order by debt_to_ebitda) as debt_to_ebitda_p60,
        percentile_cont(0.8) within group (order by debt_to_ebitda) as debt_to_ebitda_p80,

        -- current_ratio
        percentile_cont(0.2) within group (order by current_ratio) as current_ratio_p20,
        percentile_cont(0.4) within group (order by current_ratio) as current_ratio_p40,
        percentile_cont(0.5) within group (order by current_ratio) as current_ratio_median,
        percentile_cont(0.6) within group (order by current_ratio) as current_ratio_p60,
        percentile_cont(0.8) within group (order by current_ratio) as current_ratio_p80,

        -- interest_coverage
        percentile_cont(0.2) within group (order by interest_coverage) as interest_coverage_p20,
        percentile_cont(0.4) within group (order by interest_coverage) as interest_coverage_p40,
        percentile_cont(0.5) within group (order by interest_coverage) as interest_coverage_median,
        percentile_cont(0.6) within group (order by interest_coverage) as interest_coverage_p60,
        percentile_cont(0.8) within group (order by interest_coverage) as interest_coverage_p80,

        -- revenue_consistency (lower CV is better — inverted in scoring)
        percentile_cont(0.2) within group (order by revenue_consistency) as revenue_consistency_p20,
        percentile_cont(0.4) within group (order by revenue_consistency) as revenue_consistency_p40,
        percentile_cont(0.5) within group (order by revenue_consistency) as revenue_consistency_median,
        percentile_cont(0.6) within group (order by revenue_consistency) as revenue_consistency_p60,
        percentile_cont(0.8) within group (order by revenue_consistency) as revenue_consistency_p80,

        count(*) as company_count

    from metrics
    group by
        gics_sector,
        filing_type,
        period_of_report

)

select * from benchmarks
