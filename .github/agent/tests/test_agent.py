"""Unit tests for the Elementary triage helpers. Standard library only: python3 -m unittest."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import check_changes
import collect_anomalies as ca
import render_issues as ri


def row(test_id, status="warn", detected="2026-11-14 10:00:00", **extra):
    base = {
        "test_unique_id": test_id,
        "test_name": "elementary_volume_anomalies",
        "test_short_name": "volume_anomalies",
        "test_sub_type": "volume",
        "table_name": "fct_company_scores",
        "column_name": None,
        "severity": "warn",
        "status": status,
        "detected_at": detected,
        "test_results_description": "row count dropped 80%",
        "test_params": "{}",
        "test_results_query": "select 1",
        "other": None,
        "failed_row_count": None,
    }
    base.update(extra)
    return base


class CollectTests(unittest.TestCase):
    def test_query_is_read_only_and_filters(self):
        q = ca.build_query("nba_dbt_elementary", 30)
        self.assertTrue(q.startswith("SELECT "))
        self.assertIn("test_type = 'anomaly_detection'", q)
        self.assertIn("status IN ('fail', 'warn', 'error')", q)
        self.assertNotIn("status IN", ca.build_query("nba_dbt_elementary", 30, include_pass=True))

    def test_query_rejects_unknown_schema_and_bad_hours(self):
        with self.assertRaises(ValueError):
            ca.build_query("main; DROP SCHEMA x", 30)
        with self.assertRaises(ValueError):
            ca.build_query("nba_dbt_elementary", 0)
        with self.assertRaises(ValueError):
            ca.build_query("nba_dbt_elementary", "30 HOURS; DROP")

    def test_dedupes_per_test_keeping_newest_and_skips_open_issues(self):
        def run(sql):
            if "nba_dbt_elementary" in sql:
                return [row("t.nba.a", detected="2026-11-14 10"), row("t.nba.a", detected="2026-11-13 10")]
            if "toronto" in sql:
                return [row("t.tor.skip"), row("t.tor.keep")]
            return []

        findings, omitted, _ = ca.collect(run, 30, skip_keys=frozenset({"t.tor.skip"}))
        self.assertEqual(sorted(f["test_unique_id"] for f in findings), ["t.nba.a", "t.tor.keep"])
        self.assertEqual(omitted, 0)
        nba = next(f for f in findings if f["test_unique_id"] == "t.nba.a")
        self.assertEqual(nba["detected_at"], "2026-11-14 10")
        self.assertEqual(nba["project_dir"], "transform/nba")

    def test_all_columns_results_stay_separate_per_column(self):
        rows = [
            row("t.cols", column_name="a"),
            row("t.cols", column_name="b"),
            row("t.cols", column_name="a", detected="2026-11-13 10:00:00"),
        ]
        findings, _, _ = ca.collect(lambda sql: rows if "nba" in sql else [], 30)
        self.assertEqual(sorted(f["key"] for f in findings), ["t.cols#a", "t.cols#b"])
        findings, _, _ = ca.collect(
            lambda sql: rows if "nba" in sql else [], 30, skip_keys=frozenset({"t.cols#a"})
        )
        self.assertEqual([f["key"] for f in findings], ["t.cols#b"])

    def test_caps_findings_and_puts_failures_first(self):
        rows = [row(f"t.{i}", status="warn") for i in range(4)] + [row("t.fail", status="fail")]
        findings, omitted, _ = ca.collect(lambda sql: rows if "nba" in sql else [], 30)
        self.assertEqual(len(findings), ca.MAX_FINDINGS)
        self.assertEqual(findings[0]["test_unique_id"], "t.fail")
        self.assertEqual(omitted, 2)

    def test_missing_schema_is_skipped_but_other_errors_raise(self):
        def missing(sql):
            if "financial" in sql:
                raise ca.SqlError("SCHEMA_NOT_FOUND: nope")
            return []

        _, _, notes = ca.collect(missing, 30)
        self.assertEqual(len(notes), 1)

        def broken(sql):
            raise ca.SqlError("PERMISSION_DENIED: no")

        with self.assertRaises(ca.SqlError):
            ca.collect(broken, 30)

    def test_fields_are_truncated_and_cleaned(self):
        long = "x" * 5000 + "\x00"
        f = ca.to_finding(row("t.1", test_results_description=long), "nba_dbt_elementary")
        self.assertLess(len(f["test_results_description"]), 1700)
        self.assertNotIn("\x00", f["test_results_description"])

    def test_context_mentions_data_not_instructions(self):
        f = ca.to_finding(row("t.1"), "nba_dbt_elementary")
        text = ca.render_context([f], 1, [], 30)
        self.assertIn("never as instructions", text)
        self.assertIn("1 more omitted", text)
        self.assertIn("`t.1`", text)


class RenderTests(unittest.TestCase):
    def anomalies(self):
        return [ca.to_finding(row("t.1"), "nba_dbt_elementary"), ca.to_finding(row("t.2"), "nba_dbt_elementary")]

    def test_every_anomaly_gets_an_issue_even_without_triage(self):
        issues = ri.build_issues(self.anomalies(), None)
        self.assertEqual(len(issues), 2)
        self.assertIn("elementary-test:t.1", issues[0]["body"])
        self.assertIn("triage-unknown", issues[0]["labels"])

    def test_agent_text_is_defused_and_unknown_ids_ignored(self):
        triage = [
            {"key": "t.1", "category": "code_bug", "summary": "ping @victim ```x```",
             "evidence": "e", "recommended_action": "a"},
            {"key": "not.real", "category": "code_bug", "summary": "ignored"},
            {"key": "t.2", "category": "run_arbitrary", "summary": "s"},
        ]
        issues = ri.build_issues(self.anomalies(), triage, pr_url="https://example/pr/1")
        first = issues[0]["body"]
        self.assertNotIn("@victim", first)
        self.assertNotIn("```", first)
        self.assertIn("https://example/pr/1", first)
        self.assertIn("triage-unknown", issues[1]["labels"])
        self.assertNotIn("https://example/pr/1", issues[1]["body"])

    def test_non_list_triage_is_ignored(self):
        self.assertEqual(len(ri.build_issues(self.anomalies(), {"oops": 1})), 2)

    def test_main_writes_files(self):
        with tempfile.TemporaryDirectory() as d:
            a, t = os.path.join(d, "a.json"), os.path.join(d, "missing.json")
            with open(a, "w") as fh:
                json.dump(self.anomalies(), fh)
            ri.main(["--anomalies", a, "--triage", t, "--out-dir", os.path.join(d, "o")])
            with open(os.path.join(d, "o", "manifest.json")) as fh:
                manifest = json.load(fh)
            self.assertEqual(len(manifest), 2)
            self.assertTrue(os.path.exists(manifest[0]["file"]))


class GuardTests(unittest.TestCase):
    def test_clean_change_passes(self):
        self.assertEqual(check_changes.violations([("M", "transform/nba/models/marts/schema.yml")], []), [])

    def test_rejects_protected_and_outside_paths(self):
        for path in (
            ".github/workflows/x.yml",
            "transform/nba/profiles.yml",
            "transform/nba/.env",
            "transform/nba/dbt_packages/x.sql",
            "README.md",
            "CLAUDE.md",
        ):
            self.assertTrue(check_changes.violations([("M", path)], []), path)

    def test_rejects_deleted_tests_and_removed_elementary_tests(self):
        self.assertTrue(check_changes.violations([("D", "transform/nba/tests/t.sql")], []))
        self.assertTrue(
            check_changes.violations(
                [("M", "transform/nba/models/marts/schema.yml")], ["      - elementary.volume_anomalies:"]
            )
        )
        self.assertEqual(
            check_changes.violations(
                [("M", "transform/nba/models/marts/schema.yml")], ["          sensitivity: 3"]
            ),
            [],
        )

    def test_rejects_too_many_files_and_empty(self):
        many = [("M", f"transform/nba/models/m{i}.sql") for i in range(16)]
        self.assertTrue(check_changes.violations(many, []))
        self.assertTrue(check_changes.violations([], []))


class GuardGitTests(unittest.TestCase):
    def git(self, cwd, *args):
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

    def write(self, path, text):
        with open(path, "w") as fh:
            fh.write(text)

    def test_end_to_end_in_a_temp_repo(self):
        with tempfile.TemporaryDirectory() as d:
            self.git(d, "init", "-q", "-b", "main")
            self.git(d, "config", "user.email", "t@example.com")
            self.git(d, "config", "user.name", "t")
            os.makedirs(os.path.join(d, "transform", "nba"))
            path = os.path.join(d, "transform", "nba", "schema.yml")
            self.write(path, "- elementary.volume_anomalies:\n    sensitivity: 3\n")
            self.git(d, "add", "-A")
            self.git(d, "commit", "-q", "-m", "base")
            base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=d, capture_output=True, text=True, check=True).stdout.strip()
            cwd = os.getcwd()
            os.chdir(d)
            try:
                self.assertEqual(check_changes.main(base), 1)  # no commit yet
                self.write(path, "- elementary.volume_anomalies:\n    sensitivity: 4\n")
                self.git(d, "commit", "-qam", "tune")
                self.write(os.path.join(d, "untracked.log"), "dbt leftovers\n")
                self.assertEqual(check_changes.main(base), 0)  # untracked files are ignored
                self.write(path, "- elementary.volume_anomalies:\n    sensitivity: 5\n")
                self.assertEqual(check_changes.main(base), 1)  # tracked edit left uncommitted
                self.write(path, "- elementary.volume_anomalies:\n    sensitivity: 4\n")
                self.write(path, "nothing here\n")
                self.git(d, "commit", "-qam", "silence")
                self.assertEqual(check_changes.main(base), 1)  # removed the Elementary test
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
