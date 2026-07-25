from unittest.mock import patch, MagicMock
import pandas as pd
import pytest

from nba_ingestion.scraper import get_season_stats


SAMPLE_HTML = """
<html><body>
<table id="totals_stats">
  <thead><tr><th>Player</th><th>Age</th><th>Tm</th><th>Pos</th><th>G</th><th>PTS</th></tr></thead>
  <tbody>
    <tr>
      <td data-stat="name_display" data-append-csv="jamesle01">LeBron James</td>
      <td data-stat="age">39</td>
      <td data-stat="team_name_abbr">LAL</td>
      <td data-stat="pos">SF</td>
      <td data-stat="g">71</td>
      <td data-stat="pts">1769</td>
    </tr>
    <tr>
      <td data-stat="name_display" data-append-csv="curryst01">Stephen Curry</td>
      <td data-stat="age">35</td>
      <td data-stat="team_name_abbr">GSW</td>
      <td data-stat="pos">PG</td>
      <td data-stat="g">74</td>
      <td data-stat="pts">1886</td>
    </tr>
    <tr>
      <td data-stat="name_display" class="thead">Player</td>
    </tr>
  </tbody>
</table>
</body></html>
"""


@patch("nba_ingestion.scraper.requests.get")
def test_get_season_stats_returns_dataframe(mock_get):
    mock_response = MagicMock()
    mock_response.content = SAMPLE_HTML.encode()
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    df = get_season_stats(2024)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2  # repeated header row filtered out
    assert "PLAYER_ID" in df.columns
    assert "Player" in df.columns


@patch("nba_ingestion.scraper.requests.get")
def test_get_season_stats_extracts_player_ids(mock_get):
    mock_response = MagicMock()
    mock_response.content = SAMPLE_HTML.encode()
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    df = get_season_stats(2024)

    assert df.iloc[0]["PLAYER_ID"] == "jamesle01"
    assert df.iloc[1]["PLAYER_ID"] == "curryst01"


@patch("nba_ingestion.scraper.requests.get")
def test_get_season_stats_raises_on_missing_table(mock_get):
    mock_response = MagicMock()
    mock_response.content = b"<html><body><p>No table here</p></body></html>"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    with pytest.raises(ValueError, match="Stats table not found"):
        get_season_stats(2024)


@patch("nba_ingestion.scraper.requests.get")
def test_get_season_stats_raises_on_http_error(mock_get):
    mock_get.side_effect = Exception("Connection refused")

    with pytest.raises(Exception, match="Connection refused"):
        get_season_stats(2024)
