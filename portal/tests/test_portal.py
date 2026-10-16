from django.test import TestCase, override_settings
from django.urls import reverse

from billing.models import Payment
from core.tests.factories import make_owner, make_package, make_router


@override_settings(PAYMENT_PROVIDER="sandbox", ALLOW_SANDBOX_PAYMENTS=True)
class PortalFlowTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.router = make_router(self.owner)
        self.package = make_package(self.owner, name="Saa 1", price=500)
        make_package(self.owner, name="Kimezimwa", price=100, is_active=False)
        self.home_url = reverse("portal:home", args=[self.router.slug])

    def test_home_lists_only_active_packages(self):
        response = self.client.get(self.home_url)

        self.assertContains(response, "Mama Neema WiFi")
        self.assertContains(response, "Saa 1")
        self.assertNotContains(response, "Kimezimwa")

    def test_full_purchase_hands_voucher_to_hotspot(self):
        self.client.get(
            self.home_url,
            {"link-login-only": "http://login.wifi.test/login", "link-orig": "http://neverssl.com/",
             "mac": "08:00:27:50:4C:14", "ip": "10.5.50.20"},
        )
        response = self.client.post(
            reverse("portal:pay", args=[self.router.slug]),
            {"package": self.package.pk, "phone": "0712 345 678"},
        )

        payment = Payment.objects.get()
        self.assertRedirects(
            response, reverse("portal:payment_status", args=[self.router.slug, payment.pk])
        )
        self.assertEqual(payment.phone, "255712345678")
        self.assertEqual(payment.client_mac, "08:00:27:50:4C:14")
        self.assertEqual(payment.client_ip, "10.5.50.20")

        status = self.client.get(response.url)
        self.assertContains(status, payment.voucher.code)
        self.assertContains(status, 'action="http://login.wifi.test/login"')
        self.assertContains(status, 'name="dst" value="http://neverssl.com/"')

    def test_router_login_url_overrides_hotspot_param(self):
        self.router.login_url = "http://10.5.50.1/login"
        self.router.save()
        self.client.get(self.home_url, {"link-login-only": "http://evil.example/steal"})

        response = self.client.get(self.home_url)
        self.assertContains(response, 'action="http://10.5.50.1/login"')
        self.assertNotContains(response, "evil.example")

    def test_non_http_login_target_is_ignored(self):
        response = self.client.get(self.home_url, {"link-login-only": "javascript:alert(1)"})
        self.assertNotContains(response, "javascript:alert")

    def test_invalid_phone_shows_error(self):
        response = self.client.post(
            reverse("portal:pay", args=[self.router.slug]),
            {"package": self.package.pk, "phone": "123"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "namba sahihi", status_code=400)
        self.assertFalse(Payment.objects.exists())

    def test_payment_status_hidden_from_other_devices(self):
        self.client.post(
            reverse("portal:pay", args=[self.router.slug]),
            {"package": self.package.pk, "phone": "0712345678"},
        )
        payment = Payment.objects.get()
        url = reverse("portal:payment_status", args=[self.router.slug, payment.pk])

        self.client.logout()
        self.client.cookies.clear()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_inactive_router_returns_404(self):
        self.router.is_active = False
        self.router.save()
        self.assertEqual(self.client.get(self.home_url).status_code, 404)
