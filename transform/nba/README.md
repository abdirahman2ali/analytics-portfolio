# NBA Analytics dbt Project

A data transformation pipeline for NBA player statistics built with dbt. Transforms raw scraped data into analytics-ready datasets covering every season from 1950 to present.

Part of a three-project analytics portfolio: [nba-ingestion-pipeline](https://github.com/abdirahman2ali/nba-ingestion-pipeline) → **nba-dbt** → nba-evidence (BI layer).

---

## What This Project Does

- Standardizes raw player season totals with consistent column names and data types
- Handles mid-season trades (collapses multi-team records into one row per player-season)
- Calculates advanced metrics: True Shooting %, Per-36 stats, usage rate, offensive rating
- Categorizes players by role, scoring output, playing time, and efficiency tier
- Validates data quality with custom and generic dbt tests

---

## Data Pipeline

```
Raw Source (nba.player_season_averages)
        |
        v
Staging: stg_player_season_totals  [view]
  - Rename columns, standardize types
        |
        v
Intermediate: int_player_season_totals  [table]
  - One row per player-season
  - Multi-team season handling (2TM)
  - Filter 0-game records
        |
        v
Mart: fct_player_season_stats  [table]
  - Per-game averages
  - Advanced metrics (TS%, PER-36, usage rate)
  - Player categorizations
  - Fantasy scoring
```

---

## Project Structure

```
nba-dbt/
├── models/
│   ├── staging/
│   │   ├── sources.yml
│   │   ├── schema.yml
│   │   └── stg_player_season_totals.sql
│   ├── intermediate/
│   │   ├── schema.yml
│   │   └── int_player_season_totals.sql
│   └── marts/
│       ├── schema.yml
│       └── fct_player_season_stats.sql
├── tests/
│   ├── field_goals_match_components.sql
│   ├── made_not_greater_than_attempted.sql
│   ├── rebounds_match_components.sql
│   └── games_started_not_greater_than_played.sql
├── dbt_project.yml
├── packages.yml
└── profiles.example.yml
```

---

## Setup

### Prerequisites

- Python 3.9+
- PostgreSQL database populated by [nba-ingestion-pipeline](https://github.com/abdirahman2ali/nba-ingestion-pipeline)

### Install dbt

```bash
pip install dbt-postgres
```

### Configure database connection

Copy the example profiles file to your dbt home directory:

```bash
cp profiles.example.yml ~/.dbt/profiles.yml
```

Edit `~/.dbt/profiles.yml` and fill in your database credentials. The project name is `nba_dbt`.

### Install dbt packages

```bash
dbt deps
```

### Run the pipeline

```bash
dbt run
```

### Run tests

```bash
dbt test
```

### Generate docs

```bash
dbt docs generate
dbt docs serve
```

---

## Models

### `stg_player_season_totals`
Cleans the raw source table. Renames cryptic Basketball Reference abbreviations to full column names (e.g. `fg` → `total_field_goals_made`, `g` → `games_played`). No filtering or aggregation.

### `int_player_season_totals`
Produces one row per player-season. Basketball Reference includes separate rows for each team a player played for plus a combined "2TM" aggregate. This model keeps only the combined row for traded players and removes records with 0 games played.

### `fct_player_season_stats`
Analytics-ready fact table with 64 columns. Key additions over the intermediate layer:

- Per-game averages (PPG, RPG, APG, SPG, BPG)
- True Shooting % (TS%)
- Per-36 minute stats
- Assist-to-turnover ratio
- Usage rate
- Offensive rating approximation
- Fantasy points
- Player role, scoring, efficiency, and playing-time categories
- Season participation % (accounts for lockout and COVID-shortened seasons)

---

## Data Quality Tests

### Generic tests (schema.yml)
- `unique` and `not_null` on primary keys at every layer

### Custom tests (tests/)
- `field_goals_match_components` — total FG = 2PT + 3PT made
- `made_not_greater_than_attempted` — made shots never exceed attempts
- `rebounds_match_components` — total rebounds = offensive + defensive
- `games_started_not_greater_than_played` — starts never exceed games played

---

## Source Data

Raw data is loaded by [nba-ingestion-pipeline](https://github.com/abdirahman2ali/nba-ingestion-pipeline), which scrapes Basketball Reference and writes to `nba.player_season_averages`.

---

## License

MIT
