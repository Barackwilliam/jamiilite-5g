from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from core.models import Owner
from core.tests.factories import make_owner, make_router


class LanguageTests(TestCase):
    def test_signup_saves_chosen_language(self):
        response = self.client.post(reverse("dashboard:signup"), {
            "business_name": "Neema WiFi", "phone": "0712345678", "language": "en",
            "password1": "Sinza-wifi-2026", "password2": "Sinza-wifi-2026",
        })
        owner = Owner.objects.get()
        self.assertEqual(owner.language, "en")
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "en")
        home = self.client.get(reverse("dashboard:home"))
        self.assertContains(home, "Overview")
        self.assertContains(home, '<html lang="en">')

    def test_signup_page_offers_both_languages(self):
        response = self.client.get(reverse("dashboard:signup"))
        self.assertContains(response, 'value="sw"')
        self.assertContains(response, 'value="en"')

    def test_browser_language_used_before_login(self):
        response = self.client.get(reverse("dashboard:login"), HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")
        self.assertContains(response, "Log in to your dashboard")
        self.assertContains(self.client.get(reverse("dashboard:login")), "Ingia kwenye dashboard yako")

    def test_owner_choice_beats_browser(self):
        owner = make_owner(language="sw")
        self.client.force_login(owner.user)
        response = self.client.get(reverse("dashboard:home"), HTTP_ACCEPT_LANGUAGE="en")
        self.assertContains(response, "Muhtasari")

    def test_switch_updates_owner_and_cookie(self):
        owner = make_owner()
        self.client.force_login(owner.user)
        response = self.client.post(reverse("ui:set_language"), {"language": "en", "next": reverse("dashboard:routers")})
        self.assertRedirects(response, reverse("dashboard:routers"))
        owner.refresh_from_db()
        self.assertEqual(owner.language, "en")
        self.assertContains(self.client.get(reverse("dashboard:routers")), "Your locations")

    def test_switch_ignores_unknown_language_and_external_next(self):
        owner = make_owner()
        self.client.force_login(owner.user)
        response = self.client.post(reverse("ui:set_language"), {"language": "fr", "next": "https://evil.example/"})
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        owner.refresh_from_db()
        self.assertEqual(owner.language, "sw")

    def test_settings_form_changes_language(self):
        owner = make_owner()
        self.client.force_login(owner.user)
        self.client.post(reverse("dashboard:settings"), {"business_name": "Neema", "phone": "0712345678", "language": "en"})
        owner.refresh_from_db()
        self.assertEqual(owner.language, "en")

    def test_portal_follows_customer_phone_and_translates_router_errors(self):
        router = make_router(make_owner())
        url = reverse("portal:home", args=[router.slug])
        response = self.client.get(url, {"error": "Vocha si sahihi"}, HTTP_ACCEPT_LANGUAGE="en")
        self.assertContains(response, "Buy a package")
        self.assertContains(response, "Invalid voucher")
        self.assertContains(self.client.get(url, {"error": "Vocha si sahihi"}), "Nunua kifurushi")

    def test_english_strings_in_python_code(self):
        owner = make_owner(language="en")
        self.client.force_login(owner.user)
        response = self.client.post(reverse("dashboard:routers"), {"name": "Main Shop", "location": "", "wifi_name": ""}, follow=True)
        self.assertContains(response, "Main Shop has been added.")

    def test_javascript_catalog(self):
        response = self.client.get(reverse("javascript-catalog"), HTTP_ACCEPT_LANGUAGE="en")
        self.assertContains(response, "Show a demo")
