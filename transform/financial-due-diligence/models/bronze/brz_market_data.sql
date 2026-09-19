with raw as (

    select
        ticker,
        price_date,
        close_price,
        shares_outstanding,
        market_cap,
        ingested_at,
        row_number() over (
            partition by ticker, price_date
            order by ingested_at desc
        ) as _rn

    from {{ source('market_raw', 'brz_market_data') }}

)

select
    ticker,
    price_date,
    close_price,
    shares_outstanding,
    market_cap,
    ingested_at

from raw
where _rn = 1
