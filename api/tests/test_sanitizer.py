"""Unit tests for the sanitizer — XSS prevention, length limits, tag/color/emoji
normalization. The sanitizer had no tests, so the export XSS (#376) went undetected."""

import sys
import types
import unittest

if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from services.sanitizer import (
    MAX_CONTENT_LENGTH,
    MAX_TITLE_LENGTH,
    sanitize_color,
    sanitize_content,
    sanitize_emoji,
    sanitize_html,
    sanitize_tag,
    sanitize_title,
)


class HtmlSanitizerTest(unittest.TestCase):
    def test_strips_script_tags(self):
        out = sanitize_html('<p>hi</p><script>alert(1)</script>')
        self.assertNotIn("<script>", out.lower())
        self.assertIn("hi", out)

    def test_strips_event_handlers(self):
        out = sanitize_html('<a href="#" onclick="steal()">x</a>')
        self.assertNotIn("onclick", out.lower())

    def test_preserves_safe_tags(self):
        out = sanitize_html("<strong>bold</strong> and <em>italic</em>")
        self.assertIn("<strong>", out)
        self.assertIn("<em>", out)


class TitleSanitizerTest(unittest.TestCase):
    def test_strips_and_validates(self):
        self.assertEqual(sanitize_title("  Hello  "), "Hello")

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            sanitize_title("   ")

    def test_rejects_too_long(self):
        with self.assertRaises(ValueError):
            sanitize_title("x" * (MAX_TITLE_LENGTH + 1))

    def test_strips_xss_from_title(self):
        out = sanitize_title('<script>alert(1)</script>Title')
        self.assertNotIn("<script>", out.lower())


class ContentSanitizerTest(unittest.TestCase):
    def test_truncates_overlong_content(self):
        long = "a" * (MAX_CONTENT_LENGTH + 100)
        out = sanitize_content(long)
        self.assertEqual(len(out), MAX_CONTENT_LENGTH)

    def test_empty_content_passes(self):
        self.assertEqual(sanitize_content(""), "")


class TagSanitizerTest(unittest.TestCase):
    def test_lowercases_and_strips(self):
        self.assertEqual(sanitize_tag("  MyTag  "), "mytag")

    def test_removes_special_chars(self):
        self.assertEqual(sanitize_tag("tag<script>"), "tagscript")

    def test_rejects_bare_hex_color_codes(self):
        # 6-char hex codes are color values misused as tag names (#268).
        self.assertEqual(sanitize_tag("ef4444"), "")

    def test_allows_short_hex_like_tags(self):
        # 3-char codes are legitimate short tags.
        self.assertEqual(sanitize_tag("abc"), "abc")


class ColorEmojiSanitizerTest(unittest.TestCase):
    def test_valid_color_passes(self):
        self.assertEqual(sanitize_color("#c8a96e"), "#c8a96e")

    def test_invalid_color_falls_back(self):
        self.assertEqual(sanitize_color("javascript:alert(1)"), "#888888")
        self.assertEqual(sanitize_color("red"), "#888888")

    def test_emoji_limited_length(self):
        self.assertEqual(sanitize_emoji("a" * 50), "a" * 20)

    def test_emoji_default_when_empty(self):
        self.assertEqual(sanitize_emoji(""), "🔴")


if __name__ == "__main__":
    unittest.main()
