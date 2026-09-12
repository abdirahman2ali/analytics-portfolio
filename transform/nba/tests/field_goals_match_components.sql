-- Test to ensure total field goals equals sum of 2PT + 3PT
-- This validates the fundamental math of basketball shooting statistics

select
    player_season_id,
    player_name,
    season,
    total_field_goals_made,
    total_two_pointers_made,
    total_three_pointers_made,
    (total_two_pointers_made + total_three_pointers_made) as calculated_field_goals_made,
    total_field_goals_attempted,
    total_two_pointers_attempted,
    total_three_pointers_attempted,
    (total_two_pointers_attempted + total_three_pointers_attempted) as calculated_field_goals_attempted
from {{ ref('fct_player_season_stats') }}
where 
    -- Test made field goals
    total_field_goals_made != (total_two_pointers_made + total_three_pointers_made)
    -- Test attempted field goals
    or total_field_goals_attempted != (total_two_pointers_attempted + total_three_pointers_attempted)

