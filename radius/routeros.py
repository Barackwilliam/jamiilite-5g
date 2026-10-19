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
HOTSPOT_NAME = "jamiilite"
OPEN_PROFILE = "jamiilite-open"
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


def _destination(url):
    """(host-au-IP, port) ya URL, kwa ajili ya walled garden."""
    parts = urlsplit(url if "//" in url else f"https://{url}")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return parts.hostname, port


def _walled_garden_rule(host, port):
    try:
        ipaddress.ip_address(host)
        destination = f"dst-address={host}"
    except ValueError:
        destination = f"dst-host={ros_string(host)}"
    return f"/ip hotspot walled-garden ip add {destination} protocol=tcp dst-port={port} action=accept comment={COMMENT}"


def walled_garden_rules():
    """
    Anwani ambazo mteja anaweza kufungua kabla ya kulipa: ukurasa wetu wa
    kulipia, picha (logo) zilizo Supabase, na hosts za ziada za malipo.
    """
    destinations = [_destination(_base_url())]
    if settings.USE_SUPABASE_STORAGE:
        destinations.append((f"{settings.SUPABASE_PROJECT_REF}.supabase.co", 443))
    destinations += [_destination(host) for host in settings.JAMIILITE_WALLED_GARDEN_EXTRA]
    unique = list(dict.fromkeys(destinations))
    return [_walled_garden_rule(host, port) for host, port in unique]


def _create_hotspot_if_missing():
    """
    Router mpya (default config) haina hotspot. Tunaiweka kwenye bridge ya LAN
    ili mmiliki asihitaji kupitia "Hotspot Setup" mwenyewe.
    """
    interface = ros_string(settings.JAMIILITE_HOTSPOT_INTERFACE)
    missing = (
        ':error "JamiiLite: hakuna hotspot, na interface '
        + settings.JAMIILITE_HOTSPOT_INTERFACE.replace('"', "")
        + ' haina IP. Weka hotspot kwa mkono (IP > Hotspot > Hotspot Setup) kisha jaribu tena."'
    )
    return [
        ":if ([:len [/ip hotspot find]] = 0) do={",
        f"  :local lan [/ip address find where interface={interface} disabled=no]",
        f"  :if ([:len $lan] = 0) do={{ {missing} }}",
        "  :local cidr [/ip address get [:pick $lan 0] address]",
        '  :local gw [:pick $cidr 0 [:find $cidr "/"]]',
        f"  /ip hotspot profile remove [find name={HOTSPOT_NAME}]",
        f"  /ip hotspot profile add name={HOTSPOT_NAME} hotspot-address=$gw login-by=http-pap use-radius=yes",
        f"  /ip hotspot add name={HOTSPOT_NAME} interface={interface} profile={HOTSPOT_NAME} address-pool=none disabled=no",
        # Router inatengeneza faili za ukurasa (hotspot/login.html...) ikiwasha hotspot.
        "  :delay 3s",
        '  :log info "JamiiLite: hotspot mpya imewekwa"',
        "}",
    ]


def _wifi_name_lines(router):
    """
    Weka jina la WiFi na uifanye wazi (bila password), kama WiFi za kulipia
    mtaani: mteja anagusa jina, na ukurasa wa kulipia unafunguka wenyewe.

    Amri zinapitia :parse kwa sababu router zina kifurushi kimoja kati ya
    "wireless" (hAP lite, hAP ac lite...) na "wifi" (hAP ax...), na amri ya
    menyu isiyokuwepo ingevunja script nzima.
    """
    if not router.wifi_name:
        return []
    ssid = ros_string(router.wifi_name)
    commands = [
        # Kifurushi cha "wireless": badilisha AP tu, si interface inayotumika kupokea internet.
        f"/interface wireless security-profiles remove [find name={OPEN_PROFILE}]",
        f"/interface wireless security-profiles add name={OPEN_PROFILE} mode=none",
        f"/interface wireless set [find where mode=ap-bridge] ssid={ssid} security-profile={OPEN_PROFILE}",
    ]
    wifi_package = (
        f'/interface wifi set [find where configuration.mode="ap"] configuration.ssid={ssid} '
        'security.authentication-types=""'
    )
    lines = []
    for command in commands + [wifi_package]:
        lines.append(f":do {{ :local run [:parse {ros_string(command)}]; $run }} on-error={{}}")
    lines.append(f':log info ("JamiiLite: jina la WiFi ni " . {ssid})')
    return lines


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
        *_create_hotspot_if_missing(),
        f"/system identity set name={ros_string(router.nas_identifier)}",
        # Wateja ambao bado hawajalipa wanatumia DNS ya router.
        "/ip dns set allow-remote-requests=yes",
        f"/radius remove [find comment={COMMENT}]",
        f"/radius add service=hotspot address={settings.RADIUS_PUBLIC_ADDRESS} "
        f"secret={ros_string(router.radius_secret)} timeout=3s comment={COMMENT}",
        "/ip hotspot profile set [find] use-radius=yes login-by=http-pap "
        "radius-accounting=yes radius-interim-update=5m",
        f"/ip hotspot walled-garden ip remove [find comment={COMMENT}]",
        *walled_garden_rules(),
        # login.html iko "hotspot/" kwenye CHR, na "flash/hotspot/" kwenye routers zenye flash.
        ':foreach f in=[/file find where name~"hotspot/login.html\\$"] do={ '
        f"/file set $f contents={ros_string(_login_html(router))} }}",
        *_wifi_name_lines(router),
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
