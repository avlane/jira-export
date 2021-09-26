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

    def test_links_show_their_target(self):
        link = {"type": "text", "text": "runbook", "marks": [{"type": "link", "attrs": {"href": "https://wiki.example.com/r"}}]}
        bare = {"type": "text", "text": "https://x.example.com", "marks": [{"type": "link", "attrs": {"href": "https://x.example.com"}}]}
        self.assertEqual(adf.to_text({"type": "doc", "content": [para(link, text(" and "), bare)]}),
                         "runbook (https://wiki.example.com/r) and https://x.example.com")

    def test_code_block_and_quote(self):
        doc = {"type": "doc", "content": [
            {"type": "codeBlock", "attrs": {"language": "sql"}, "content": [text("SELECT 1;\nSELECT 2;")]},
            {"type": "blockquote", "content": [para(text("quoted"))]}]}
        self.assertEqual(adf.to_text(doc), "    SELECT 1;\n    SELECT 2;\n> quoted")

    def test_panel(self):
        doc = {"type": "doc", "content": [{"type": "panel", "attrs": {"panelType": "warning"}, "content": [para(text("careful"))]}]}
        self.assertEqual(adf.to_text(doc), "[warning] careful")

    def test_table(self):
        cell = lambda kind, value: {"type": kind, "attrs": {}, "content": [para(text(value))]}
        row = lambda kind, *values: {"type": "tableRow", "content": [cell(kind, v) for v in values]}
        doc = {"type": "doc", "content": [{"type": "table", "content": [row("tableHeader", "Env", "Owner"), row("tableCell", "prod", "ops")]}]}
        self.assertEqual(adf.to_text(doc), "Env | Owner\nprod | ops")

    def test_inline_extras(self):
        doc = {"type": "doc", "content": [para(
            {"type": "mention", "attrs": {"id": "x", "text": "@Alice"}}, text(" "), {"type": "emoji", "attrs": {"shortName": ":tada:", "text": "\U0001F389"}},
            text(" "), {"type": "status", "attrs": {"text": "READY", "color": "green"}}, text(" "),
            {"type": "date", "attrs": {"timestamp": "1612396800000"}}, text(" "),
            {"type": "inlineCard", "attrs": {"url": "https://example.atlassian.net/browse/PLAT-9"}})]}
        self.assertEqual(adf.to_text(doc), "@Alice \U0001F389 [READY] 2021-02-04 https://example.atlassian.net/browse/PLAT-9")

    def test_media_placeholder(self):
        doc = {"type": "doc", "content": [{"type": "mediaSingle", "content": [{"type": "media", "attrs": {"id": "abc", "type": "file", "alt": "spinner.png"}}]}]}
        self.assertEqual(adf.to_text(doc), "[media: spinner.png]")

    def test_expand_title(self):
        doc = {"type": "doc", "content": [{"type": "expand", "attrs": {"title": "Details"}, "content": [para(text("hidden text"))]}]}
        self.assertEqual(adf.to_text(doc), "Details\nhidden text")

    def test_recorded_description(self):
        description = load("issues.json")[0]["fields"]["description"]
        got = adf.to_text(description).splitlines()
        self.assertEqual(got[0], "Summary")
        self.assertIn("1. Open the login page", got)
        self.assertIn("- Not reproducible on staging", got)
        self.assertIn("    curl -s -o /dev/null -w '%{time_total}' https://app.example.com/login", got)
        self.assertIn("Users on the login page see a spinner for 30 seconds and then a timeout. Reported by @Bob Okafor.", got)
        self.assertEqual(got[-1], "See the runbook (https://wiki.example.com/runbooks/login) for rollback steps.")


if __name__ == "__main__":
    unittest.main()
