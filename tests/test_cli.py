import contextlib
import csv
import io
import os
import tempfile
import unittest

from jiraexport import cli
from jiraexport.client import JiraClient
from tests.helpers import FakeResponse, FakeSession, load, search_handler, since_handler


def run(argv, session=None):
    session = session or FakeSession().add("GET", r"/rest/api/3/search$", search_handler(load("issues.json")))
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stderr(err):
        code = cli.main(argv, client=JiraClient("https://example.atlassian.net", session=session), out=out)
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def test_csv_to_stdout(self):
        code, text, err = run(["--jql", "project = PLAT"])
        self.assertEqual(code, 0)
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual([r["key"] for r in rows], ["PLAT-101", "PLAT-102", "PLAT-103"])
        self.assertIn("exported 3 issues", err)

    def test_csv_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "issues.csv")
            code, text, _ = run(["--jql", "project = PLAT", "-o", path])
            with open(path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(text, "")
        self.assertEqual(len(rows), 3)

    def test_json_format(self):
        import json
        code, text, _ = run(["--jql", "project = PLAT", "--format", "json"])
        data = json.loads(text)
        self.assertEqual([r["key"] for r in data], ["PLAT-101", "PLAT-102", "PLAT-103"])
        self.assertEqual(data[0]["labels"], "auth, p1")

    def test_custom_field_columns(self):
        session = FakeSession().add("GET", r"/rest/api/3/field$", load("fields.json"))
        session.add("GET", r"/rest/api/3/search$", search_handler(load("issues.json")))
        code, text, _ = run(["--jql", "project = PLAT", "-F", "Story point estimate=points", "-F", "customfield_10030"], session)
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(code, 0)
        self.assertEqual([(r["key"], r["points"]) for r in rows], [("PLAT-101", "5"), ("PLAT-102", "3"), ("PLAT-103", "")])
        self.assertIn("customer_impact", rows[0])
        fields = session.calls_to("GET", "/search")[0]["params"]["fields"].split(",")
        self.assertIn("customfield_10016", fields)

    def test_unknown_field_is_a_usage_error(self):
        session = FakeSession().add("GET", r"/rest/api/3/field$", load("fields.json"))
        code, _, err = run(["--jql", "project = PLAT", "-F", "Nope"], session)
        self.assertEqual(code, 2)
        self.assertIn("Nope", err)

    def test_gzip_output_and_sidecar_names(self):
        import gzip
        self.assertEqual(cli.sidecar_path("out/issues.csv.gz", "comments"), "out/issues-comments.csv.gz")
        self.assertEqual(cli.sidecar_path("issues", "comments"), "issues-comments")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "issues.csv.gz")
            code, _, _ = run(["--jql", "project = PLAT", "-o", path, "--comments"])
            with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            with gzip.open(os.path.join(tmp, "issues-comments.csv.gz"), "rt", encoding="utf-8", newline="") as handle:
                comment_rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(comment_rows), 2)

    def test_manifest(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "issues.csv")
            code, _, _ = run(["--jql", "project = PLAT", "-o", path, "--comments", "--manifest"])
            with open(path + ".manifest.json", encoding="utf-8") as handle:
                data = json.load(handle)
        self.assertEqual(code, 0)
        self.assertEqual(data["files"], [{"path": "issues.csv", "rows": 3}, {"path": "issues-comments.csv", "rows": 2}])
        self.assertEqual(data["jql"], "project = PLAT")

    def test_manifest_needs_output(self):
        code, _, err = run(["--jql", "project = PLAT", "--manifest"])
        self.assertEqual(code, 2)

    def test_excel_adds_a_bom_to_every_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "issues.csv")
            run(["--jql", "project = PLAT", "-o", path, "--comments", "--excel"])
            for name in ("issues.csv", "issues-comments.csv"):
                with open(os.path.join(tmp, name), "rb") as handle:
                    self.assertEqual(handle.read(3), b"\xef\xbb\xbf")
            run(["--jql", "project = PLAT", "-o", path])
            with open(path, "rb") as handle:
                self.assertEqual(handle.read(3), b"key")

    def test_excel_on_stdout(self):
        code, text, _ = run(["--jql", "project = PLAT", "--excel"])
        self.assertTrue(text.startswith("\ufeffkey,"))

    def test_summaries_that_look_like_formulas_are_quoted(self):
        import json
        issues = json.loads(json.dumps(load("issues.json")))
        issues[0]["fields"]["summary"] = "=cmd|' /C calc'!A0"
        session = FakeSession().add("GET", r"/rest/api/3/search$", search_handler(issues))
        code, text, _ = run(["--jql", "project = PLAT"], session)
        self.assertEqual(list(csv.DictReader(io.StringIO(text)))[0]["summary"], "'=cmd|' /C calc'!A0")
        session = FakeSession().add("GET", r"/rest/api/3/search$", search_handler(issues))
        code, text, _ = run(["--jql", "project = PLAT", "--raw-csv"], session)
        self.assertEqual(list(csv.DictReader(io.StringIO(text)))[0]["summary"], "=cmd|' /C calc'!A0")

    def test_limit(self):
        code, text, err = run(["--jql", "project = PLAT", "--limit", "2"])
        self.assertEqual([r["key"] for r in csv.DictReader(io.StringIO(text))], ["PLAT-101", "PLAT-102"])
        self.assertIn("exported 2 issues", err)

    def test_column_selection_and_order(self):
        code, text, _ = run(["--jql", "project = PLAT", "--columns", "status,key"])
        self.assertEqual(text.splitlines()[:2], ["status,key", "In Progress,PLAT-101"])

    def test_unknown_column(self):
        code, _, err = run(["--jql", "project = PLAT", "--columns", "key,colour"])
        self.assertEqual(code, 2)
        self.assertIn("colour", err)

    def test_columns_apply_to_json_too(self):
        import json
        code, text, _ = run(["--jql", "project = PLAT", "--format", "jsonl", "--columns", "key,status", "--comments"])
        first = json.loads(text.splitlines()[0])
        self.assertEqual(list(first), ["key", "status", "comments"])

    def test_html_column(self):
        session = FakeSession().add("GET", r"/rest/api/3/search$", search_handler(load("issues.json")))
        code, text, _ = run(["--jql", "project = PLAT", "--html"], session)
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertTrue(rows[0]["description_html"].startswith("<h2>Summary</h2>"))
        self.assertEqual(rows[2]["description_html"], "")
        self.assertEqual(session.calls[0]["params"]["expand"], "renderedFields")

    def test_links_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "issues.csv")
            code, _, _ = run(["--jql", "project = PLAT", "-o", path, "--links"])
            with open(os.path.join(tmp, "issues-links.csv"), newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(code, 0)
        self.assertEqual([(r["issue"], r["relation"], r["other"]) for r in rows],
                         [("PLAT-101", "blocks", "PLAT-103"), ("PLAT-103", "is blocked by", "PLAT-101")])

    def test_changelog_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "issues.csv")
            session = FakeSession().add("GET", r"/rest/api/3/search$", search_handler(load("issues.json")))
            code, _, _ = run(["--jql", "project = PLAT", "-o", path, "--changelog"], session)
            with open(os.path.join(tmp, "issues-changelog.csv"), newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(code, 0)
        self.assertEqual([r["issue"] for r in rows], ["PLAT-101"] * 4 + ["PLAT-102"])
        self.assertEqual(session.calls[0]["params"]["expand"], "changelog")

    def test_jsonl_nests_the_extras(self):
        import json
        code, text, _ = run(["--jql", "project = PLAT", "--format", "jsonl", "--comments", "--worklogs", "--attachments"])
        self.assertEqual(code, 0)
        records = [json.loads(line) for line in text.splitlines()]
        self.assertEqual(len(records), 3)
        self.assertEqual([c["author"] for c in records[0]["comments"]], ["Bob Okafor", "Alice Moreau"])
        self.assertEqual(len(records[0]["worklogs"]), 2)
        self.assertEqual(len(records[0]["attachments"]), 2)
        self.assertEqual(records[2]["comments"], [])

    def test_comments_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "issues.csv")
            code, _, _ = run(["--jql", "project = PLAT", "-o", path, "--comments"])
            with open(os.path.join(tmp, "issues-comments.csv"), newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(code, 0)
        self.assertEqual([(r["issue"], r["author"]) for r in rows], [("PLAT-101", "Bob Okafor"), ("PLAT-101", "Alice Moreau")])

    def test_worklogs_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "issues.csv")
            code, _, _ = run(["--jql", "project = PLAT", "-o", path, "--worklogs", "--comments"])
            self.assertEqual(sorted(os.listdir(tmp)), ["issues-comments.csv", "issues-worklogs.csv", "issues.csv"])
            with open(os.path.join(tmp, "issues-worklogs.csv"), newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual([(r["issue"], r["timeSpentSeconds"]) for r in rows], [("PLAT-101", "7200"), ("PLAT-101", "5400")])

    def test_incremental_second_run_appends_only_new_issues(self):
        import json
        everything = load("issues.json")
        newer = json.loads(json.dumps(everything[2]))
        newer.update(key="PLAT-104", id="10104")
        newer["fields"]["updated"] = "2021-02-13T09:00:00.000+0000"
        with tempfile.TemporaryDirectory() as tmp:
            path, state = os.path.join(tmp, "issues.csv"), os.path.join(tmp, "state.json")
            first = FakeSession().add("GET", r"/rest/api/3/search$", since_handler(everything))
            code, _, _ = run(["--jql", "project = PLAT", "-o", path, "--incremental", state], first)
            self.assertEqual(code, 0)
            with open(state, encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual(saved["last_updated"], "2021-02-12T08:30:00.000+00:00")
            self.assertEqual(first.calls[0]["params"]["jql"], "project = PLAT")
            second = FakeSession().add("GET", r"/rest/api/3/search$", since_handler(everything + [newer]))
            code, _, err = run(["--jql", "project = PLAT", "-o", path, "--incremental", state], second)
            self.assertEqual(second.calls[0]["params"]["jql"], '(project = PLAT) AND updated >= "2021-02-12 08:30"')
            with open(path, newline="", encoding="utf-8") as handle:
                text = handle.read()
            with open(state, encoding="utf-8") as handle:
                saved = json.load(handle)
        self.assertEqual(text.count("key,summary"), 1)
        self.assertEqual([r["key"] for r in csv.DictReader(io.StringIO(text))], ["PLAT-101", "PLAT-102", "PLAT-103", "PLAT-104"])
        self.assertEqual(saved["last_updated"], "2021-02-13T09:00:00.000+00:00")
        self.assertEqual(saved["runs"], 2)

    def test_incremental_needs_a_file_and_an_appendable_format(self):
        code, _, err = run(["--jql", "project = PLAT", "--incremental", "state.json"])
        self.assertEqual(code, 2)
        code, _, err = run(["--jql", "project = PLAT", "-o", "x.json", "-f", "json", "--incremental", "state.json"])
        self.assertEqual(code, 2)
        self.assertIn("JSON Lines", err)

    def test_attachments_metadata_and_download(self):
        session = FakeSession().add("GET", r"/rest/api/3/search$", search_handler(load("issues.json")))
        session.add("GET", r"/attachment/content/\d+$", FakeResponse(200, "file body"))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "issues.csv")
            files = os.path.join(tmp, "files")
            code, _, _ = run(["--jql", "project = PLAT", "-o", path, "--download-attachments", files, "--max-attachment-mb", "0.02"], session)
            with open(os.path.join(tmp, "issues-attachments.csv"), newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            saved = os.listdir(os.path.join(files, "PLAT-101"))
        self.assertEqual(code, 0)
        self.assertTrue(rows[0]["saved_as"].startswith("skipped"))
        self.assertEqual(saved, ["30002-spinner.png"])

    def test_comments_need_an_output_file(self):
        code, _, err = run(["--jql", "project = PLAT", "--comments"])
        self.assertEqual(code, 2)
        self.assertIn("--output", err)

    def test_api_error_exit_code(self):
        session = FakeSession().add("GET", r"/search$", FakeResponse(400, {"errorMessages": ["Error in the JQL Query"]}))
        code, _, err = run(["--jql", "project ="], session)
        self.assertEqual(code, 2)
        self.assertIn("HTTP 400", err)

    def test_a_query_or_a_filter_is_required(self):
        code, _, err = run([])
        self.assertEqual(code, 2)
        self.assertIn("--jql", err)

    def test_filters_build_the_query(self):
        session = FakeSession().add("GET", r"/rest/api/3/search$", search_handler(load("issues.json")))
        code, _, _ = run(["-p", "PLAT", "--status", "To Do", "--updated-since", "2024-03-01"], session)
        self.assertEqual(session.calls[0]["params"]["jql"], 'project in ("PLAT") AND status in ("To Do") AND updated >= "2024-03-01"')

    def test_bad_date_is_reported(self):
        code, _, err = run(["-p", "PLAT", "--updated-since", "yesterday"])
        self.assertEqual(code, 2)
        self.assertIn("--updated-since", err)


if __name__ == "__main__":
    unittest.main()
