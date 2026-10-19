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
        self.assertContains(response, "Ombi 1 la kutoa pesa linasubiri")

    def test_routers_offline_first(self):
        now = timezone.now()
        make_router(self.owner, name="Online", last_seen_at=now)
        make_router(self.owner, name="Offline", last_seen_at=now - timedelta(hours=2))
        response = self.client.get(reverse("control:routers"))
        self.assertEqual([r.name for r in response.context["page"].object_list], ["Offline", "Online"])


@override_settings(PAYMENT_PROVIDER="sandbox", ALLOW_SANDBOX_PAYMENTS=True, **FEES)
class RouterManagementTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("boss", password="x-pass-123")
        self.client.force_login(self.admin)
        self.owner = make_owner()
        self.router = make_router(self.owner, nas_identifier="jl-duka")
        self.url = reverse("control:router_detail", args=[self.router.pk])

    def test_admin_can_open_any_router(self):
        response = self.client.get(self.url)
        self.assertContains(response, self.router.provision_token)
        self.assertContains(response, self.owner.business_name)

    def test_commands(self):
        from core.models import RouterCommand

        self.client.post(self.url, {"action": "reboot"})
        self.client.post(self.url, {"action": "reapply"})
        self.assertEqual(
            list(RouterCommand.objects.values_list("action", flat=True)),
            [RouterCommand.Action.REBOOT, RouterCommand.Action.REAPPLY_SETUP],
        )

    def test_disable_stops_radius_and_checkin(self):
        self.client.post(self.url, {"action": "disable"})
        self.router.refresh_from_db()
        self.assertFalse(self.router.is_active)
        checkin = self.client.post(reverse("radius:checkin", args=[self.router.provision_token]), "v=7&up=1h&users=2", content_type="text/plain")
        self.assertEqual(checkin.status_code, 404)
        self.client.post(self.url, {"action": "enable"})
        self.router.refresh_from_db()
        self.assertTrue(self.router.is_active)

    def test_rotate_secret_queues_reapply(self):
        old = self.router.radius_secret
        self.client.post(self.url, {"action": "rotate_secret"})
        self.router.refresh_from_db()
        self.assertNotEqual(self.router.radius_secret, old)
        self.assertEqual(self.router.commands.get().action, "reapply_setup")

    def test_edit_nas_identifier_queues_reapply(self):
        self.client.post(self.url, {"action": "edit", "name": "Duka Jipya", "location": "", "nas_identifier": "jl-mpya", "login_url": "", "wifi_name": ""})
        self.router.refresh_from_db()
        self.assertEqual((self.router.name, self.router.nas_identifier), ("Duka Jipya", "jl-mpya"))
        self.assertEqual(self.router.commands.count(), 1)

    def test_edit_without_nas_change_sends_nothing(self):
        self.client.post(self.url, {"action": "edit", "name": "Duka", "location": "Sinza", "nas_identifier": "jl-duka", "login_url": "", "wifi_name": ""})
        self.assertEqual(self.router.commands.count(), 0)

    def test_duplicate_nas_identifier_is_refused(self):
        make_router(self.owner, name="Nyingine", nas_identifier="jl-nyingine")
        response = self.client.post(self.url, {"action": "edit", "name": "Duka", "location": "", "nas_identifier": "jl-nyingine", "login_url": "", "wifi_name": ""})
        self.assertEqual(response.status_code, 200)
        self.router.refresh_from_db()
        self.assertEqual(self.router.nas_identifier, "jl-duka")

    def test_router_filters(self):
        make_router(self.owner, name="Hai", last_seen_at=timezone.now())
        response = self.client.get(reverse("control:routers"), {"hali": "online"})
        self.assertEqual([r.name for r in response.context["page"].object_list], ["Hai"])


class SystemStatusTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("boss", password="x-pass-123")
        self.client.force_login(self.admin)

    def checks(self):
        from control import status

        return {c.key: c for c in status.run_checks()}

    def test_radius_never_started(self):
        self.assertEqual(self.checks()["radius"].state, "bad")

    def test_radius_heartbeat_fresh_and_stale(self):
        from core.models import ServiceHeartbeat

        now = timezone.now()
        beat = ServiceHeartbeat.objects.create(name="radius", started_at=now, last_seen_at=now, stats={"counts": {"accept": 5}})
        self.assertEqual(self.checks()["radius"].state, "ok")
        beat.last_seen_at = now - timedelta(minutes=30)
        beat.save()
        self.assertEqual(self.checks()["radius"].state, "bad")

    @override_settings(DEBUG=False, PAYMENT_PROVIDER="sandbox")
    def test_sandbox_in_production_is_a_problem(self):
        self.assertEqual(self.checks()["payments"].state, "bad")

    def test_status_page_renders_with_warnings(self):
        from core.models import ServiceHeartbeat

        now = timezone.now()
        ServiceHeartbeat.objects.create(
            name="radius", started_at=now, last_seen_at=now,
            stats={"warnings": [{"at": now.isoformat(), "message": "Message-Authenticator batili kutoka 'jl-x'"}]},
        )
        response = self.client.get(reverse("control:status"))
        self.assertContains(response, "Message-Authenticator batili")
        self.assertContains(response, "RADIUS server")

    def test_home_shows_problems(self):
        response = self.client.get(reverse("control:home"))
        self.assertContains(response, "Hali ya mfumo")
        self.assertContains(response, "Haijawahi kuripoti")


@override_settings(**FEES)
class PlatformConfigTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("boss", password="x-pass-123")
        self.client.force_login(self.admin)

    def save(self, **data):
        base = {"monthly_fee": "", "trial_days": "", "min_withdrawal": "", "sale_fee_percent": "",
                "whatsapp_number": "", "signups_open": "on", "announcement": ""}
        base.update(data)
        return self.client.post(reverse("control:config"), base)

    def test_empty_fields_fall_back_to_env(self):
        from core import config

        self.save()
        self.assertEqual(config.current().monthly_fee, 10000)

    def test_new_fee_is_charged(self):
        from billing import subscriptions

        self.save(monthly_fee="15000", min_withdrawal="2000")
        owner = make_owner()
        give_balance(owner, 20000)
        self.assertEqual(subscriptions.pay_from_balance(owner).amount, 15000)
        with self.assertRaises(Exception):
            wallet.request_withdrawal(owner, 1500, "255712345678")

    def test_trial_days_apply_to_new_signups(self):
        self.save(trial_days="30")
        self.client.logout()
        self.client.post(reverse("dashboard:signup"), {
            "business_name": "Mpya", "phone": "0712000111", "password1": "Sinza-wifi-2026", "password2": "Sinza-wifi-2026",
        })
        owner = get_user_model().objects.get(username="255712000111").owner
        self.assertGreater(owner.trial_ends_at, timezone.now() + timedelta(days=29))

    def test_closed_signups(self):
        self.save(signups_open="")
        self.client.logout()
        response = self.client.post(reverse("dashboard:signup"), {
            "business_name": "Mpya", "phone": "0712000111", "password1": "Sinza-wifi-2026", "password2": "Sinza-wifi-2026",
        })
        self.assertContains(response, "Usajili umefungwa")
        self.assertFalse(get_user_model().objects.filter(username="255712000111").exists())

    def test_announcement_reaches_owners(self):
        self.save(announcement="Matengenezo kesho saa 2 usiku")
        owner = make_owner()
        self.client.force_login(owner.user)
        self.assertContains(self.client.get(reverse("dashboard:home")), "Matengenezo kesho saa 2 usiku")

    def test_invalid_values(self):
        response = self.save(sale_fee_percent="50", whatsapp_number="0712")
        self.assertContains(response, "kati ya 0 na 20")
        self.assertContains(response, "255712345678")

    def test_landing_page_uses_new_fee(self):
        self.save(monthly_fee="12000")
        self.assertContains(self.client.get(reverse("pages:home")), "12,000")
