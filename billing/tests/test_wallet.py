from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing import subscriptions, wallet
from billing.models import LedgerEntry, Payment, SubscriptionCharge, Withdrawal
from billing.services import start_payment
from core.tests.factories import make_owner, make_package, make_router

FEES = {"JAMIILITE_MONTHLY_FEE": 10000, "JAMIILITE_MIN_WITHDRAWAL": 1000, "JAMIILITE_SALE_FEE_PERCENT": 0}


def give_balance(owner, amount):
    LedgerEntry.objects.create(owner=owner, kind=LedgerEntry.Kind.ADJUSTMENT, amount=amount)


@override_settings(PAYMENT_PROVIDER="sandbox", ALLOW_SANDBOX_PAYMENTS=True, **FEES)
class SaleCreditTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.router = make_router(self.owner)
        self.package = make_package(self.owner, price=1500)

    def test_paid_sale_credits_owner_once(self):
        payment = start_payment(router=self.router, package=self.package, phone="255712345678")

        self.assertEqual(wallet.balance(self.owner), 1500)
        entry = LedgerEntry.objects.get()
        self.assertEqual((entry.kind, entry.payment), (LedgerEntry.Kind.SALE, payment))

    @override_settings(JAMIILITE_SALE_FEE_PERCENT=3)
    def test_sale_fee_is_deducted(self):
        start_payment(router=self.router, package=self.package, phone="255712345678")
        self.assertEqual(wallet.balance(self.owner), 1455)


@override_settings(**FEES)
class WithdrawalTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        give_balance(self.owner, 5000)
        self.admin = get_user_model().objects.create_superuser("bosi", "b@example.com", "siri-ndefu-123")

    def test_request_holds_money_and_paid_keeps_it_out(self):
        withdrawal = wallet.request_withdrawal(self.owner, 3000, "255712345678")
        self.assertEqual(wallet.balance(self.owner), 2000)

        wallet.mark_withdrawal_paid(withdrawal.pk, self.admin, "MPESA123")
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.PAID)
        self.assertEqual(wallet.balance(self.owner), 2000)

    def test_rejection_returns_money(self):
        withdrawal = wallet.request_withdrawal(self.owner, 3000, "255712345678")
        wallet.reject_withdrawal(withdrawal.pk, self.admin, "Namba si sahihi")
        self.assertEqual(wallet.balance(self.owner), 5000)

    def test_cannot_overdraw_or_process_twice(self):
        with self.assertRaises(ValidationError):
            wallet.request_withdrawal(self.owner, 6000, "255712345678")
        with self.assertRaises(ValidationError):
            wallet.request_withdrawal(self.owner, 500, "255712345678")

        withdrawal = wallet.request_withdrawal(self.owner, 5000, "255712345678")
        with self.assertRaises(ValidationError):
            wallet.request_withdrawal(self.owner, 1000, "255712345678")
        wallet.mark_withdrawal_paid(withdrawal.pk, self.admin)
        with self.assertRaises(ValidationError):
            wallet.reject_withdrawal(withdrawal.pk, self.admin)
        self.assertEqual(wallet.balance(self.owner), 0)


@override_settings(**FEES)
class SubscriptionTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.owner = make_owner(trial_ends_at=self.now + timedelta(days=3))

    def test_trial_counts_as_active(self):
        self.assertTrue(self.owner.has_active_subscription(self.now))
        self.assertTrue(self.owner.is_in_trial(self.now))
        self.assertFalse(self.owner.has_active_subscription(self.now + timedelta(days=4)))

    def test_paying_during_trial_extends_from_trial_end(self):
        give_balance(self.owner, 10000)
        subscriptions.pay_from_balance(self.owner, now=self.now)

        self.owner.refresh_from_db()
        self.assertEqual(self.owner.paid_until, self.now + timedelta(days=33))
        self.assertEqual(wallet.balance(self.owner), 0)
        self.assertEqual(SubscriptionCharge.objects.get().source, SubscriptionCharge.Source.BALANCE)

    def test_expired_owner_renews_from_balance_automatically(self):
        later = self.now + timedelta(days=10)
        self.assertFalse(subscriptions.ensure_active(self.owner, now=later))

        give_balance(self.owner, 12000)
        self.assertTrue(subscriptions.ensure_active(self.owner, now=later))
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.paid_until, later + timedelta(days=30))
        self.assertEqual(wallet.balance(self.owner), 2000)

    def test_cash_payment_extends_without_touching_balance(self):
        admin = get_user_model().objects.create_superuser("bosi", "b@example.com", "siri-ndefu-123")
        subscriptions.record_cash_payment(self.owner, 2, admin, now=self.now)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.paid_until, self.now + timedelta(days=63))
        self.assertEqual(wallet.balance(self.owner), 0)

    def test_suspended_owner_cannot_sell(self):
        self.owner.is_active = False
        self.assertFalse(subscriptions.ensure_active(self.owner, now=self.now))


@override_settings(PAYMENT_PROVIDER="sandbox", ALLOW_SANDBOX_PAYMENTS=True, **FEES)
class PortalPausedTests(TestCase):
    def test_expired_owner_portal_stops_new_sales(self):
        owner = make_owner(trial_ends_at=timezone.now() - timedelta(days=1))
        router = make_router(owner)
        package = make_package(owner)

        home = self.client.get(reverse("portal:home", args=[router.slug]))
        self.assertContains(home, "Mauzo ya vifurushi yamesimama")
        self.assertNotContains(home, "Lipa kwa simu")

        response = self.client.post(
            reverse("portal:pay", args=[router.slug]), {"package": package.pk, "phone": "0712345678"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Payment.objects.exists())
