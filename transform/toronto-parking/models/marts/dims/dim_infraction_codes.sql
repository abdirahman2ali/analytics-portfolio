{{
    config(
        materialized='table',
    )
}}

with tickets as (
    select * from {{ ref('stg_parking_tickets') }}
),

-- Rank description + fine combinations per code to pick the most common
code_variants as (
    select
        infraction_code,
        infraction_description,
        set_fine_amount,
        count(*)            as occurrence_count
    from tickets
    where infraction_code is not null
    group by
        infraction_code,
        infraction_description,
        set_fine_amount
),

ranked as (
    select
        infraction_code,
        infraction_description,
        set_fine_amount         as standard_fine_amount,
        row_number() over (
            partition by infraction_code
            order by occurrence_count desc
        )                       as rn
    from code_variants
),

top_variant as (
    select infraction_code, infraction_description, standard_fine_amount
    from ranked
    where rn = 1
),

ticket_counts as (
    select
        infraction_code,
        count(*)            as total_tickets,
        min(infraction_date) as first_seen_date,
        max(infraction_date) as last_seen_date
    from tickets
    where infraction_code is not null
    group by infraction_code
)

select
    {{ dbt_utils.generate_surrogate_key(['t.infraction_code']) }}   as infraction_code_id,
    t.infraction_code,
    t.infraction_description,
    t.standard_fine_amount,
    c.total_tickets,
    c.first_seen_date,
    c.last_seen_date
from top_variant as t
inner join ticket_counts as c
    on t.infraction_code = c.infraction_code
