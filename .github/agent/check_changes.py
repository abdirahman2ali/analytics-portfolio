"""Guard for the Elementary triage agent. Run from a trusted copy, never from the agent's branch.

Usage: check_changes.py <base-sha>
Exit 0 when the agent's commit is safe to push, 1 otherwise. The reason is printed.
"""

import re
import subprocess
import sys

ALLOWED_ROOTS = ("transform/", "ingestion/")
PROTECTED = re.compile(
    r"(^|/)("
    r"\.github/|\.claude/|CLAUDE\.md$|\.env($|\.)|profiles\.yml$|dbt_packages/|target/"
    r"|package-lock\.yml$|packages\.yml$|dbt_project\.yml$|generate_schema_name\.sql$"
    r")"
)
ELEMENTARY_TEST = re.compile(r"-\s*elementary\.\w+")
# Config that turns a test off or changes what counts as a failure. Silencing an alert is not a
# fix, so any added or removed line touching these in a YAML file is rejected.
GATED_KEYS = re.compile(r"\b(severity|enabled|warn_if|error_if|fail_calc|limit)\s*:")
YAML_FILE = re.compile(r"\.ya?ml$")
MAX_FILES = 15

# git runs in a checkout the agent could write to, so switch off every config hook we know of.
GIT_SAFE = ["-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-c", "core.pager=cat"]


def violations(changes, diff_lines=()):
    """changes: [(status, path)]. diff_lines: [(path, sign, text)] for added and removed lines."""
    found = []
    if not changes:
        return ["no changes"]
    if len(changes) > MAX_FILES:
        found.append(f"{len(changes)} files changed, limit is {MAX_FILES}")
    for status, path in changes:
        if not path.startswith(ALLOWED_ROOTS):
            found.append(f"outside transform/ and ingestion/: {path}")
        if PROTECTED.search(path):
            found.append(f"protected path: {path}")
        if status == "D" and "/tests/" in path:
            found.append(f"deletes a test: {path}")
    for path, sign, text in diff_lines:
        if sign == "-" and ELEMENTARY_TEST.search("-" + text):
            found.append(f"removes an Elementary test in {path}: {text.strip()}")
        if YAML_FILE.search(path) and GATED_KEYS.search(text):
            found.append(f"changes test severity or enablement in {path}: {text.strip()}")
    return found


def _git(*args):
    return subprocess.run(
        ["git", *GIT_SAFE, *args], check=True, capture_output=True, text=True
    ).stdout


def parse_diff(text):
    """Turn `git diff -U0` output into [(path, sign, text)] for added and removed lines."""
    lines, path, in_hunk = [], "", False
    for line in text.splitlines():
        if line.startswith("diff --git "):
            in_hunk, path = False, ""
        elif line.startswith("@@"):
            in_hunk = True
        elif not in_hunk:
            # File headers only appear before the first hunk. A deleted file has no "+++ b/".
            if line.startswith(("--- a/", "+++ b/")):
                path = line[6:]
        elif line[:1] in ("+", "-"):
            lines.append((path, line[0], line[1:]))
    return lines


def _diff_lines(base):
    return parse_diff(_git("diff", "--no-renames", "-U0", base, "HEAD"))


def main(base):
    # Untracked files (dbt_packages/, target/) are never pushed, so only tracked edits count.
    if _git("status", "--porcelain", "--untracked-files=no").strip():
        print("Uncommitted changes left behind.")
        return 1
    if _git("rev-parse", "HEAD").strip() == base:
        print("Agent made no commit.")
        return 1
    changes = []
    for line in _git("diff", "--no-renames", "--name-status", base, "HEAD").splitlines():
        status, _, path = line.partition("\t")
        changes.append((status.strip(), path.strip()))
    problems = violations(changes, _diff_lines(base))
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
