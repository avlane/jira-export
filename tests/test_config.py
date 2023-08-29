import unittest

from jiraexport import config

GOOD = {"JIRA_URL": "https://example.atlassian.net/", "JIRA_EMAIL": "ops@example.com", "JIRA_API_TOKEN": "tok"}


class ConfigTests(unittest.TestCase):
    def test_reads_and_normalises(self):
        self.assertEqual(config.from_env(GOOD), ("https://example.atlassian.net", "ops@example.com", "tok"))

    def test_names_missing_variables(self):
        with self.assertRaises(config.ConfigError) as ctx:
            config.from_env({})
        for name in ("JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
            self.assertIn(name, str(ctx.exception))

    def test_requires_https(self):
        with self.assertRaises(config.ConfigError):
            config.from_env(dict(GOOD, JIRA_URL="http://example.atlassian.net"))


class TuningTests(unittest.TestCase):
    def test_defaults_and_overrides(self):
        self.assertEqual(config.tuning({}), {"timeout": 60, "max_retries": 5})
        self.assertEqual(config.tuning({"JIRA_TIMEOUT": "20", "JIRA_MAX_RETRIES": "0"}), {"timeout": 20, "max_retries": 0})

    def test_rejects_junk(self):
        for bad in ({"JIRA_TIMEOUT": "soon"}, {"JIRA_MAX_RETRIES": "-1"}):
            with self.assertRaises(config.ConfigError):
                config.tuning(bad)


if __name__ == "__main__":
    unittest.main()
