{{
    config(
        materialized='incremental',
        unique_key='filing_id',
        file_format='delta',
        incremental_strategy='merge'
    )
}}

with source as (

    select * from {{ source('edgar_raw', 'edgar_raw_facts') }}
    where concept in ('ocf', 'capex')

    {% if is_incremental() %}
        and ingested_at > (select max(ingested_at) from {{ this }})
    {% endif %}

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['cik', 'concept', 'period_of_report', 'filing_type']) }} as filing_id,
        ticker,
        cik,
        company_name,
        filing_type,
        cast(period_of_report as date)  as period_of_report,
        cast(filed_date as date)         as filed_date,
        cast(fiscal_year as int)         as fiscal_year,
        cast(fiscal_quarter as int)      as fiscal_quarter,
        concept,
        xbrl_concept,
        cast(value as double)            as value,
        unit,
        ingested_at

    from source

)

select * from final
