# analytics-portfolio

Personal data engineering portfolio built as a monorepo. Each project covers a different analytical domain and follows the same end-to-end pattern: a Python ingestion layer that loads raw data into Databricks, a shared dbt project that transforms it into a dimensional model, and Omni for BI and exploration.

## Architecture

Every domain in this repo follows the same pipeline shape:

**Ingest** — a Python package fetches data from an external source (API, scraper, or file download) and writes it into Delta tables in the `abdirahman_portfolio` Databricks catalog.

**Transform** — a single shared dbt project (`transform/`) covers all domains. Models are namespaced by domain under `models/<domain>/` and follow a three-layer pattern:

- **Staging** — one-to-one with the raw source, typed and renamed, no joins
- **Intermediate** — joins and business logic, not exposed to BI
- **Marts** — queryable grain tables (`fct_`, `dim_`, `rpt_`) materialized as tables or incremental models

A custom `generate_schema_name` macro isolates each domain into its own schema (`<domain>_dbt_staging`, `<domain>_dbt_marts`, etc.) within the shared catalog, so domains don't collide and Omni can model them independently.

**BI** — Omni connects to the `abdirahman_portfolio` catalog with the dbt integration enabled, pulling column descriptions, primary keys, and relationships directly from `schema.yml`.

## Structure

```
analytics-portfolio/
├── ingestion/
│   └── <domain>/           one Python package per source domain
│       ├── main.py
│       ├── <domain>/       ingestion logic (fetcher, transformer, loader)
│       ├── tests/
│       └── requirements.txt
└── transform/              single dbt project covering all domains
    ├── dbt_project.yml
    ├── macros/
    └── models/
        └── <domain>/
            ├── staging/
            ├── intermediate/
            └── marts/
```

## Local dbt development (financial-due-diligence)

The `prod` target (used by the Databricks job) writes to `financial_due_diligence_{bronze,silver,gold}`. Local runs use the `dev` target, which builds every layer into one schema, `dev_<DBT_BRANCH_SLUG>`, so parallel branches never overwrite each other or prod. Raw source tables are still read from the prod bronze schema.

| Variable | Description | Example |
|----------|-------------|---------|
| `DBT_BRANCH_SLUG` | Branch identifier, lowercase letters, digits and underscores | `feat_add_scoring_chart` |

```sh
cd transform/financial-due-diligence
DBT_BRANCH_SLUG=feat_add_scoring_chart dbt build --target dev
```

Never run `--target prod` locally. The macro rejects any non-prod schema that does not match `dev_<slug>`. Drop the `dev_<slug>` schema once the branch is merged.

## Stack

Python, Databricks (Delta Lake, serverless compute), dbt Core, Omni

## CI

Pull requests touching `ingestion/**` run lint (`ruff`) and unit tests (`pytest`) against the affected domain's ingestion package before merge is allowed.
