import unittest

from jiraexport import fieldmap
from jiraexport.client import JiraClient
from tests.helpers import FakeSession, load


def make_client():
    session = FakeSession().add("GET", r"/rest/api/3/field$", load("fields.json"))
    return JiraClient("https://example.atlassian.net", session=session), session


class FieldMapTests(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(fieldmap.slug("Story point estimate"), "story_point_estimate")
        self.assertEqual(fieldmap.slug("Component/s (legacy)"), "component_s_legacy")

    def test_parse_spec(self):
        self.assertEqual(fieldmap.parse_spec("customfield_10016=points"), ("customfield_10016", "points"))
        self.assertEqual(fieldmap.parse_spec("Sprint"), ("Sprint", ""))

    def test_resolves_ids_and_names(self):
        client, session = make_client()
        got = fieldmap.resolve(client, ["customfield_10016=points", "sprint", "Customer Impact"])
        self.assertEqual(got, [("customfield_10016", "points"), ("customfield_10020", "sprint"), ("customfield_10030", "customer_impact")])
        self.assertEqual(len(session.calls), 1)

    def test_no_specs_means_no_request(self):
        client, session = make_client()
        self.assertEqual(fieldmap.resolve(client, []), [])
        self.assertEqual(session.calls, [])

    def test_unknown_field(self):
        client, _ = make_client()
        with self.assertRaises(fieldmap.FieldError) as ctx:
            fieldmap.resolve(client, ["Nope"])
        self.assertIn("'Nope'", str(ctx.exception))

    def test_column_clash(self):
        client, _ = make_client()
        with self.assertRaises(fieldmap.FieldError):
            fieldmap.resolve(client, ["customfield_10016=summary"])
        with self.assertRaises(fieldmap.FieldError):
            fieldmap.resolve(client, ["Sprint=x", "customfield_10030=x"])


if __name__ == "__main__":
    unittest.main()
