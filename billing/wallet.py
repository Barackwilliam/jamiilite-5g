"""
Salio la mmiliki na kutoa pesa.

Salio linahesabiwa kutoka LedgerEntry tu. Kila operesheni inayopunguza salio
inafunga safu ya mmiliki (select_for_update) kwanza, ili maombi mawili ya wakati
mmoja yasimwezeshe mtu kutoa pesa zaidi ya alizonazo.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core import config
from core.models import Owner

from .models import LedgerEntry, Withdrawal


def balance(owner):
    return owner.ledger.aggregate(total=Sum("amount"))["total"] or 0


def lock_owner(owner):
    return Owner.objects.select_for_update().get(pk=owner.pk)


def sale_net_amount(amount):
    fee = amount * config.current().sale_fee_percent // 100
    return amount - fee


def credit_sale(payment):
    """Ongeza mauzo kwenye salio la mmiliki. Inaitwa ndani ya transaction ya malipo."""
    return LedgerEntry.objects.create(
        owner=payment.router.owner,
        kind=LedgerEntry.Kind.SALE,
        amount=sale_net_amount(payment.amount),
        payment=payment,
        description=f"{payment.package.name} · {payment.phone}",
    )


def request_withdrawal(owner, amount, phone):
    minimum = config.current().min_withdrawal
    if amount < minimum:
        raise ValidationError(f"Kiasi cha chini ni Tsh {minimum:,}.")
    with transaction.atomic():
        owner = lock_owner(owner)
        if amount > balance(owner):
            raise ValidationError("Salio lako halitoshi kwa kiasi hicho.")
        withdrawal = Withdrawal.objects.create(owner=owner, amount=amount, phone=phone)
        # Pesa inashikiliwa papo hapo ili isitumike mara mbili wakati ombi linasubiri.
        LedgerEntry.objects.create(
            owner=owner,
            kind=LedgerEntry.Kind.WITHDRAWAL,
            amount=-amount,
            withdrawal=withdrawal,
            description=f"Kutoa pesa kwenda {phone}",
        )
    return withdrawal


def _process(withdrawal_id, by, status):
    withdrawal = Withdrawal.objects.select_for_update().get(pk=withdrawal_id)
    if withdrawal.status != Withdrawal.Status.PENDING:
        raise ValidationError("Ombi hili limeshashughulikiwa.")
    withdrawal.status = status
    withdrawal.processed_at = timezone.now()
    withdrawal.processed_by = by
    return withdrawal


def mark_withdrawal_paid(withdrawal_id, by, reference=""):
    with transaction.atomic():
        withdrawal = _process(withdrawal_id, by, Withdrawal.Status.PAID)
        withdrawal.reference = reference[:100]
        withdrawal.save()
    return withdrawal


def reject_withdrawal(withdrawal_id, by, note=""):
    with transaction.atomic():
        withdrawal = _process(withdrawal_id, by, Withdrawal.Status.REJECTED)
        withdrawal.note = note[:255]
        withdrawal.save()
        LedgerEntry.objects.create(
            owner=withdrawal.owner,
            kind=LedgerEntry.Kind.WITHDRAWAL_REVERSAL,
            amount=withdrawal.amount,
            withdrawal=withdrawal,
            description="Ombi la kutoa pesa limekataliwa, pesa imerudishwa",
        )
    return withdrawal
