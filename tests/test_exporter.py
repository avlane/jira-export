import io
import unittest

from jiraexport import exporter, writers
from jiraexport.client import JiraClient
from tests.helpers import FakeSession, load, search_handler


class ProgressLoggingTests(unittest.TestCase):
    def test_progress_is_logged_every_n_issues(self):
        session = FakeSession().add("GET", r"/rest/api/3/search$", search_handler(load("issues.json")))
        client = JiraClient("https://example.atlassian.net", session=session)
        sink = writers.open_sink("jsonl", io.StringIO(), ())
        old = exporter.PROGRESS_EVERY
        exporter.PROGRESS_EVERY = 2
        self.addCleanup(setattr, exporter, "PROGRESS_EVERY", old)
        with self.assertLogs("jiraexport", level="INFO") as captured:
            exporter.export(client, "project = PLAT", sink)
        self.assertEqual(captured.output, ["INFO:jiraexport:exported 2 issues (last: PLAT-102)",
                                           "INFO:jiraexport:export finished: 3 issues"])


if __name__ == "__main__":
    unittest.main()
