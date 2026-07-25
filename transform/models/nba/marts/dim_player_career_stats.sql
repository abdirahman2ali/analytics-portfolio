{{
    config(
        materialized='table'
    )
}}

-- Career aggregates per player across all seasons.
-- TS% is calculated from career totals (not an average of season averages) for accuracy.
-- Powers player comparison views and career leaderboards.

WITH base AS (

    SELECT * FROM {{ ref('fct_player_season_stats') }}

)

SELECT

    player_id,
    player_name,

    -- Career span
    MIN(season_year) AS first_season_year,
    MAX(season_year) AS last_season_year,
    COUNT(*) AS seasons_played,

    -- Career volume
    SUM(games_played) AS career_games_played,

    -- Career totals
    SUM(total_points) AS career_total_points,
    SUM(total_rebounds) AS career_total_rebounds,
    SUM(total_assists) AS career_total_assists,
    SUM(total_steals) AS career_total_steals,
    SUM(total_blocks) AS career_total_blocks,
    SUM(total_turnovers) AS career_total_turnovers,
    SUM(triple_doubles) AS career_triple_doubles,

    -- Career per-game averages
    ROUND(SUM(total_points)::NUMERIC / NULLIF(SUM(games_played), 0), 1) AS career_ppg,
    ROUND(SUM(total_rebounds)::NUMERIC / NULLIF(SUM(games_played), 0), 1) AS career_rpg,
    ROUND(SUM(total_assists)::NUMERIC / NULLIF(SUM(games_played), 0), 1) AS career_apg,
    ROUND(SUM(total_steals)::NUMERIC / NULLIF(SUM(games_played), 0), 1) AS career_spg,
    ROUND(SUM(total_blocks)::NUMERIC / NULLIF(SUM(games_played), 0), 1) AS career_bpg,

    -- Career true shooting % (from totals, not avg of season TS%)
    CASE
        WHEN (SUM(total_field_goals_attempted) + 0.44 * SUM(total_free_throws_attempted)) > 0
        THEN ROUND(
            SUM(total_points)::NUMERIC /
            (2 * (SUM(total_field_goals_attempted) + 0.44 * SUM(total_free_throws_attempted))),
            3
        )
        ELSE NULL
    END AS career_true_shooting_pct,

    -- Career shooting totals
    SUM(total_field_goals_made) AS career_total_fg,
    SUM(total_field_goals_attempted) AS career_total_fga,
    SUM(total_three_pointers_made) AS career_total_3pm,
    SUM(total_three_pointers_attempted) AS career_total_3pa,
    SUM(total_free_throws_made) AS career_total_ft,
    SUM(total_free_throws_attempted) AS career_total_fta,

    -- Peak season
    MAX(points_per_game) AS best_season_ppg,
    MAX(rebounds_per_game) AS best_season_rpg,
    MAX(assists_per_game) AS best_season_apg

FROM base

GROUP BY player_id, player_name
