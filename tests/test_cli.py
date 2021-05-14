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
