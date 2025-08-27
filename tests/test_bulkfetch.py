import unittest

from jiraexport import issues
from jiraexport.client import JiraClient
from tests.helpers import FakeSession, bulkfetch_handler, search_handler, load


def make(failing=(), source=None):
    source = source if source is not None else load("issues.json")
    session = FakeSession()
    session.add("POST", r"/rest/api/3/search/jql$", search_handler(source))
    session.add("POST", r"/rest/api/3/issue/bulkfetch$", bulkfetch_handler(source, failing))
    return JiraClient("https://example.atlassian.net", session=session), session


class BulkFetchTests(unittest.TestCase):
    def test_bulk_fetch_request_shape(self):
        client, session = make()
        found, errors = issues.bulk_fetch(client, ["10101", "10102"], fields=("summary",), expand=("changelog",))
        self.assertEqual(sorted(i["key"] for i in found), ["PLAT-101", "PLAT-102"])
        self.assertEqual(errors, [])
        self.assertEqual(session.calls[0]["json"], {"issueIdsOrKeys": ["10101", "10102"], "fields": ["summary"], "expand": ["changelog"]})

    def test_more_than_a_hundred_is_refused(self):
        client, _ = make()
        with self.assertRaises(ValueError):
            issues.bulk_fetch(client, [str(n) for n in range(101)])

    def test_hydrated_search_keeps_search_order(self):
        client, session = make()
        got = list(issues.search_hydrated(client, "project = PLAT", fields=("summary",), expand=("changelog",)))
        self.assertEqual([i["key"] for i in got], ["PLAT-101", "PLAT-102", "PLAT-103"])
        self.assertEqual(session.calls[0]["json"]["fields"], ["id"])
        self.assertNotIn("expand", session.calls[0]["json"])
        self.assertEqual(session.calls[1]["json"]["expand"], ["changelog"])

    def test_batches_of_a_hundred(self):
        import copy
        base = load("issues.json")[0]
        many = []
        for n in range(250):
            issue = copy.deepcopy(base)
            issue.update(id=str(20000 + n), key="PLAT-%d" % (200 + n))
            many.append(issue)
        client, session = make(source=many)
        got = list(issues.search_hydrated(client, "project = PLAT"))
        self.assertEqual(len(got), 250)
        sizes = [len(c["json"]["issueIdsOrKeys"]) for c in session.calls_to("POST", "/issue/bulkfetch")]
        self.assertEqual(sizes, [100, 100, 50])

    def test_failures_are_skipped_and_reported(self):
        client, _ = make(failing=("10102",))
        failures = []
        with self.assertLogs("jiraexport", level="WARNING") as captured:
            got = list(issues.search_hydrated(client, "project = PLAT", failures=failures))
        self.assertEqual([i["key"] for i in got], ["PLAT-101", "PLAT-103"])
        self.assertEqual(failures, ["10102"])
        self.assertIn("could not fetch 10102", captured.output[0])

    def test_failures_list_is_optional(self):
        client, _ = make(failing=("10101",))
        with self.assertLogs("jiraexport", level="WARNING"):
            self.assertEqual(len(list(issues.search_hydrated(client, "project = PLAT"))), 2)


if __name__ == "__main__":
    unittest.main()
