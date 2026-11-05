from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone, translation

from ui.templatetags.ui_tags import day_label, flag, phone_display, phones_display


class StatementTagsTests(SimpleTestCase):
    def test_phones_in_text_are_spaced(self):
        self.assertEqual(phones_display("Siku 1 · 255726172964"), "Siku 1 · 0726 172 964")
        self.assertEqual(phones_display("Wiki 1 · 0729205756"), "Wiki 1 · 0729 205 756")
        self.assertEqual(phones_display("Kumb 12345678901"), "Kumb 12345678901")

    def test_phone_display_accepts_local_numbers(self):
        self.assertEqual(phone_display("255712345678"), "0712 345 678")
        self.assertEqual(phone_display("0712345678"), "0712 345 678")
        self.assertEqual(phone_display("bosi"), "bosi")

    def test_day_label(self):
        now = timezone.now()
        with translation.override("sw"):
            self.assertEqual(day_label(now), "Leo")
            self.assertEqual(day_label(now - timedelta(days=1)), "Jana")
        with translation.override("en"):
            self.assertEqual(day_label(now - timedelta(days=1)), "Yesterday")
        self.assertEqual(day_label(None), "")


class FlagTests(SimpleTestCase):
    def test_flags_are_svg_not_emoji(self):
        # Emoji za bendera zinaonekana kama "TZ" kwenye Windows, kwa hiyo tunatumia SVG.
        self.assertTrue(flag("tz").startswith('<svg class="flag"'))
        self.assertIn('width="21" height="14"', flag("tz"))
        self.assertTrue(flag("gb").startswith('<svg class="flag"'))
        self.assertEqual(flag("xx"), "")
