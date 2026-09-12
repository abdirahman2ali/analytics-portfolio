{{
    config(
        materialized='incremental',
        unique_key='location_key',
        incremental_strategy='delete+insert',
    )
}}
-- depends_on: {{ ref('fct_parking_tickets') }}

with street_centrelines as (
    -- location1 in stg_street_centrelines is the bare street name (e.g. "KEELE ST")
    select location1 as street_name, latitude, longitude
    from {{ ref('stg_street_centrelines') }}
),

{% if is_incremental() %}
-- Only the current year's tickets: fast, one year partition on fct
changed_keys as (
    select
        location1,
        coalesce(location2, '') as location2,
        max(infraction_year) as year,
        count(*) as new_year_count
    from {{ ref('fct_parking_tickets') }}
    where infraction_year = (select max(infraction_year) from {{ ref('fct_parking_tickets') }})
    group by location1, coalesce(location2, '')
),

-- Existing dim rows for those keys: reads {{ this }}, not the large fct table
prior_dim as (
    select d.location1, coalesce(d.location2, '') as location2, d.ticket_count, d.current_year, d.current_year_count
    from {{ this }} as d
    inner join changed_keys as c
        on d.location1 = c.location1
        and coalesce(d.location2, '') = c.location2
),

locations as (
    select
        c.location1,
        c.location2,
        -- Subtract the old current-year slice (if this is a mid-year re-run) then add the new count.
        -- If the year rolled over, d.current_year != c.year so nothing is subtracted.
        coalesce(d.ticket_count, 0)
            - case when d.current_year = c.year
                   then coalesce(d.current_year_count, 0)
                   else 0
              end
            + c.new_year_count as ticket_count,
        c.year as current_year,
        c.new_year_count as current_year_count
    from changed_keys as c
    left join prior_dim as d
        on c.location1 = d.location1
        and c.location2 = d.location2
)

{% else %}
-- Full refresh: read from raw source, compute all-time totals
max_year as (
    select max(year(infraction_date)) as yr
    from {{ ref('stg_parking_tickets') }}
),

locations as (
    select
        t.location1,
        coalesce(t.location2, '') as location2,
        count(*) as ticket_count,
        max(m.yr) as current_year,
        count(case when year(t.infraction_date) = m.yr then 1 end) as current_year_count
    from {{ ref('stg_parking_tickets') }} as t
    cross join max_year as m
    where t.location1 is not null
    group by t.location1, coalesce(t.location2, '')
)

{% endif %}

select
    {{ dbt_utils.generate_surrogate_key(['l.location1', 'l.location2']) }} as location_key,
    l.location1,
    l.location2 as location2,
    if(
        l.location2 is not null and l.location2 != '',
        concat(l.location1, ' at ', l.location2),
        l.location1
    ) as location_display,
    g.latitude,
    g.longitude,
    l.ticket_count,
    l.current_year,
    l.current_year_count
from locations as l
left join street_centrelines as g
    -- In parking data, location2 holds the address (e.g. "4700 KEELE ST").
    -- Strip leading house number to get a bare street name for the centreline join.
    on regexp_replace(coalesce(l.location2, ''), '^[0-9]+\\s+', '') = g.street_name
