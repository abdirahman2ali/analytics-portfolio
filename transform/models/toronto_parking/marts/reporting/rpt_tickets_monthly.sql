{{
    config(
        materialized='incremental',
        unique_key='year_month',
        incremental_strategy='delete+insert',
    )
}}

with facts as (
    select * from {{ ref('fct_parking_tickets') }}
    {% if is_incremental() %}
        -- Re-process only the current year; deletes and replaces those year_month rows
        where infraction_year = (select max(infraction_year) from {{ ref('fct_parking_tickets') }})
    {% endif %}
),

monthly as (
    select
        infraction_year as year,
        infraction_month as month,
        concat(
            cast(infraction_year as string), '-',
            lpad(cast(infraction_month as string), 2, '0')
        ) as year_month,
        count(*) as ticket_count,
        sum(set_fine_amount) as total_fines_cad,
        round(avg(set_fine_amount), 2) as avg_fine_cad,
        count(distinct infraction_code) as unique_infraction_codes,
        count(distinct location1) as unique_streets,
        count(case when is_weekend then 1 end) as weekend_ticket_count,
        count(case when time_of_day_bucket = 'Morning' then 1 end) as morning_ticket_count,
        count(case when time_of_day_bucket = 'Afternoon' then 1 end) as afternoon_ticket_count,
        count(case when time_of_day_bucket = 'Evening' then 1 end) as evening_ticket_count,
        count(case when time_of_day_bucket = 'Night' then 1 end) as night_ticket_count
    from facts
    group by infraction_year, infraction_month
),

-- Most frequent infraction code per month
top_codes as (
    select
        infraction_year,
        infraction_month,
        infraction_code as top_infraction_code
    from (
        select
            infraction_year,
            infraction_month,
            infraction_code,
            row_number() over (
                partition by infraction_year, infraction_month
                order by count(*) desc
            ) as rn
        from facts
        where infraction_code is not null
        group by infraction_year, infraction_month, infraction_code
    )
    where rn = 1
)

select
    m.year,
    m.month,
    m.year_month,
    m.ticket_count,
    m.total_fines_cad,
    m.avg_fine_cad,
    m.unique_infraction_codes,
    m.unique_streets,
    m.weekend_ticket_count,
    m.morning_ticket_count,
    m.afternoon_ticket_count,
    m.evening_ticket_count,
    m.night_ticket_count,
    t.top_infraction_code
from monthly as m
left join top_codes as t
    on m.year = t.infraction_year
    and m.month = t.infraction_month
order by year, month
