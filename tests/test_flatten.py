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

    def test_description_is_plain_text(self):
        description = self.rows["PLAT-101"]["description"]
        self.assertTrue(description.startswith("Summary\nUsers on the login page"))
        self.assertNotIn("{", description.splitlines()[0])
        self.assertEqual(self.rows["PLAT-102"]["description"], "As an auditor I can download the audit log as CSV.")

    def test_timestamps_use_iso_offsets(self):
        self.assertEqual(self.rows["PLAT-101"]["created"], "2021-02-03T10:15:22.123+00:00")
        self.assertEqual(flatten.normalise_timestamp("2021-02-03T10:15:22.123-0530"), "2021-02-03T10:15:22.123-05:30")
        self.assertEqual(flatten.normalise_timestamp("2021-02-03T10:15:22.123+00:00"), "2021-02-03T10:15:22.123+00:00")
        self.assertEqual(flatten.normalise_timestamp(None), "")

    def test_parent_and_subtasks(self):
        self.assertEqual(self.rows["PLAT-103"]["parent"], "PLAT-101")
        self.assertEqual(self.rows["PLAT-101"]["subtasks"], "PLAT-105")
        self.assertEqual(self.rows["PLAT-102"]["parent"], "")
        self.assertEqual(self.rows["PLAT-102"]["subtasks"], "")

    def test_custom_columns(self):
        from jiraexport.fieldmap import Field
        issue = load("issues.json")[0]
        row = flatten.flatten(issue, [Field("customfield_10016", "points"), Field("customfield_99999", "missing")])
        self.assertEqual(row["points"], "5")
        self.assertEqual(row["missing"], "")

    def test_render_value(self):
        render = flatten.render_value
        self.assertEqual(render(None), "")
        self.assertEqual(render(8.0), "8")
        self.assertEqual(render(2.5), "2.5")
        self.assertEqual(render(True), "true")
        self.assertEqual(render({"self": "x", "value": "High", "id": "10"}), "High")
        self.assertEqual(render({"name": "2.15", "id": "5"}), "2.15")

    def test_render_lists_users_cascades_and_rich_text(self):
        render = flatten.render_value
        self.assertEqual(render([{"value": "prod"}, {"value": "staging"}]), "prod, staging")
        self.assertEqual(render([]), "")
        self.assertEqual(render([{"id": 1, "name": "Sprint 41", "state": "closed", "boardId": 3}, {"id": 2, "name": "Sprint 42", "state": "active"}]),
                         "Sprint 41, Sprint 42")
        self.assertEqual(render({"accountId": "x", "displayName": "Carol Nguyen", "active": True}), "Carol Nguyen")
        self.assertEqual(render({"value": "Hardware", "child": {"value": "Laptop"}}), "Hardware / Laptop")
        self.assertEqual(render({"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "rich"}]}]}), "rich")
        self.assertEqual(render({"unexpected": [1, 2]}), '{"unexpected": [1, 2]}')

    def test_resolution(self):
        self.assertEqual(self.rows["PLAT-102"]["resolution"], "Done")

    def test_every_column_is_present(self):
        for row in self.rows.values():
            self.assertEqual(tuple(row), flatten.COLUMNS)


if __name__ == "__main__":
    unittest.main()
