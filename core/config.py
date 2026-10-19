"""
Mipangilio ya biashara ya JamiiLite: kutoka PlatformConfig (dashboard ya Super
Admin) ikiwa imewekwa, vinginevyo kutoka `.env`.
"""

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


def current():
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
