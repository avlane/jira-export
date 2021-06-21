import unittest

from jiraexport import adf
from tests.helpers import load


def text(value):
    return {"type": "text", "text": value}


def para(*inline):
    return {"type": "paragraph", "content": list(inline)}


class AdfTests(unittest.TestCase):
    def test_empty_inputs(self):
        self.assertEqual(adf.to_text(None), "")
        self.assertEqual(adf.to_text({}), "")
        self.assertEqual(adf.to_text("already text"), "already text")

    def test_paragraphs_and_marks(self):
        doc = {"type": "doc", "version": 1, "content": [
            para(text("Hello "), {"type": "text", "text": "world", "marks": [{"type": "strong"}]}), para(text("Second"))]}
        self.assertEqual(adf.to_text(doc), "Hello world\nSecond")

    def test_hard_break_inside_a_paragraph(self):
        doc = {"type": "doc", "content": [para(text("one"), {"type": "hardBreak"}, text("two"))]}
        self.assertEqual(adf.to_text(doc), "one\ntwo")

    def test_lists(self):
        item = lambda value: {"type": "listItem", "content": [para(text(value))]}
        doc = {"type": "doc", "content": [
            {"type": "bulletList", "content": [item("a"), item("b")]},
            {"type": "orderedList", "attrs": {"order": 3}, "content": [item("c"), item("d")]}]}
        self.assertEqual(adf.to_text(doc), "- a\n- b\n3. c\n4. d")

    def test_nested_list(self):
        inner = {"type": "bulletList", "content": [{"type": "listItem", "content": [para(text("child"))]}]}
        outer = {"type": "bulletList", "content": [{"type": "listItem", "content": [para(text("parent")), inner]}]}
        self.assertEqual(adf.to_text({"type": "doc", "content": [outer]}), "- parent\n  - child")

    def test_unknown_blocks_keep_their_text(self):
        doc = {"type": "doc", "content": [{"type": "somethingNew", "content": [para(text("still here"))]}]}
        self.assertEqual(adf.to_text(doc), "still here")

    def test_recorded_description(self):
        description = load("issues.json")[0]["fields"]["description"]
        got = adf.to_text(description).splitlines()
        self.assertEqual(got[0], "Summary")
        self.assertIn("1. Open the login page", got)
        self.assertIn("- Not reproducible on staging", got)


if __name__ == "__main__":
    unittest.main()
