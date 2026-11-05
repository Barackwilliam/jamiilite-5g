from django.test import TestCase, override_settings
from django.urls import reverse

from core.tests.factories import make_owner, make_package, make_router
from ui.templatetags.ui_tags import join_words


class PaymentMethodsTests(TestCase):
    def setUp(self):
        owner = make_owner()
        self.router = make_router(owner)
        make_package(owner)

    def test_portal_lists_only_the_accepted_methods(self):
        html = self.client.get(reverse("portal:home", args=[self.router.slug])).content.decode()
        for method in ("Airtel Money", "Mixx by Yas", "Visa", "American Express"):
            self.assertIn(f"<li>{method}</li>", html)
        self.assertNotIn("M-Pesa", html)
        self.assertNotIn("HaloPesa", html)

    @override_settings(JAMIILITE_PAYMENT_METHODS=["M-Pesa", "Airtel Money"])
    def test_methods_follow_the_setting(self):
        html = self.client.get(reverse("portal:home", args=[self.router.slug])).content.decode()
        self.assertIn("<li>M-Pesa</li>", html)
        self.assertNotIn("Mixx by Yas", html)
        terms = self.client.get(reverse("pages:masharti") + "?lang=sw").content.decode()
        self.assertIn("Pesapal (M-Pesa au Airtel Money)", terms)

    def test_public_pages_do_not_promise_unsupported_methods(self):
        for url in ["/", reverse("pages:masharti"), reverse("dashboard:login"), "/makala/mikrotik-hotspot-malipo-ya-simu/"]:
            with self.subTest(url):
                html = self.client.get(url).content.decode()
                self.assertNotIn("HaloPesa", html)
                self.assertNotIn("M-Pesa", html)

    def test_join_words(self):
        self.assertEqual(join_words(["A", "B", "C"], "na"), "A, B na C")
        self.assertEqual(join_words(["A"], "na"), "A")
        self.assertEqual(join_words([], "na"), "")
