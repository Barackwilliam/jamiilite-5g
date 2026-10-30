from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from billing.models import Payment, Voucher
from billing.providers import pesapal
from core.tests.factories import make_owner, make_package, make_router
from radius import routeros

PESAPAL = {
    "PAYMENT_PROVIDER": "pesapal",
    "PESAPAL_CONSUMER_KEY": "key-for-tests",
    "PESAPAL_CONSUMER_SECRET": "value-for-tests",
    "PESAPAL_ENV": "sandbox",
    "PESAPAL_IPN_ID": "",
    "JAMIILITE_PUBLIC_URL": "https://jamiilite.example.com",
}


class FakePesapal:
    """Majibu ya API ya Pesapal kama ilivyo, bila mtandao."""

    def __init__(self):
        self.calls = []
        self.orders = 0
        self.status = {"status_code": 0, "payment_status_description": "INVALID"}

    def __call__(self, method, path, payload=None, token=None):
        self.calls.append((method, path, payload))
        if path == "/Auth/RequestToken":
            return {"token": "tok", "expiryDate": "2030-01-01T00:00:00Z", "status": "200"}
        if path == "/URLSetup/GetIpnList":
            return []
        if path == "/URLSetup/RegisterIPN":
            return {"ipn_id": "ipn-123", "url": payload["url"], "status": "200"}
        if path == "/Transactions/SubmitOrderRequest":
            self.orders += 1
            tracking = f"trk-{self.orders}"
            return {"order_tracking_id": tracking, "merchant_reference": payload["id"],
                    "redirect_url": f"https://cybqa.pesapal.com/iframe/{tracking}", "status": "200"}
        if path.startswith("/Transactions/GetTransactionStatus"):
            return {"status": "200", "currency": "TZS", **self.status}
        raise AssertionError(path)

    def paths(self):
        return [path.split("?")[0] for _method, path, _payload in self.calls]


@override_settings(**PESAPAL)
class PesapalFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        owner = make_owner(business_name="Neema WiFi")
        self.router = make_router(owner, slug="neema")
        self.package = make_package(owner, name="Siku 1", price=1000, duration_minutes=1440)
        self.fake = FakePesapal()
        patcher = mock.patch.object(pesapal, "_call", self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def buy(self):
        response = self.client.post(reverse("portal:pay", args=["neema"]), {"package": self.package.pk, "phone": "0712345678"})
        return Payment.objects.latest("created_at"), response

    def ipn(self, payment, tracking="trk-1"):
        return self.client.get(reverse("billing:pesapal_ipn"), {
            "OrderTrackingId": tracking, "OrderMerchantReference": str(payment.pk), "OrderNotificationType": "IPNCHANGE",
        })

    def test_order_is_sent_and_checkout_shown_on_our_page(self):
        payment, response = self.buy()
        self.assertEqual((payment.status, payment.provider_reference), (Payment.Status.PENDING, "trk-1"))
        order = next(p for _m, path, p in self.fake.calls if path == "/Transactions/SubmitOrderRequest")
        self.assertEqual(order["amount"], 1000)
        self.assertEqual(order["currency"], "TZS")
        self.assertEqual(order["notification_id"], "ipn-123")
        self.assertEqual(order["billing_address"]["phone_number"], "0712345678")
        self.assertEqual(order["redirect_mode"], "PARENT_WINDOW")
        self.assertTrue(order["callback_url"].startswith("https://jamiilite.example.com/p/neema/malipo/"))
        page = self.client.get(response["Location"])
        self.assertContains(page, 'src="https://cybqa.pesapal.com/iframe/trk-1"')
        self.assertNotContains(page, 'http-equiv="refresh"')

    def test_completed_payment_gives_a_voucher(self):
        payment, _ = self.buy()
        self.fake.status = {"status_code": 1, "amount": 1000.0, "confirmation_code": "MPESA123", "merchant_reference": str(payment.pk)}
        reply = self.ipn(payment).json()
        self.assertEqual(reply["status"], 200)
        self.assertEqual(reply["orderTrackingId"], "trk-1")
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.confirmation_code), (Payment.Status.PAID, "MPESA123"))
        self.ipn(payment)  # Pesapal ikirudia IPN: vocha bado ni moja tu
        self.assertEqual(Voucher.objects.count(), 1)

    def test_wrong_amount_is_not_accepted(self):
        payment, _ = self.buy()
        self.fake.status = {"status_code": 1, "amount": 10.0, "merchant_reference": str(payment.pk)}
        self.ipn(payment)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertFalse(Voucher.objects.exists())

    def test_failed_payment_is_marked_failed(self):
        payment, _ = self.buy()
        self.fake.status = {"status_code": 2, "payment_status_description": "Failed", "merchant_reference": str(payment.pk)}
        self.ipn(payment)
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.failure_reason), (Payment.Status.FAILED, "Failed"))

    def test_ipn_for_unknown_payment_is_refused(self):
        payment, _ = self.buy()
        self.assertEqual(self.ipn(payment, tracking="sio-yenyewe").json()["status"], 500)
        self.assertNotIn("/Transactions/GetTransactionStatus", self.fake.paths())

    def test_customer_page_asks_pesapal_at_most_every_few_seconds(self):
        payment, _ = self.buy()
        url = reverse("portal:payment_state", args=["neema", payment.pk])
        self.assertEqual(self.client.get(url).json(), {"status": "pending"})
        self.client.get(url)
        self.assertEqual(self.fake.paths().count("/Transactions/GetTransactionStatus"), 1)

    def test_token_and_ipn_are_reused(self):
        self.buy()
        self.client.post(reverse("portal:pay", args=["neema"]), {"package": self.package.pk, "phone": "0754000111"})
        self.assertEqual(self.fake.paths().count("/Auth/RequestToken"), 1)
        self.assertEqual(self.fake.paths().count("/URLSetup/RegisterIPN"), 1)

    def test_provider_error_fails_the_payment(self):
        def broken(method, path, payload=None, token=None):
            raise pesapal.PesapalError("timeout")
        with mock.patch.object(pesapal, "_call", broken):
            payment, _ = self.buy()
        self.assertEqual(payment.status, Payment.Status.FAILED)

    def test_hotspot_lets_customers_reach_pesapal_before_paying(self):
        self.assertIn('dst-host="cybqa.pesapal.com" protocol=tcp dst-port=443', "\n".join(routeros.walled_garden_rules()))

    @override_settings(PESAPAL_CONSUMER_KEY="")
    def test_missing_keys_do_not_break_router_setup(self):
        rules = "\n".join(routeros.walled_garden_rules())
        self.assertNotIn("pesapal", rules)


@override_settings(**{**PESAPAL, "PESAPAL_ENV": "live"})
class PesapalLiveTests(TestCase):
    def test_live_uses_the_real_pesapal_server(self):
        self.assertEqual(pesapal.BASE_URLS[pesapal._environment()], "https://pay.pesapal.com/v3/api")
        self.assertIn('dst-host="pay.pesapal.com" protocol=tcp dst-port=443', "\n".join(routeros.walled_garden_rules()))
