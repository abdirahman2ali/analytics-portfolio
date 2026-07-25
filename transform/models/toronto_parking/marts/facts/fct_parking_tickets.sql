{{
    config(
        materialized='incremental',
        unique_key='infraction_year',
        incremental_strategy='delete+insert',
    )
}}

with source as (
    select * from {{ ref('int_tickets_enriched') }}
    {% if is_incremental() %}
        -- Re-process the current year to pick up late-arriving records
        where infraction_year = (select max(infraction_year) from {{ this }})
    {% endif %}
),

-- Deduplicate genuine source duplicates (identical rows in Toronto Open Data)
deduped as (
    select
        *,
        row_number() over (
            partition by tag_number_masked, infraction_date, time_of_infraction,
                         infraction_code, location2
            order by tag_number_masked
        ) as rn
    from source
)

select
    {{ dbt_utils.generate_surrogate_key(['tag_number_masked', 'infraction_date', 'time_of_infraction', "cast(coalesce(infraction_code, 0) as string)", 'location2']) }} as ticket_id,
    tag_number_masked,
    infraction_date,
    infraction_code,
    infraction_description,
    set_fine_amount,
    time_of_infraction,
    location1,
    location2,
    officer_tag_number,
    province,
    infraction_year,
    infraction_month,
    infraction_day,
    day_of_week_num,
    day_of_week_name,
    iso_week,
    infraction_quarter,
    infraction_hour,
    time_of_day_bucket,
    is_weekend
from deduped
where rn = 1
