import copy
import unittest

from jiraexport import comments
from jiraexport.client import JiraClient
from tests.helpers import FakeSession, load


def issue():
    return load("issues.json")[0]


class CommentTests(unittest.TestCase):
    def test_embedded_comments_need_no_extra_request(self):
        session = FakeSession()
        got = comments.fetch(JiraClient("https://example.atlassian.net", session=session), issue())
        self.assertEqual(len(got), 2)
        self.assertEqual(session.calls, [])

    def test_missing_comments_are_fetched_in_pages(self):
        full = issue()["fields"]["comment"]["comments"]
        partial = copy.deepcopy(issue())
        partial["fields"]["comment"] = {"comments": full[:1], "total": 2, "maxResults": 1, "startAt": 0}

        def handler(call):
            start = call["params"]["startAt"]
            return {"startAt": start, "maxResults": 100, "total": 2, "comments": full[start:]}

        session = FakeSession().add("GET", r"/issue/PLAT-101/comment$", handler)
        got = comments.fetch(JiraClient("https://example.atlassian.net", session=session), partial)
        self.assertEqual([c["id"] for c in got], ["10001", "10002"])
        self.assertEqual(session.calls[0]["params"], {"startAt": 1, "maxResults": 100, "orderBy": "created"})

    def test_no_comment_block(self):
        bare = {"key": "PLAT-9", "fields": {}}
        self.assertEqual(comments.fetch(JiraClient("https://example.atlassian.net", session=FakeSession()), bare), [])

    def test_rows(self):
        rows = comments.rows("PLAT-101", issue()["fields"]["comment"]["comments"])
        self.assertEqual(rows[0]["author"], "Bob Okafor")
        self.assertEqual(rows[0]["body"], "Seeing this on production since the 2.14 deploy.")
        self.assertEqual(rows[1]["visibility"], "Developers")
        self.assertEqual(rows[1]["body"], "@Bob Okafor can you attach a HAR file?\nInternal note: check the session store.")
        self.assertEqual(set(rows[0]), set(comments.COLUMNS))


if __name__ == "__main__":
    unittest.main()
