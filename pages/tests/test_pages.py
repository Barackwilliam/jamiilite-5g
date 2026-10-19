from django.test import TestCase, override_settings
from django.urls import reverse


class PublicPagesTests(TestCase):
    def test_pages_render(self):
        for name, text in [
            ("pages:home", "Uza WiFi yako kiotomatiki"),
            ("pages:mahitaji", "Una router gani sasa hivi?"),
            ("pages:mwongozo", "Weka msimbo wa usanidi wa JamiiLite"),
        ]:
            with self.subTest(name):
                self.assertContains(self.client.get(reverse(name)), text)

    @override_settings(JAMIILITE_WHATSAPP_NUMBER="255712345678")
    def test_whatsapp_button_uses_configured_number(self):
        response = self.client.get(reverse("pages:home"))
        self.assertContains(response, "https://wa.me/255712345678?text=")

    @override_settings(JAMIILITE_WHATSAPP_NUMBER="")
    def test_without_whatsapp_number_cta_points_to_requirements(self):
        response = self.client.get(reverse("pages:home"))
        self.assertNotContains(response, "wa.me")
        self.assertContains(response, f'href="{reverse("pages:mahitaji")}"')

    @override_settings(JAMIILITE_MONTHLY_FEE=10000, JAMIILITE_TRIAL_DAYS=14)
    def test_pricing_uses_monthly_fee_and_trial(self):
        response = self.client.get(reverse("pages:home"))
        self.assertContains(response, "Tsh 10,000<span>/mwezi</span>")
        self.assertContains(response, "Siku 14 za majaribio bure")
        self.assertContains(response, "vifurushi <strong>20</strong> tu")
        self.assertContains(response, "bila kamisheni")


class LandingLanguageTests(TestCase):
    def test_landing_has_simulator_and_language_switch(self):
        response = self.client.get(reverse("pages:home"))
        self.assertContains(response, "data-sim")
        self.assertContains(response, "data-scene")
        self.assertContains(response, 'name="language" value="en"')

    def test_public_pages_in_english(self):
        for name, text in [
            ("pages:home", "Turn your WiFi into a"),
            ("pages:mahitaji", "Which router do you have right now?"),
            ("pages:mwongozo", "Connect your router in 7 steps"),
        ]:
            with self.subTest(name):
                response = self.client.get(reverse(name), HTTP_ACCEPT_LANGUAGE="en")
                self.assertContains(response, text)
                self.assertContains(response, '<html lang="en">')

    def test_landing_has_packet_journey_and_tabs(self):
        response = self.client.get(reverse("pages:home"))
        self.assertContains(response, "data-journey")
        self.assertContains(response, 'role="tablist"')
        self.assertContains(response, "Access-Request")
        self.assertNotContains(response, "si data halisi")

    def test_landing_scripts_are_embedded_without_extra_requests(self):
        response = self.client.get(reverse("pages:home"), HTTP_ACCEPT_LANGUAGE="en")
        self.assertContains(response, 'id="landing-i18n"')
        self.assertContains(response, "1 hour")
        self.assertNotContains(response, reverse("javascript-catalog"))
