from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing.models import Voucher
from billing.services import start_payment
from core import events
from core.models import NetworkEvent
from core.tests.factories import make_owner, make_package, make_router
from radius import packet as rp
from radius.handlers import handle
from radius.tests.test_radius import MAC_A, access_request


@override_settings(PAYMENT_PROVIDER="sandbox", ALLOW_SANDBOX_PAYMENTS=True, RADIUS_REQUIRE_MESSAGE_AUTHENTICATOR=True)
class EventRecordingTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.router = make_router(self.owner, nas_identifier="jl-duka")
        self.package = make_package(self.owner)
        self.secret = self.router.radius_secret.encode()

    def kinds(self):
        return list(NetworkEvent.objects.order_by("id").values_list("kind", flat=True))

    def test_payment_and_login_are_recorded(self):
        payment = start_payment(router=self.router, package=self.package, phone="255712345678", client_mac=MAC_A)
        code = payment.voucher.code
        handle(access_request(self.secret, "jl-duka", code, code), "auth")
        handle(access_request(self.secret, "jl-duka", "HAKUNA", "HAKUNA"), "auth")
        self.assertEqual(self.kinds(), ["payment_started", "payment_paid", "auth_accept", "auth_reject"])
        paid = NetworkEvent.objects.get(kind="payment_paid")
        self.assertEqual((paid.amount, paid.mac), (500, MAC_A))
        self.assertEqual(NetworkEvent.objects.get(kind="auth_reject").detail, "Vocha si sahihi")

    def test_accounting_records_data_used(self):
        voucher = Voucher.objects.create(router=self.router, package=self.package)
        attributes = [
            (rp.NAS_IDENTIFIER, b"jl-duka"), (rp.USER_NAME, voucher.code.encode()),
            (rp.CALLING_STATION_ID, MAC_A.encode()),
            (rp.ACCT_STATUS_TYPE, rp.int_attr(rp.ACCT_INTERIM_UPDATE)),
            (rp.ACCT_OUTPUT_OCTETS, rp.int_attr(12_500_000)), (rp.ACCT_INPUT_OCTETS, rp.int_attr(1_000_000)),
        ]
        handle(rp.build_request(rp.ACCOUNTING_REQUEST, 9, b"", self.secret, attributes), "acct")
        event = NetworkEvent.objects.get()
        self.assertEqual(event.kind, "acct_update")
        self.assertEqual(event.detail, "↓ 12.5 MB · ↑ 1.0 MB")

    def test_prune_keeps_two_days(self):
        old = NetworkEvent.objects.create(router=self.router, kind="acct_update", created_at=timezone.now() - timedelta(hours=49))
        fresh = NetworkEvent.objects.create(router=self.router, kind="acct_update")
        self.assertEqual(events.prune(), 1)
        self.assertFalse(NetworkEvent.objects.filter(pk=old.pk).exists())
        self.assertTrue(NetworkEvent.objects.filter(pk=fresh.pk).exists())


@override_settings(PAYMENT_PROVIDER="sandbox", ALLOW_SANDBOX_PAYMENTS=True)
class LiveFeedTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.router = make_router(self.owner, nas_identifier="jl-duka", last_seen_at=timezone.now(), active_clients=3)
        other = make_owner(username="mwingine", business_name="Mwingine")
        self.other_router = make_router(other, name="Siri", nas_identifier="jl-siri")
        NetworkEvent.objects.create(router=self.other_router, kind="auth_accept", detail="si yako")
        start_payment(router=self.router, package=make_package(self.owner, price=700), phone="255712345678")
        self.client.force_login(self.owner.user)

    def test_page_renders(self):
        response = self.client.get(reverse("dashboard:live"))
        self.assertContains(response, "data-live")
        self.assertContains(response, reverse("dashboard:live_data"))

    def test_first_load_backfills_only_own_events(self):
        data = self.client.get(reverse("dashboard:live_data")).json()
        self.assertTrue(data["backfill"])
        self.assertEqual([e["kind"] for e in data["events"]], ["payment_started", "payment_paid"])
        self.assertEqual([r["name"] for r in data["routers"]], ["Duka la Kati"])
        self.assertEqual(data["stats"]["today_amount"], 700)
        self.assertEqual(data["stats"]["clients"], 3)
        self.assertNotIn("si yako", str(data))

    def test_since_returns_only_newer(self):
        cursor = self.client.get(reverse("dashboard:live_data")).json()["cursor"]
        self.assertEqual(self.client.get(reverse("dashboard:live_data"), {"since": cursor}).json()["events"], [])
        NetworkEvent.objects.create(router=self.router, kind="acct_update", mac="08:00:27:50:4C:14", detail="↓ 1.0 MB")
        data = self.client.get(reverse("dashboard:live_data"), {"since": cursor}).json()
        self.assertFalse(data["backfill"])
        self.assertEqual([(e["kind"], e["device"]) for e in data["events"]], [("acct_update", "…4C:14")])

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("dashboard:live_data")).status_code, 302)

    def test_superadmin_sees_all_routers(self):
        admin = get_user_model().objects.create_superuser("boss", password="x-pass-123")
        self.client.force_login(admin)
        data = self.client.get(reverse("control:live_data")).json()
        self.assertEqual({r["name"] for r in data["routers"]}, {"Duka la Kati", "Siri"})
        self.assertTrue(data["show_owner"])
        self.assertEqual(self.client.get(reverse("control:live")).status_code, 200)

    def test_owner_cannot_open_control_feed(self):
        self.assertEqual(self.client.get(reverse("control:live_data")).status_code, 404)
