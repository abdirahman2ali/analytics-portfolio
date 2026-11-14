"""Turn the agent's triage.json into GitHub issue bodies. Run from a trusted copy.

Every collected anomaly gets an issue, even when the agent produced nothing for it, so a human
always hears about it and the open issue stops the same anomaly being triaged again.
The agent's text is untrusted: it is cleaned, shortened and has @mentions defused.
"""

import argparse
import json
import os
import sys

CATEGORIES = {"code_bug", "upstream_data", "noisy_test", "unknown"}
LIMIT = 2000
FIX_CATEGORIES = {"code_bug", "noisy_test"}


def clean(value, limit=LIMIT):
    text = "" if value is None else str(value)
    text = "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)
    text = text.replace("@", "@\u200b").replace("```", "'''")
    return text if len(text) <= limit else text[:limit] + " ...[truncated]"


def load_json(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def index_triage(triage, known_ids):
    entries = {}
    if not isinstance(triage, list):
        return entries
    for item in triage:
        if isinstance(item, dict) and item.get("key") in known_ids:
            entries[item["key"]] = item
    return entries


def build_issues(anomalies, triage, pr_url=None):
    by_id = index_triage(triage, {a["key"] for a in anomalies})
    issues = []
    for a in anomalies:
        entry = by_id.get(a["key"], {})
        category = entry.get("category")
        category = category if category in CATEGORIES else "unknown"
        target = a["table_name"] + (f".{a['column_name']}" if a["column_name"] else "")
        name = a["test_short_name"] or a["test_name"]
        body = [
            f"<!-- elementary-test:{a['key']} -->",
            f"**Category:** `{category}`",
            "",
            f"**Summary:** {clean(entry.get('summary')) or 'The agent produced no triage for this anomaly.'}",
            "",
            f"**Evidence:** {clean(entry.get('evidence')) or 'None.'}",
            "",
            f"**Recommended action:** {clean(entry.get('recommended_action')) or 'Investigate manually.'}",
            "",
        ]
        if pr_url and category in FIX_CATEGORIES:
            body += [f"**Proposed change:** {pr_url}", ""]
        body += [
            "| | |",
            "|---|---|",
            f"| Test | `{clean(a['test_unique_id'], 300)}` |",
            f"| Model | `{clean(target, 200)}` |",
            f"| Status | {clean(a['status'], 40)} (severity {clean(a['severity'], 40)}) |",
            f"| Detected | {clean(a['detected_at'], 60)} |",
            f"| Description | {clean(a['test_results_description'], 500)} |",
            "",
            "Opened by the Elementary triage agent. Close this issue once handled.",
        ]
        issues.append(
            {
                "title": clean(f"Elementary: {name} on {target} ({category})", 120),
                "labels": ["elementary-anomaly", f"triage-{category}"],
                "body": "\n".join(body),
            }
        )
    return issues


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--anomalies", required=True)
    ap.add_argument("--triage", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--pr-url")
    args = ap.parse_args(argv)

    issues = build_issues(
        load_json(args.anomalies, []), load_json(args.triage, []), args.pr_url
    )
    os.makedirs(args.out_dir, exist_ok=True)
    manifest = []
    for i, issue in enumerate(issues, 1):
        path = os.path.join(args.out_dir, f"issue-{i}.md")
        with open(path, "w") as fh:
            fh.write(issue["body"])
        manifest.append({"file": path, "title": issue["title"], "labels": issue["labels"]})
    with open(os.path.join(args.out_dir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"rendered {len(manifest)} issue(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
