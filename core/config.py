"""
Mipangilio ya biashara ya JamiiLite: kutoka PlatformConfig (dashboard ya Super
Admin) ikiwa imewekwa, vinginevyo kutoka `.env`.
"""

import threading
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

from .models import PlatformConfig


@dataclass(frozen=True)
class Config:
    monthly_fee: int
    trial_days: int
    min_withdrawal: int
    sale_fee_percent: int
    whatsapp_number: str
    signups_open: bool
    announcement: str


_request = threading.local()


CACHE_KEY = "jl:platform-config"
CACHE_SECONDS = 300
PAGES_VERSION_KEY = "jl:pages-version"


def current():
    """Inasomwa mara moja tu kwa kila ombi (RequestConfigMiddleware), si kila inapoitwa.

    Kati ya maombi inakaa kwenye cache kwa dakika chache, ili kurasa zisiulize database kila mara.
    """
    if getattr(_request, "active", False):
        if _request.value is None:
            _request.value = _cached()
        return _request.value
    return _cached()


def _cached():
    if not settings.JAMIILITE_CACHE_PAGES:
        return _build()
    value = cache.get(CACHE_KEY)
    if value is None:
        value = _build()
        cache.set(CACHE_KEY, value, CACHE_SECONDS)
    return value


def forget():
    """Baada ya kuhifadhi mipangilio mipya: ombi hili, cache na kurasa zilizohifadhiwa zisome upya."""
    _request.value = None
    cache.delete(CACHE_KEY)
    pages_version(bump=True)


def pages_version(bump=False):
    """Namba inayobadilika mipangilio ikihifadhiwa, ili kurasa za hadhara zilizohifadhiwa zisitumike tena."""
    if bump:
        try:
            return cache.incr(PAGES_VERSION_KEY)
        except ValueError:
            cache.set(PAGES_VERSION_KEY, 2, None)
            return 2
    return cache.get_or_set(PAGES_VERSION_KEY, 1, None)


class RequestConfigMiddleware:
    """Mipangilio inakumbukwa kwa muda wa ombi moja, kisha inasahaulika."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _request.active, _request.value = True, None
        try:
            return self.get_response(request)
        finally:
            _request.active, _request.value = False, None


def _build():
    row = PlatformConfig.load()

    def pick(field, default):
        value = getattr(row, field)
        return default if value is None or value == "" else value

    return Config(
        monthly_fee=pick("monthly_fee", settings.JAMIILITE_MONTHLY_FEE),
        trial_days=pick("trial_days", settings.JAMIILITE_TRIAL_DAYS),
        min_withdrawal=pick("min_withdrawal", settings.JAMIILITE_MIN_WITHDRAWAL),
        sale_fee_percent=pick("sale_fee_percent", settings.JAMIILITE_SALE_FEE_PERCENT),
        whatsapp_number=pick("whatsapp_number", settings.JAMIILITE_WHATSAPP_NUMBER).lstrip("+"),
        signups_open=row.signups_open,
        announcement=row.announcement.strip(),
    )
