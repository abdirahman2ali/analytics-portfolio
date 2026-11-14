#!/usr/bin/env bash
# Parse one dbt project with dummy connection values, so the triage agent can check its edits
# without any warehouse credentials. Run from a trusted copy.
# Usage: parse_project.sh <financial-due-diligence|nba|toronto-parking> [deps]
#   deps  install the project's dbt packages instead of parsing (the workflow does this once
#         before the agent starts, so the agent itself never needs network access)
# DBT_BIN is the absolute path to dbt. The workflow never adds that folder to PATH.
set -euo pipefail

project="$1"
mode="${2:-parse}"
dbt_bin="${DBT_BIN:-dbt}"
case "$project" in
  financial-due-diligence | nba | toronto-parking) ;;
  *) echo "unknown project: $project" >&2; exit 2 ;;
esac

cd "${GITHUB_WORKSPACE:-.}/transform/$project"
export DATABRICKS_HOST=example.invalid DATABRICKS_SERVER_HOSTNAME=example.invalid
export DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/none DATABRICKS_TOKEN=none
export DATABRICKS_CATALOG=abdirahman_portfolio DBT_BRANCH_SLUG=triage_agent

if [ "$mode" = "deps" ]; then
  "$dbt_bin" deps
  exit 0
fi

if [ "$project" = "financial-due-diligence" ]; then
  "$dbt_bin" parse --no-partial-parse --target dev
else
  "$dbt_bin" parse --no-partial-parse
fi
