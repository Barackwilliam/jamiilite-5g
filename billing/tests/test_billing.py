from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from billing.models import VOUCHER_ALPHABET, Payment, Voucher
from billing.phone import normalize_tz_phone
from billing.providers import get_provider
from billing.services import confirm_payment, start_payment
from core.tests.factories import make_owner, make_package, make_router


class PhoneTests(TestCase):
    def test_accepts_common_formats(self):
        for raw in ["0712345678", "0712 345 678", "+255712345678", "255712345678", "712345678", "0655123456"]:
            with self.subTest(raw=raw):
                self.assertRegex(normalize_tz_phone(raw), r"^255[67]\d{8}$")

    def test_rejects_invalid_numbers(self):
        for raw in ["", "12345", "0812345678", "07123456789", "abc"]:
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                normalize_tz_phone(raw)


@override_settings(PAYMENT_PROVIDER="sandbox", ALLOW_SANDBOX_PAYMENTS=True)
class PaymentServiceTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.router = make_router(self.owner)
        self.package = make_package(self.owner, price=1000, duration_minutes=1440)

    def test_sandbox_payment_creates_voucher(self):
        payment = start_payment(router=self.router, package=self.package, phone="255712345678")

        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(payment.amount, 1000)
        self.assertTrue(payment.provider_reference.startswith("SBX-"))
        voucher = payment.voucher
        self.assertEqual(voucher.package, self.package)
        self.assertEqual(len(voucher.code), 8)
        self.assertTrue(set(voucher.code) <= set(VOUCHER_ALPHABET))

    def test_confirm_payment_is_idempotent(self):
        payment = Payment.objects.create(
            router=self.router, package=self.package, phone="255712345678",
            amount=self.package.price, provider="sandbox",
        )
        first = confirm_payment(payment.pk)
        second = confirm_payment(payment.pk)

        self.assertEqual(first, second)
        self.assertEqual(Voucher.objects.filter(payment=payment).count(), 1)

    @override_settings(ALLOW_SANDBOX_PAYMENTS=False)
    def test_sandbox_refused_unless_allowed(self):
        with self.assertRaises(ImproperlyConfigured):
            get_provider()


class VoucherTests(TestCase):
    def test_activation_starts_calendar_countdown_once(self):
        owner = make_owner()
        router = make_router(owner)
        package = make_package(owner, duration_minutes=60)
        voucher = Voucher.objects.create(router=router, package=package)
        start = timezone.now()

        voucher.activate(now=start)
        voucher.activate(now=start + timedelta(minutes=30))

        self.assertEqual(voucher.expires_at, start + timedelta(minutes=60))
        self.assertFalse(voucher.is_expired(now=start + timedelta(minutes=59)))
        self.assertTrue(voucher.is_expired(now=start + timedelta(minutes=60)))
