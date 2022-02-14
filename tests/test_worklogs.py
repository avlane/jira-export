import copy
import unittest

from jiraexport import worklogs
from jiraexport.client import JiraClient
from tests.helpers import FakeSession, load


def issue():
    return load("issues.json")[0]


class WorklogTests(unittest.TestCase):
    def test_embedded_worklogs(self):
        session = FakeSession()
        got = worklogs.fetch(JiraClient("https://example.atlassian.net", session=session), issue())
        self.assertEqual([w["id"] for w in got], ["20001", "20002"])
        self.assertEqual(session.calls, [])

    def test_the_rest_are_fetched(self):
        full = issue()["fields"]["worklog"]["worklogs"]
        partial = copy.deepcopy(issue())
        partial["fields"]["worklog"] = {"startAt": 0, "maxResults": 20, "total": 2, "worklogs": full[:1]}
        session = FakeSession().add("GET", r"/issue/PLAT-101/worklog$", lambda call: {
            "startAt": call["params"]["startAt"], "maxResults": 100, "total": 2, "worklogs": full[call["params"]["startAt"]:]})
        got = worklogs.fetch(JiraClient("https://example.atlassian.net", session=session), partial)
        self.assertEqual(len(got), 2)
        self.assertEqual(session.calls[0]["params"], {"startAt": 1, "maxResults": 100})

    def test_rows(self):
        rows = worklogs.rows("PLAT-101", issue()["fields"]["worklog"]["worklogs"])
        self.assertEqual(rows[0]["author"], "Alice Moreau")
        self.assertEqual(rows[0]["started"], "2021-02-04T09:00:00.000+00:00")
        self.assertEqual(rows[0]["timeSpent"], "2h")
        self.assertEqual(rows[0]["comment"], "Reproduced and profiled the login handler")
        self.assertEqual(rows[1]["timeSpent"], "90m")
        self.assertEqual(rows[1]["comment"], "")

    def test_total_seconds(self):
        self.assertEqual(worklogs.total_seconds(issue()["fields"]["worklog"]["worklogs"]), 12600)


if __name__ == "__main__":
    unittest.main()
