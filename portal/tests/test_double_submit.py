from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from billing.providers.base import PaymentRequestResult
from billing.providers.sandbox import SandboxProvider

from billing.models import Payment
from core.tests.factories import make_owner, make_package, make_router


def _pending(self, payment):
    # Kama Pesapal: ombi linaanza, mteja bado hajalipa.
    return PaymentRequestResult(reference=f"REF-{payment.pk}", confirmed=False)


@override_settings(PAYMENT_PROVIDER="sandbox", ALLOW_SANDBOX_PAYMENTS=True)
@mock.patch.object(SandboxProvider, "request_payment", _pending)
class DoubleSubmitTests(TestCase):
    def setUp(self):
        owner = make_owner()
        self.router = make_router(owner)
        self.package = make_package(owner)
        self.url = reverse("portal:pay", args=[self.router.slug])

    def test_second_click_reuses_the_pending_payment(self):
        data = {"package": self.package.pk, "phone": "0712345678"}
        first = self.client.post(self.url, data)
        second = self.client.post(self.url, data)
        self.assertEqual(first["Location"], second["Location"])
        self.assertEqual(Payment.objects.count(), 1)

    def test_another_device_gets_its_own_payment(self):
        data = {"package": self.package.pk, "phone": "0712345678"}
        self.client.post(self.url, data)
        self.client_class().post(self.url, data)
        self.assertEqual(Payment.objects.count(), 2)

    def test_pages_carry_the_busy_guard(self):
        html = self.client.get(reverse("portal:home", args=[self.router.slug])).content.decode()
        self.assertIn("form.dataset.busy", html)
