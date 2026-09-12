WITH base AS (

    SELECT

        player_season_id,
        player_id,
        player_name,
        age,
        position,
        CASE WHEN COUNT(team_abbreviation) OVER (PARTITION BY player_id, season) > 1
            THEN TRUE
            ELSE FALSE
        END AS is_two_team_season_flag,
        team_abbreviation,
        season,
        season_year,

        -- Game statistics
        games_played,
        games_started,
        total_minutes_played,

        -- Shooting stats (season totals)
        total_field_goals_made,
        total_field_goals_attempted,
        field_goal_percentage,
        total_three_pointers_made,
        total_three_pointers_attempted,
        three_point_percentage,
        total_two_pointers_made,
        total_two_pointers_attempted,
        two_point_percentage,
        effective_field_goal_percentage,
        total_free_throws_made,
        total_free_throws_attempted,
        free_throw_percentage,

        -- Counting stats (season totals)
        total_offensive_rebounds,
        total_defensive_rebounds,
        total_rebounds,
        total_assists,
        total_steals,
        total_blocks,
        total_turnovers,
        total_personal_fouls,
        total_points,

        -- Performance metrics
        triple_doubles,

        awards,
        loaded_at

    FROM {{ ref('stg_player_season_totals') }}
    WHERE games_played > 0 -- Filter out players with no games played

),

players_one_team_season AS (

    SELECT * FROM base
    WHERE is_two_team_season_flag = FALSE

),

players_multi_team_season AS (

    SELECT * FROM base
    WHERE is_two_team_season_flag = TRUE
    AND team_abbreviation = '2TM' -- 2TM row contains combined season totals for players who changed teams mid-season

),

union_seasons AS (

    SELECT * FROM players_one_team_season
    UNION ALL
    SELECT * FROM players_multi_team_season

)

SELECT * FROM union_seasons
