with source as (
    select * from {{ source('toronto', 'parking_tickets_raw') }}
),

cleaned as (
    select
        tag_number_masked,
        date_of_infraction                                              as infraction_date,
        infraction_code,
        trim(infraction_description)                                    as infraction_description,
        set_fine_amount,
        lpad(coalesce(time_of_infraction, '0000'), 4, '0')              as time_of_infraction,
        nullif(upper(trim(location1)), '')                              as location1,
        nullif(upper(trim(location2)), '')                              as location2,
        nullif(officer_tag_number, '')                                  as officer_tag_number,
        nullif(upper(trim(province)), '')                               as province
    from source
    where date_of_infraction is not null
      and tag_number_masked is not null
)

select * from cleaned
