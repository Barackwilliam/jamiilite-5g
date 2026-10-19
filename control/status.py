"""
Ukaguzi wa "Hali ya mfumo" kwa Super Admin.

Kila ukaguzi unarudisha Check yenye hali moja kati ya ok / warn / bad / info,
pamoja na maelezo ya nini cha kufanya ikiwa kuna tatizo.
"""

import platform
import subprocess
import time
from dataclasses import dataclass, field
from datetime import timedelta

import django
from django.conf import settings
from django.db import connection
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from billing.models import Payment, Withdrawal
from core.models import Router, RouterCommand, ServiceHeartbeat

from .queries import online_q

SEVERITY = {"bad": 3, "warn": 2, "info": 1, "ok": 0}
LABELS = {"ok": "Sawa", "warn": "Angalia", "bad": "Tatizo", "info": "Taarifa"}
ICONS = {"ok": "check", "warn": "alert", "bad": "alert", "info": "shield"}

RADIUS_FRESH = timedelta(seconds=90)
RADIUS_STALE = timedelta(minutes=10)


@dataclass
class Check:
    key: str
    title: str
    state: str
    value: str
    detail: str = ""
    fix: str = ""
    facts: list = field(default_factory=list)

    @property
    def label(self):
        return LABELS[self.state]

    @property
    def icon(self):
        return ICONS[self.state]


def _minutes(delta):
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "chini ya dakika 1"
    if minutes < 120:
        return f"dakika {minutes}"
    if minutes < 48 * 60:
        return f"saa {minutes // 60}"
    return f"siku {minutes // 1440}"


def check_database():
    started = time.perf_counter()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 - tunataka kuonyesha kosa lolote
        return Check("database", "Database", "bad", "Haifikiki", str(exc)[:200])
    ms = (time.perf_counter() - started) * 1000
    name = {"postgresql": "PostgreSQL", "sqlite": "SQLite"}.get(connection.vendor, connection.vendor)
    state = "ok" if ms < 250 else "warn"
    facts = [("Aina", name), ("Muda wa kujibu", f"{ms:.0f} ms")]
    if connection.vendor == "sqlite":
        return Check(
            "database", "Database", "warn" if not settings.DEBUG else "info", name,
            "SQLite ni ya majaribio ya ndani tu.", "Weka DATABASE_URL ya Supabase kwenye .env.", facts,
        )
    return Check("database", "Database", state, f"{ms:.0f} ms", "Database inajibu.", "", facts)


def check_radius(now):
    beat = ServiceHeartbeat.objects.filter(name="radius").first()
    fix = "Washa server ya RADIUS: python manage.py radius_server (kwenye VPS iwe service ya systemd)."
    if beat is None:
        return Check(
            "radius", "RADIUS server", "bad", "Haijawahi kuripoti",
            "Bila RADIUS, wateja hawawezi kuingia kwa vocha.", fix,
        )
    age = now - beat.last_seen_at
    counts = beat.stats.get("counts", {})
    facts = [
        ("Ilianza", timezone.localtime(beat.started_at).strftime("%d/%m/%Y %H:%M")),
        ("Kompyuta", f"{beat.host} (pid {beat.pid})"),
        ("Ports", ", ".join(str(p) for p in beat.stats.get("ports", [])) or "—"),
        ("Zimekubaliwa", f"{counts.get('accept', 0):,}"),
        ("Zimekataliwa", f"{counts.get('reject', 0):,}"),
        ("Accounting", f"{counts.get('accounting', 0):,}"),
        ("Zimepuuzwa", f"{counts.get('ignored', 0):,}"),
    ]
    if age <= RADIUS_FRESH:
        return Check("radius", "RADIUS server", "ok", "Inafanya kazi", f"Iliripoti {_minutes(age)} iliyopita.", "", facts)
    state = "warn" if age <= RADIUS_STALE else "bad"
    return Check(
        "radius", "RADIUS server", state, "Imekaa kimya",
        f"Haijaripoti kwa {_minutes(age)}. Huenda imesimama.", fix, facts,
    )


def check_routers(now):
    active = Router.objects.filter(is_active=True, owner__is_active=True)
    total = active.count()
    online = active.filter(online_q(now)).count()
    never = active.filter(last_seen_at__isnull=True).count()
    facts = [("Zinazotumika", total), ("Online", online), ("Hazijawahi kuunganishwa", never),
             ("Zimezimwa na admin", Router.objects.filter(is_active=False).count())]
    if total == 0:
        return Check("routers", "Routers", "info", "Hakuna bado", "Hakuna router iliyoongezwa.", "", facts)
    connected = total - never
    if connected and online == 0:
        return Check(
            "routers", "Routers", "bad", f"0 / {total} online",
            "Hakuna router inayoripoti. Huenda server haifikiki kutoka kwa routers.",
            f"Hakikisha {settings.JAMIILITE_PUBLIC_URL} inafunguka kutoka mtandaoni.", facts,
        )
    return Check("routers", "Routers", "ok", f"{online} / {total} online", "Routers zinaripoti kila dakika.", "", facts)


def check_payments(now):
    provider = settings.PAYMENT_PROVIDER
    day = now - timedelta(hours=24)
    recent = Payment.objects.filter(created_at__gte=day)
    by_status = dict(recent.values_list("status").annotate(n=Count("pk")))
    stuck = Payment.objects.filter(status=Payment.Status.PENDING, created_at__lt=now - timedelta(minutes=15)).count()
    facts = [
        ("Mtoa huduma", provider),
        ("Saa 24: yamelipwa", by_status.get(Payment.Status.PAID, 0)),
        ("Saa 24: yameshindwa", by_status.get(Payment.Status.FAILED, 0)),
        ("Yamekwama (>dk 15)", stuck),
    ]
    if provider == "sandbox":
        if not settings.DEBUG:
            return Check(
                "payments", "Malipo", "bad", "Sandbox kwenye production",
                "Malipo yanakubaliwa bila pesa halisi: mtu yeyote anapata vocha bure.",
                "Weka PAYMENT_PROVIDER ya kweli na ALLOW_SANDBOX_PAYMENTS=False.", facts,
            )
        return Check(
            "payments", "Malipo", "info", "Sandbox (majaribio)",
            "Malipo ni ya kuigiza. Sawa kwa majaribio ya ndani.", "", facts,
        )
    failed = by_status.get(Payment.Status.FAILED, 0)
    paid = by_status.get(Payment.Status.PAID, 0)
    if stuck or (failed and failed >= paid):
        return Check(
            "payments", "Malipo", "warn", "Kuna malipo yenye shida",
            "Malipo mengi yameshindwa au yamekwama.", "Angalia akaunti ya mtoa huduma wa malipo.", facts,
        )
    return Check("payments", "Malipo", "ok", provider, "Malipo yanapita.", "", facts)


def check_storage():
    if settings.USE_SUPABASE_STORAGE:
        return Check(
            "storage", "Hifadhi ya picha", "ok", "Supabase Storage",
            f"Bucket: {settings.SUPABASE_STORAGE_BUCKET}", "", [("Bucket", settings.SUPABASE_STORAGE_BUCKET)],
        )
    return Check(
        "storage", "Hifadhi ya picha", "info", "Kompyuta hii (media/)",
        "Logo zinahifadhiwa ndani ya server. Sawa kwa majaribio.",
        "Weka SUPABASE_* kwenye .env kwa production.",
    )


def check_security():
    problems, facts = [], []
    if settings.DEBUG:
        problems.append("DEBUG imewashwa")
    if settings.SECRET_KEY == "dev-only-insecure-key":
        problems.append("SECRET_KEY ni ya majaribio")
    if not settings.RADIUS_REQUIRE_MESSAGE_AUTHENTICATOR:
        problems.append("Kinga ya BlastRADIUS imezimwa")
    if not settings.JAMIILITE_PUBLIC_URL.startswith("https://"):
        problems.append("Anwani ya umma haitumii https")
    facts = [
        ("DEBUG", "Imewashwa" if settings.DEBUG else "Imezimwa"),
        ("Message-Authenticator", "Inahitajika" if settings.RADIUS_REQUIRE_MESSAGE_AUTHENTICATOR else "Haihitajiki"),
        ("ALLOWED_HOSTS", ", ".join(settings.ALLOWED_HOSTS) or "—"),
    ]
    if not problems:
        return Check("security", "Usalama", "ok", "Sawa", "Mipangilio ya usalama ya production iko sawa.", "", facts)
    state = "warn" if settings.DEBUG else "bad"
    return Check(
        "security", "Usalama", state, f"Mambo {len(problems)} ya kuangalia", " · ".join(problems),
        "Kwenye VPS: DEBUG=False, SECRET_KEY ndefu ya siri, na https.", facts,
    )


def check_queues(now):
    stuck_commands = RouterCommand.objects.filter(
        delivered_at__isnull=True, created_at__lt=now - timedelta(minutes=10)
    ).count()
    old_withdrawals = Withdrawal.objects.filter(
        status=Withdrawal.Status.PENDING, created_at__lt=now - timedelta(hours=48)
    ).count()
    facts = [("Maagizo ya routers yaliyokwama", stuck_commands), ("Maombi ya pesa > saa 48", old_withdrawals)]
    if old_withdrawals:
        return Check(
            "queues", "Foleni", "warn", f"Maombi {old_withdrawals} yamechelewa",
            "Wamiliki wanasubiri pesa zao kwa zaidi ya saa 48.", "Fungua ukurasa wa Kutoa pesa.", facts,
        )
    if stuck_commands:
        return Check(
            "queues", "Foleni", "warn", f"Maagizo {stuck_commands} hayajafika",
            "Routers husika ziko offline, maagizo yatafika zikirudi.", "", facts,
        )
    return Check("queues", "Foleni", "ok", "Hakuna kilichokwama", "", "", facts)


def run_checks(now=None):
    now = now or timezone.now()
    checks = [
        check_radius(now), check_database(), check_routers(now), check_payments(now),
        check_security(), check_queues(now), check_storage(),
    ]
    # Matatizo kwanza; sorted ni stable, kwa hiyo mpangilio wa ndani unabaki.
    return sorted(checks, key=lambda c: -SEVERITY[c.state])


def overall(checks):
    return max(checks, key=lambda c: SEVERITY[c.state]).state if checks else "ok"


def radius_warnings():
    beat = ServiceHeartbeat.objects.filter(name="radius").first()
    items = beat.stats.get("warnings", []) if beat else []
    return [{"at": parse_datetime(w.get("at", "")), "message": w.get("message", "")} for w in items]


def _git_commit():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=settings.BASE_DIR,
            capture_output=True, text=True, timeout=2, check=True,
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "—"


def environment_facts():
    versions = (
        Router.objects.exclude(routeros_version="").values_list("routeros_version")
        .annotate(n=Count("pk")).order_by("-n")[:4]
    )
    return [
        ("Anwani ya umma", settings.JAMIILITE_PUBLIC_URL),
        ("Anwani ya RADIUS kwa routers", settings.RADIUS_PUBLIC_ADDRESS),
        ("Saa za mfumo", f"{settings.TIME_ZONE} · {timezone.localtime():%d/%m/%Y %H:%M}"),
        ("Toleo la msimbo (git)", _git_commit()),
        ("Django / Python", f"{django.get_version()} / {platform.python_version()}"),
        ("RouterOS kwenye routers", ", ".join(f"{v} ({n})" for v, n in versions) or "—"),
    ]
