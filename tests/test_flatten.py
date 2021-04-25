import unittest

from jiraexport import flatten
from tests.helpers import load


class FlattenTests(unittest.TestCase):
    def setUp(self):
        self.rows = {i["key"]: flatten.flatten(i) for i in load("issues.json")}

    def test_core_fields(self):
        row = self.rows["PLAT-101"]
        self.assertEqual(row["summary"], "Login page times out")
        self.assertEqual(row["issuetype"], "Bug")
        self.assertEqual(row["status"], "In Progress")
        self.assertEqual(row["priority"], "High")
        self.assertEqual(row["assignee"], "Alice Moreau")
        self.assertEqual(row["reporter"], "Bob Okafor")
        self.assertEqual(row["project"], "PLAT")

    def test_lists_are_joined(self):
        row = self.rows["PLAT-101"]
        self.assertEqual(row["labels"], "auth, p1")
        self.assertEqual(row["components"], "Web")
        self.assertEqual(row["fixVersions"], "2.15")
        self.assertEqual(self.rows["PLAT-102"]["components"], "API, Web")

    def test_missing_values_become_empty_strings(self):
        row = self.rows["PLAT-103"]
        self.assertEqual(row["assignee"], "")
        self.assertEqual(row["resolution"], "")
        self.assertEqual(row["description"], "")
        self.assertEqual(row["labels"], "")

    def test_resolution(self):
        self.assertEqual(self.rows["PLAT-102"]["resolution"], "Done")

    def test_every_column_is_present(self):
        for row in self.rows.values():
            self.assertEqual(tuple(row), flatten.COLUMNS)


if __name__ == "__main__":
    unittest.main()
