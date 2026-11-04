from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone, translation

from ui.templatetags.ui_tags import day_label, phones_display


class StatementTagsTests(SimpleTestCase):
    def test_phones_in_text_are_spaced(self):
        self.assertEqual(phones_display("Siku 1 · 255726172964"), "Siku 1 · 0726 172 964")
        self.assertEqual(phones_display("Wiki 1 · 0729205756"), "Wiki 1 · 0729 205 756")
        self.assertEqual(phones_display("Kumb 12345678901"), "Kumb 12345678901")

    def test_day_label(self):
        now = timezone.now()
        with translation.override("sw"):
            self.assertEqual(day_label(now), "Leo")
            self.assertEqual(day_label(now - timedelta(days=1)), "Jana")
        with translation.override("en"):
            self.assertEqual(day_label(now - timedelta(days=1)), "Yesterday")
        self.assertEqual(day_label(None), "")
