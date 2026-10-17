from django.test import TestCase, override_settings
from django.urls import reverse


class PublicPagesTests(TestCase):
    def test_pages_render(self):
        for name, text in [
            ("pages:home", "Uza WiFi yako kiotomatiki"),
            ("pages:mahitaji", "Una router gani sasa hivi?"),
            ("pages:mwongozo", "Bandika mstari wako wa JamiiLite"),
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
        self.assertNotContains(response, "kamisheni")
