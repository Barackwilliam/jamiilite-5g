from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import RouterCommand
from core.tests.factories import make_owner, make_router
from radius import routeros

HTTPS = {"JAMIILITE_PUBLIC_URL": "https://jamiilite.example.com"}
LAB = {"JAMIILITE_PUBLIC_URL": "http://10.0.2.2:8000"}


@override_settings(**HTTPS)
class RouterTlsTests(TestCase):
    def setUp(self):
        self.router = make_router(make_owner(), slug="duka", nas_identifier="jl-duka")

    def test_checkin_verifies_the_server_once_roots_are_installed(self):
        source = routeros.checkin_source(self.router)
        self.assertIn('trusted=yes]] > 0) do={ :set cc "yes-without-crl" }', source)
        self.assertIn("/checkin\" check-certificate=$cc http-method=post", source)

    def test_setup_checks_version_then_clock_then_roots(self):
        lines = routeros.setup_script(self.router).splitlines()
        self.assertIn("< 7) do={ :error", lines[1])
        self.assertIn("/system ntp client set enabled=yes", lines[2])
        script = "\n".join(lines)
        fetch = script.index('/r/ca.pem" check-certificate=$cc dst-path="jamiilite-ca.pem"')
        replace = script.index(':if ([:len [/file find name="jamiilite-ca.pem"]] > 0) do={ /certificate remove')
        self.assertLess(fetch, replace)
        self.assertLess(replace, script.index("/system script add name=jamiilite-checkin"))

    def test_paste_line_and_remote_reapply_verify_when_they_can(self):
        command = routeros.provision_command(self.router)
        self.assertTrue(command.startswith('{ :local cc "no";'))
        self.assertIn("setup.rsc\" check-certificate=$cc", command)
        reply = routeros.command_script([RouterCommand(router=self.router, action=RouterCommand.Action.REAPPLY_SETUP)])
        self.assertLess(reply.index(':local cc "no"'), reply.index("check-certificate=$cc"))

    def test_roots_are_served_without_comments(self):
        response = self.client.get(reverse("radius:trust_roots"))
        body = response.content.decode()
        self.assertEqual(body.count("-----BEGIN CERTIFICATE-----"), 5)
        self.assertNotIn("#", body)


@override_settings(**LAB)
class LabWithoutTlsTests(TestCase):
    def test_plain_http_lab_has_no_certificate_steps(self):
        router = make_router(make_owner(), slug="duka", nas_identifier="jl-duka")
        script = routeros.setup_script(router) + routeros.checkin_source(router) + routeros.provision_command(router)
        self.assertNotIn("check-certificate", script)
        self.assertNotIn("/certificate", script)


class VersionTests(TestCase):
    def test_reported_versions(self):
        self.assertTrue(routeros.version_supported("7.16.1 (stable)"))
        self.assertTrue(routeros.version_supported("7.15"))
        self.assertFalse(routeros.version_supported("7.14.3 (stable)"))
        self.assertFalse(routeros.version_supported("6.49.10 (long-term)"))
        self.assertIsNone(routeros.version_supported(""))
