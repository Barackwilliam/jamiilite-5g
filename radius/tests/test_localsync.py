from datetime import timedelta

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing.models import RouterVoucher, Voucher, VoucherDevice
from core.models import NetworkEvent
from core.tests.factories import make_owner, make_package, make_router
from radius import localsync

LAB = {"JAMIILITE_PUBLIC_URL": "http://10.0.2.2:8000", "JAMIILITE_AUTH_MODE": "local"}
MAC = "9C:2A:70:4C:14:E1"


@override_settings(**LAB)
class LocalSyncTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.router = make_router(self.owner, slug="demo", nas_identifier="wifi-majaribio")
        self.package = make_package(self.owner, rate_limit="1M/2M", shared_users=2)
        self.now = timezone.now()

    def voucher(self, **kwargs):
        return Voucher.objects.create(router=self.router, package=self.package, **kwargs)

    def test_new_voucher_is_pushed_with_profile_and_backstop_limit(self):
        voucher = self.voucher()
        lines = "\n".join(localsync.handle_report(self.router, {"jl": "0", "act": ""}, now=self.now))

        profile = f'"jl-{self.package.pk}"'
        self.assertIn(f"/ip hotspot user profile add name={profile}", lines)
        self.assertIn(f'/ip hotspot user profile set [find name={profile}] shared-users=2 rate-limit="1M/2M"', lines)
        self.assertIn(
            f'/ip hotspot user add name="{voucher.code}" password="{voucher.code}" profile={profile} '
            "limit-uptime=3600s comment=JamiiLite", lines,
        )
        self.assertTrue(RouterVoucher.objects.filter(router=self.router, voucher=voucher).exists())

    def test_voucher_is_pushed_once(self):
        self.voucher()
        localsync.handle_report(self.router, {"jl": "0"}, now=self.now)
        again = localsync.handle_report(self.router, {"jl": "1"}, now=self.now)
        self.assertEqual(again, [])

    def test_owner_vouchers_reach_all_his_routers(self):
        voucher = self.voucher()
        other = make_router(self.owner, name="Tawi", slug="tawi", nas_identifier="wifi-tawi")
        lines = "\n".join(localsync.handle_report(other, {"jl": "0"}, now=self.now))
        self.assertIn(voucher.code, lines)

    def test_other_owners_vouchers_are_not_pushed(self):
        stranger = make_owner(username="mwingine", business_name="Mwingine")
        Voucher.objects.create(router=make_router(stranger, slug="x"), package=make_package(stranger))
        self.assertEqual(localsync.handle_report(self.router, {"jl": "0"}, now=self.now), [])

    def test_expired_voucher_is_removed_and_user_kicked(self):
        voucher = self.voucher()
        localsync.handle_report(self.router, {"jl": "0"}, now=self.now)
        voucher.activated_at = self.now - timedelta(hours=2)
        voucher.expires_at = self.now - timedelta(hours=1)
        voucher.save()

        lines = localsync.handle_report(self.router, {"jl": "1"}, now=self.now)
        self.assertIn(f'/ip hotspot active remove [find user="{voucher.code}"]', lines)
        self.assertIn(f'/ip hotspot user remove [find name="{voucher.code}"]', lines)
        self.assertFalse(RouterVoucher.objects.filter(voucher=voucher).exists())

    def test_count_mismatch_triggers_full_resync(self):
        voucher = self.voucher()
        localsync.handle_report(self.router, {"jl": "0"}, now=self.now)
        # Router imewashwa upya bila vocha, au mtu amezifuta kwa mkono.
        lines = localsync.handle_report(self.router, {"jl": "0"}, now=self.now)
        self.assertEqual(lines[0], "/ip hotspot user remove [find comment=JamiiLite]")
        self.assertIn(voucher.code, "\n".join(lines))
        self.assertEqual(RouterVoucher.objects.filter(router=self.router).count(), 1)

    def test_old_report_without_count_does_not_resync(self):
        self.voucher()
        localsync.handle_report(self.router, {}, now=self.now)
        self.assertEqual(localsync.handle_report(self.router, {}, now=self.now), [])

    def test_pushes_are_capped_newest_first(self):
        vouchers = [self.voucher() for _ in range(localsync.MAX_PUSH + 3)]
        lines = "\n".join(localsync.handle_report(self.router, {"jl": "0"}, now=self.now))
        self.assertIn(vouchers[-1].code, lines)
        self.assertEqual(RouterVoucher.objects.count(), localsync.MAX_PUSH)
        rest = "\n".join(localsync.handle_report(self.router, {"jl": str(localsync.MAX_PUSH)}, now=self.now))
        self.assertEqual(rest.count("/ip hotspot user add"), 3)

    def test_unlimited_package_has_no_rate_limit(self):
        self.package.rate_limit = ""
        self.package.save()
        self.voucher()
        lines = "\n".join(localsync.handle_report(self.router, {"jl": "0"}, now=self.now))
        self.assertNotIn("rate-limit", lines)


@override_settings(**LAB)
class SessionTrackingTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.router = make_router(self.owner, slug="demo", nas_identifier="wifi-majaribio")
        self.voucher = Voucher.objects.create(router=self.router, package=make_package(self.owner))
        self.now = timezone.now()

    def report(self, act, now=None):
        pushed = RouterVoucher.objects.filter(router=self.router).count()
        localsync.handle_report(self.router, {"jl": str(pushed), "act": act}, now=now or self.now)
        self.router.refresh_from_db()
        self.voucher.refresh_from_db()

    def kinds(self):
        return list(NetworkEvent.objects.order_by("id").values_list("kind", flat=True))

    def test_parse_sessions_skips_garbage(self):
        sessions = localsync.parse_sessions(f"{self.voucher.code.lower()},{MAC.lower()},100,2000;bad;,x,1,2;")
        self.assertEqual(sessions, {(self.voucher.code, MAC): (2000, 100)})

    def test_first_sight_starts_calendar_time_and_remembers_device(self):
        self.report(f"{self.voucher.code},{MAC},10,20;")
        self.assertEqual(self.voucher.activated_at, self.now)
        self.assertEqual(self.voucher.expires_at, self.now + timedelta(hours=1))
        self.assertTrue(VoucherDevice.objects.filter(voucher=self.voucher, mac_address=MAC).exists())
        self.assertIn(f"{self.voucher.code}|{MAC}", self.router.active_sessions)
        self.assertEqual(self.kinds()[:2], [NetworkEvent.Kind.AUTH_ACCEPT, NetworkEvent.Kind.ACCT_START])

    def test_usage_is_recorded_every_five_minutes_and_stop_when_gone(self):
        act = f"{self.voucher.code},{MAC},1000000,8000000;"
        self.report(act)
        self.report(act, now=self.now + timedelta(minutes=1))
        self.assertNotIn(NetworkEvent.Kind.ACCT_UPDATE, self.kinds())

        self.report(act, now=self.now + timedelta(minutes=6))
        update = NetworkEvent.objects.filter(kind=NetworkEvent.Kind.ACCT_UPDATE).get()
        self.assertEqual(update.detail, "↓ 8.0 MB · ↑ 1.0 MB")

        self.report("", now=self.now + timedelta(minutes=7))
        self.assertEqual(self.kinds()[-1], NetworkEvent.Kind.ACCT_STOP)
        self.assertEqual(self.router.active_sessions, {})

    def test_unknown_users_are_ignored(self):
        self.report(f"admin,{MAC},1,1;")
        self.assertEqual(self.router.active_sessions, {})
        self.assertIsNone(self.voucher.activated_at)


@override_settings(**LAB)
class CheckinViewLocalTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.router = make_router(self.owner, slug="demo", nas_identifier="wifi-majaribio")
        self.voucher = Voucher.objects.create(router=self.router, package=make_package(self.owner))
        self.client = Client(enforce_csrf_checks=True)
        self.url = reverse("radius:checkin", args=[self.router.provision_token])

    def post(self, body):
        return self.client.post(self.url, body, content_type="application/x-www-form-urlencoded")

    def test_checkin_reply_carries_vouchers_and_reads_sessions(self):
        body = f"v=7.16&up=1h&users=1&jl=0&act={self.voucher.code},{MAC},5,6;"
        reply = self.post(body).content.decode()
        self.assertIn(f'/ip hotspot user add name="{self.voucher.code}"', reply)
        self.assertNotIn("#", reply.splitlines()[0])
        self.voucher.refresh_from_db()
        self.assertIsNotNone(self.voucher.activated_at)

    @override_settings(JAMIILITE_AUTH_MODE="radius")
    def test_radius_mode_sends_no_vouchers(self):
        reply = self.post("v=7.16&jl=0&act=").content.decode()
        self.assertNotIn("/ip hotspot user add", reply)
        self.assertFalse(RouterVoucher.objects.exists())
