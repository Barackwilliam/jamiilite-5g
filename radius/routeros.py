"""
Kutengeneza script za RouterOS kwa kila router.

Mmiliki (au fundi) anabandika mstari mmoja tu (`provision_command`). Mstari
huo unapakua `setup_script` kutoka kwenye mfumo na kuuweka. Usanidi huo
unaweka RADIUS, ukurasa wa kulipia, na ripoti ya kila dakika (check-in)
ambayo inaleta maagizo kutoka mbali, kama reboot.
"""

import ipaddress
from urllib.parse import urlsplit

from django.conf import settings
from django.urls import reverse

from core.models import RouterCommand

COMMENT = "JamiiLite"
CHECKIN_NAME = "jamiilite-checkin"
SETUP_FILE = "jamiilite-setup.rsc"
COMMAND_FILE = "jamiilite-cmd.rsc"


def ros_string(value):
    """String ya RouterOS ndani ya alama za nukuu, ikiwa imeepushwa (escaped)."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("$", "\\$")
        .replace("?", "\\?")
        .replace("\r", "")
        .replace("\n", "\\r\\n")
    )
    return f'"{escaped}"'


def _base_url():
    return settings.JAMIILITE_PUBLIC_URL.rstrip("/")


def setup_url(router):
    return _base_url() + reverse("radius:setup_script", args=[router.provision_token])


def checkin_url(router):
    return _base_url() + reverse("radius:checkin", args=[router.provision_token])


def fetch_and_import(url, filename):
    return [
        f"/tool fetch url={ros_string(url)} dst-path={ros_string(filename)}",
        f"/import file-name={ros_string(filename)}",
    ]


def provision_command(router):
    """Mstari mmoja wa kubandika kwenye terminal ya MikroTik."""
    return "; ".join(fetch_and_import(setup_url(router), SETUP_FILE))


def _walled_garden_rule():
    parts = urlsplit(_base_url())
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        ipaddress.ip_address(parts.hostname)
        destination = f"dst-address={parts.hostname}"
    except ValueError:
        destination = f"dst-host={parts.hostname}"
    return f"/ip hotspot walled-garden ip add {destination} protocol=tcp dst-port={port} action=accept comment={COMMENT}"


def _login_html(router):
    portal = _base_url() + reverse("portal:home", args=[router.slug])
    # Vigezo vya $(...) vinajazwa na MikroTik yenyewe kabla ya kumtumia mteja.
    return (
        '<html><head><meta http-equiv="refresh" content="0; url='
        f"{portal}?link-login-only=$(link-login-only-esc)&link-orig=$(link-orig-esc)"
        '&mac=$(mac-esc)&ip=$(ip)&error=$(error-esc)"></head></html>'
    )


def checkin_source(router):
    """Script inayoendeshwa kila dakika: ripoti hali, kisha tekeleza maagizo yaliyopo."""
    return "\n".join(
        [
            ':local data ("v=" . [/system resource get version] . "&up=" . '
            '[/system resource get uptime] . "&users=" . [:len [/ip hotspot active find]])',
            ":do {",
            f"  /tool fetch url={ros_string(checkin_url(router))} http-method=post http-data=$data "
            f'http-header-field="Content-Type: application/x-www-form-urlencoded" '
            f"dst-path={ros_string(COMMAND_FILE)}",
            f"  /import file-name={ros_string(COMMAND_FILE)}",
            '} on-error={ :log warning "JamiiLite: imeshindwa kuripoti kwa mfumo" }',
        ]
    )


def setup_script(router):
    """Usanidi kamili wa router. Ni salama kuuendesha mara nyingi."""
    lines = [
        f"# JamiiLite 5G: usanidi wa {router.name}",
        ":if ([:len [/ip hotspot find]] = 0) do={ "
        ':error "JamiiLite: hakuna hotspot kwenye router hii. Weka hotspot kwanza." }',
        f"/system identity set name={ros_string(router.nas_identifier)}",
        f"/radius remove [find comment={COMMENT}]",
        f"/radius add service=hotspot address={settings.RADIUS_PUBLIC_ADDRESS} "
        f"secret={ros_string(router.radius_secret)} timeout=3s comment={COMMENT}",
        "/ip hotspot profile set [find] use-radius=yes login-by=http-pap "
        "radius-accounting=yes radius-interim-update=5m",
        f"/ip hotspot walled-garden ip remove [find comment={COMMENT}]",
        _walled_garden_rule(),
        # login.html iko "hotspot/" kwenye CHR, na "flash/hotspot/" kwenye routers zenye flash.
        ':foreach f in=[/file find where name~"hotspot/login.html\\$"] do={ '
        f"/file set $f contents={ros_string(_login_html(router))} }}",
        f"/system script remove [find name={CHECKIN_NAME}]",
        f"/system script add name={CHECKIN_NAME} source={ros_string(checkin_source(router))}",
        f"/system scheduler remove [find name={CHECKIN_NAME}]",
        f"/system scheduler add name={CHECKIN_NAME} interval=1m "
        f'on-event="/system script run {CHECKIN_NAME}"',
        ':log info "JamiiLite: usanidi umekamilika"',
        ':put "JamiiLite: usanidi umekamilika. Router itaripoti ndani ya dakika 1."',
    ]
    return "\n".join(lines) + "\n"


def command_script(commands):
    """Badilisha maagizo yanayosubiri kuwa script ambayo router itaitekeleza."""
    lines = ["# JamiiLite 5G: maagizo"]
    reboot = False
    for command in commands:
        if command.action == RouterCommand.Action.REAPPLY_SETUP:
            lines += [':log info "JamiiLite: inaweka upya usanidi"']
            lines += fetch_and_import(setup_url(command.router), SETUP_FILE)
        elif command.action == RouterCommand.Action.REBOOT:
            reboot = True
    if reboot:
        # Reboot iwe ya mwisho ili maagizo mengine yatekelezwe kwanza.
        lines += [':log info "JamiiLite: reboot kutoka mbali"', "/system reboot"]
    return "\n".join(lines) + "\n"
