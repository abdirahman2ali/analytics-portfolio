-- Assert that brz_edgar_submissions has no duplicate filing_ids.
-- Returns rows on failure; dbt treats any returned rows as a test failure.

select
    filing_id,
    count(*) as cnt

from {{ ref('brz_edgar_submissions') }}

group by filing_id

having count(*) > 1
