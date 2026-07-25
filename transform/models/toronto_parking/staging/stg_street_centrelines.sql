with source as (
    select * from {{ source('toronto', 'street_centrelines') }}
)

select
    lname       as location1,
    latitude,
    longitude
from source
