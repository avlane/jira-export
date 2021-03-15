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


if __name__ == "__main__":
    unittest.main()
