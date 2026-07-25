{{
    config(
        materialized='table'
    )
}}

-- Season-level league aggregates for historical trend analysis.
-- Filters to players with >= 20 games played to exclude short stints that would skew averages.
-- Powers the historical page: PPG trends, 3PT revolution, scoring by era.

WITH base AS (

    SELECT * FROM {{ ref('fct_player_season_stats') }}
    WHERE games_played >= 20

)

SELECT

    season,
    season_year,
    MAX(scheduled_games_in_season) AS scheduled_games_in_season,

    -- Player volume
    COUNT(*) AS player_count,

    -- League-average per-game stats
    ROUND(AVG(points_per_game), 1) AS avg_ppg,
    ROUND(AVG(rebounds_per_game), 1) AS avg_rpg,
    ROUND(AVG(assists_per_game), 1) AS avg_apg,
    ROUND(AVG(steals_per_game), 1) AS avg_spg,
    ROUND(AVG(blocks_per_game), 1) AS avg_bpg,
    ROUND(AVG(turnovers_per_game), 1) AS avg_topg,
    ROUND(AVG(minutes_per_game), 1) AS avg_mpg,

    -- League-average shooting efficiency
    ROUND(AVG(true_shooting_percentage), 3) AS avg_ts_pct,
    ROUND(AVG(field_goal_percentage), 3) AS avg_fg_pct,
    ROUND(AVG(three_point_percentage), 3) AS avg_3pt_pct,
    ROUND(AVG(free_throw_percentage), 3) AS avg_ft_pct,
    ROUND(AVG(effective_field_goal_percentage), 3) AS avg_efg_pct,

    -- Three-point volume (tracks the 3PT revolution over time)
    SUM(total_three_pointers_attempted) AS total_3pa_league,
    SUM(total_three_pointers_made) AS total_3pm_league,
    ROUND(AVG(CAST(total_three_pointers_attempted AS NUMERIC) / NULLIF(games_played, 0)), 1) AS avg_3pa_per_game,

    -- Season scoring leaders
    MAX(points_per_game) AS max_ppg_in_season,
    MAX(rebounds_per_game) AS max_rpg_in_season,
    MAX(assists_per_game) AS max_apg_in_season

FROM base

GROUP BY season, season_year
ORDER BY season_year
