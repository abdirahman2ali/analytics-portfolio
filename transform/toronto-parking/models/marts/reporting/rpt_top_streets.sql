{{
    config(
        materialized='table',
    )
}}

select
    location2                as street_address,
    sum(ticket_count)        as ticket_count
from {{ ref('dim_locations') }}
where location2 is not null
  and location2 != ''
group by location2
order by ticket_count desc
limit 100
