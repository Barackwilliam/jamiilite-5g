"""
Kutengeneza script za RouterOS kwa kila router.

Mmiliki (au fundi) anabandika mstari mmoja tu (`provision_command`). Mstari
huo unapakua `setup_script` kutoka kwenye mfumo na kuuweka. Usanidi huo
unaweka ukurasa wa kulipia, uthibitishaji wa vocha (ndani ya router, au kwa
RADIUS), na ripoti ya router (check-in) inayoleta vocha na maagizo kutoka mbali.
"""

import ipaddress
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

from core.models import RouterCommand

COMMENT = "JamiiLite"
CHECKIN_NAME = "jamiilite-checkin"
SETUP_FILE = "jamiilite-setup.rsc"
HOTSPOT_NAME = "jamiilite"
OPEN_PROFILE = "jamiilite-open"
CA_FILE = "jamiilite-ca.pem"
# Vyeti vinavyoingizwa kutoka CA_FILE vinapewa majina yanayoanza hivi ("jamiilite-ca.pem_0"...).
CA_NAME_PATTERN = "^jamiilite-ca"
MIN_ROUTEROS = (7, 15)


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


def ca_url():
    return _base_url() + reverse("radius:trust_roots")


def _verifies_tls():
    return _base_url().startswith("https://")


def _cert_check_lines():
    """
    Weka $cc: router inahakiki cheti cha server ikishakuwa na vyeti vya JamiiLite.
    Bila hakiki, mtu aliye katikati ya mtandao angeweza kuituma router amri zake.
    "no" ni kwa router ambayo bado haijapata vyeti (usanidi wa kwanza tu).
    """
    return [
        ':local cc "no"',
        f':if ([:len [/certificate find where name~"{CA_NAME_PATTERN}" trusted=yes]] > 0) do={{ :set cc "yes-without-crl" }}',
    ]


def _fetch(url, extra):
    check = " check-certificate=$cc" if _verifies_tls() else ""
    return f"/tool fetch url={ros_string(url)}{check} {extra}"


def fetch_and_import(url, filename):
    """Pakua script na uiendeshe. Mistari hii inaendeshwa pamoja (:parse), kwa hiyo $cc inaonekana."""
    lines = _cert_check_lines() if _verifies_tls() else []
    return lines + [
        _fetch(url, f"dst-path={ros_string(filename)}"),
        f"/import file-name={ros_string(filename)}",
    ]


def _one_line(lines):
    """Kwenye /import kila mstari unaendeshwa peke yake; {...} inaweka $cc na fetch pamoja."""
    return "{ " + "; ".join(lines) + " }"


def _version_guard():
    major, minor = MIN_ROUTEROS
    message = (
        f"JamiiLite: inahitaji RouterOS {major}.{minor} au zaidi. "
        "Sasisha kwanza: System > Packages > Check For Updates, kisha bandika mstari tena."
    )
    return [
        f":if ([:tonum [:pick [/system resource get version] 0 1]] < {major}) do={{ :error {ros_string(message)} }}",
    ]


def _clock_lines():
    """Cheti kinahakikiwa kwa tarehe, kwa hiyo saa ya router lazima iwe sahihi."""
    commands = [
        "/system ntp client set enabled=yes servers=time.google.com,time.cloudflare.com,pool.ntp.org",
        "/ip cloud set update-time=yes",
    ]
    return [f":do {{ :local run [:parse {ros_string(c)}]; $run }} on-error={{}}" for c in commands]


def _trust_lines():
    """
    Pakua vyeti vya msingi (Let's Encrypt, Google) na uviamini. Router yenye vyeti
    vya zamani inavitumia kuhakiki upakuaji huu pia, kwa hiyo mtu hawezi kuweka vyake.
    """
    if not _verifies_tls():
        return []
    pattern = ros_string(CA_NAME_PATTERN)
    ca_file = ros_string(CA_FILE)
    # Vyeti vya zamani vinaondolewa tu kama vipya vimepakuliwa: upakuaji ukizuiwa,
    # router inabaki na vyeti ilivyonavyo badala ya kurudi bila hakiki.
    replace = [
        f"/certificate remove [find where name~{pattern}]",
        f'/certificate import file-name={ca_file} passphrase=""',
        f"/certificate set [find where name~{pattern}] trusted=yes",
        f"/file remove [find name={ca_file}]",
    ]
    return [
        f"/file remove [find name={ca_file}]",
        _one_line(_cert_check_lines() + [_fetch(ca_url(), f"dst-path={ca_file}")]),
        f":if ([:len [/file find name={ca_file}]] > 0) do={{ " + "; ".join(replace) + " }",
    ]


def version_supported(version):
    """True kama toleo lililoripotiwa (mfano "7.16.1 (stable)") linatosha; None kama halijulikani."""
    head = (version or "").split(" ")[0]
    try:
        parts = tuple(int(p) for p in head.split(".")[:2])
    except ValueError:
        return None
    if not parts:
        return None
    return parts + (0,) * (2 - len(parts)) >= MIN_ROUTEROS


def provision_command(router):
    """Mstari mmoja wa kubandika kwenye terminal ya MikroTik."""
    lines = fetch_and_import(setup_url(router), SETUP_FILE)
    return _one_line(lines) if _verifies_tls() else "; ".join(lines)


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


def _payment_hosts():
    """Ukurasa wa malipo (mfano Pesapal) lazima ufunguke kabla mteja hajalipa."""
    from billing.providers import get_provider

    try:
        return get_provider().walled_garden_hosts()
    except ImproperlyConfigured:
        return []


def walled_garden_rules():
    """
    Anwani ambazo mteja anaweza kufungua kabla ya kulipa: ukurasa wetu wa
    kulipia, picha (logo) zilizo Supabase, na hosts za ziada za malipo.
    """
    destinations = [_destination(_base_url())]
    if settings.USE_SUPABASE_STORAGE:
        destinations.append((f"{settings.SUPABASE_PROJECT_REF}.supabase.co", 443))
    destinations += [(host, 443) for host in _payment_hosts()]
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
        f"  /ip hotspot profile add name={HOTSPOT_NAME} hotspot-address=$gw login-by=http-pap use-radius={_use_radius()}",
        f"  /ip hotspot add name={HOTSPOT_NAME} interface={interface} profile={HOTSPOT_NAME} address-pool=none disabled=no",
        # Router inatengeneza faili za ukurasa (hotspot/login.html...) ikiwasha hotspot.
        "  :delay 3s",
        '  :log info "JamiiLite: hotspot mpya imewekwa"',
        "}",
    ]


def _use_radius():
    return "yes" if settings.JAMIILITE_AUTH_MODE == "radius" else "no"


def _auth_lines(router):
    """Router inathibitisha vocha kwa RADIUS, au kwa vocha zilizo ndani yake (local)."""
    lines = [f"/radius remove [find comment={COMMENT}]"]
    if settings.JAMIILITE_AUTH_MODE == "radius":
        lines += [
            f"/radius add service=hotspot address={settings.RADIUS_PUBLIC_ADDRESS} "
            f"secret={ros_string(router.radius_secret)} timeout=3s comment={COMMENT}",
            "/ip hotspot profile set [find] use-radius=yes login-by=http-pap "
            "radius-accounting=yes radius-interim-update=5m",
        ]
    else:
        lines += ["/ip hotspot profile set [find] use-radius=no login-by=http-pap"]
    return lines


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
    """
    Script ya ripoti: tuma hali ya router na wateja walio online, kisha tekeleza
    jibu (vocha na maagizo). Jibu linasomwa kwenye kumbukumbu (output=user) badala
    ya faili, ili ripoti za mara kwa mara zisichakaze flash ya router.
    """
    return "\n".join(
        [
            ':local act ""',
            ":foreach a in=[/ip hotspot active find] do={ :set act ($act . "
            "[/ip hotspot active get $a user] . \",\" . [/ip hotspot active get $a mac-address] . \",\" . "
            "[/ip hotspot active get $a bytes-in] . \",\" . [/ip hotspot active get $a bytes-out] . \";\") }",
            ':local data ("v=" . [/system resource get version] . "&up=" . '
            '[/system resource get uptime] . "&users=" . [:len [/ip hotspot active find]] . '
            f'"&jl=" . [:len [/ip hotspot user find comment={COMMENT}]] . "&act=" . $act)',
            *(_cert_check_lines() if _verifies_tls() else []),
            ":do {",
            "  :local r ["
            + _fetch(
                checkin_url(router),
                'http-method=post http-data=$data '
                'http-header-field="Content-Type: application/x-www-form-urlencoded" output=user as-value',
            )
            + "]",
            '  :local run [:parse ($r->"data")]',
            "  $run",
            '} on-error={ :log warning "JamiiLite: imeshindwa kuripoti kwa mfumo" }',
        ]
    )


def setup_script(router):
    """Usanidi kamili wa router. Ni salama kuuendesha mara nyingi."""
    lines = [
        # Jina linaandikwa na mmiliki: mstari mpya ndani yake ungekuwa amri mpya kwenye script.
        f"# JamiiLite 5G: usanidi wa {' '.join(router.name.split())}",
        *_version_guard(),
        *_clock_lines(),
        *_trust_lines(),
        *_create_hotspot_if_missing(),
        f"/system identity set name={ros_string(router.nas_identifier or f'jl-{router.slug}')}",
        # Wateja ambao bado hawajalipa wanatumia DNS ya router.
        "/ip dns set allow-remote-requests=yes",
        *_auth_lines(router),
        f"/ip hotspot walled-garden ip remove [find comment={COMMENT}]",
        *walled_garden_rules(),
        # login.html iko "hotspot/" kwenye CHR, na "flash/hotspot/" kwenye routers zenye flash.
        ':foreach f in=[/file find where name~"hotspot/login.html\\$"] do={ '
        f"/file set $f contents={ros_string(_login_html(router))} }}",
        *_wifi_name_lines(router),
        f"/system script remove [find name={CHECKIN_NAME}]",
        f"/system script add name={CHECKIN_NAME} source={ros_string(checkin_source(router))}",
        f"/system scheduler remove [find name={CHECKIN_NAME}]",
        f"/system scheduler add name={CHECKIN_NAME} interval={settings.JAMIILITE_CHECKIN_SECONDS}s "
        f'on-event="/system script run {CHECKIN_NAME}"',
        ':log info "JamiiLite: usanidi umekamilika"',
        ':put "JamiiLite: usanidi umekamilika. Router itaripoti ndani ya sekunde chache."',
    ]
    return "\n".join(lines) + "\n"


def command_script(commands, sync=()):
    """
    Jibu la ripoti: amri za vocha (njia ya local), kisha maagizo yanayosubiri.
    Linaendeshwa kwa :parse, kwa hiyo halina maoni (#) wala mistari tupu.
    """
    lines = list(sync)
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
