{{
    config(
        materialized='table',
    )
}}

-- One row per geocoded street: total tickets + centroid coordinates.
-- In Toronto parking data, location2 holds the address (e.g. "4700 KEELE ST").
-- The leading house number is stripped to get a bare street name for the centreline join.
-- Rows without a centreline match are excluded (no coordinates to plot).
with tickets as (
    select
        regexp_replace(location2, '^[0-9]+\\s+', '') as street_name,
        count(*) as ticket_count
    from {{ ref('fct_parking_tickets') }}
    where location2 is not null
    group by regexp_replace(location2, '^[0-9]+\\s+', '')
),

centrelines as (
    select location1 as street_name, latitude, longitude
    from {{ ref('stg_street_centrelines') }}
)

select
    t.street_name,
    c.latitude,
    c.longitude,
    t.ticket_count as total_tickets
from tickets as t
inner join centrelines as c
    on t.street_name = c.street_name
