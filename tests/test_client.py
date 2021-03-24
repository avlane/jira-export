import unittest

from jiraexport.client import JiraClient, JiraError
from tests.helpers import FakeResponse, FakeSession, Seq


def make(session, **kwargs):
    return JiraClient("https://example.atlassian.net/", session=session, sleep=lambda s: None, **kwargs)


class ClientTests(unittest.TestCase):
    def test_get_builds_v3_url(self):
        session = FakeSession().add("GET", r"/myself$", {"accountId": "abc"})
        self.assertEqual(make(session).get("myself", {"expand": "groups"})["accountId"], "abc")
        self.assertEqual(session.calls[0]["url"], "https://example.atlassian.net/rest/api/3/myself")
        self.assertEqual(session.calls[0]["params"], {"expand": "groups"})

    def test_http_error(self):
        session = FakeSession().add("GET", r"/myself$", FakeResponse(401, {"message": "Unauthorized"}))
        with self.assertRaises(JiraError) as ctx:
            make(session).get("myself")
        self.assertEqual(ctx.exception.status, 401)

    def test_absolute_urls_are_left_alone(self):
        session = FakeSession().add("GET", r"/content/1$", {"ok": True})
        make(session).get("https://example.atlassian.net/rest/api/3/attachment/content/1")
        self.assertEqual(session.calls[0]["url"], "https://example.atlassian.net/rest/api/3/attachment/content/1")


class RateLimitTests(unittest.TestCase):
    def test_retry_after_is_honoured(self):
        limited = FakeResponse(429, None, {"Retry-After": "9"})
        session = FakeSession().add("GET", r"/myself$", Seq(limited, limited, {"ok": True}))
        sleeps = []
        client = JiraClient("https://example.atlassian.net", session=session, sleep=sleeps.append)
        self.assertEqual(client.get("myself"), {"ok": True})
        self.assertEqual(sleeps, [9, 9])

    def test_gives_up(self):
        session = FakeSession().add("GET", r"/myself$", FakeResponse(429, None, {"Retry-After": "1"}))
        with self.assertRaises(JiraError) as ctx:
            make(session, max_retries=2).get("myself")
        self.assertEqual(ctx.exception.status, 429)
        self.assertEqual(len(session.calls), 3)


if __name__ == "__main__":
    unittest.main()
