with source as (
    select * from {{ ref('stg_parking_tickets') }}
),

enriched as (
    select
        -- identifiers
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

        -- date dimensions
        year(infraction_date)                                           as infraction_year,
        month(infraction_date)                                          as infraction_month,
        day(infraction_date)                                            as infraction_day,
        -- dayofweek: 1=Sun, 2=Mon ... 7=Sat; subtract 1 for Postgres-style 0=Sun
        (dayofweek(infraction_date) - 1)                               as day_of_week_num,
        case dayofweek(infraction_date)
            when 1 then 'Sunday'
            when 2 then 'Monday'
            when 3 then 'Tuesday'
            when 4 then 'Wednesday'
            when 5 then 'Thursday'
            when 6 then 'Friday'
            when 7 then 'Saturday'
        end                                                             as day_of_week_name,
        weekofyear(infraction_date)                                     as iso_week,
        quarter(infraction_date)                                        as infraction_quarter,

        -- time dimensions (time_of_infraction is a 4-char HHMM string)
        case
            when time_of_infraction rlike '^\\d{4}$'
            then cast(left(time_of_infraction, 2) as int)
            else null
        end                                                             as infraction_hour,

        case
            when time_of_infraction rlike '^\\d{4}$'
                and cast(left(time_of_infraction, 2) as int) between 6 and 11
            then 'Morning'
            when time_of_infraction rlike '^\\d{4}$'
                and cast(left(time_of_infraction, 2) as int) between 12 and 17
            then 'Afternoon'
            when time_of_infraction rlike '^\\d{4}$'
                and cast(left(time_of_infraction, 2) as int) between 18 and 22
            then 'Evening'
            when time_of_infraction rlike '^\\d{4}$'
            then 'Night'
            else null
        end                                                             as time_of_day_bucket,

        -- weekend flag: dayofweek 1=Sun, 7=Sat
        dayofweek(infraction_date) in (1, 7)                           as is_weekend
    from source
)

select * from enriched
