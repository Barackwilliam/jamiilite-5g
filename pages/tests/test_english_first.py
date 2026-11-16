from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Owner


@override_settings(LANGUAGE_CODE="en")
class EnglishFirstTests(TestCase):
    """Kama mfumo halisi: Kiingereza kwanza, Kiswahili kwa anayekichagua."""

    def test_home_is_english_at_the_clean_address(self):
        html = self.client.get("/").content.decode()
        self.assertIn('<html lang="en">', html)
        self.assertIn('<link rel="canonical" href="http://testserver/">', html)
        self.assertIn('hreflang="en" href="http://testserver/"', html)
        self.assertIn('hreflang="sw" href="http://testserver/?lang=sw"', html)

    def test_swahili_when_chosen_and_remembered(self):
        html = self.client.get("/?lang=sw").content.decode()
        self.assertIn('<html lang="sw">', html)
        # Maandishi yenyewe yawe ya Kiswahili, si Kiingereza chenye lang="sw".
        self.assertIn("WiFi yako", html)
        self.assertNotIn("Your WiFi", html)
        self.assertIn('<html lang="sw">', self.client.get(reverse("pages:mahitaji")).content.decode())


class SwahiliCatalogTests(TestCase):
    """Kila neno lenye tafsiri ya Kiingereza liwe pia kwenye faili la Kiswahili (msgstr = msgid)."""

    def test_swahili_catalog_covers_every_message(self):
        import gettext
        from pathlib import Path

        from django.conf import settings

        base = Path(settings.BASE_DIR) / "locale"
        for name in ("django", "djangojs"):
            with open(base / "en/LC_MESSAGES" / f"{name}.mo", "rb") as f:
                en = gettext.GNUTranslations(f)._catalog
            with open(base / "sw/LC_MESSAGES" / f"{name}.mo", "rb") as f:
                sw = gettext.GNUTranslations(f)._catalog
            missing = [k for k in en if k and k not in sw]
            self.assertEqual(missing, [], f"{name}: maneno haya hayapo kwenye locale/sw")
