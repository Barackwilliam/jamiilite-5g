from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from core.tests.factories import make_owner, make_router


class MikrotikConfigTests(TestCase):
    def run_command(self, *args):
        out = StringIO()
        call_command("mikrotik_config", *args, stdout=out)
        return out.getvalue()

    def test_prints_commands_for_virtualbox_lab(self):
        router = make_router(make_owner(), slug="demo", nas_identifier="wifi-majaribio")
        output = self.run_command("demo")

        self.assertIn("/system identity set name=wifi-majaribio", output)
        self.assertIn(f'address=10.0.2.2 secret="{router.radius_secret}"', output)
        self.assertIn("login-by=http-pap", output)
        self.assertIn("walled-garden ip add dst-address=10.0.2.2 protocol=tcp dst-port=8000", output)
        self.assertIn("url=http://10.0.2.2:8000/p/demo/?link-login-only=\\$(link-login-only-esc)", output)

    def test_hostname_portal_uses_dst_host(self):
        make_router(make_owner(), slug="duka", nas_identifier="duka")
        output = self.run_command("duka", "--portal-base", "https://jamiilite.example.com/")

        self.assertIn("dst-host=jamiilite.example.com protocol=tcp dst-port=443", output)
        self.assertIn("url=https://jamiilite.example.com/p/duka/?", output)

    def test_requires_nas_identifier(self):
        make_router(make_owner(), slug="bila")
        with self.assertRaises(CommandError):
            self.run_command("bila")
