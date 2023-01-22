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
        self.assertEqual(got, 'project = PLAT AND updated >= "2021-02-12 08:30"')

    def test_advance_moves_to_the_latest_update(self):
        issues = [{"fields": {"updated": "2021-02-03T10:00:00.000+0000"}}, {"fields": {"updated": "2021-02-05T11:30:00.000+0000"}}]
        state = incremental.advance(incremental.fresh("q"), issues, 2)
        self.assertEqual(state["last_updated"], "2021-02-05T11:30:00.000+00:00")
        self.assertEqual((state["runs"], state["exported"]), (1, 2))
        again = incremental.advance(state, [{"fields": {"updated": "2021-02-01T00:00:00.000+0000"}}], 1)
        self.assertEqual(again["last_updated"], "2021-02-05T11:30:00.000+00:00")
        self.assertEqual((again["runs"], again["exported"]), (2, 3))

    def test_advance_with_nothing_new_keeps_the_marker(self):
        state = dict(incremental.fresh("q"), last_updated="2021-02-05T11:30:00.000+00:00")
        self.assertEqual(incremental.advance(state, [], 0)["last_updated"], "2021-02-05T11:30:00.000+00:00")


if __name__ == "__main__":
    unittest.main()
