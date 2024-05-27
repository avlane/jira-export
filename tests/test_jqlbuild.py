import unittest

from jiraexport import jqlbuild


class JqlBuildTests(unittest.TestCase):
    def test_raw_jql_alone_is_unchanged(self):
        self.assertEqual(jqlbuild.build("project = PLAT ORDER BY key"), "project = PLAT ORDER BY key")

    def test_filters(self):
        got = jqlbuild.build(projects=["PLAT", "OPS"], statuses=["In Progress"], updated_since="2024-03-01")
        self.assertEqual(got, 'project in ("PLAT", "OPS") AND status in ("In Progress") AND updated >= "2024-03-01"')

    def test_raw_jql_is_parenthesised_and_order_by_moves_to_the_end(self):
        got = jqlbuild.build("labels = a OR labels = b ORDER BY created DESC", projects=["PLAT"])
        self.assertEqual(got, '(labels = a OR labels = b) AND project in ("PLAT") ORDER BY created DESC')

    def test_only_order_by(self):
        self.assertEqual(jqlbuild.build("ORDER BY key"), "ORDER BY key")

    def test_quoting(self):
        self.assertEqual(jqlbuild.quote('say "hi" \\ bye'), '"say \\"hi\\" \\\\ bye"')

    def test_date_formats(self):
        self.assertIn("2024-03-01 09:30", jqlbuild.build(updated_since="2024-03-01 09:30"))
        for bad in ("yesterday", "2024/03/01", "-7d"):
            with self.assertRaises(jqlbuild.JqlError):
                jqlbuild.build(updated_since=bad)

    def test_nothing_to_search_for(self):
        with self.assertRaises(jqlbuild.JqlError):
            jqlbuild.build()


if __name__ == "__main__":
    unittest.main()
