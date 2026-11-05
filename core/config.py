"""
Mipangilio ya biashara ya JamiiLite: kutoka PlatformConfig (dashboard ya Super
Admin) ikiwa imewekwa, vinginevyo kutoka `.env`.
"""

import threading
from dataclasses import dataclass

from django.conf import settings

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


def current():
    """Inasomwa mara moja tu kwa kila ombi (RequestConfigMiddleware), si kila inapoitwa."""
    if getattr(_request, "active", False):
        if _request.value is None:
            _request.value = _build()
        return _request.value
    return _build()


def forget():
    """Baada ya kuhifadhi mipangilio mipya, ombi hili lisome upya."""
    _request.value = None


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
