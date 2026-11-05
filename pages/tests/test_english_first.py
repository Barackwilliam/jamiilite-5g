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
        self.assertIn('<html lang="sw">', self.client.get("/?lang=sw").content.decode())
        self.assertIn('<html lang="sw">', self.client.get(reverse("pages:mahitaji")).content.decode())

    def test_clean_address_stays_english_whatever_the_browser(self):
        html = self.client.get("/", HTTP_ACCEPT_LANGUAGE="sw").content.decode()
        self.assertIn('<html lang="en">', html)

    def test_language_switch_shows_english_first(self):
        html = self.client.get("/").content.decode()
        self.assertLess(html.index('value="en"'), html.index('value="sw"'))

    def test_sitemap_lists_english_at_clean_address(self):
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("<loc>http://testserver/mahitaji/</loc>", body)
        self.assertIn("<loc>http://testserver/mahitaji/?lang=sw</loc>", body)
        self.assertNotIn("?lang=en", body)

    def test_new_owner_defaults_to_english(self):
        self.client.post(reverse("dashboard:signup"), {
            "business_name": "Test WiFi", "phone": "0712345670",
            "password1": "Strong-pass-9081", "password2": "Strong-pass-9081",
        })
        self.assertEqual(Owner.objects.get(business_name="Test WiFi").language, "en")
