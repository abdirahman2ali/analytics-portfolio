# NBA Ingestion Pipeline

Scrapes NBA player season totals from Basketball Reference (1950 to present) and loads them into PostgreSQL. Part of a three-project analytics portfolio:

**nba-ingestion-pipeline** → [nba-dbt](https://github.com/abdirahman2ali/nba-dbt) → nba-evidence (BI layer)

---

## What It Does

- Scrapes season totals for every player from every NBA season (1950 onwards)
- Extracts player IDs, handles repeated header rows, and normalizes column names
- Loads data into `nba.player_season_totals` in PostgreSQL
- Respects Basketball Reference rate limits (1 request per second)

---

## Project Structure

```
nba-ingestion-pipeline/
├── nba_ingestion/
│   ├── scraper.py      # HTTP scraping and HTML parsing
│   ├── transformer.py  # Column cleaning and season formatting
│   └── loader.py       # PostgreSQL connection and writes
├── tests/
│   ├── test_scraper.py
│   └── test_transformer.py
├── main.py             # Entrypoint
├── requirements.txt
└── .env.example
```

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/abdirahman2ali/nba-ingestion-pipeline.git
cd nba-ingestion-pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your PostgreSQL credentials. For cloud databases (e.g. Neon), use the `DATABASE_URL` option and set `PGSSLMODE=require`.

### 3. Run

```bash
python3 main.py
```

This scrapes all seasons from 1950 to 2025 and writes to `nba.player_season_totals`. Estimated run time: ~80 seconds (one second per season for rate limiting).

---

## Configuration

Edit the constants at the top of `main.py` to change the season range or table name:

```python
START_YEAR = 1950
END_YEAR = 2025
TABLE_NAME = "player_season_totals"
```

---

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

Tests use mocked HTTP responses — no network access required.

---

## Output Schema

Data is written to `nba.player_season_totals` with the following key columns:

| Column | Description |
|---|---|
| `player_id` | Basketball Reference player ID (e.g. `jamesle01`) |
| `player` | Player name |
| `season` | Season in `YYYY-YY` format (e.g. `2023-24`) |
| `team` | Team abbreviation |
| `pos` | Position |
| `g` | Games played |
| `pts` | Total points |
| `ast` | Total assists |
| `trb` | Total rebounds |
| `fg_pct` | Field goal percentage |
| `three_p_pct` | Three-point percentage |
| `ft_pct` | Free throw percentage |

Full schema defined in `nba_ingestion/loader.py`.

---

## Data Source

[Basketball Reference](https://www.basketball-reference.com/) — player season totals pages.

---

## License

MIT
