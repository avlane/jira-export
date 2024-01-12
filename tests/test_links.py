import unittest

from jiraexport import links
from tests.helpers import load


class LinkTests(unittest.TestCase):
    def test_outward_and_inward_links(self):
        issues = {i["key"]: i for i in load("issues.json")}
        out = links.rows("PLAT-101", issues["PLAT-101"]["fields"]["issuelinks"])
        self.assertEqual([(r["relation"], r["other"], r["other_status"]) for r in out], [("blocks", "PLAT-103", "To Do")])
        back = links.rows("PLAT-103", issues["PLAT-103"]["fields"]["issuelinks"])
        self.assertEqual([(r["direction"], r["relation"], r["other"], r["other_summary"]) for r in back],
                         [("inward", "is blocked by", "PLAT-101", "Login page times out")])

    def test_no_links(self):
        self.assertEqual(links.rows("PLAT-102", load("issues.json")[1]["fields"]["issuelinks"]), [])
        self.assertEqual(links.rows("X-1", None), [])

    def test_unknown_link_shapes_are_skipped(self):
        self.assertEqual(links.rows("X-1", [{"id": "1", "type": {"name": "Odd"}}]), [])


if __name__ == "__main__":
    unittest.main()
