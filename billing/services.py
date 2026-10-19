from django.db import transaction
from django.utils import timezone

from core import events

from .models import Payment, Voucher
from .providers import get_provider
from .wallet import credit_sale


def start_payment(*, router, package, phone, client_mac="", client_ip=None):
    """Anzisha malipo ya kifurushi na umuombe mteja alipe kwa simu."""
    provider = get_provider()
    payment = Payment.objects.create(
        router=router,
        package=package,
        phone=phone,
        amount=package.price,
        provider=provider.name,
        client_mac=client_mac,
        client_ip=client_ip,
    )

    events.record(
        router, events.Kind.PAYMENT_STARTED, mac=client_mac, amount=payment.amount,
        detail=f"{package.name} · {phone[:5]}…{phone[-3:]}",
    )
    result = provider.request_payment(payment)
    if result.error:
        payment.status = Payment.Status.FAILED
        payment.failure_reason = result.error[:255]
        payment.save(update_fields=["status", "failure_reason"])
        events.record(router, events.Kind.PAYMENT_FAILED, mac=client_mac, amount=payment.amount, detail=payment.failure_reason)
        return payment

    if result.reference:
        payment.provider_reference = result.reference
        payment.save(update_fields=["provider_reference"])

    if result.confirmed:
        confirm_payment(payment.pk)
        payment.refresh_from_db()
    return payment


def confirm_payment(payment_id, reference=""):
    """
    Weka malipo kuwa yamelipwa na umpe mteja vocha.

    Ni salama kuitwa zaidi ya mara moja (mfano callback ikirudiwa): malipo
    yanapata vocha moja tu.
    """
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment_id)
        if payment.status == Payment.Status.PAID:
            return payment.voucher

        payment.status = Payment.Status.PAID
        payment.paid_at = timezone.now()
        update_fields = ["status", "paid_at"]
        if reference and not payment.provider_reference:
            payment.provider_reference = reference
            update_fields.append("provider_reference")
        payment.save(update_fields=update_fields)

        credit_sale(payment)
        events.record(
            payment.router, events.Kind.PAYMENT_PAID, mac=payment.client_mac, amount=payment.amount,
            detail=payment.package.name,
        )
        return Voucher.objects.create(
            router=payment.router, package=payment.package, payment=payment
        )
