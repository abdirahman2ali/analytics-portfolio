# analytics-portfolio

Personal data engineering portfolio. End-to-end pipelines across multiple domains — ingestion, transformation via dbt, and BI via Omni. All projects run on Databricks (`abdirahman_portfolio` catalog) with a shared dbt project.

## Projects

### NBA Analytics
Python scraper pulls player season data from Basketball Reference (1950–present) into Databricks. dbt models produce advanced metrics (TS%, PER-36, usage rate, fantasy scoring) across staging → intermediate → mart layers.

Stack: Python, BeautifulSoup, Databricks, dbt, Omni

### Toronto Parking Analytics
Ingests 34.7M+ Toronto Open Data parking tickets (2006–present) via the CKAN API into Delta tables. dbt models build a dimensional model for infraction pattern analysis, street-level enforcement trends, and fine revenue by violation type. Includes geospatial centreline data for map-based queries.

Stack: Python, Databricks, dbt, Omni

## Structure

```
analytics-portfolio/
├── ingestion/
│   ├── nba/            Python scraper (Basketball Reference → Databricks)
│   └── toronto-parking/  CKAN API ingestion (Toronto Open Data → Databricks)
└── transform/          Single dbt project covering all domains
    └── models/
        ├── nba/
        └── toronto_parking/
```
