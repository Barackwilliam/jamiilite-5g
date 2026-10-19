import secrets
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Min, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from billing import subscriptions, wallet
from billing.models import Payment, SubscriptionCharge, Voucher
from core import config
from core.models import Owner, Package, RouterCommand
from radius import routeros
from ui.charts import SWAHILI_DAYS, bar_chart, daily_totals

from .accounts import create_owner_account
from .forms import (
    LoginForm,
    OwnerSettingsForm,
    PackageForm,
    RouterForm,
    SignupForm,
    VoucherBatchForm,
    WifiNameForm,
    WithdrawForm,
)
from .stats import greeting, local_day_start, sales_summary, top_by, trend

NAV = [
    ("home", "Muhtasari", "home"),
    ("routers", "Routers", "router"),
    ("packages", "Vifurushi", "package"),
    ("vouchers", "Vocha", "ticket"),
    ("sales", "Mauzo", "chart"),
    ("wallet", "Salio", "wallet"),
    ("subscription", "Usajili", "calendar"),
    ("settings", "Mipangilio", "settings"),
]
# Kwenye simu, hizi zinakaa chini ya skrini kama app; nyingine ziko kwenye "Zaidi".
BOTTOM_NAV = {"home", "sales", "vouchers", "wallet"}


# --- Kuingia na kujisajili ------------------------------------------------------

def _after_login_url(user, next_url, request):
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
        return next_url
    if user.is_superuser and not Owner.objects.filter(user=user).exists():
        return reverse("control:home")
    return reverse("dashboard:home")


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect(_after_login_url(request.user, "", request))
    cfg = config.current()
    if not cfg.signups_open:
        return render(request, "dashboard/signup_closed.html", {"whatsapp": cfg.whatsapp_number})
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        owner = create_owner_account(
            form.cleaned_data["business_name"], form.cleaned_data["phone"], form.cleaned_data["password1"]
        )
        login(request, owner.user)
        messages.success(
            request, f"Karibu {owner.business_name}! Una siku {cfg.trial_days} za majaribio bure."
        )
        return redirect("dashboard:home")
    return render(request, "dashboard/signup.html", {"form": form, "trial_days": cfg.trial_days})


@require_http_methods(["GET", "POST"])
def login_view(request):
    next_url = request.POST.get("next") or request.GET.get("next", "")
    if request.user.is_authenticated:
        return redirect(_after_login_url(request.user, next_url, request))
    form = LoginForm(request, request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.user)
        return redirect(_after_login_url(form.user, next_url, request))
    return render(request, "dashboard/login.html", {"form": form, "next": next_url})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("pages:home")


# --- Msaada wa kurasa za mmiliki ---------------------------------------------------

def owner_required(view):
    @login_required(login_url="dashboard:login")
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        owner = Owner.objects.filter(user=request.user).first()
        if owner is None:
            if request.user.is_superuser:
                return redirect("control:home")
            raise Http404
        if not owner.is_active:
            return render(request, "dashboard/suspended.html", {"owner": owner}, status=403)
        request.owner = owner
        return view(request, *args, **kwargs)

    return wrapper


def subscription_status(owner, now=None):
    now = now or timezone.now()
    ends = owner.subscription_ends_at
    if not owner.has_active_subscription(now):
        return {"state": "expired", "ends": ends, "days_left": 0}
    days_left = max(0, (ends - now).days)
    return {"state": "trial" if owner.is_in_trial(now) else "active", "ends": ends, "days_left": days_left}


def render_owner(request, template, context, active, title):
    owner = request.owner
    nav = [
        {"url": reverse(f"dashboard:{name}"), "label": label, "icon": icon, "active": name == active,
         "bottom": name in BOTTOM_NAV}
        for name, label, icon in NAV
    ]
    cfg = config.current()
    sub = subscription_status(owner)
    context.update(
        owner=owner,
        area="dashboard",
        nav=nav,
        page_title=title,
        home_url=reverse("dashboard:home"),
        who_name=owner.business_name,
        who_detail=owner.user.username,
        who_initial=owner.business_name[:1].upper(),
        sub=sub,
        sub_meter=_sub_meter(sub, cfg),
        monthly_fee=cfg.monthly_fee,
        announcement=cfg.announcement,
    )
    return render(request, template, context)


def _sub_meter(sub, cfg):
    """Asilimia ya muda uliobaki, kwa mstari mdogo kwenye sidebar."""
    if sub["state"] == "expired":
        return 0
    total = cfg.trial_days if sub["state"] == "trial" else 30
    return max(4, min(100, round(sub["days_left"] * 100 / max(total, 1))))


def _mini_bars(points):
    """Siku 7 kama vipau vidogo ndani ya kadi ya mapato ya leo."""
    peak = max((value for _, value in points), default=0) or 1
    last = len(points) - 1
    return [
        {"label": SWAHILI_DAYS[day.weekday()], "value": value, "pct": max(4, round(value * 100 / peak)), "today": i == last}
        for i, (day, value) in enumerate(points)
    ]


def owner_payments(owner):
    return Payment.objects.filter(router__owner=owner)


# --- Muhtasari ---------------------------------------------------------------------

@owner_required
def home(request):
    owner = request.owner
    subscriptions.ensure_active(owner)
    owner.refresh_from_db()
    routers = list(owner.routers.all())
    payments = owner_payments(owner)
    paid = payments.filter(status=Payment.Status.PAID)
    summary = sales_summary(payments)
    today_by_router = dict(
        paid.filter(paid_at__gte=local_day_start()).values_list("router").annotate(total=Sum("amount"))
    )
    for router in routers:
        router.today_amount = today_by_router.get(router.pk, 0)
    context = {
        "summary": summary,
        "greet": greeting(),
        "today_trend": trend(summary["today_amount"], summary["yesterday_amount"]),
        "week_trend": trend(summary["week_amount"], summary["prev_week_amount"]),
        "top_packages": top_by(payments, "package__name"),
        "top_routers": top_by(payments, "router__name") if len(routers) > 1 else [],
        "balance": wallet.balance(owner),
        "chart": bar_chart(daily_totals(paid, "paid_at", "amount", days=14)),
        "hero_week": _mini_bars(daily_totals(paid, "paid_at", "amount", days=7)),
        "routers": routers,
        "online_routers": sum(1 for r in routers if r.is_online),
        "online_clients": sum(r.active_clients for r in routers if r.is_online),
        "recent_sales": paid.select_related("package", "router").order_by("-paid_at")[:6],
        "has_packages": owner.packages.exists(),
        "has_sales": paid.exists(),
    }
    return render_owner(request, "dashboard/home.html", context, "home", "Muhtasari")


# --- Routers -----------------------------------------------------------------------

@owner_required
@require_http_methods(["GET", "POST"])
def routers(request):
    owner = request.owner
    form = RouterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        router = form.save(commit=False)
        router.owner = owner
        router.save()
        router.nas_identifier = f"jl-{router.slug}"[:64]
        router.save(update_fields=["nas_identifier"])
        messages.success(request, f"{router.name} imeongezwa. Sasa iunganishe kwa mstari wa usanidi.")
        return redirect("dashboard:router_detail", pk=router.pk)
    return render_owner(
        request, "dashboard/routers.html",
        {"routers": owner.routers.order_by("name"), "form": form}, "routers", "Routers",
    )


@owner_required
@require_http_methods(["GET", "POST"])
def router_detail(request, pk):
    router = get_object_or_404(request.owner.routers, pk=pk)
    wifi_form = WifiNameForm(instance=router)
    if request.method == "POST" and request.POST.get("action") == "wifi":
        before = router.wifi_name
        wifi_form = WifiNameForm(request.POST, instance=router)
        if wifi_form.is_valid():
            router = wifi_form.save()
            if router.wifi_name != before:
                RouterCommand.objects.create(router=router, action=RouterCommand.Action.REAPPLY_SETUP)
                messages.success(request, f"Jina la WiFi litabadilika kuwa “{router.wifi_name}” ndani ya dakika 1.")
            return redirect("dashboard:router_detail", pk=router.pk)
    elif request.method == "POST":
        actions = {"reboot": RouterCommand.Action.REBOOT, "reapply": RouterCommand.Action.REAPPLY_SETUP}
        action = actions.get(request.POST.get("action"))
        if action:
            RouterCommand.objects.create(router=router, action=action)
            messages.success(request, "Agizo limetumwa. Router italitekeleza ndani ya dakika 1 ikiwa online.")
        return redirect("dashboard:router_detail", pk=router.pk)
    return render_owner(
        request, "dashboard/router_detail.html",
        {
            "router": router,
            "setup_command": routeros.provision_command(router) if router.nas_identifier else "",
            "portal_url": request.build_absolute_uri(reverse("portal:home", args=[router.slug])),
            "commands": router.commands.order_by("-created_at")[:5],
            "wifi_form": wifi_form,
        },
        "routers", router.name,
    )


# --- Vifurushi ---------------------------------------------------------------------

@owner_required
@require_http_methods(["GET", "POST"])
def packages(request):
    owner = request.owner
    form = PackageForm(request.POST or None, initial={"is_active": True, "shared_users": 1})
    if request.method == "POST" and form.is_valid():
        package = form.save(commit=False)
        package.owner = owner
        package.sort_order = owner.packages.count()
        package.save()
        messages.success(request, f"Kifurushi “{package.name}” kimeongezwa.")
        return redirect("dashboard:packages")
    return render_owner(
        request, "dashboard/packages.html",
        {"packages": owner.packages.all(), "form": form}, "packages", "Vifurushi",
    )


@owner_required
@require_http_methods(["GET", "POST"])
def package_edit(request, pk):
    package = get_object_or_404(request.owner.packages, pk=pk)
    form = PackageForm(request.POST or None, instance=package)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Mabadiliko yamehifadhiwa. Yanaanza kufanya kazi papo hapo.")
        return redirect("dashboard:packages")
    return render_owner(
        request, "dashboard/package_edit.html", {"form": form, "package": package}, "packages", package.name,
    )


# --- Vocha za kuuza kwa mkono --------------------------------------------------------

@owner_required
@require_http_methods(["GET", "POST"])
def vouchers(request):
    owner = request.owner
    form = VoucherBatchForm(owner, request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not subscriptions.ensure_active(owner):
            messages.error(request, "Usajili wako umeisha. Lipia ada ya mwezi ili kutengeneza vocha mpya.")
            return redirect("dashboard:subscription")
        batch = secrets.token_hex(6)
        with transaction.atomic():
            Voucher.objects.bulk_create(
                Voucher(router=form.cleaned_data["router"], package=form.cleaned_data["package"], batch=batch)
                for _ in range(form.cleaned_data["count"])
            )
        return redirect("dashboard:voucher_print", batch=batch)

    batches = (
        Voucher.objects.filter(router__owner=owner, payment__isnull=True)
        .exclude(batch="")
        .values("batch", "package__name")
        .annotate(
            count=Count("pk"),
            used=Count("pk", filter=Q(activated_at__isnull=False)),
            created_at=Min("created_at"),
        )
        .order_by("-created_at")[:10]
    )
    return render_owner(
        request, "dashboard/vouchers.html",
        {"form": form, "batches": batches, "has_routers": owner.routers.exists(), "has_packages": owner.packages.exists()},
        "vouchers", "Vocha",
    )


@owner_required
def voucher_print(request, batch):
    owner = request.owner
    items = Voucher.objects.filter(router__owner=owner, batch=batch).select_related("package", "router")
    if not items:
        raise Http404
    return render(request, "dashboard/voucher_print.html", {"owner": owner, "vouchers": items})


# --- Mauzo -------------------------------------------------------------------------

@owner_required
def sales(request):
    paid = owner_payments(request.owner).filter(status=Payment.Status.PAID)
    page = Paginator(paid.select_related("package", "router").order_by("-paid_at"), 25).get_page(request.GET.get("ukurasa"))
    return render_owner(
        request, "dashboard/sales.html",
        {"page": page, "summary": sales_summary(owner_payments(request.owner)),
         "chart": bar_chart(daily_totals(paid, "paid_at", "amount", days=30))},
        "sales", "Mauzo",
    )


# --- Salio na kutoa pesa -------------------------------------------------------------

@owner_required
@require_http_methods(["GET", "POST"])
def wallet_view(request):
    owner = request.owner
    form = WithdrawForm(request.POST or None, initial={"phone": owner.phone})
    if request.method == "POST" and form.is_valid():
        try:
            wallet.request_withdrawal(owner, form.cleaned_data["amount"], form.cleaned_data["phone"])
        except ValidationError as exc:
            form.add_error("amount", exc.messages[0])
        else:
            messages.success(request, "Ombi lako limepokelewa. Pesa itatumwa kwenye namba yako hivi karibuni.")
            return redirect("dashboard:wallet")
    page = Paginator(owner.ledger.all(), 20).get_page(request.GET.get("ukurasa"))
    return render_owner(
        request, "dashboard/wallet.html",
        {"balance": wallet.balance(owner), "form": form, "page": page,
         "withdrawals": owner.withdrawals.all()[:8], "min_withdrawal": config.current().min_withdrawal},
        "wallet", "Salio",
    )


# --- Usajili -----------------------------------------------------------------------

@owner_required
@require_http_methods(["GET", "POST"])
def subscription(request):
    owner = request.owner
    if request.method == "POST":
        months = 3 if request.POST.get("months") == "3" else 1
        try:
            subscriptions.pay_from_balance(owner, months=months)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            messages.success(request, f"Asante! Umelipia miezi {months}.")
        return redirect("dashboard:subscription")
    return render_owner(
        request, "dashboard/subscription.html",
        {"balance": wallet.balance(owner), "charges": owner.subscription_charges.all()[:12],
         "fee_3": config.current().monthly_fee * 3, "cash_source": SubscriptionCharge.Source.CASH},
        "subscription", "Usajili",
    )


# --- Mipangilio --------------------------------------------------------------------

@owner_required
@require_http_methods(["GET", "POST"])
def settings_view(request):
    form = OwnerSettingsForm(request.POST or None, request.FILES or None, instance=request.owner)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Mipangilio imehifadhiwa.")
        return redirect("dashboard:settings")
    return render_owner(request, "dashboard/settings.html", {"form": form}, "settings", "Mipangilio")
