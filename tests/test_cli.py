import contextlib
import csv
import io
import os
import tempfile
import unittest

from jiraexport import cli
from jiraexport.client import JiraClient
from tests.helpers import FakeResponse, FakeSession, load, search_handler


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

    def test_jql_is_required(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.build_parser().parse_args([])


if __name__ == "__main__":
    unittest.main()
