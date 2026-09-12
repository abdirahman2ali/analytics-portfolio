-- Test to ensure a player can't start more games than they played
-- This is a basic logical consistency check

select
    player_season_id,
    player_name,
    season,
    games_played,
    games_started
from {{ ref('fct_player_season_stats') }}
where games_started > games_played

