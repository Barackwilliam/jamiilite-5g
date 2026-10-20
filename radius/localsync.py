"""
Njia ya "local": router inahifadhi vocha yenyewe, bila RADIUS server.

Kila ripoti ya router (check-in) inafanya mambo mawili:

1. Inasoma wateja walio online (vocha, MAC, data). Kutoka hapo tunajua vocha
   imeanza kutumika lini (muda wa kalenda unaanza), tunarekodi kifaa kwa ajili
   ya kuunganishwa tena, na tunaweka matukio kwenye ramani ya Live.
2. Inalinganisha vocha zilizo kwenye router na zinazopaswa kuwepo, kisha
   inarudisha amri za RouterOS: ongeza mpya, ondoa zilizoisha (na mkate mteja).
   Idadi ikitofautiana na tunavyojua, tunatuma orodha nzima upya, kwa hiyo
   router inajirekebisha yenyewe.
"""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from billing.models import RouterVoucher, Voucher, VoucherDevice
from core import events

from .routeros import COMMENT, ros_string

# Majibu ya check-in yanasomwa ndani ya kumbukumbu ya router (output=user), na
# RouterOS 6 inakubali hadi 4KB. Vocha za ziada zinatumwa kwenye ripoti zinazofuata.
MAX_PUSH = 15
MAX_SESSIONS = 500
USAGE_EVERY = timedelta(minutes=5)


def profile_name(package):
    return f"jl-{package.pk}"


def _normalize_mac(value):
    return (value or "").strip().upper().replace("-", ":")[:17]


def _int(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def parse_sessions(raw):
    """'VOCHA,MAC,bytes-in,bytes-out;...' -> {(VOCHA, MAC): (down, up)}."""
    sessions = {}
    for item in (raw or "").split(";")[:MAX_SESSIONS]:
        parts = item.split(",")
        if len(parts) != 4:
            continue
        code, mac = parts[0].strip().upper()[:16], _normalize_mac(parts[1])
        if not code:
            continue
        # bytes-in ni data kutoka kwa mteja (upload), bytes-out ni kwenda kwake (download).
        sessions[(code, mac)] = (_int(parts[3]), _int(parts[2]))
    return sessions


def _usage(down, up):
    return f"↓ {down / 1_000_000:.1f} MB · ↑ {up / 1_000_000:.1f} MB"


def record_sessions(router, sessions, now):
    """Vocha zilizo online: anza muda wake, kumbuka kifaa, na rekodi matukio."""
    previous = router.active_sessions if isinstance(router.active_sessions, dict) else {}
    codes = {code for code, _mac in sessions}
    vouchers = {
        v.code: v
        for v in Voucher.objects.select_related("package").filter(code__in=codes, router__owner=router.owner)
    }

    current = {}
    for (code, mac), (down, up) in sessions.items():
        voucher = vouchers.get(code)
        if voucher is None:
            continue  # mtumiaji asiye wa JamiiLite (mfano wa mmiliki mwenyewe)
        voucher.activate(now=now)
        if mac:
            device, created = VoucherDevice.objects.get_or_create(voucher=voucher, mac_address=mac)
            if not created:
                device.save(update_fields=["last_seen_at"])

        key = f"{code}|{mac}"
        before = previous.get(key)
        state = {"down": down, "up": up, "at": now.isoformat()}
        if before is None:
            events.record(router, events.Kind.AUTH_ACCEPT, mac=mac, detail=f"{voucher.package.name} · vocha {code[:4]}…")
            events.record(router, events.Kind.ACCT_START, mac=mac)
        else:
            last = parse_datetime(before.get("at", "")) if isinstance(before, dict) else None
            if last and now - last < USAGE_EVERY:
                state["at"] = before["at"]
            else:
                events.record(router, events.Kind.ACCT_UPDATE, mac=mac, detail=_usage(down, up))
        current[key] = state

    for key, before in previous.items():
        if key not in current:
            _code, _sep, mac = key.partition("|")
            usage = _usage(before.get("down", 0), before.get("up", 0)) if isinstance(before, dict) else ""
            events.record(router, events.Kind.ACCT_STOP, mac=mac, detail=usage)

    if current != previous:
        router.active_sessions = current
        router.save(update_fields=["active_sessions"])


def live_vouchers(router, now):
    """Vocha za mmiliki ambazo bado zina muda: zinapaswa kuwa kwenye kila router yake."""
    return (
        Voucher.objects.select_related("package")
        .filter(router__owner=router.owner)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    )


def _profile_lines(package):
    name = ros_string(profile_name(package))
    settings = f"shared-users={package.shared_users}"
    if package.rate_limit:
        settings += f" rate-limit={ros_string(package.rate_limit)}"
    return [
        f":if ([:len [/ip hotspot user profile find name={name}]] = 0) do={{ /ip hotspot user profile add name={name} }}",
        f"/ip hotspot user profile set [find name={name}] {settings}",
    ]


def _add_lines(voucher, now):
    code = ros_string(voucher.code)
    # Kinga ya ziada: router inamkata yenyewe hata ikikosa mawasiliano na mfumo.
    seconds = max(1, voucher.remaining_seconds(now=now))
    return [
        f"/ip hotspot user remove [find name={code}]",
        f":do {{ /ip hotspot user add name={code} password={code} profile={ros_string(profile_name(voucher.package))} "
        f'limit-uptime={seconds}s comment={COMMENT} }} on-error={{ :log warning "JamiiLite: vocha haikuongezwa" }}',
    ]


def _remove_lines(code):
    code = ros_string(code)
    return [
        f"/ip hotspot active remove [find user={code}]",
        f"/ip hotspot user remove [find name={code}]",
    ]


def sync_lines(router, reported_count, now):
    """Amri za kuifanya router iwe na vocha sahihi, na kurekebisha orodha yetu."""
    lines = []
    desired = {v.pk: v for v in live_vouchers(router, now)}
    pushed = dict(RouterVoucher.objects.filter(router=router).values_list("voucher_id", "voucher__code"))

    if reported_count is not None and reported_count != len(pushed):
        # Router haina tulichodhani (imewashwa upya, mtu amefuta vocha, amri ilishindwa).
        lines.append(f"/ip hotspot user remove [find comment={COMMENT}]")
        RouterVoucher.objects.filter(router=router).delete()
        pushed = {}

    expired = [pk for pk in pushed if pk not in desired]
    for pk in expired:
        lines += _remove_lines(pushed[pk])
    if expired:
        RouterVoucher.objects.filter(router=router, voucher_id__in=expired).delete()

    # Za karibuni kwanza: mteja aliyelipa sasa hivi asisubiri vocha za zamani.
    missing = sorted((v for pk, v in desired.items() if pk not in pushed), key=lambda v: v.created_at, reverse=True)
    batch = missing[:MAX_PUSH]
    profiles = {}
    for voucher in batch:
        profiles.setdefault(voucher.package.pk, voucher.package)
    for package in profiles.values():
        lines += _profile_lines(package)
    for voucher in batch:
        lines += _add_lines(voucher, now)
    RouterVoucher.objects.bulk_create(
        [RouterVoucher(router=router, voucher=v, pushed_at=now) for v in batch], ignore_conflicts=True
    )

    if batch or expired:
        parts = []
        if batch:
            parts.append(f"vocha zimetumwa: {len(batch)}")
        if expired:
            parts.append(f"zimeondolewa: {len(expired)}")
        events.record(router, events.Kind.COMMAND, detail=" · ".join(parts))
    return lines


def handle_report(router, report, now=None):
    """Shughulikia ripoti moja ya router; rudisha amri za kuongeza kwenye jibu."""
    now = now or timezone.now()
    if "act" in report:
        record_sessions(router, parse_sessions(report.get("act", "")), now)
    reported = report.get("jl")
    reported_count = _int(reported) if reported not in (None, "") else None
    return sync_lines(router, reported_count, now)


def is_on_router(voucher, router, settle=timedelta(seconds=2)):
    """Je, router imeshapokea vocha hii (na imepata muda wa kuiweka)?"""
    return RouterVoucher.objects.filter(
        router=router, voucher=voucher, pushed_at__lte=timezone.now() - settle
    ).exists()
