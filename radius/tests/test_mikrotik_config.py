from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Router, RouterCommand
from core.tests.factories import make_owner, make_router
from radius import routeros

LAB = {"JAMIILITE_PUBLIC_URL": "http://10.0.2.2:8000", "RADIUS_PUBLIC_ADDRESS": "10.0.2.2"}


class RouterOSStringTests(TestCase):
    def test_escapes_quotes_dollars_backslashes_and_newlines(self):
        self.assertEqual(routeros.ros_string('a"b$c\\d\ne?'), '"a\\"b\\$c\\\\d\\r\\ne\\?"')


@override_settings(**LAB)
class SetupScriptTests(TestCase):
    def setUp(self):
        self.router = make_router(make_owner(), slug="demo", nas_identifier="wifi-majaribio")
        self.script = routeros.setup_script(self.router)

    def test_configures_radius_portal_and_checkin(self):
        script = self.script
        self.assertIn(':error "JamiiLite: hakuna hotspot', script)
        self.assertIn('/system identity set name="wifi-majaribio"', script)
        self.assertIn(f'address=10.0.2.2 secret="{self.router.radius_secret}"', script)
        self.assertIn("/radius remove [find comment=JamiiLite]", script)
        self.assertIn("login-by=http-pap", script)
        self.assertIn("walled-garden ip add dst-address=10.0.2.2 protocol=tcp dst-port=8000", script)
        self.assertIn('name~"hotspot/login.html\\$"', script)
        self.assertIn("url=http://10.0.2.2:8000/p/demo/\\?link-login-only=\\$(link-login-only-esc)", script)
        self.assertIn("/system scheduler add name=jamiilite-checkin interval=1m", script)

    def test_checkin_script_is_stored_with_escaped_variables(self):
        source_line = next(line for line in self.script.splitlines() if line.startswith("/system script add"))
        self.assertIn("\\$data", source_line)
        self.assertIn(f"/r/{self.router.provision_token}/checkin", source_line)
        self.assertIn("on-error", source_line)

    def test_provision_command_is_one_line(self):
        command = routeros.provision_command(self.router)
        self.assertNotIn("\n", command)
        self.assertEqual(
            command,
            f'/tool fetch url="http://10.0.2.2:8000/r/{self.router.provision_token}/setup.rsc" '
            'dst-path="jamiilite-setup.rsc"; /import file-name="jamiilite-setup.rsc"',
        )

    @override_settings(JAMIILITE_PUBLIC_URL="https://jamiilite.example.com/")
    def test_hostname_server_uses_dst_host_on_https(self):
        script = routeros.setup_script(self.router)
        self.assertIn("dst-host=jamiilite.example.com protocol=tcp dst-port=443", script)
        self.assertIn("url=https://jamiilite.example.com/p/demo/\\?", script)


@override_settings(**LAB)
class ProvisioningViewTests(TestCase):
    def setUp(self):
        self.router = make_router(make_owner(), slug="demo", nas_identifier="wifi-majaribio")
        self.setup_url = reverse("radius:setup_script", args=[self.router.provision_token])
        self.checkin_url = reverse("radius:checkin", args=[self.router.provision_token])
        # Router haitumi CSRF token, kwa hiyo majaribio yanalazimisha ukaguzi wa CSRF.
        self.client = Client(enforce_csrf_checks=True)

    def checkin(self, body="v=7.23.8 (long-term)&up=1d02:03:04&users=3"):
        return self.client.post(
            self.checkin_url, body, content_type="application/x-www-form-urlencoded"
        )

    def test_setup_script_is_served_as_text(self):
        response = self.client.get(self.setup_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertIn(self.router.radius_secret, response.content.decode())

    def test_unknown_token_and_inactive_router_get_404(self):
        self.assertEqual(self.client.get(reverse("radius:setup_script", args=["batili"])).status_code, 404)
        self.router.is_active = False
        self.router.save()
        self.assertEqual(self.client.get(self.setup_url).status_code, 404)
        self.assertEqual(self.checkin().status_code, 404)

    def test_checkin_records_status(self):
        self.assertFalse(self.router.is_online)

        response = self.checkin()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("/system reboot", response.content.decode())

        self.router.refresh_from_db()
        self.assertTrue(self.router.is_online)
        self.assertEqual(self.router.routeros_version, "7.23.8 (long-term)")
        self.assertEqual(self.router.uptime, "1d02:03:04")
        self.assertEqual(self.router.active_clients, 3)

    def test_router_goes_offline_after_silence(self):
        self.router.last_seen_at = timezone.now() - timezone.timedelta(minutes=4)
        self.assertFalse(self.router.is_online)

    def test_garbage_report_does_not_crash(self):
        self.assertEqual(self.checkin("users=mia&v=").status_code, 200)
        self.router.refresh_from_db()
        self.assertEqual(self.router.active_clients, 0)

    def test_pending_commands_are_delivered_once_with_reboot_last(self):
        RouterCommand.objects.create(router=self.router, action=RouterCommand.Action.REBOOT)
        RouterCommand.objects.create(router=self.router, action=RouterCommand.Action.REAPPLY_SETUP)

        script = self.checkin().content.decode()
        self.assertIn(f"/r/{self.router.provision_token}/setup.rsc", script)
        self.assertTrue(script.rstrip().endswith("/system reboot"))
        self.assertFalse(RouterCommand.objects.filter(delivered_at__isnull=True).exists())

        again = self.checkin().content.decode()
        self.assertNotIn("/system reboot", again)
        self.assertNotIn("setup.rsc", again)

    def test_checkin_requires_post(self):
        self.assertEqual(self.client.get(self.checkin_url).status_code, 405)


@override_settings(**LAB)
class MikrotikConfigCommandTests(TestCase):
    def run_command(self, *args):
        out = StringIO()
        call_command("mikrotik_config", *args, stdout=out)
        return out.getvalue()

    def test_prints_one_line_by_default_and_script_with_full(self):
        router = make_router(make_owner(), slug="demo", nas_identifier="wifi-majaribio")
        self.assertEqual(self.run_command("demo").strip(), routeros.provision_command(router))
        self.assertIn("/system scheduler add", self.run_command("demo", "--full"))

    def test_requires_nas_identifier(self):
        make_router(make_owner(), slug="bila")
        with self.assertRaises(CommandError):
            self.run_command("bila")


@override_settings(**LAB)
class RouterAdminTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("bosi", "bosi@example.com", "siri-ndefu-123")
        self.client.force_login(self.admin)
        self.router = make_router(make_owner(), slug="demo", nas_identifier="wifi-majaribio")

    def test_change_page_shows_setup_command(self):
        response = self.client.get(reverse("admin:core_router_change", args=[self.router.pk]))
        self.assertContains(response, f"/r/{self.router.provision_token}/setup.rsc")
        self.assertContains(response, "Offline")

    def test_reboot_action_queues_command(self):
        self.client.post(
            reverse("admin:core_router_changelist"),
            {"action": "send_reboot", "_selected_action": [self.router.pk]},
        )
        command = RouterCommand.objects.get()
        self.assertEqual(command.action, RouterCommand.Action.REBOOT)
        self.assertEqual(command.router, Router.objects.get(pk=self.router.pk))
