import pandas as pd

from nba_ingestion.transformer import add_season_column, clean_column_names, prepare_for_db


def make_df():
    return pd.DataFrame({
        "Player": ["LeBron James"],
        "Age": [39],
        "FG%": [0.540],
        "3P": [78],
        "3PA": [213],
        "3P%": [0.366],
        "2P": [456],
        "2PA": [780],
        "2P%": [0.585],
        "eFG%": [0.571],
    })


def test_add_season_column():
    df = make_df()
    result = add_season_column(df, 2024)
    assert "SEASON" in result.columns
    assert result.iloc[0]["SEASON"] == "2023-24"


def test_add_season_column_does_not_mutate_input():
    df = make_df()
    add_season_column(df, 2024)
    assert "SEASON" not in df.columns


def test_clean_column_names_lowercase():
    df = make_df()
    result = clean_column_names(df)
    assert all(col == col.lower() or "_" in col for col in result.columns)
    assert "player" in result.columns
    assert "age" in result.columns


def test_clean_column_names_replaces_pct():
    df = make_df()
    result = clean_column_names(df)
    assert "fg_pct" in result.columns
    assert "FG%" not in result.columns


def test_clean_column_names_replaces_three_p():
    df = make_df()
    result = clean_column_names(df)
    assert "three_p" in result.columns
    assert "three_pa" in result.columns
    assert "three_p_pct" in result.columns


def test_clean_column_names_replaces_two_p():
    df = make_df()
    result = clean_column_names(df)
    assert "two_p" in result.columns
    assert "two_pa" in result.columns
    assert "two_p_pct" in result.columns


def test_prepare_for_db_combines_season_and_clean():
    df = make_df()
    result = prepare_for_db(df, 2024)
    # SEASON is added first, then clean_column_names lowercases it to 'season'
    assert "season" in result.columns
    assert "fg_pct" in result.columns
    assert result.iloc[0]["season"] == "2023-24"
