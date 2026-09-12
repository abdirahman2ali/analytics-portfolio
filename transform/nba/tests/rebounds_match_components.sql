-- Test to ensure total rebounds equals sum of offensive + defensive rebounds
-- This validates rebounding statistics integrity

select
    player_season_id,
    player_name,
    season,
    total_rebounds,
    total_offensive_rebounds,
    total_defensive_rebounds,
    (total_offensive_rebounds + total_defensive_rebounds) as calculated_total_rebounds
from {{ ref('fct_player_season_stats') }}
where total_rebounds != (total_offensive_rebounds + total_defensive_rebounds)

