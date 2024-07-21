import csv
import io
import json
import unittest

from jiraexport import writers

ROWS = [{"key": "A-1", "n": 1, "extra": "ignored"}, {"key": "A-2", "n": 2}]


def write(fmt, rows=ROWS):
    stream = io.StringIO()
    sink = writers.open_sink(fmt, stream, ("key", "n"))
    for row in rows:
        sink.write(row)
    sink.close()
    return stream.getvalue(), sink.count


class SinkTests(unittest.TestCase):
    def test_csv(self):
        text, count = write("csv")
        self.assertEqual(list(csv.reader(io.StringIO(text))), [["key", "n"], ["A-1", "1"], ["A-2", "2"]])
        self.assertEqual(count, 2)

    def test_jsonl_has_one_object_per_line(self):
        text, count = write("jsonl")
        self.assertEqual([json.loads(line)["key"] for line in text.splitlines()], ["A-1", "A-2"])
        self.assertEqual(count, 2)

    def test_json_is_a_valid_array(self):
        text, _ = write("json")
        self.assertEqual([r["key"] for r in json.loads(text)], ["A-1", "A-2"])

    def test_empty_json_array(self):
        text, count = write("json", [])
        self.assertEqual(json.loads(text), [])
        self.assertEqual(count, 0)

    def test_non_ascii_is_kept(self):
        text, _ = write("jsonl", [{"key": "caf\u00e9"}])
        self.assertIn("caf\u00e9", text)

    def test_formulas_are_defused_in_csv(self):
        rows = [{"key": '=HYPERLINK("http://evil.example","x")', "n": "+1+1"}, {"key": "@SUM(A1)", "n": "-cmd|calc"},
                {"key": "- a list item", "n": "-12.5"}, {"key": "plain", "n": ""}]
        text, _ = write("csv", rows)
        got = list(csv.reader(io.StringIO(text)))[1:]
        self.assertEqual(got, [["'=HYPERLINK(\"http://evil.example\",\"x\")", "'+1+1"], ["'@SUM(A1)", "'-cmd|calc"],
                               ["- a list item", "-12.5"], ["plain", ""]])

    def test_escaping_can_be_turned_off_and_does_not_touch_json(self):
        stream = io.StringIO()
        sink = writers.open_sink("csv", stream, ("key",), True, False)
        sink.write({"key": "=1+1"})
        self.assertEqual(stream.getvalue().splitlines()[1], "=1+1")
        text, _ = write("jsonl", [{"key": "=1+1", "n": "x"}])
        self.assertEqual(json.loads(text)["key"], "=1+1")

    def test_unknown_format(self):
        with self.assertRaises(ValueError):
            writers.open_sink("xml", io.StringIO(), ())

    def test_write_csv_helper(self):
        stream = io.StringIO()
        self.assertEqual(writers.write_csv(iter(ROWS), ("key",), stream), 2)


if __name__ == "__main__":
    unittest.main()
