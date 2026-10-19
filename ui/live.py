"""
Data ya ramani ya "Live": matukio mapya tangu `since`, hali ya routers, na
takwimu za leo. Inatumiwa na dashboard ya mmiliki na ya Super Admin.
"""

from django.conf import settings
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.utils import timezone

from billing.models import Payment
from core.models import ONLINE_THRESHOLD, NetworkEvent
from dashboard.stats import local_day_start

FIRST_LOAD = 15  # matukio ya karibuni ya kujaza log mara ya kwanza
MAX_BATCH = 150
MAX_ROUTERS = 30

PROVIDER_LABELS = {"sandbox": "Malipo (majaribio)"}


def _mac_tail(mac):
    return f"…{mac[-5:]}" if mac else ""


def _event(e):
    return {
        "id": e.id,
        "kind": e.kind,
        "label": e.get_kind_display(),
        "router": e.router_id,
        "router_name": e.router.name,
        "device": _mac_tail(e.mac),
        "detail": e.detail,
        "amount": e.amount,
        "at": int(e.created_at.timestamp() * 1000),
    }


def _router(r, now):
    online = bool(r.last_seen_at and now - r.last_seen_at <= ONLINE_THRESHOLD)
    return {
        "id": r.id,
        "name": r.name,
        "owner": r.owner.business_name,
        "online": online,
        "clients": r.active_clients if online else 0,
        "seen": int(r.last_seen_at.timestamp() * 1000) if r.last_seen_at else None,
    }


def payload(request, routers, events, payments, show_owner=False):
    """`routers`, `events` na `payments` ni querysets zilizochujwa kwa mwenye haki."""
    now = timezone.now()
    try:
        since = int(request.GET.get("since", ""))
    except ValueError:
        since = None

    events = events.select_related("router")
    if since is None:
        batch = list(events.order_by("-id")[:FIRST_LOAD])[::-1]
    else:
        batch = list(events.filter(id__gt=since).order_by("id")[:MAX_BATCH])
    cursor = batch[-1].id if batch else (since if since is not None else 0)

    today = local_day_start(now)
    counts = events.filter(created_at__gte=today).aggregate(
        accepts=Count("pk", filter=Q(kind=NetworkEvent.Kind.AUTH_ACCEPT)),
        rejects=Count("pk", filter=Q(kind=NetworkEvent.Kind.AUTH_REJECT)),
    )
    sales = payments.filter(status=Payment.Status.PAID, paid_at__gte=today).aggregate(
        amount=Sum("amount"), count=Count("pk")
    )
    router_rows = [
        _router(r, now)
        for r in routers.select_related("owner").order_by(F("last_seen_at").desc(nulls_last=True), "name")[:MAX_ROUTERS]
    ]
    return JsonResponse({
        "now": int(now.timestamp() * 1000),
        "cursor": cursor,
        "backfill": since is None,
        "events": [_event(e) for e in batch],
        "routers": router_rows,
        "router_total": routers.count(),
        "show_owner": show_owner,
        "gateway": PROVIDER_LABELS.get(settings.PAYMENT_PROVIDER, settings.PAYMENT_PROVIDER.title()),
        "stats": {
            "today_amount": sales["amount"] or 0,
            "today_count": sales["count"] or 0,
            "accepts": counts["accepts"],
            "rejects": counts["rejects"],
            "clients": sum(r["clients"] for r in router_rows),
            "online": sum(1 for r in router_rows if r["online"]),
        },
    })
