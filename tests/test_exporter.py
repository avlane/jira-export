import io
import unittest

from jiraexport import exporter, writers
from jiraexport.client import JiraClient
from tests.helpers import FakeSession, load, search_handler


class ProgressLoggingTests(unittest.TestCase):
    def test_progress_is_logged_every_n_issues(self):
        session = FakeSession().add("POST", r"/rest/api/3/search/jql$", search_handler(load("issues.json")))
        client = JiraClient("https://example.atlassian.net", session=session)
        sink = writers.open_sink("jsonl", io.StringIO(), ())
        old = exporter.PROGRESS_EVERY
        exporter.PROGRESS_EVERY = 2
        self.addCleanup(setattr, exporter, "PROGRESS_EVERY", old)
        with self.assertLogs("jiraexport", level="INFO") as captured:
            exporter.export(client, "project = PLAT", sink)
        self.assertEqual(captured.output, ["INFO:jiraexport:exported 2 issues (last: PLAT-102)",
                                           "INFO:jiraexport:export finished: 3 issues"])


class EstimateTests(unittest.TestCase):
    def test_estimate_appears_in_progress_messages(self):
        session = FakeSession().add("POST", r"/rest/api/3/search/jql$", search_handler(load("issues.json")))
        client = JiraClient("https://example.atlassian.net", session=session)
        sink = writers.open_sink("jsonl", io.StringIO(), ())
        old = exporter.PROGRESS_EVERY
        exporter.PROGRESS_EVERY = 3
        self.addCleanup(setattr, exporter, "PROGRESS_EVERY", old)
        with self.assertLogs("jiraexport", level="INFO") as captured:
            exporter.export(client, "project = PLAT", sink, estimate=250)
        self.assertEqual(captured.output[0], "INFO:jiraexport:about 250 issues match")
        self.assertEqual(captured.output[1], "INFO:jiraexport:exported 3 of about 250 issues (last: PLAT-103)")


if __name__ == "__main__":
    unittest.main()
