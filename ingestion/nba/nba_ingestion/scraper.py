import io
import pandas as pd
import requests
from bs4 import BeautifulSoup


def get_season_stats(season_end_year: int) -> pd.DataFrame:
    """
    Scrape season totals for all players from Basketball Reference.

    Args:
        season_end_year: The year the season ended (e.g., 2024 for 2023-24 season).

    Returns:
        DataFrame with all players' season totals including a PLAYER_ID column.

    Raises:
        Exception: If the HTTP request fails or the stats table is not found.
    """
    stat_type = "totals"
    url = f"https://www.basketball-reference.com/leagues/NBA_{season_end_year}_{stat_type}.html"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table", {"id": f"{stat_type}_stats"})

    if not table:
        raise ValueError(f"Stats table not found for season ending {season_end_year}")

    player_ids = _extract_player_ids(table)

    df = pd.read_html(io.StringIO(str(table)))[0]
    df = df[df["Player"] != "Player"]  # drop repeated header rows
    if "Rk" in df.columns:
        df = df.drop("Rk", axis=1)
    df = df.reset_index(drop=True)

    # Align player_ids with cleaned df length
    aligned_ids = [
        player_ids[i] if i < len(player_ids) else None for i in range(len(df))
    ]
    df.insert(0, "PLAYER_ID", aligned_ids)

    return df


def _extract_player_ids(table) -> list:
    """Extract Basketball Reference player IDs from the stats table.

    Basketball Reference stores the player ID in the data-append-csv attribute
    of the name_display cell (e.g. data-append-csv="jamesle01").
    """
    player_ids = []
    for row in table.find("tbody").find_all("tr"):
        cell = row.find("td", {"data-stat": "name_display"})
        if cell:
            player_id = cell.get("data-append-csv")
        else:
            player_id = None
        player_ids.append(player_id)
    return player_ids
