"""Maswali ya takwimu za jukwaa zima kwa ajili ya Super Admin."""

from django.db.models import Case, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from billing.models import LedgerEntry, Withdrawal
from core.models import ONLINE_THRESHOLD, Owner, Router

STATE_LABELS = {
    "trial": _("Majaribio"),
    "paid": _("Amelipia"),
    "expired": _("Muda umeisha"),
    "suspended": _("Amesitishwa"),
}


def owners_with_state(now=None):
    """Owner queryset yenye `ends_at` na `state` (trial/paid/expired/suspended)."""
    now = now or timezone.now()
    # Greatest ya SQLite inarudisha NULL ikiwa moja ni NULL, kwa hiyo jaza kwanza.
    ends = Greatest(Coalesce("trial_ends_at", "paid_until"), Coalesce("paid_until", "trial_ends_at"))
    return Owner.objects.select_related("user").annotate(
        ends_at=ends,
        state=Case(
            When(is_active=False, then=Value("suspended")),
            When(paid_until__gt=now, then=Value("paid")),
            When(trial_ends_at__gt=now, then=Value("trial")),
            default=Value("expired"),
        ),
    )


def owner_counts(now=None):
    qs = owners_with_state(now)
    counts = {state: 0 for state in STATE_LABELS}
    for row in qs.values("state"):
        counts[row["state"]] += 1
    counts["total"] = sum(counts.values())
    return counts


def online_q(now=None):
    return Q(last_seen_at__gte=(now or timezone.now()) - ONLINE_THRESHOLD)


def router_counts(now=None):
    online = Router.objects.filter(online_q(now))
    total, online_count = Router.objects.count(), online.count()
    return {
        "total": total,
        "online": online_count,
        "offline": total - online_count,
        "clients": online.aggregate(n=Sum("active_clients"))["n"] or 0,
        "never": Router.objects.filter(last_seen_at__isnull=True).count(),
    }


def held_balance():
    """Pesa zote za wamiliki ambazo jukwaa linazishikilia sasa hivi."""
    return LedgerEntry.objects.aggregate(total=Sum("amount"))["total"] or 0


def pending_withdrawals():
    return Withdrawal.objects.filter(status=Withdrawal.Status.PENDING)


def owner_balances(owner_ids):
    rows = (
        LedgerEntry.objects.filter(owner_id__in=owner_ids)
        .values("owner_id")
        .annotate(total=Sum("amount"))
    )
    return {row["owner_id"]: row["total"] or 0 for row in rows}


def routers_offline_first(now=None):
    now = now or timezone.now()
    return Router.objects.select_related("owner").annotate(
        online=Case(When(online_q(now), then=Value(1)), default=Value(0)),
    ).order_by("online", F("last_seen_at").desc(nulls_last=True), "name")
