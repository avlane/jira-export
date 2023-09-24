import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from jiraexport import __version__, manifest


class ManifestTests(unittest.TestCase):
    def test_build_and_write(self):
        start = datetime(2023, 9, 24, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2023, 9, 24, 10, 0, 42, 500000, tzinfo=timezone.utc)
        data = manifest.build("project = PLAT", "csv", start, end, {"/tmp/x/issues.csv": 3, "/tmp/x/issues-comments.csv": 2})
        self.assertEqual(data["version"], __version__)
        self.assertEqual(data["started"], "2023-09-24T10:00:00+00:00")
        self.assertEqual(data["finished"], "2023-09-24T10:00:42+00:00")
        self.assertEqual(data["files"], [{"path": "issues.csv", "rows": 3}, {"path": "issues-comments.csv", "rows": 2}])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "m.json")
            manifest.write(path, data)
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), data)


if __name__ == "__main__":
    unittest.main()
