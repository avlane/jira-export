import json
import os
import tempfile
import unittest

from jiraexport import incremental


class StateFileTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state.json")
            self.assertIsNone(incremental.load(path))
            incremental.save(path, incremental.fresh("project = PLAT"))
            self.assertEqual(incremental.load(path)["jql"], "project = PLAT")
            self.assertEqual(os.listdir(tmp), ["state.json"])

    def test_broken_files_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{not json")
            with self.assertRaises(incremental.StateError):
                incremental.load(path)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"version": 99}, handle)
            with self.assertRaises(incremental.StateError):
                incremental.load(path)

    def test_jql_since(self):
        got = incremental.jql_since("project = PLAT", "2021-02-12T08:30:45.000+00:00")
        self.assertEqual(got, '(project = PLAT) AND updated >= "2021-02-12 08:30"')

    def test_since_is_converted_to_the_users_time_zone(self):
        since = "2025-01-15T14:05:30.000+00:00"
        self.assertEqual(incremental.jql_since("project = A", since, "Europe/Dublin"), '(project = A) AND updated >= "2025-01-15 14:05"')
        self.assertEqual(incremental.jql_since("project = A", since, "Australia/Sydney"), '(project = A) AND updated >= "2025-01-16 01:05"')
        self.assertEqual(incremental.jql_since("project = A", "2025-07-15T14:05:00.000+00:00", "Europe/Dublin"), '(project = A) AND updated >= "2025-07-15 15:05"')

    def test_unknown_zone_falls_back_to_the_recorded_offset(self):
        with self.assertLogs("jiraexport", level="WARNING"):
            got = incremental.jql_since("project = A", "2025-01-15T14:05:30.000+01:00", "Mars/Olympus")
        self.assertEqual(got, '(project = A) AND updated >= "2025-01-15 14:05"')

    def test_order_by_stays_last_and_or_is_grouped(self):
        since = "2021-02-12T08:30:45.000+00:00"
        self.assertEqual(incremental.jql_since("project = PLAT OR project = OPS ORDER BY updated DESC, key", since),
                         '(project = PLAT OR project = OPS) AND updated >= "2021-02-12 08:30" ORDER BY updated DESC, key')
        self.assertEqual(incremental.jql_since("order by created", since), 'updated >= "2021-02-12 08:30" order by created')

    def test_order_by_inside_a_string_is_not_a_clause(self):
        where, order = incremental.split_order_by('summary ~ "order by hand" AND reorder_by = 1 ORDER BY key')
        self.assertEqual(where, 'summary ~ "order by hand" AND reorder_by = 1')
        self.assertEqual(order, "ORDER BY key")
        self.assertEqual(incremental.split_order_by("project = A"), ("project = A", ""))

    def test_advance_moves_to_the_latest_update(self):
        issues = [{"key": "A-1", "fields": {"updated": "2021-02-03T10:00:00.000+0000"}}, {"key": "A-2", "fields": {"updated": "2021-02-05T11:30:00.000+0000"}}]
        state = incremental.advance(incremental.fresh("q"), issues, 2)
        self.assertEqual(state["last_updated"], "2021-02-05T11:30:00.000+00:00")
        self.assertEqual((state["runs"], state["exported"]), (1, 2))
        again = incremental.advance(state, [{"key": "A-3", "fields": {"updated": "2021-02-01T00:00:00.000+0000"}}], 1)
        self.assertEqual(again["last_updated"], "2021-02-05T11:30:00.000+00:00")
        self.assertEqual((again["runs"], again["exported"]), (2, 3))

    def test_only_the_last_minute_is_remembered(self):
        issues = [{"key": "A-1", "fields": {"updated": "2021-02-03T10:00:10.000+0000"}},
                  {"key": "A-2", "fields": {"updated": "2021-02-05T11:30:05.000+0000"}},
                  {"key": "A-3", "fields": {"updated": "2021-02-05T11:30:50.000+0000"}}]
        state = incremental.advance(incremental.fresh("q"), issues, 3)
        self.assertEqual(sorted(state["seen"]), ["A-2", "A-3"])
        self.assertTrue(incremental.already_exported(state, issues[1]))
        changed = {"key": "A-2", "fields": {"updated": "2021-02-05T11:30:59.000+0000"}}
        self.assertFalse(incremental.already_exported(state, changed))
        self.assertFalse(incremental.already_exported(state, issues[0]))

    def test_advance_with_nothing_new_keeps_the_marker(self):
        state = dict(incremental.fresh("q"), last_updated="2021-02-05T11:30:00.000+00:00")
        self.assertEqual(incremental.advance(state, [], 0)["last_updated"], "2021-02-05T11:30:00.000+00:00")


if __name__ == "__main__":
    unittest.main()
