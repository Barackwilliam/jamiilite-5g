import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from core import events

from .models import Payment, Voucher
from .providers import get_provider
from .providers.base import PaymentRequestResult

logger = logging.getLogger(__name__)
# Mteja asipothibitisha kwa PIN ndani ya muda huu, ombi linahesabiwa limeshindwa.
PENDING_TIMEOUT = timedelta(minutes=10)
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
    try:
        result = provider.request_payment(payment)
    except Exception as exc:  # Mtoa huduma hakujibu (timeout, kosa la mtandao...): malipo yasibaki "yanasubiri".
        logger.exception("Ombi la malipo %s limeshindwa", payment.pk)
        result = PaymentRequestResult(error=_("Imeshindwa kuwasiliana na mtoa huduma wa malipo. Jaribu tena.") + f" ({type(exc).__name__})")
    if result.error:
        payment.status = Payment.Status.FAILED
        payment.failure_reason = result.error[:255]
        payment.save(update_fields=["status", "failure_reason"])
        events.record(router, events.Kind.PAYMENT_FAILED, mac=client_mac, amount=payment.amount, detail=payment.failure_reason)
        return payment

    if result.reference or result.checkout_url:
        payment.provider_reference = result.reference
        payment.checkout_url = result.checkout_url
        payment.save(update_fields=["provider_reference", "checkout_url"])

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


def expire_if_stale(payment, now=None):
    """Malipo yaliyosubiri kupita PENDING_TIMEOUT yanawekwa "yameshindwa" ili mteja ajaribu tena."""
    now = now or timezone.now()
    if payment.status != Payment.Status.PENDING or now - payment.created_at < PENDING_TIMEOUT:
        return payment
    updated = Payment.objects.filter(pk=payment.pk, status=Payment.Status.PENDING).update(
        status=Payment.Status.FAILED, failure_reason=_("Muda wa kuthibitisha malipo umeisha.")
    )
    if updated:
        payment.refresh_from_db()
    return payment


# Ukurasa wa mteja unauliza kila sekunde chache; mtoa huduma anaulizwa mara moja tu kwa kipindi hiki.
CHECK_EVERY = timedelta(seconds=5)


def sync_with_provider(payment, throttle=True, now=None):
    """
    Muulize mtoa huduma hali ya malipo yanayosubiri, kisha yathibitishe au yaweke "yameshindwa".
    Kiasi na sarafu lazima vilingane na malipo yetu, vinginevyo hayathibitishwi.
    """
    now = now or timezone.now()
    if payment.status == Payment.Status.PAID:
        return payment
    if throttle and payment.last_checked_at and now - payment.last_checked_at < CHECK_EVERY:
        return payment
    Payment.objects.filter(pk=payment.pk).update(last_checked_at=now)
    provider = get_provider()
    if provider.name != payment.provider:
        return payment
    try:
        result = provider.check_status(payment)
    except Exception:
        logger.exception("Kukagua malipo %s kumeshindwa", payment.pk)
        return payment
    if result is None or result.state == "pending":
        return payment
    if result.state == "paid":
        if result.amount != payment.amount or (result.currency and result.currency != "TZS"):
            logger.error("Malipo %s: kiasi %s %s hakilingani na %s TZS", payment.pk, result.amount, result.currency, payment.amount)
            return payment
        confirm_payment(payment.pk)
        if result.confirmation:
            Payment.objects.filter(pk=payment.pk).update(confirmation_code=result.confirmation[:100])
    elif payment.status == Payment.Status.PENDING:
        reason = result.reason or _("Malipo hayakukamilika.")
        if Payment.objects.filter(pk=payment.pk, status=Payment.Status.PENDING).update(
            status=Payment.Status.FAILED, failure_reason=reason[:255]
        ):
            events.record(payment.router, events.Kind.PAYMENT_FAILED, mac=payment.client_mac, amount=payment.amount, detail=reason[:160])
    payment.refresh_from_db()
    return payment
