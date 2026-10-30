"""
Kuzuia majaribio mengi: kubahatisha password, au kubonyeza "Lipa" mara nyingi
na kumtumia mtu maombi ya malipo yasiyoisha.

Hesabu zinakaa kwenye database ili gunicorn workers wote waone hesabu moja.
"""

import random
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext as _

from core.models import RateLimit

PRUNE_CHANCE = 0.01


def client_ip(request):
    """
    IP ya mtumiaji. Nyuma ya proxy (Render), anwani ya kweli ni ile ambayo proxy
    yetu iliiona: ya mwisho kwenye X-Forwarded-For. Za mwanzo mtu anaweza kuziandika mwenyewe.
    """
    hops = settings.JAMIILITE_PROXY_HOPS
    forwarded = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
    if hops and len(forwarded) >= hops:
        return forwarded[-hops][:45]
    return request.META.get("REMOTE_ADDR", "")[:45]


def is_blocked(key, limit, now=None):
    now = now or timezone.now()
    return RateLimit.objects.filter(key=key, reset_at__gt=now, count__gte=limit).exists()


def hit(key, window, now=None):
    """Ongeza jaribio moja kwenye `key`, ndani ya kipindi `window` (timedelta). Inarudisha hesabu."""
    now = now or timezone.now()
    for _attempt in range(2):
        try:
            with transaction.atomic():
                row, _created = RateLimit.objects.select_for_update().get_or_create(
                    key=key, defaults={"count": 0, "reset_at": now + window}
                )
                if row.reset_at <= now:
                    row.count, row.reset_at = 0, now + window
                row.count += 1
                row.save(update_fields=["count", "reset_at"])
            break
        except IntegrityError:
            # Ombi lingine limeunda safu hiyo hiyo sasa hivi; jaribu tena, sasa ipo.
            continue
    if random.random() < PRUNE_CHANCE:
        RateLimit.objects.filter(reset_at__lt=now - timedelta(days=1)).delete()
    return row.count


def clear(key):
    RateLimit.objects.filter(key=key).delete()


def minutes_left(key, now=None):
    now = now or timezone.now()
    reset_at = RateLimit.objects.filter(key=key).values_list("reset_at", flat=True).first()
    if not reset_at:
        return 0
    return max(1, -(-int((reset_at - now).total_seconds()) // 60))


def protect_login(view, limit=20, window=timedelta(minutes=15)):
    """Kwa ukurasa wa kuingia wa Django admin: majaribio yaliyoshindwa yanahesabiwa kwa IP."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.method != "POST":
            return view(request, *args, **kwargs)
        key = f"admin:ip:{client_ip(request)}"
        if is_blocked(key, limit):
            message = _("Umejaribu mara nyingi. Subiri dakika %(n)s, kisha ujaribu tena.") % {"n": minutes_left(key)}
            return HttpResponse(message, status=429, content_type="text/plain; charset=utf-8")
        response = view(request, *args, **kwargs)
        if response.status_code != 302:  # Imeshindwa: fomu imerudishwa na kosa.
            hit(key, window)
        return response

    return wrapper
