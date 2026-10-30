from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from billing.models import Payment

def local_day_start(now=None):
    local = timezone.localtime(now or timezone.now())
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def sales_summary(payments, now=None):
    """Mauzo ya leo, siku 7 na siku 30, pamoja na vipindi vilivyotangulia kwa kulinganisha."""
    now = now or timezone.now()
    paid = payments.filter(status=Payment.Status.PAID)
    today = local_day_start(now)
    periods = {
        "today": Q(paid_at__gte=today),
        "yesterday": Q(paid_at__gte=today - timedelta(days=1), paid_at__lt=today),
        # Jana mpaka saa hii hii: leo saa 3 asubuhi inalinganishwa na jana saa 3, si siku nzima.
        "yesterday_so_far": Q(paid_at__gte=today - timedelta(days=1), paid_at__lt=now - timedelta(days=1)),
        "week": Q(paid_at__gte=now - timedelta(days=7)),
        "prev_week": Q(paid_at__gte=now - timedelta(days=14), paid_at__lt=now - timedelta(days=7)),
        "month": Q(paid_at__gte=now - timedelta(days=30)),
    }
    result = paid.aggregate(
        **{f"{name}_amount": Sum("amount", filter=q) for name, q in periods.items()},
        **{f"{name}_count": Count("pk", filter=q) for name, q in periods.items()},
    )
    return {key: value or 0 for key, value in result.items()}


def trend(current, previous):
    """Mabadiliko kwa asilimia, au None ikiwa hakuna cha kulinganisha."""
    if not previous:
        return None
    pct = round((current - previous) * 100 / previous)
    return {"pct": abs(pct), "up": pct >= 0}


def top_by(payments, field, days=30, limit=5, now=None):
    """Orodha ya [{label, total, count, share}] kwa siku `days`, kubwa kwanza."""
    now = now or timezone.now()
    rows = list(
        payments.filter(status=Payment.Status.PAID, paid_at__gte=now - timedelta(days=days))
        # Panga kwa kitambulisho: routers mbili zenye jina moja zisiunganishwe kuwa moja.
        .values(field.replace("__name", "_id"), field)
        .annotate(total=Sum("amount"), count=Count("pk"))
        .order_by("-total")[:limit]
    )
    peak = rows[0]["total"] if rows else 0
    return [
        {"label": row[field], "total": row["total"], "count": row["count"],
         "share": round(row["total"] * 100 / peak) if peak else 0}
        for row in rows
    ]


def greeting(now=None):
    """Salamu ya wakati huu wa siku, na tarehe (template inaipanga kwa lugha husika)."""
    local = timezone.localtime(now or timezone.now())
    hour = local.hour
    if 4 <= hour < 12:
        text = _("Habari za asubuhi")
    elif hour < 16:
        text = _("Habari za mchana")
    elif hour < 20:
        text = _("Habari za jioni")
    else:
        text = _("Habari za usiku")
    return {"text": text, "date": local}
