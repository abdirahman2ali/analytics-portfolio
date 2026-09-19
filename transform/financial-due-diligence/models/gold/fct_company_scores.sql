{{ config(materialized='table') }}

-- Weighted composite score, letter grade, peer rank, and red/yellow flag overlays.
-- Grain: ticker + period_of_report + filing_type

with scores as (

    select * from {{ ref('fct_metric_scores') }}

),

with_flags as (

    select
        *,

        -- fcf_negative: FCF < 0 for 2+ consecutive quarters
        case
            when fcf < 0
             and lag(fcf, 1) over (partition by ticker, filing_type order by period_of_report) < 0
            then true
            else false
        end as flag_fcf_negative,

        -- debt_overload: debt_to_ebit > 5x
        case when debt_to_ebit > 5 then true else false end as flag_debt_overload,

        -- interest_coverage_weak: interest_coverage < 2x
        case when interest_coverage < 2 then true else false end as flag_interest_coverage_weak,

        -- negative_equity
        case when total_equity < 0 then true else false end as flag_negative_equity,

        -- margin_compression: gross_margin declining 3 consecutive quarters
        case when gross_margin_trend = 'declining' then true else false end as flag_margin_compression,

        -- revenue_deceleration: revenue_growth declining 3 consecutive quarters
        case when revenue_growth_trend = 'declining' then true else false end as flag_revenue_deceleration,

        -- earnings_quality_risk: fcf_conversion < 0.6
        case when fcf_conversion < 0.6 then true else false end as flag_earnings_quality_risk,

        -- revenue_inconsistency: CV > 0.3
        case when revenue_consistency > 0.3 then true else false end as flag_revenue_inconsistency

    from scores

),

composite as (

    select
        *,

        -- Weighted average over available scores only; missing scores are excluded
        -- and weights renormalize so data gaps don't penalize the composite.
        round(
            (
                coalesce(revenue_growth_yoy_score * 0.15, 0)
                + coalesce(revenue_cagr_3yr_score * 0.10, 0)
                + coalesce(gross_margin_score * 0.15, 0)
                + coalesce(ebitda_margin_score * 0.15, 0)
                + coalesce(fcf_margin_score * 0.10, 0)
                + coalesce(fcf_conversion_score * 0.10, 0)
                + coalesce(debt_to_ebit_score * 0.10, 0)
                + coalesce(assets_to_liabilities_score * 0.05, 0)
                + coalesce(interest_coverage_score * 0.05, 0)
                + coalesce(revenue_consistency_score * 0.05, 0)
            ) / nullif(
                case when revenue_growth_yoy_score is not null then 0.15 else 0 end
                + case when revenue_cagr_3yr_score is not null then 0.10 else 0 end
                + case when gross_margin_score is not null then 0.15 else 0 end
                + case when ebitda_margin_score is not null then 0.15 else 0 end
                + case when fcf_margin_score is not null then 0.10 else 0 end
                + case when fcf_conversion_score is not null then 0.10 else 0 end
                + case when debt_to_ebit_score is not null then 0.10 else 0 end
                + case when assets_to_liabilities_score is not null then 0.05 else 0 end
                + case when interest_coverage_score is not null then 0.05 else 0 end
                + case when revenue_consistency_score is not null then 0.05 else 0 end,
                0
            ),
            1
        ) as composite_score

    from with_flags

),

graded as (

    select
        *,

        case
            when composite_score >= 90 then 'A+'
            when composite_score >= 80 then 'A'
            when composite_score >= 70 then 'B+'
            when composite_score >= 60 then 'B'
            when composite_score >= 50 then 'C+'
            when composite_score >= 40 then 'C'
            when composite_score >= 30 then 'D'
            else 'F'
        end as grade,

        rank() over (
            partition by gics_sector, filing_type, period_of_report
            order by composite_score desc
        ) as peer_rank,

        -- build flags array; array_compact removes nulls
        array_compact(array(
            case when flag_fcf_negative then '🔴 fcf_negative' end,
            case when flag_debt_overload then '🔴 debt_overload' end,
            case when flag_interest_coverage_weak then '🔴 interest_coverage_weak' end,
            case when flag_negative_equity then '🔴 negative_equity' end,
            case when flag_margin_compression then '🟡 margin_compression' end,
            case when flag_revenue_deceleration then '🟡 revenue_deceleration' end,
            case when flag_earnings_quality_risk then '🟡 earnings_quality_risk' end,
            case when flag_revenue_inconsistency then '🟡 revenue_inconsistency' end
        )) as flags

    from composite

),

final as (

    select
        ticker,
        company_name,
        gics_sector as sector,
        period_of_report,
        filing_type,
        composite_score,
        grade,
        peer_rank,
        flags,
        revenue_growth_yoy_score,
        revenue_cagr_3yr_score,
        gross_margin_score,
        ebitda_margin_score,
        fcf_margin_score,
        fcf_conversion_score,
        debt_to_ebit_score,
        assets_to_liabilities_score,
        interest_coverage_score,
        revenue_consistency_score,
        -- raw metrics for reference
        revenue_growth_yoy,
        revenue_cagr_3yr,
        gross_margin,
        ebitda_margin,
        net_income_margin,
        fcf_margin,
        fcf_conversion,
        debt_to_ebit,
        assets_to_liabilities,
        interest_coverage,
        revenue_consistency,
        gross_margin_trend,
        ebitda_margin_trend,
        revenue_growth_trend,
        filed_date,
        fiscal_year,
        fiscal_quarter

    from graded

)

select * from final
