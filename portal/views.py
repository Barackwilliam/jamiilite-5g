from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv46_address
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from billing.models import Payment
from billing.services import start_payment
from core.models import Router

from .forms import PayForm

# Vigezo ambavyo MikroTik inatuma ikimpeleka mteja kwenye ukurasa wetu
# (kutoka login.html yake: $(link-login-only), $(link-orig), $(mac), $(ip)).
HOTSPOT_PARAMS = ("link-login-only", "link-orig", "mac", "ip")
SESSION_PAYMENTS_KEY = "portal_payments"


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

    form = PayForm(packages=_active_packages(router))
    return render(
        request,
        "portal/home.html",
        {
            "router": router,
            "owner": router.owner,
            "form": form,
            "hotspot_error": request.GET.get("error", ""),
            **_hotspot_context(request, router),
        },
    )


@require_POST
def pay(request, slug):
    router = _get_router(slug)
    form = PayForm(request.POST, packages=_active_packages(router))
    if not form.is_valid():
        return render(
            request,
            "portal/home.html",
            {"router": router, "owner": router.owner, "form": form, **_hotspot_context(request, router)},
            status=400,
        )

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
    return render(
        request,
        "portal/status.html",
        {
            "router": router,
            "owner": router.owner,
            "payment": payment,
            "voucher": voucher,
            **_hotspot_context(request, router),
        },
    )


def _valid_ip(value):
    try:
        validate_ipv46_address(value)
    except ValidationError:
        return None
    return value
