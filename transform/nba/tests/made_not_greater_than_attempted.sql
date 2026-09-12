-- Test to ensure made shots never exceed attempted shots
-- This is a fundamental rule in basketball statistics

select
    player_season_id,
    player_name,
    season,
    'field_goals' as stat_type,
    total_field_goals_made as made,
    total_field_goals_attempted as attempted
from {{ ref('fct_player_season_stats') }}
where total_field_goals_made > total_field_goals_attempted

union all

select
    player_season_id,
    player_name,
    season,
    'three_pointers' as stat_type,
    total_three_pointers_made as made,
    total_three_pointers_attempted as attempted
from {{ ref('fct_player_season_stats') }}
where total_three_pointers_made > total_three_pointers_attempted

union all

select
    player_season_id,
    player_name,
    season,
    'two_pointers' as stat_type,
    total_two_pointers_made as made,
    total_two_pointers_attempted as attempted
from {{ ref('fct_player_season_stats') }}
where total_two_pointers_made > total_two_pointers_attempted

union all

select
    player_season_id,
    player_name,
    season,
    'free_throws' as stat_type,
    total_free_throws_made as made,
    total_free_throws_attempted as attempted
from {{ ref('fct_player_season_stats') }}
where total_free_throws_made > total_free_throws_attempted

