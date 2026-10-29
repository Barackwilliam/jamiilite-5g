from urllib.parse import urlsplit

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv46_address
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from django.utils import timezone
from django.utils.translation import gettext, ngettext

from billing.models import Payment, VoucherDevice
from billing.services import start_payment
from billing.subscriptions import ensure_active
from core.models import Router
from radius import localsync
from ui import ratelimit

from .forms import PayForm

# Vigezo ambavyo MikroTik inatuma ikimpeleka mteja kwenye ukurasa wetu
# (kutoka login.html yake: $(link-login-only), $(link-orig), $(mac), $(ip)).
HOTSPOT_PARAMS = ("link-login-only", "link-orig", "mac", "ip")
SESSION_PAYMENTS_KEY = "portal_payments"
# Njia ya "local": router ikichelewa kupokea vocha kiasi hiki, mteja anapewa kitufe cha kuunganisha mwenyewe.
ROUTER_WAIT = timedelta(seconds=60)


def _is_http_url(value):
    return urlsplit(value).scheme in {"http", "https"}


def _hotspot_session_key(router):
    return f"portal_hotspot_{router.pk}"


def _get_router(slug):
    return get_object_or_404(
        Router.objects.select_related("owner"), slug=slug, is_active=True, owner__is_active=True
    )


def _active_packages(router):
    return router.owner.packages.filter(is_active=True)


def _hotspot_context(request, router):
    """Mahali pa kutuma vocha kwa MikroTik ili mteja aunganishwe."""
    params = request.session.get(_hotspot_session_key(router), {})
    login_target = router.login_url
    if not login_target:
        candidate = params.get("link-login-only", "")
        login_target = candidate if _is_http_url(candidate) else ""
    dst = params.get("link-orig", "")
    return {"login_target": login_target, "dst": dst if _is_http_url(dst) else ""}


@require_http_methods(["GET"])
def home(request, slug):
    router = _get_router(slug)

    incoming = {key: request.GET[key] for key in HOTSPOT_PARAMS if request.GET.get(key)}
    if incoming:
        request.session[_hotspot_session_key(router)] = incoming

    return _render_home(request, router, PayForm(packages=_active_packages(router)))


def _returning_voucher(request, router):
    """
    Simu iliyokwisha kulipa na bado ina muda: iunganishe tena bila kuandika
    vocha, kama WiFi za kulipia mtaani. Inarukwa MikroTik ikirudisha kosa ili
    tusizunguke kwenye jaribio lilelile.
    """
    if request.GET.get("error"):
        return None
    params = request.session.get(_hotspot_session_key(router), {})
    mac = params.get("mac", "").strip().upper().replace("-", ":")[:17]
    if not mac:
        return None
    device = (
        VoucherDevice.objects.select_related("voucher__package")
        .filter(mac_address=mac, voucher__router=router, voucher__expires_at__gt=timezone.now())
        .order_by("-voucher__expires_at")
        .first()
    )
    return device.voucher if device else None


def _remaining_label(seconds):
    minutes = max(1, seconds // 60)
    days, rest = divmod(minutes, 1440)
    hours, mins = divmod(rest, 60)
    day_part = ngettext("siku %(n)s", "siku %(n)s", days) % {"n": days}
    hour_part = ngettext("saa %(n)s", "saa %(n)s", hours) % {"n": hours}
    min_part = ngettext("dakika %(n)s", "dakika %(n)s", mins) % {"n": mins}
    if days:
        return f"{day_part} {hour_part}" if hours else day_part
    if hours:
        return f"{hour_part} {min_part}" if mins else hour_part
    return min_part


def _render_home(request, router, form, status=200):
    return render(
        request,
        "portal/home.html",
        {
            "router": router,
            "owner": router.owner,
            "form": form,
            # Usajili wa mmiliki ukiisha, mauzo mapya yanasimama, lakini vocha za
            # zamani bado zinaweza kutumika.
            "selling_paused": not ensure_active(router.owner),
            # Ujumbe unaojulikana kutoka RADIUS (msgid ya Kiswahili) unatafsiriwa; mwingine unabaki kama ulivyo.
            "hotspot_error": gettext(request.GET.get("error", "")) if request.GET.get("error") else "",
            **_hotspot_context(request, router),
            **_returning_context(request, router),
        },
        status=status,
    )


def _returning_context(request, router):
    voucher = _returning_voucher(request, router) if request.method == "GET" else None
    if voucher is None:
        return {}
    return {"returning": voucher, "returning_left": _remaining_label(voucher.remaining_seconds())}


# Namba moja ya simu: maombi 3 kwa dakika 5, ili mtu asitumie ukurasa kumsumbua mwingine
# kwa USSD push. Router moja: 60 kwa dakika 10 (wateja wa hotspot moja wanashiriki IP).
PAY_LIMITS = {"phone": (3, timedelta(minutes=5)), "router": (60, timedelta(minutes=10))}


def _too_many_payments(router, phone):
    checks = [("phone", f"pay:phone:{phone}"), ("router", f"pay:router:{router.pk}")]
    for kind, key in checks:
        limit = PAY_LIMITS[kind][0]
        if ratelimit.is_blocked(key, limit):
            return True
    for kind, key in checks:
        ratelimit.hit(key, PAY_LIMITS[kind][1])
    return False


@require_POST
def pay(request, slug):
    router = _get_router(slug)
    form = PayForm(request.POST, packages=_active_packages(router))
    if not ensure_active(router.owner):
        return _render_home(request, router, form, status=403)
    if not form.is_valid():
        return _render_home(request, router, form, status=400)
    if _too_many_payments(router, form.cleaned_data["phone"]):
        form.add_error("phone", gettext("Maombi mengi ya malipo kwa namba hii. Subiri dakika chache, kisha ujaribu tena."))
        return _render_home(request, router, form, status=429)

    params = request.session.get(_hotspot_session_key(router), {})
    payment = start_payment(
        router=router,
        package=form.cleaned_data["package"],
        phone=form.cleaned_data["phone"],
        client_mac=params.get("mac", "")[:17],
        client_ip=_valid_ip(params.get("ip", "")),
    )

    owned = request.session.get(SESSION_PAYMENTS_KEY, [])
    owned.append(str(payment.pk))
    request.session[SESSION_PAYMENTS_KEY] = owned[-20:]
    return redirect("portal:payment_status", slug=router.slug, payment_id=payment.pk)


@require_http_methods(["GET"])
def payment_status(request, slug, payment_id):
    router = _get_router(slug)
    # Malipo yanaonekana tu kwenye kifaa kilichoyaanzisha, ili vocha isivuje.
    if str(payment_id) not in request.session.get(SESSION_PAYMENTS_KEY, []):
        raise Http404
    payment = get_object_or_404(
        Payment.objects.select_related("package"), pk=payment_id, router=router
    )
    voucher = getattr(payment, "voucher", None) if payment.status == Payment.Status.PAID else None
    # Njia ya "local": vocha inaweza kutumika tu router ikishaipokea kwenye ripoti yake.
    router_ready = True
    if voucher and settings.JAMIILITE_AUTH_MODE == "local":
        router_ready = localsync.is_on_router(voucher, router)
    waited_long = bool(payment.paid_at and timezone.now() - payment.paid_at > ROUTER_WAIT)
    return render(
        request,
        "portal/status.html",
        {
            "router": router,
            "owner": router.owner,
            "payment": payment,
            "voucher": voucher,
            "router_ready": router_ready,
            "waited_long": waited_long,
            **_hotspot_context(request, router),
        },
    )


def _valid_ip(value):
    try:
        validate_ipv46_address(value)
    except ValidationError:
        return None
    return value
