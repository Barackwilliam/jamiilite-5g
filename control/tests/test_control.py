from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing import wallet
from billing.models import LedgerEntry, SubscriptionCharge, Withdrawal
from billing.services import start_payment
from control import queries
from core.tests.factories import make_owner, make_package, make_router

FEES = {"JAMIILITE_MONTHLY_FEE": 10000, "JAMIILITE_MIN_WITHDRAWAL": 1000, "JAMIILITE_SALE_FEE_PERCENT": 0}


def give_balance(owner, amount):
    LedgerEntry.objects.create(owner=owner, kind=LedgerEntry.Kind.ADJUSTMENT, amount=amount)


@override_settings(PAYMENT_PROVIDER="sandbox", ALLOW_SANDBOX_PAYMENTS=True, **FEES)
class ControlTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("boss", password="x-pass-123")
        self.client.force_login(self.admin)
        self.owner = make_owner()

    def test_owners_cannot_open_control(self):
        self.client.force_login(self.owner.user)
        self.assertEqual(self.client.get(reverse("control:home")).status_code, 404)

    def test_every_page_renders(self):
        router = make_router(self.owner, last_seen_at=timezone.now() - timedelta(hours=1))
        start_payment(router=router, package=make_package(self.owner), phone="255712345678")
        give_balance(self.owner, 5000)
        wallet.request_withdrawal(self.owner, 2000, "255712345678")
        for name, args in [
            ("home", []), ("owners", []), ("owner_detail", [self.owner.pk]),
            ("withdrawals", []), ("routers", []), ("payments", []),
        ]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(f"control:{name}", args=args)).status_code, 200)

    def test_owner_states(self):
        now = timezone.now()
        make_owner(username="a", business_name="Paid", paid_until=now + timedelta(days=5), trial_ends_at=now - timedelta(days=1))
        make_owner(username="b", business_name="Expired", trial_ends_at=now - timedelta(days=1))
        make_owner(username="c", business_name="Off", is_active=False)
        make_owner(username="d", business_name="NoDates", trial_ends_at=None)
        states = dict(queries.owners_with_state(now).values_list("business_name", "state"))
        self.assertEqual(states, {
            "Mama Neema WiFi": "trial", "Paid": "paid", "Expired": "expired", "Off": "suspended", "NoDates": "expired",
        })
        response = self.client.get(reverse("control:owners"), {"hali": "expired"})
        self.assertEqual({o.business_name for o in response.context["page"].object_list}, {"Expired", "NoDates"})

    def test_search_owners(self):
        make_owner(username="x", business_name="Juma Net")
        response = self.client.get(reverse("control:owners"), {"q": "juma"})
        self.assertEqual([o.business_name for o in response.context["page"].object_list], ["Juma Net"])

    def test_suspend_and_activate(self):
        url = reverse("control:owner_detail", args=[self.owner.pk])
        self.client.post(url, {"action": "suspend"})
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.is_active)
        self.client.post(url, {"action": "activate"})
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)

    def test_cash_payment_extends_without_touching_balance(self):
        ends = self.owner.subscription_ends_at
        self.client.post(reverse("control:owner_detail", args=[self.owner.pk]), {"action": "cash", "months": "3"})
        self.owner.refresh_from_db()
        charge = SubscriptionCharge.objects.get()
        self.assertEqual((charge.source, charge.amount, charge.created_by), ("cash", 30000, self.admin))
        self.assertEqual(self.owner.paid_until, ends + timedelta(days=90))
        self.assertEqual(wallet.balance(self.owner), 0)

    def test_cash_payment_rejects_odd_months(self):
        self.client.post(reverse("control:owner_detail", args=[self.owner.pk]), {"action": "cash", "months": "100"})
        self.assertFalse(SubscriptionCharge.objects.exists())

    def test_mark_withdrawal_paid_needs_reference(self):
        give_balance(self.owner, 5000)
        w = wallet.request_withdrawal(self.owner, 3000, "255712345678")
        url = reverse("control:withdrawal_action", args=[w.pk])
        self.client.post(url, {"action": "pay", "reference": ""})
        w.refresh_from_db()
        self.assertEqual(w.status, Withdrawal.Status.PENDING)
        self.client.post(url, {"action": "pay", "reference": "QK12AB34"})
        w.refresh_from_db()
        self.assertEqual((w.status, w.reference, w.processed_by), (Withdrawal.Status.PAID, "QK12AB34", self.admin))
        self.assertEqual(wallet.balance(self.owner), 2000)

    def test_reject_withdrawal_returns_money(self):
        give_balance(self.owner, 5000)
        w = wallet.request_withdrawal(self.owner, 3000, "255712345678")
        response = self.client.post(reverse("control:withdrawal_action", args=[w.pk]), {
            "action": "reject", "note": "Namba si sahihi", "back": "https://evil.example/",
        })
        self.assertRedirects(response, reverse("control:withdrawals"))
        self.assertEqual(wallet.balance(self.owner), 5000)

    def test_home_kpis(self):
        router = make_router(self.owner, last_seen_at=timezone.now(), active_clients=4)
        start_payment(router=router, package=make_package(self.owner, price=2500), phone="255712345678")
        give_balance(self.owner, 1000)
        wallet.request_withdrawal(self.owner, 1000, "255712345678")
        response = self.client.get(reverse("control:home"))
        ctx = response.context
        self.assertEqual(ctx["gmv"]["today_amount"], 2500)
        self.assertEqual((ctx["routers"]["online"], ctx["routers"]["clients"]), (1, 4))
        self.assertEqual(ctx["held"], 2500)
        self.assertEqual(ctx["pending_count"], 1)
        self.assertContains(response, "Maombi 1 ya kutoa pesa")

    def test_routers_offline_first(self):
        now = timezone.now()
        make_router(self.owner, name="Online", last_seen_at=now)
        make_router(self.owner, name="Offline", last_seen_at=now - timedelta(hours=2))
        response = self.client.get(reverse("control:routers"))
        self.assertEqual([r.name for r in response.context["page"].object_list], ["Offline", "Online"])
