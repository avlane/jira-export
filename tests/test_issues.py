import unittest

from jiraexport import issues
from jiraexport.client import JiraClient
from tests.helpers import FakeSession, load, search_handler


def make(handler):
    session = FakeSession().add("POST", r"/rest/api/3/search/jql$", handler)
    return JiraClient("https://example.atlassian.net", session=session), session


class SearchTests(unittest.TestCase):
    def test_follows_next_page_token(self):
        client, session = make(search_handler(load("issues.json")))
        got = list(issues.search(client, "project = PLAT", fields=("summary",), expand=("changelog", "renderedFields"), page_size=2))
        self.assertEqual([i["key"] for i in got], ["PLAT-101", "PLAT-102", "PLAT-103"])
        first, second = [c["json"] for c in session.calls]
        self.assertNotIn("nextPageToken", first)
        self.assertEqual(second["nextPageToken"], "2")
        self.assertEqual(first["fields"], ["summary"])
        self.assertEqual(first["expand"], "changelog,renderedFields")

    def test_a_server_side_page_cap_is_followed(self):
        client, session = make(search_handler(load("issues.json"), cap=1))
        got = list(issues.search(client, "project = PLAT", page_size=100))
        self.assertEqual(len(got), 3)
        self.assertEqual([c["json"].get("nextPageToken") for c in session.calls], [None, "1", "2"])

    def test_stops_on_is_last_even_if_a_token_is_present(self):
        page = {"issues": [{"id": "1", "key": "A-1", "fields": {}}], "nextPageToken": "x", "isLast": True}
        client, session = make(page)
        self.assertEqual(len(list(issues.search(client, "project = A"))), 1)
        self.assertEqual(len(session.calls), 1)

    def test_long_queries_need_no_special_case(self):
        client, session = make(search_handler([]))
        jql = "issue in ({})".format(",".join("A-%d" % n for n in range(1000)))
        list(issues.search(client, jql))
        self.assertEqual(session.calls[0]["json"]["jql"], jql)

    def test_no_matches(self):
        client, session = make(search_handler([]))
        self.assertEqual(list(issues.search(client, "project = NONE")), [])
        self.assertEqual(len(session.calls), 1)


class ApproximateCountTests(unittest.TestCase):
    def test_reads_the_count(self):
        session = FakeSession().add("POST", r"/search/approximate-count$", {"count": 4321})
        client = JiraClient("https://example.atlassian.net", session=session)
        self.assertEqual(issues.approximate_count(client, "project = PLAT"), 4321)
        self.assertEqual(session.calls[0]["json"], {"jql": "project = PLAT"})


if __name__ == "__main__":
    unittest.main()
