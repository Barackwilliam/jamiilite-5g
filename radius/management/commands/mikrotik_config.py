import ipaddress
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from core.models import Router

# Vigezo vya MikroTik vinaanza na "$", ambayo kwenye RouterOS console lazima
# iandikwe "\$" ndani ya string.
LOGIN_HTML = (
    '<html><head><meta http-equiv=\\"refresh\\" content=\\"0; url={portal}'
    "?link-login-only=\\$(link-login-only-esc)&link-orig=\\$(link-orig-esc)"
    '&mac=\\$(mac-esc)&ip=\\$(ip)&error=\\$(error-esc)\\"></head></html>'
)


class Command(BaseCommand):
    help = "Chapisha amri za RouterOS za kuunganisha MikroTik na JamiiLite 5G."

    def add_arguments(self, parser):
        parser.add_argument("slug", help="Kitambulisho cha router, mfano demo")
        parser.add_argument(
            "--radius-address",
            default="10.0.2.2",
            help="IP ya RADIUS server kama MikroTik inavyoiona (VirtualBox NAT: 10.0.2.2)",
        )
        parser.add_argument(
            "--portal-base",
            default="http://10.0.2.2:8000",
            help="Anwani ya mfumo kama mteja anavyoiona, bila / mwishoni",
        )

    def handle(self, *args, slug, radius_address, portal_base, **options):
        router = Router.objects.filter(slug=slug).first()
        if router is None:
            raise CommandError(f"Hakuna router yenye kitambulisho '{slug}'.")
        if not router.nas_identifier:
            raise CommandError(
                "Router hii haina NAS identifier. Iweke kwenye admin, iwe sawa na /system identity ya MikroTik."
            )

        portal_base = portal_base.rstrip("/")
        parts = urlsplit(portal_base)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise CommandError("--portal-base iwe kama http://10.0.2.2:8000 au https://jamiilite.example.com")
        port = parts.port or (443 if parts.scheme == "https" else 80)
        portal_url = portal_base + reverse("portal:home", args=[router.slug])

        try:
            ipaddress.ip_address(parts.hostname)
            destination = f"dst-address={parts.hostname}"
        except ValueError:
            destination = f"dst-host={parts.hostname}"

        lines = [
            f"# JamiiLite 5G: {router}",
            f"/system identity set name={router.nas_identifier}",
            f'/radius add service=hotspot address={radius_address} secret="{router.radius_secret}" '
            "timeout=3s comment=JamiiLite",
            "/ip hotspot profile set [find] use-radius=yes login-by=http-pap "
            "radius-accounting=yes radius-interim-update=5m",
            f"/ip hotspot walled-garden ip add {destination} protocol=tcp dst-port={port} "
            "action=accept comment=JamiiLite",
            f'/file set hotspot/login.html contents="{LOGIN_HTML.format(portal=portal_url)}"',
        ]
        self.stdout.write("\n".join(lines))
