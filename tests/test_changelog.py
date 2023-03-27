import copy
import unittest

from jiraexport import changelog
from jiraexport.client import JiraClient
from tests.helpers import FakeSession, load


def issue():
    return load("issues.json")[0]


class ChangelogTests(unittest.TestCase):
    def test_embedded_changelog_is_used_as_is(self):
        session = FakeSession()
        got = changelog.fetch(JiraClient("https://example.atlassian.net", session=session), issue())
        self.assertEqual([h["id"] for h in got], ["40001", "40002", "40003"])
        self.assertEqual(session.calls, [])

    def test_remaining_pages_come_from_the_changelog_endpoint(self):
        histories = issue()["changelog"]["histories"]
        partial = copy.deepcopy(issue())
        partial["changelog"] = {"startAt": 0, "maxResults": 1, "total": 3, "histories": histories[:1]}

        def handler(call):
            start = call["params"]["startAt"]
            page = histories[start:start + 1]
            return {"startAt": start, "maxResults": 1, "total": 3, "isLast": start + 1 >= 3, "values": page}

        session = FakeSession().add("GET", r"/issue/PLAT-101/changelog$", handler)
        got = changelog.fetch(JiraClient("https://example.atlassian.net", session=session), partial)
        self.assertEqual([h["id"] for h in got], ["40001", "40002", "40003"])
        self.assertEqual([c["params"]["startAt"] for c in session.calls], [1, 2])

    def test_issue_without_changelog(self):
        self.assertEqual(changelog.fetch(JiraClient("https://example.atlassian.net", session=FakeSession()), {"key": "A-1"}), [])

    def test_one_row_per_changed_field(self):
        rows = changelog.rows("PLAT-101", issue()["changelog"]["histories"])
        self.assertEqual(len(rows), 4)
        status = rows[0]
        self.assertEqual((status["field"], status["fromString"], status["toString"]), ("status", "To Do", "In Progress"))
        self.assertEqual(status["created"], "2021-02-03T10:15:22.123+00:00")
        self.assertEqual(status["author"], "Bob Okafor")
        assignee = rows[1]
        self.assertEqual((assignee["from"], assignee["to"], assignee["toString"]), ("", "5b10ac8d82e05b22cc7d4ef5", "Alice Moreau"))


if __name__ == "__main__":
    unittest.main()
