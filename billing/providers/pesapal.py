"""
Pesapal (API 3.0).

Pesapal haina njia ya kutuma ombi la malipo moja kwa moja kwenye simu: mteja anachagua
mtandao na kuthibitisha kwenye fomu ya Pesapal. Fomu hiyo inawekwa ndani ya ukurasa wetu
(portal/status.html), kwa hiyo mteja anabaki kwenye ukurasa wa biashara yenyewe.

Malipo yanathibitishwa kwa kumuuliza Pesapal (GetTransactionStatus) tu: si kwa IPN wala
kwa link ya kurudi, ambazo mtu yeyote anaweza kuziita.
"""

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse

from .base import PaymentProvider, PaymentRequestResult, PaymentStatusResult

logger = logging.getLogger(__name__)

BASE_URLS = {
    "sandbox": "https://cybqa.pesapal.com/pesapalv3/api",
    "live": "https://pay.pesapal.com/v3/api",
}
HOSTS = {"sandbox": "cybqa.pesapal.com", "live": "pay.pesapal.com"}
# status_code ya GetTransactionStatus: 0 = bado (INVALID), 1 = COMPLETED, 2 = FAILED, 3 = REVERSED.
COMPLETED, FAILED, REVERSED = 1, 2, 3
TOKEN_CACHE_KEY = "pesapal:token"
IPN_CACHE_KEY = "pesapal:ipn"
TIMEOUT = 20


class PesapalError(Exception):
    pass


def _environment():
    return "live" if settings.PESAPAL_ENV == "live" else "sandbox"


def _call(method, path, payload=None, token=None):
    url = BASE_URLS[_environment()] + path
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = json.loads(response.read() or b"null")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise PesapalError(f"{method} {path}: {exc}") from exc
    if isinstance(body, dict):
        error = body.get("error")
        status = str(body.get("status", "200"))
        if status != "200" or (isinstance(error, dict) and any(error.values())):
            raise PesapalError(f"{method} {path}: {error or status}")
    return body


def access_token():
    token = cache.get(TOKEN_CACHE_KEY)
    if token:
        return token
    body = _call("POST", "/Auth/RequestToken", {
        "consumer_key": settings.PESAPAL_CONSUMER_KEY,
        "consumer_secret": settings.PESAPAL_CONSUMER_SECRET,
    })
    token = body.get("token")
    if not token:
        raise PesapalError("Pesapal haikurudisha token.")
    cache.set(TOKEN_CACHE_KEY, token, 4 * 60)  # token ya Pesapal inaisha baada ya dakika 5
    return token


def ipn_url():
    return settings.JAMIILITE_PUBLIC_URL.rstrip("/") + reverse("billing:pesapal_ipn")


def ipn_id():
    """Kitambulisho cha IPN yetu kwa Pesapal: kinasajiliwa mara moja, kisha kinakumbukwa."""
    if settings.PESAPAL_IPN_ID:
        return settings.PESAPAL_IPN_ID
    cached = cache.get(IPN_CACHE_KEY)
    if cached:
        return cached
    url = ipn_url()
    token = access_token()
    registered = _call("GET", "/URLSetup/GetIpnList", token=token)
    found = next((row.get("ipn_id") for row in registered or [] if row.get("url") == url), None)
    if not found:
        found = _call("POST", "/URLSetup/RegisterIPN", {"url": url, "ipn_notification_type": "GET"}, token=token).get("ipn_id")
    if not found:
        raise PesapalError("Pesapal haikurudisha ipn_id.")
    cache.set(IPN_CACHE_KEY, found, 24 * 60 * 60)
    return found


class PesapalProvider(PaymentProvider):
    name = "pesapal"

    def request_payment(self, payment):
        router = payment.router
        callback = settings.JAMIILITE_PUBLIC_URL.rstrip("/") + reverse(
            "portal:payment_status", args=[router.slug, payment.pk]
        )
        local_phone = "0" + payment.phone[3:] if payment.phone.startswith("255") else payment.phone
        body = _call("POST", "/Transactions/SubmitOrderRequest", {
            "id": str(payment.pk),
            "currency": "TZS",
            "amount": payment.amount,
            "description": f"{payment.package.name} · {router.owner.business_name}"[:100],
            "callback_url": callback,
            # Pesapal ikimaliza, ukurasa wote (si fomu ndani yake tu) unarudi kwetu.
            "redirect_mode": "PARENT_WINDOW",
            "notification_id": ipn_id(),
            "billing_address": {"phone_number": local_phone, "country_code": "TZ", "email_address": ""},
        }, token=access_token())
        return PaymentRequestResult(
            reference=body.get("order_tracking_id", ""), checkout_url=body.get("redirect_url", ""),
        )

    def check_status(self, payment):
        if not payment.provider_reference:
            return PaymentStatusResult(state="pending")
        body = _call(
            "GET", f"/Transactions/GetTransactionStatus?orderTrackingId={payment.provider_reference}",
            token=access_token(),
        )
        code = int(body.get("status_code") or 0)
        state = {COMPLETED: "paid", FAILED: "failed", REVERSED: "failed"}.get(code, "pending")
        if str(body.get("merchant_reference", "")) not in ("", str(payment.pk)):
            logger.error("Pesapal: malipo %s yana merchant_reference tofauti", payment.pk)
            state = "pending"
        return PaymentStatusResult(
            state=state,
            amount=int(float(body.get("amount") or 0)),
            currency=str(body.get("currency") or ""),
            confirmation=str(body.get("confirmation_code") or ""),
            reason=str(body.get("payment_status_description") or body.get("description") or ""),
        )

    def walled_garden_hosts(self):
        return [HOSTS[_environment()]]
