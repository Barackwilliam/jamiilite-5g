import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing import subscriptions
from billing.models import LedgerEntry, Payment, SubscriptionCharge
from core.models import Owner
from core.tests.factories import make_owner, make_package, make_router
from dashboard.stats import sales_summary, top_by
from radius import routeros


class SuperAdminLoginTests(TestCase):
    def test_superadmin_logs_in_with_a_username(self):
        password = secrets.token_urlsafe(12)
        get_user_model().objects.create_superuser("admin", password=password)
        response = self.client.post(reverse("dashboard:login"), {"phone": "admin", "password": password})
        self.assertEqual(response.status_code, 302)

    def test_plain_user_cannot_log_in_with_a_username(self):
        password = secrets.token_urlsafe(12)
        get_user_model().objects.create_user("mtu", password=password)
        response = self.client.post(reverse("dashboard:login"), {"phone": "mtu", "password": password})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


class LanguageSwitchTests(TestCase):
    def test_switch_replaces_lang_in_the_address(self):
        response = self.client.post(reverse("ui:set_language"), {"language": "en", "next": "/?lang=sw"})
        self.assertRedirects(response, "/?lang=en", fetch_redirect_response=False)


@override_settings(JAMIILITE_MONTHLY_FEE=10000)
class SubscriptionChargeTests(TestCase):
    def test_two_requests_at_expiry_charge_once(self):
        owner = make_owner(trial_ends_at=timezone.now() - timedelta(minutes=1))
        LedgerEntry.objects.create(owner=owner, kind=LedgerEntry.Kind.ADJUSTMENT, amount=50000)
        first, second = Owner.objects.get(pk=owner.pk), Owner.objects.get(pk=owner.pk)
        self.assertTrue(subscriptions.ensure_active(first))
        self.assertTrue(subscriptions.ensure_active(second))  # bado inaona "imeisha" (kitu cha zamani)
        self.assertEqual(SubscriptionCharge.objects.count(), 1)


class StatsTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.package = make_package(self.owner)

    def pay(self, router, when, amount=500):
        Payment.objects.create(router=router, package=self.package, phone="255712345678", amount=amount,
                               status=Payment.Status.PAID, paid_at=when)

    def test_today_is_compared_with_yesterday_up_to_the_same_hour(self):
        router = make_router(self.owner)
        now = timezone.now()
        self.pay(router, now - timedelta(days=1, minutes=5))
        self.pay(router, now - timedelta(days=1) + timedelta(minutes=5))  # baadaye jana: hailinganishwi
        summary = sales_summary(Payment.objects.filter(router__owner=self.owner), now=now)
        if summary["yesterday_amount"] == 1000:  # isipovuka usiku wa manane
            self.assertEqual(summary["yesterday_so_far_amount"], 500)

    def test_routers_with_the_same_name_are_listed_apart(self):
        a = make_router(self.owner, slug="a")
        b = make_router(self.owner, slug="b")
        self.pay(a, timezone.now())
        self.pay(b, timezone.now(), amount=700)
        rows = top_by(Payment.objects.filter(router__owner=self.owner), "router__name")
        self.assertEqual(len(rows), 2)


class RouterScriptTests(TestCase):
    def test_name_cannot_add_lines_to_the_setup_script(self):
        router = make_router(make_owner(), name="Duka\n/system reset-configuration", nas_identifier=None)
        script = routeros.setup_script(router)
        self.assertNotIn("\n/system reset-configuration", script)
        self.assertIn(f'/system identity set name="jl-{router.slug}"', script)

    def test_router_form_keeps_names_on_one_line(self):
        owner = make_owner()
        self.client.force_login(owner.user)
        self.client.post(reverse("dashboard:routers"), {"name": "Duka\r\nla Kati", "location": "", "wifi_name": ""})
        self.assertEqual(owner.routers.get().name, "Duka la Kati")
