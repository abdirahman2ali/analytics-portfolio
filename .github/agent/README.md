# Elementary triage agent

Once a day, `../workflows/elementary-triage.yml` reads the anomalies Elementary recorded in
Databricks, asks an AI agent to find the cause, opens one issue per anomaly, and opens a PR when
the cause is a code or test change. Nothing merges automatically.

```
Databricks job runs dbt build (Elementary tests record results)
  -> daily workflow: collect_anomalies.py reads <project>_elementary.elementary_test_results
  -> agent (no credentials) reads code and git history, writes triage.json, may commit locally
  -> check_changes.py guards the commit -> push + PR for review
  -> render_issues.py opens an issue per anomaly (label elementary-anomaly)
```

Files:

- `collect_anomalies.py`: read-only query of the three Elementary schemas. Standard library only.
- `triage-prompt.md`: the agent's instructions.
- `check_changes.py`: guard. Edits only under `transform/` and `ingestion/`, at most 15 files,
  no `.github/`, `.claude/`, `CLAUDE.md`, `.env`, `profiles.yml`, lock files, `dbt_packages/`,
  no deleted tests, no removed Elementary tests.
- `render_issues.py`: turns the agent's `triage.json` into issues. Agent text is cleaned and
  `@mentions` are defused.
- `parse_project.sh`: lets the agent check an edit parses, using dummy connection values.
- `tests/`: `python3 -m unittest discover -s .github/agent/tests`. The workflow runs them first.

The workflow runs the scripts from a copy taken before the agent starts, so the agent editing
them has no effect.

## One-time setup (the agent stays off until the last step)

1. GitHub App: install your existing App on this repo with Contents, Pull requests and Issues
   set to read and write. Add repo variable `AGENT_APP_ID` and secret `AGENT_APP_PRIVATE_KEY`.
2. Claude: run `claude setup-token` on your laptop and add the result as secret
   `CLAUDE_CODE_OAUTH_TOKEN`.
3. Databricks, read-only: create a token for a principal that can only `SELECT` on the
   `*_elementary` schemas and use the SQL warehouse. Add secrets `DATABRICKS_HOST` (host name,
   no path) and `DATABRICKS_TRIAGE_TOKEN`, and repo variable `DATABRICKS_WAREHOUSE_ID`.
4. Add repo variable `AGENT_ENABLED` = `true`. Set it to anything else to stop the agent.

Dry run: with the variable on, start the workflow by hand from the Actions tab
(`workflow_dispatch`) and set the look-back hours. With no anomalies it finishes without
opening anything.

## Limits

- At most 3 anomalies per run, failures first. The rest are picked up on later runs.
- No new PR while a triage PR is open, and at most 2 triage PRs per 7 days. Issues are still
  opened, and the agent only classifies in those runs.
- An open `elementary-anomaly` issue stops that anomaly being triaged again. Close it when done.
- The agent has no warehouse access, so it works from the code, test config and git history.
  When that is not enough it says `unknown` and what data would settle it.
- The first run of a test has no baseline and Elementary logs "not enough data". That is not an
  anomaly and is not collected.
