"""
Maamuzi ya RADIUS: vocha ipi iruhusiwe, kwa muda gani, na kwa kasi gani.

Kila packet inatambuliwa kwa NAS-Identifier (jina la MikroTik). Packet kutoka
router isiyojulikana, au yenye Message-Authenticator batili, inapuuzwa bila
jibu, kama RFC 2865 inavyoelekeza.
"""

import hmac
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from billing.models import Voucher, VoucherDevice
from core.models import Router

from . import packet as rp

logger = logging.getLogger("jamiilite.radius")

INTERIM_INTERVAL_SECONDS = 300

MSG_INVALID = "Vocha si sahihi"
MSG_EXPIRED = "Muda wa vocha umeisha"
MSG_DEVICE_LIMIT = "Vocha hii inatumika kwenye kifaa kingine"
MSG_USE_PAP = "Router haijawekwa login-by=http-pap"


def _router_for(request):
    nas_identifier = request.get_str(rp.NAS_IDENTIFIER)
    if not nas_identifier:
        logger.warning("Packet bila NAS-Identifier imepuuzwa")
        return None
    router = (
        Router.objects.select_related("owner")
        .filter(nas_identifier=nas_identifier, is_active=True, owner__is_active=True)
        .first()
    )
    if router is None:
        logger.warning("NAS-Identifier '%s' haijulikani; packet imepuuzwa", nas_identifier)
    return router


def _normalize_mac(value):
    return (value or "").strip().upper().replace("-", ":")[:17]


def handle_access_request(request, now=None):
    """Rudisha bytes za jibu, au None kama packet inapaswa kupuuzwa."""
    router = _router_for(request)
    if router is None:
        return None
    secret = router.radius_secret.encode()

    message_auth = rp.verify_message_authenticator(request, secret)
    if message_auth is False:
        logger.warning("Message-Authenticator batili kutoka '%s' (secret si sahihi?)", router.nas_identifier)
        return None
    if message_auth is None and settings.RADIUS_REQUIRE_MESSAGE_AUTHENTICATOR:
        logger.warning(
            "'%s' haikutuma Message-Authenticator; packet imepuuzwa. "
            "Weka RADIUS_REQUIRE_MESSAGE_AUTHENTICATOR=False kwa RouterOS ya zamani.",
            router.nas_identifier,
        )
        return None

    def reject(message):
        logger.info("Imekataliwa (%s): %s", router.nas_identifier, message)
        return rp.build_response(
            rp.ACCESS_REJECT, request, secret, [(rp.REPLY_MESSAGE, message.encode())]
        )

    encrypted = request.get(rp.USER_PASSWORD)
    if encrypted is None:
        return reject(MSG_USE_PAP)
    try:
        password = rp.decrypt_pap_password(encrypted, secret, request.authenticator)
    except rp.PacketError:
        return reject(MSG_INVALID)

    code = (request.get_str(rp.USER_NAME) or "").strip().upper()
    if not code or not hmac.compare_digest(password.decode(errors="replace").strip().upper(), code):
        return reject(MSG_INVALID)

    now = now or timezone.now()
    mac = _normalize_mac(request.get_str(rp.CALLING_STATION_ID))

    with transaction.atomic():
        voucher = (
            Voucher.objects.select_for_update()
            .select_related("package")
            .filter(code=code, router__owner=router.owner)
            .first()
        )
        if voucher is None:
            return reject(MSG_INVALID)

        voucher.activate(now=now)
        if voucher.is_expired(now=now):
            return reject(MSG_EXPIRED)

        if mac:
            device = voucher.devices.filter(mac_address=mac).first()
            if device is None:
                if voucher.devices.count() >= voucher.package.shared_users:
                    return reject(MSG_DEVICE_LIMIT)
                VoucherDevice.objects.create(voucher=voucher, mac_address=mac)
            else:
                device.save(update_fields=["last_seen_at"])

        remaining = voucher.remaining_seconds(now=now)

    attributes = [
        (rp.SESSION_TIMEOUT, rp.int_attr(remaining)),
        (rp.ACCT_INTERIM_INTERVAL, rp.int_attr(INTERIM_INTERVAL_SECONDS)),
    ]
    if voucher.package.rate_limit:
        attributes.append(
            (
                rp.VENDOR_SPECIFIC,
                rp.mikrotik_attr(rp.MIKROTIK_RATE_LIMIT, voucher.package.rate_limit.encode()),
            )
        )
    logger.info(
        "Imekubaliwa (%s): vocha %s, kifaa %s, sekunde %s zimebaki",
        router.nas_identifier, code, mac or "-", remaining,
    )
    return rp.build_response(rp.ACCESS_ACCEPT, request, secret, attributes)


def handle_accounting_request(request):
    router = _router_for(request)
    if router is None:
        return None
    secret = router.radius_secret.encode()
    if not rp.verify_accounting_request(request, secret):
        logger.warning("Accounting kutoka '%s' ina authenticator batili", router.nas_identifier)
        return None

    code = (request.get_str(rp.USER_NAME) or "").strip().upper()
    mac = _normalize_mac(request.get_str(rp.CALLING_STATION_ID))
    if code and mac:
        VoucherDevice.objects.filter(
            voucher__code=code, voucher__router__owner=router.owner, mac_address=mac
        ).update(last_seen_at=timezone.now())

    return rp.build_response(rp.ACCOUNTING_RESPONSE, request, secret)


def handle(data, port_kind):
    """Kituo kimoja cha kupokea packet. port_kind ni 'auth' au 'acct'."""
    try:
        request = rp.parse(data)
    except rp.PacketError as exc:
        logger.warning("Packet imeharibika imepuuzwa: %s", exc)
        return None

    if port_kind == "auth" and request.code == rp.ACCESS_REQUEST:
        return handle_access_request(request)
    if port_kind == "acct" and request.code == rp.ACCOUNTING_REQUEST:
        return handle_accounting_request(request)
    logger.warning("Packet code %s haitarajiwi kwenye port ya %s", request.code, port_kind)
    return None
