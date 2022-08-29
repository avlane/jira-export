import unittest

from jiraexport import issues
from jiraexport.client import JiraClient
from tests.helpers import FakeSession, load, search_handler


def make(handler):
    session = FakeSession().add("GET", r"/rest/api/3/search$", handler)
    return JiraClient("https://example.atlassian.net", session=session), session


class SearchTests(unittest.TestCase):
    def test_walks_all_pages(self):
        client, session = make(search_handler(load("issues.json")))
        got = list(issues.search(client, "project = PLAT", page_size=2))
        self.assertEqual([i["key"] for i in got], ["PLAT-101", "PLAT-102", "PLAT-103"])
        self.assertEqual([c["params"]["startAt"] for c in session.calls], [0, 2])

    def test_server_cap_on_page_size_is_respected(self):
        client, session = make(search_handler(load("issues.json"), cap=1))
        got = list(issues.search(client, "project = PLAT", page_size=100))
        self.assertEqual(len(got), 3)
        self.assertEqual([c["params"]["startAt"] for c in session.calls], [0, 1, 2])

    def test_fields_and_expand_are_sent_comma_separated(self):
        client, session = make(search_handler([]))
        list(issues.search(client, "project = NONE", fields=("summary", "status"), expand=("changelog", "names")))
        params = session.calls[0]["params"]
        self.assertEqual(params["fields"], "summary,status")
        self.assertEqual(params["expand"], "changelog,names")
        self.assertEqual(params["jql"], "project = NONE")

    def test_long_queries_are_posted(self):
        session = FakeSession().add("POST", r"/rest/api/3/search$", search_handler(load("issues.json")))
        client = JiraClient("https://example.atlassian.net", session=session)
        jql = "issue in ({}) ORDER BY key".format(",".join("PLAT-%d" % n for n in range(400)))
        got = list(issues.search(client, jql, fields=("summary",), expand=("changelog",), page_size=2))
        self.assertEqual(len(got), 3)
        self.assertEqual(session.calls_to("GET", "/search"), [])
        body = session.calls[0]["json"]
        self.assertEqual(body["jql"], jql)
        self.assertEqual(body["fields"], ["summary"])
        self.assertEqual(body["expand"], ["changelog"])
        self.assertEqual([c["json"]["startAt"] for c in session.calls], [0, 2])

    def test_short_queries_stay_on_get(self):
        client, session = make(search_handler([]))
        list(issues.search(client, "project = PLAT"))
        self.assertEqual(session.calls[0]["method"], "GET")

    def test_no_matches(self):
        client, session = make(search_handler([]))
        self.assertEqual(list(issues.search(client, "project = NONE")), [])
        self.assertEqual(len(session.calls), 1)


if __name__ == "__main__":
    unittest.main()
