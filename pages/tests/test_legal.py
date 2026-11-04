from django.test import TestCase, override_settings
from django.urls import reverse

from core.tests.factories import make_owner, make_router


@override_settings(JAMIILITE_MONTHLY_FEE=10000, JAMIILITE_TRIAL_DAYS=14, JAMIILITE_MIN_WITHDRAWAL=1000)
class LegalPagesTests(TestCase):
    def test_terms_in_swahili_show_current_fees_and_refunds(self):
        response = self.client.get(reverse("pages:masharti") + "?lang=sw")
        self.assertContains(response, "Masharti ya Huduma")
        self.assertContains(response, "siku 14 za majaribio bure")
        self.assertContains(response, "Tsh 10,000 kwa mwezi")
        self.assertContains(response, "Kiasi cha chini ni Tsh 1,000")
        self.assertContains(response, 'id="kurudisha-pesa"')

    def test_terms_in_english(self):
        response = self.client.get(reverse("pages:masharti") + "?lang=en")
        self.assertContains(response, "Terms of Service")
        self.assertContains(response, "14-day free trial")
        self.assertContains(response, "<title>Terms of Service · JamiiLite 5G</title>", html=False)

    def test_privacy_in_both_languages(self):
        self.assertContains(self.client.get(reverse("pages:faragha") + "?lang=sw"), "Sera ya Faragha")
        self.assertContains(self.client.get(reverse("pages:faragha") + "?lang=en"), "Personal Data Protection Act, 2022")

    @override_settings(JAMIILITE_CONTACT_EMAIL="msaada@example.com")
    def test_contact_email_is_shown_when_set(self):
        self.assertContains(self.client.get(reverse("pages:faragha")), 'href="mailto:msaada@example.com"')

    def test_pages_are_linked_and_listed(self):
        terms, privacy = reverse("pages:masharti"), reverse("pages:faragha")
        for page in (reverse("pages:home"), reverse("dashboard:signup")):
            response = self.client.get(page)
            self.assertContains(response, f'href="{terms}"')
            self.assertContains(response, f'href="{privacy}"')
        sitemap = self.client.get(reverse("sitemap")).content.decode()
        self.assertIn(terms, sitemap)
        self.assertIn(privacy, sitemap)

    def test_customer_payment_page_links_them(self):
        make_router(make_owner(), slug="neema")
        response = self.client.get(reverse("portal:home", args=["neema"]))
        self.assertContains(response, f'href="{reverse("pages:faragha")}"')
