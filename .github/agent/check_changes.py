"""Guard for the Elementary triage agent. Run from a trusted copy, never from the agent's branch.

Usage: check_changes.py <base-sha>
Exit 0 when the agent's commit is safe to push, 1 otherwise. The reason is printed.
"""

import re
import subprocess
import sys

ALLOWED_ROOTS = ("transform/", "ingestion/")
PROTECTED = re.compile(
    r"(^|/)(\.github/|\.claude/|CLAUDE\.md$|\.env($|\.)|profiles\.yml$|dbt_packages/|target/|package-lock\.yml$)"
)
ELEMENTARY_TEST = re.compile(r"-\s*elementary\.\w+")
MAX_FILES = 15


def violations(changes, removed_lines):
    """changes: [(status, path)]. removed_lines: removed diff lines without the leading '-'."""
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
    for line in removed_lines:
        if ELEMENTARY_TEST.search("-" + line):
            found.append(f"removes an Elementary test: {line.strip()}")
    return found


def _git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


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
    removed = [
        line[1:]
        for line in _git("diff", "--no-renames", "-U0", base, "HEAD").splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]
    problems = violations(changes, removed)
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
