from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from billing.models import Payment


def local_day_start(now=None):
    local = timezone.localtime(now or timezone.now())
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def sales_summary(payments, now=None):
    """Mauzo ya leo, siku 7 na siku 30 kutoka kwenye queryset ya Payment."""
    now = now or timezone.now()
    paid = payments.filter(status=Payment.Status.PAID)
    periods = {
        "today": Q(paid_at__gte=local_day_start(now)),
        "week": Q(paid_at__gte=now - timedelta(days=7)),
        "month": Q(paid_at__gte=now - timedelta(days=30)),
    }
    result = paid.aggregate(
        **{f"{name}_amount": Sum("amount", filter=q) for name, q in periods.items()},
        **{f"{name}_count": Count("pk", filter=q) for name, q in periods.items()},
    )
    return {key: value or 0 for key, value in result.items()}
