"""
Usajili wa mmiliki: siku za majaribio, kisha ada ya kila mwezi.

Muda ukiisha, mfumo unajaribu kulipa ada kutoka kwenye salio lake lenyewe.
Salio lisipotosha, mauzo mapya yanasimama, lakini vocha zilizokwisha kuuzwa
zinaendelea kufanya kazi hadi ziishe.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core import config

from .models import LedgerEntry, SubscriptionCharge
from .wallet import balance, lock_owner

PERIOD = timedelta(days=30)


def start_trial(owner, now=None):
    owner.trial_ends_at = (now or timezone.now()) + timedelta(days=config.current().trial_days)
    owner.save(update_fields=["trial_ends_at"])


def _extend(owner, months, now):
    start = max(now, owner.subscription_ends_at or now)
    owner.paid_until = start + PERIOD * months
    owner.save(update_fields=["paid_until"])
    return owner.paid_until


def pay_from_balance(owner, months=1, now=None):
    """Lipa ada kutoka kwenye salio. Inarudisha SubscriptionCharge."""
    now = now or timezone.now()
    amount = config.current().monthly_fee * months
    with transaction.atomic():
        owner = lock_owner(owner)
        if balance(owner) < amount:
            raise ValidationError(f"Salio halitoshi. Unahitaji Tsh {amount:,}.")
        period_end = _extend(owner, months, now)
        LedgerEntry.objects.create(
            owner=owner,
            kind=LedgerEntry.Kind.SUBSCRIPTION,
            amount=-amount,
            description=f"Ada ya JamiiLite, miezi {months}",
        )
        return SubscriptionCharge.objects.create(
            owner=owner, months=months, amount=amount,
            source=SubscriptionCharge.Source.BALANCE, period_end=period_end,
        )


def record_cash_payment(owner, months, by, now=None):
    """Super admin amepokea ada nje ya mfumo (mfano pesa taslimu)."""
    now = now or timezone.now()
    with transaction.atomic():
        owner = lock_owner(owner)
        period_end = _extend(owner, months, now)
        return SubscriptionCharge.objects.create(
            owner=owner, months=months, amount=config.current().monthly_fee * months,
            source=SubscriptionCharge.Source.CASH, period_end=period_end, created_by=by,
        )


def ensure_active(owner, now=None):
    """True kama mmiliki anaweza kuuza. Ikiisha, inajaribu kulipa kutoka salio."""
    now = now or timezone.now()
    if not owner.is_active:
        return False
    if owner.has_active_subscription(now):
        return True
    try:
        pay_from_balance(owner, now=now)
    except ValidationError:
        return False
    owner.refresh_from_db()
    return owner.has_active_subscription(now)
