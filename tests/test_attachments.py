import os
import tempfile
import unittest

from jiraexport import attachments
from jiraexport.client import JiraClient
from tests.helpers import FakeResponse, FakeSession, load


def attached():
    return load("issues.json")[0]["fields"]["attachment"]


def make_client(session):
    return JiraClient("https://example.atlassian.net", session=session, sleep=lambda s: None)


class AttachmentTests(unittest.TestCase):
    def test_rows_without_downloads(self):
        rows = attachments.rows("PLAT-101", attached())
        self.assertEqual([(r["filename"], r["size"], r["author"]) for r in rows],
                         [("login-trace.har", 48211, "Alice Moreau"), ("spinner.png", 10394, "Bob Okafor")])
        self.assertEqual(rows[0]["saved_as"], "")

    def test_download_into_issue_folder(self):
        session = FakeSession().add("GET", r"/attachment/content/\d+$", lambda call: FakeResponse(200, "data for " + call["url"][-5:]))
        with tempfile.TemporaryDirectory() as tmp:
            notes = attachments.download_all(make_client(session), "PLAT-101", attached(), tmp)
            self.assertEqual(sorted(os.listdir(os.path.join(tmp, "PLAT-101"))), ["30001-login-trace.har", "30002-spinner.png"])
            with open(notes["30001"], encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "data for 30001")
        rows = attachments.rows("PLAT-101", attached(), notes)
        self.assertTrue(rows[0]["saved_as"].endswith("30001-login-trace.har"))

    def test_files_from_an_earlier_run_are_not_fetched_again(self):
        session = FakeSession().add("GET", r"/attachment/content/\d+$", FakeResponse(200, "x" * 10394))
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "PLAT-101"))
            with open(os.path.join(tmp, "PLAT-101", "30002-spinner.png"), "wb") as handle:
                handle.write(b"x" * 10394)
            notes = attachments.download_all(make_client(session), "PLAT-101", attached(), tmp)
        self.assertEqual([c["url"][-5:] for c in session.calls], ["30001"])
        self.assertTrue(notes["30002"].endswith("30002-spinner.png"))

    def test_a_file_with_the_wrong_size_is_fetched_again(self):
        session = FakeSession().add("GET", r"/attachment/content/\d+$", FakeResponse(200, "x" * 10394))
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "PLAT-101"))
            with open(os.path.join(tmp, "PLAT-101", "30002-spinner.png"), "wb") as handle:
                handle.write(b"half")
            attachments.download_all(make_client(session), "PLAT-101", attached()[1:], tmp)
            with open(os.path.join(tmp, "PLAT-101", "30002-spinner.png"), "rb") as handle:
                self.assertEqual(len(handle.read()), 10394)

    def test_hostile_filenames_stay_inside_the_folder(self):
        evil = [{"id": "1", "filename": "../../etc/cron.d/job", "size": 1, "content": "https://example.atlassian.net/rest/api/3/attachment/content/1"},
                {"id": "2", "filename": "..\\..\\boot.ini", "size": 1, "content": "https://example.atlassian.net/rest/api/3/attachment/content/2"},
                {"id": "3", "filename": "..", "size": 1, "content": "https://example.atlassian.net/rest/api/3/attachment/content/3"}]
        session = FakeSession().add("GET", r"/attachment/content/\d+$", FakeResponse(200, "x"))
        with tempfile.TemporaryDirectory() as tmp:
            notes = attachments.download_all(make_client(session), "PLAT-1", evil, tmp)
            inside = sorted(os.listdir(os.path.join(tmp, "PLAT-1")))
            self.assertEqual(os.listdir(tmp), ["PLAT-1"])
        self.assertEqual(inside, ["1-job", "2-boot.ini", "3-attachment"])
        self.assertTrue(all(note.startswith(tmp) for note in notes.values()))

    def test_safe_filename(self):
        self.assertEqual(attachments.safe_filename("report final.pdf"), "report final.pdf")
        self.assertEqual(attachments.safe_filename("a/b/c.txt"), "c.txt")
        self.assertEqual(attachments.safe_filename("tab\there.txt"), "tab_here.txt")
        self.assertEqual(attachments.safe_filename(""), "attachment")

    def test_size_limit(self):
        session = FakeSession().add("GET", r"/attachment/content/\d+$", FakeResponse(200, "x"))
        with tempfile.TemporaryDirectory() as tmp:
            notes = attachments.download_all(make_client(session), "PLAT-101", attached(), tmp, max_bytes=20000)
        self.assertTrue(notes["30001"].startswith("skipped"))
        self.assertTrue(notes["30002"].endswith("30002-spinner.png"))
        self.assertEqual(len(session.calls), 1)

    def test_failed_download_does_not_stop_the_rest(self):
        session = FakeSession()
        session.add("GET", r"/content/30001$", FakeResponse(403, "forbidden"))
        session.add("GET", r"/content/30002$", FakeResponse(200, "png"))
        with tempfile.TemporaryDirectory() as tmp:
            notes = attachments.download_all(make_client(session), "PLAT-101", attached(), tmp)
        self.assertEqual(notes["30001"], "failed: HTTP 403")
        self.assertTrue(notes["30002"].endswith("spinner.png"))


if __name__ == "__main__":
    unittest.main()
