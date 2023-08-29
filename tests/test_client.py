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


class TransientErrorTests(unittest.TestCase):
    def test_gets_are_retried_with_backoff(self):
        session = FakeSession().add("GET", r"/myself$", Seq(FakeResponse(503), FakeResponse(504), {"ok": True}))
        sleeps = []
        client = JiraClient("https://example.atlassian.net", session=session, sleep=sleeps.append)
        self.assertEqual(client.get("myself"), {"ok": True})
        self.assertEqual(sleeps, [2, 4])

    def test_posts_are_not_retried(self):
        session = FakeSession().add("POST", r"/search$", FakeResponse(502, "bad gateway"))
        client = JiraClient("https://example.atlassian.net", session=session, sleep=lambda s: None)
        with self.assertRaises(JiraError):
            client.request("POST", "search", body={})
        self.assertEqual(len(session.calls), 1)

    def test_downloads_are_retried_too(self):
        import os
        import tempfile
        session = FakeSession().add("GET", r"/content/1$", Seq(FakeResponse(502, "bad gateway"), FakeResponse(200, "ok")))
        client = JiraClient("https://example.atlassian.net", session=session, sleep=lambda s: None)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(client.download("https://example.atlassian.net/content/1", os.path.join(tmp, "f")), 2)


class DownloadTests(unittest.TestCase):
    def test_streams_to_a_file(self):
        import os
        import tempfile
        session = FakeSession().add("GET", r"/attachment/content/1$", FakeResponse(200, "x" * 200000))
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out.bin")
            written = make(session).download("https://example.atlassian.net/rest/api/3/attachment/content/1", dest)
            with open(dest, "rb") as handle:
                self.assertEqual(len(handle.read()), 200000)
        self.assertEqual(written, 200000)
        self.assertTrue(session.calls[0]["url"].endswith("/attachment/content/1"))

    def test_interrupted_download_leaves_no_partial_file(self):
        import os
        import tempfile

        class Broken(FakeResponse):
            def iter_content(self, chunk_size=8192):
                yield b"abc"
                raise ConnectionError("connection reset")

        session = FakeSession().add("GET", r"/content/1$", Broken(200, "abc"))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ConnectionError):
                make(session).download("https://example.atlassian.net/content/1", os.path.join(tmp, "f.bin"))
            self.assertEqual(os.listdir(tmp), [])

    def test_errors_are_reported(self):
        import os
        import tempfile
        session = FakeSession().add("GET", r"/attachment/content/1$", FakeResponse(404, "gone"))
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(JiraError) as ctx:
            make(session).download("https://example.atlassian.net/rest/api/3/attachment/content/1", os.path.join(tmp, "x"))
        self.assertEqual(ctx.exception.status, 404)
        self.assertEqual(os.listdir(tmp) if os.path.exists(tmp) else [], [])

    def test_downloads_retry_on_429(self):
        import os
        import tempfile
        limited = FakeResponse(429, None, {"Retry-After": "2"})
        session = FakeSession().add("GET", r"/content/1$", Seq(limited, FakeResponse(200, "abc")))
        sleeps = []
        client = JiraClient("https://example.atlassian.net", session=session, sleep=sleeps.append)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(client.download("https://example.atlassian.net/content/1", os.path.join(tmp, "f")), 3)
        self.assertEqual(sleeps, [2])


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
