from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing.models import Payment
from core.tests.factories import make_owner, make_package, make_router
from radius import localsync


@override_settings(PAYMENT_PROVIDER="sandbox", ALLOW_SANDBOX_PAYMENTS=True, JAMIILITE_AUTH_MODE="local")
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

        # Njia ya local: tunasubiri router ipokee vocha kwenye ripoti yake.
        status = self.client.get(response.url)
        self.assertContains(status, payment.voucher.code)
        self.assertContains(status, "Tunakuunganisha")
        self.assertContains(status, 'http-equiv="refresh"')
        self.assertNotContains(status, 'action="http://login.wifi.test/login"')

        localsync.handle_report(self.router, {"jl": "0"}, now=timezone.now() - timedelta(seconds=5))
        status = self.client.get(response.url)
        self.assertContains(status, 'action="http://login.wifi.test/login"')
        self.assertContains(status, 'name="dst" value="http://neverssl.com/"')
        self.assertContains(status, 'data-autosubmit="1"')
        self.assertNotContains(status, 'http-equiv="refresh"')

    def test_slow_router_gives_manual_connect_button(self):
        self.client.get(self.home_url, {"link-login-only": "http://login.wifi.test/login"})
        response = self.client.post(
            reverse("portal:pay", args=[self.router.slug]), {"package": self.package.pk, "phone": "0712345678"},
        )
        payment = Payment.objects.get()
        Payment.objects.filter(pk=payment.pk).update(paid_at=timezone.now() - timedelta(minutes=2))
        status = self.client.get(response.url)
        self.assertContains(status, "Tunakuunganisha")
        self.assertContains(status, 'data-autosubmit="0"')

    @override_settings(JAMIILITE_AUTH_MODE="radius")
    def test_radius_mode_logs_in_right_away(self):
        self.client.get(self.home_url, {"link-login-only": "http://login.wifi.test/login"})
        response = self.client.post(
            reverse("portal:pay", args=[self.router.slug]), {"package": self.package.pk, "phone": "0712345678"},
        )
        status = self.client.get(response.url)
        self.assertContains(status, 'data-autosubmit="1"')
        self.assertNotContains(status, "Tunakuunganisha")

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


class ReturningCustomerTests(TestCase):
    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        from billing.models import Voucher, VoucherDevice

        self.owner = make_owner()
        # Ombi la jaribio linatoka 127.0.0.1, kama router ilivyoripoti: mteja yuko kwenye WiFi yake.
        self.router = make_router(self.owner, public_ip="127.0.0.1")
        package = make_package(self.owner, name="Siku 1", duration_minutes=1440)
        self.voucher = Voucher.objects.create(
            router=self.router, package=package,
            activated_at=timezone.now(), expires_at=timezone.now() + timedelta(hours=3, minutes=10),
        )
        VoucherDevice.objects.create(voucher=self.voucher, mac_address="08:00:27:50:4C:14")
        self.url = reverse("portal:home", args=[self.router.slug])
        self.params = {"link-login-only": "http://login.wifi.test/login", "mac": "08-00-27-50-4c-14"}

    def test_device_with_time_left_is_reconnected(self):
        response = self.client.get(self.url, self.params)
        self.assertContains(response, "Karibu tena")
        self.assertContains(response, "saa 3 dakika")
        self.assertContains(response, f'name="username" value="{self.voucher.code}"')
        self.assertContains(response, 'data-autosubmit="1"')

    def test_other_device_is_not(self):
        response = self.client.get(self.url, {**self.params, "mac": "AA:BB:CC:DD:EE:FF"})
        self.assertNotContains(response, "Karibu tena")
        self.assertNotContains(response, self.voucher.code)

    def test_expired_voucher_is_not_reused(self):
        from django.utils import timezone

        self.voucher.expires_at = timezone.now()
        self.voucher.save()
        self.assertNotContains(self.client.get(self.url, self.params), "Karibu tena")

    def test_no_loop_when_router_reports_error(self):
        response = self.client.get(self.url, {**self.params, "error": "vifaa vimezidi"})
        self.assertNotContains(response, "Karibu tena")

    def test_voucher_is_not_shown_to_requests_from_outside_the_hotspot(self):
        self.router.public_ip = "41.59.0.7"
        self.router.save()
        response = self.client.get(self.url, self.params)
        self.assertNotContains(response, self.voucher.code)
        self.assertNotContains(response, "Karibu tena")

    def test_voucher_works_on_another_router_of_the_same_owner(self):
        other = make_router(self.owner, name="Tawi", slug="tawi", public_ip="127.0.0.1")
        response = self.client.get(reverse("portal:home", args=[other.slug]), self.params)
        self.assertContains(response, "Karibu tena")


class HotspotLoginTargetTests(TestCase):
    def setUp(self):
        self.router = make_router(make_owner())
        self.url = reverse("portal:home", args=[self.router.slug])

    def target(self, link):
        self.client.get(self.url, {"link-login-only": link})
        return self.client.get(self.url).context["login_target"]

    def test_hotspot_addresses_are_accepted(self):
        for link in ("http://10.5.50.1/login", "http://192.168.88.1/login", "http://login.wifi/login", "http://hotspot/login"):
            self.assertEqual(self.target(link), link)

    def test_public_sites_are_refused(self):
        for link in ("https://evil.example/steal", "http://8.8.8.8/login", "javascript:alert(1)"):
            self.assertEqual(self.target(link), "")
