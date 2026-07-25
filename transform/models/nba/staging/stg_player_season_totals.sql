{{
    config(
        materialized='view'
    )
}}

SELECT
    -- Surrogate key
    md5(concat_ws('-', coalesce(player_id, ''), coalesce(season, ''), coalesce(team, ''))) AS player_season_id,

    -- Player information
    player_id,
    player AS player_name,
    age,
    pos AS position,

    -- Team information
    team AS team_abbreviation,
    season,
    CAST(LEFT(season, 4) AS INT) AS season_year,

    -- Game statistics
    g AS games_played,
    gs AS games_started,
    mp AS total_minutes_played,

    -- Shooting statistics (season totals)
    fg AS total_field_goals_made,
    fga AS total_field_goals_attempted,
    fg_pct AS field_goal_percentage,

    three_p AS total_three_pointers_made,
    three_pa AS total_three_pointers_attempted,
    three_p_pct AS three_point_percentage,

    two_p AS total_two_pointers_made,
    two_pa AS total_two_pointers_attempted,
    two_p_pct AS two_point_percentage,

    efg_pct AS effective_field_goal_percentage,

    -- Free throw statistics (season totals)
    ft AS total_free_throws_made,
    fta AS total_free_throws_attempted,
    ft_pct AS free_throw_percentage,

    -- Rebounds (season totals)
    orb AS total_offensive_rebounds,
    drb AS total_defensive_rebounds,
    trb AS total_rebounds,

    -- Other statistics (season totals)
    ast AS total_assists,
    stl AS total_steals,
    blk AS total_blocks,
    tov AS total_turnovers,
    pf AS total_personal_fouls,
    pts AS total_points,

    -- Performance metrics
    trp_dbl AS triple_doubles,

    -- Additional information
    awards,
    loaded_at

FROM {{ source('nba_raw', 'player_season_totals') }}
