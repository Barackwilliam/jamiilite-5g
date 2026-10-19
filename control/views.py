from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from billing import subscriptions, wallet
from billing.models import Payment, SubscriptionCharge, Voucher, Withdrawal
from core import config
from core.models import PlatformConfig, Router, RouterCommand, generate_radius_secret
from dashboard.stats import sales_summary
from radius import routeros
from ui.charts import bar_chart, daily_totals

from . import queries, status
from .forms import AdminRouterForm, PlatformConfigForm

NAV = [
    ("home", "Muhtasari", "home"),
    ("owners", "Wamiliki", "users"),
    ("withdrawals", "Kutoa pesa", "send"),
    ("routers", "Routers", "router"),
    ("payments", "Malipo", "chart"),
]

CASH_MONTHS = (1, 3, 6, 12)


def superuser_required(view):
    @login_required(login_url="dashboard:login")
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise Http404
        return view(request, *args, **kwargs)

    return wrapper


def render_control(request, template, context, active, title):
    pending = queries.pending_withdrawals().count()
    nav = [
        {
            "url": reverse(f"control:{name}"),
            "label": label,
            "icon": icon,
            "active": name == active,
            "badge": pending if name == "withdrawals" and pending else None,
            "bottom": name in ("home", "owners", "withdrawals", "routers"),
        }
        for name, label, icon in NAV
    ]
    nav += [
        {"section": "Mfumo"},
        {"url": reverse("control:status"), "label": "Hali ya mfumo", "icon": "pulse", "active": active == "status"},
        {"url": reverse("control:config"), "label": "Mipangilio", "icon": "settings", "active": active == "config"},
        {"url": reverse("admin:index"), "label": "Django admin", "icon": "shield"},
    ]
    user = request.user
    context.update(
        area="control",
        nav=nav,
        page_title=title,
        home_url=reverse("control:home"),
        who_name=user.get_full_name() or user.username,
        who_detail="Super Admin",
        who_initial=(user.get_full_name() or user.username)[:1].upper(),
        state_labels=queries.STATE_LABELS,
    )
    return render(request, template, context)


@superuser_required
def home(request):
    now = timezone.now()
    paid = Payment.objects.filter(status=Payment.Status.PAID)
    month_ago = now - timedelta(days=30)
    pending = queries.pending_withdrawals()
    checks = status.run_checks(now)
    context = {
        "owners": queries.owner_counts(now),
        "routers": queries.router_counts(now),
        "gmv": sales_summary(Payment.objects.all(), now),
        "sub_revenue": SubscriptionCharge.objects.filter(created_at__gte=month_ago).aggregate(n=Sum("amount"))["n"] or 0,
        "held": queries.held_balance(),
        "pending_count": pending.count(),
        "pending_total": pending.aggregate(n=Sum("amount"))["n"] or 0,
        "pending_list": pending.select_related("owner").order_by("created_at")[:5],
        "new_owners": queries.owners_with_state(now).filter(created_at__gte=now - timedelta(days=7)).count(),
        "gmv_chart": bar_chart(daily_totals(paid, "paid_at", "amount", days=30, now=now)),
        "sub_chart": bar_chart(daily_totals(SubscriptionCharge.objects.all(), "created_at", "amount", days=30, now=now)),
        "offline_routers": queries.routers_offline_first(now).filter(online=0, last_seen_at__isnull=False)[:6],
        "expiring": queries.owners_with_state(now)
        .filter(is_active=True, ends_at__gt=now, ends_at__lte=now + timedelta(days=3))
        .order_by("ends_at")[:6],
        "monthly_fee": config.current().monthly_fee,
        "checks": checks,
        "system_state": status.overall(checks),
        "problems": [c for c in checks if c.state in ("bad", "warn")],
    }
    return render_control(request, "control/home.html", context, "home", "Muhtasari wa jukwaa")


@superuser_required
def owners(request):
    q = request.GET.get("q", "").strip()
    state = request.GET.get("hali", "")
    qs = queries.owners_with_state()
    if q:
        qs = qs.filter(Q(business_name__icontains=q) | Q(phone__icontains=q) | Q(user__username__icontains=q))
    if state in queries.STATE_LABELS:
        qs = qs.filter(state=state)
    page = Paginator(qs.order_by("-created_at"), 25).get_page(request.GET.get("ukurasa"))
    balances = queries.owner_balances([o.pk for o in page.object_list])
    for owner in page.object_list:
        owner.balance = balances.get(owner.pk, 0)
    return render_control(
        request, "control/owners.html",
        {"page": page, "q": q, "state": state, "counts": queries.owner_counts()},
        "owners", "Wamiliki",
    )


@superuser_required
@require_http_methods(["GET", "POST"])
def owner_detail(request, pk):
    owner = get_object_or_404(queries.owners_with_state(), pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action in ("suspend", "activate"):
            owner.is_active = action == "activate"
            owner.save(update_fields=["is_active"])
            messages.success(request, f"{owner.business_name} {'amerudishwa' if owner.is_active else 'amesitishwa'}.")
        elif action == "cash":
            try:
                months = int(request.POST.get("months", ""))
            except ValueError:
                months = 0
            if months in CASH_MONTHS:
                charge = subscriptions.record_cash_payment(owner, months, request.user)
                messages.success(
                    request, f"Umemwongezea miezi {months}. Sasa amelipia mpaka {timezone.localtime(charge.period_end):%d/%m/%Y}."
                )
            else:
                messages.error(request, "Chagua idadi sahihi ya miezi.")
        return redirect("control:owner_detail", pk=owner.pk)

    payments = Payment.objects.filter(router__owner=owner)
    paid = payments.filter(status=Payment.Status.PAID)
    context = {
        "o": owner,
        "balance": wallet.balance(owner),
        "summary": sales_summary(payments),
        "chart": bar_chart(daily_totals(paid, "paid_at", "amount", days=30)),
        "routers": owner.routers.order_by("name"),
        "packages": owner.packages.all(),
        "recent_sales": paid.select_related("package", "router").order_by("-paid_at")[:8],
        "withdrawals": owner.withdrawals.all()[:6],
        "charges": owner.subscription_charges.select_related("created_by")[:6],
        "cash_months": CASH_MONTHS,
        "monthly_fee": config.current().monthly_fee,
    }
    return render_control(request, "control/owner_detail.html", context, "owners", owner.business_name)


@superuser_required
def withdrawals(request):
    status = request.GET.get("hali", Withdrawal.Status.PENDING)
    qs = Withdrawal.objects.select_related("owner", "processed_by")
    if status in Withdrawal.Status.values:
        qs = qs.filter(status=status)
    qs = qs.order_by("created_at" if status == Withdrawal.Status.PENDING else "-created_at")
    page = Paginator(qs, 25).get_page(request.GET.get("ukurasa"))
    balances = queries.owner_balances({w.owner_id for w in page.object_list})
    for w in page.object_list:
        w.owner_balance = balances.get(w.owner_id, 0)
    return render_control(
        request, "control/withdrawals.html",
        {"page": page, "status": status, "statuses": Withdrawal.Status.choices},
        "withdrawals", "Maombi ya kutoa pesa",
    )


@superuser_required
@require_POST
def withdrawal_action(request, pk):
    action = request.POST.get("action")
    try:
        if action == "pay":
            reference = request.POST.get("reference", "").strip()
            if not reference:
                raise ValidationError("Weka namba ya muamala (reference) uliyotumia kulipa.")
            w = wallet.mark_withdrawal_paid(pk, request.user, reference)
            messages.success(request, f"Imewekwa kuwa imelipwa: {w.owner.business_name}, Tsh {w.amount:,}.")
        elif action == "reject":
            w = wallet.reject_withdrawal(pk, request.user, request.POST.get("note", "").strip())
            messages.success(request, f"Imekataliwa. Tsh {w.amount:,} imerudishwa kwenye salio la {w.owner.business_name}.")
    except Withdrawal.DoesNotExist:
        raise Http404
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    back = request.POST.get("back", "")
    if not url_has_allowed_host_and_scheme(back, {request.get_host()}, request.is_secure()):
        back = reverse("control:withdrawals")
    return redirect(back)


ROUTER_FILTERS = {
    "online": ("Online", lambda qs: qs.filter(online=1)),
    "offline": ("Offline", lambda qs: qs.filter(online=0, last_seen_at__isnull=False)),
    "bado": ("Hazijaunganishwa", lambda qs: qs.filter(last_seen_at__isnull=True)),
    "zimezimwa": ("Zimezimwa", lambda qs: qs.filter(is_active=False)),
}


@superuser_required
def routers(request):
    q = request.GET.get("q", "").strip()
    state = request.GET.get("hali", "")
    qs = queries.routers_offline_first()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(owner__business_name__icontains=q) | Q(nas_identifier__icontains=q))
    if state in ROUTER_FILTERS:
        qs = ROUTER_FILTERS[state][1](qs)
    page = Paginator(qs, 30).get_page(request.GET.get("ukurasa"))
    return render_control(
        request, "control/routers.html",
        {"page": page, "q": q, "state": state, "counts": queries.router_counts(),
         "filters": [(key, label) for key, (label, _) in ROUTER_FILTERS.items()]},
        "routers", "Routers zote",
    )


@superuser_required
@require_http_methods(["GET", "POST"])
def router_detail(request, pk):
    router = get_object_or_404(Router.objects.select_related("owner"), pk=pk)
    form = AdminRouterForm(instance=router)
    if request.method == "POST":
        action = request.POST.get("action")
        if action in ("reboot", "reapply"):
            kind = RouterCommand.Action.REBOOT if action == "reboot" else RouterCommand.Action.REAPPLY_SETUP
            RouterCommand.objects.create(router=router, action=kind)
            messages.success(request, "Agizo limetumwa. Router italichukua ndani ya dakika 1 ikiwa online.")
        elif action in ("disable", "enable"):
            router.is_active = action == "enable"
            router.save(update_fields=["is_active"])
            if router.is_active:
                messages.success(request, f"{router.name} imewashwa tena.")
            else:
                messages.success(request, f"{router.name} imezimwa: haiwezi kuuza wala kuingiza wateja wapya.")
        elif action == "rotate_secret":
            router.radius_secret = generate_radius_secret()
            router.save(update_fields=["radius_secret"])
            RouterCommand.objects.create(router=router, action=RouterCommand.Action.REAPPLY_SETUP)
            messages.success(request, "Siri mpya ya RADIUS imetengenezwa na router imetumiwa usanidi mpya.")
        elif action == "edit":
            old_nas = router.nas_identifier
            form = AdminRouterForm(request.POST, instance=router)
            if form.is_valid():
                router = form.save()
                if router.nas_identifier != old_nas:
                    RouterCommand.objects.create(router=router, action=RouterCommand.Action.REAPPLY_SETUP)
                    messages.success(request, "Imehifadhiwa. NAS identifier imebadilika, router imetumiwa usanidi upya.")
                else:
                    messages.success(request, "Mabadiliko yamehifadhiwa.")
                return redirect("control:router_detail", pk=router.pk)
        if action != "edit":
            return redirect("control:router_detail", pk=router.pk)

    now = timezone.now()
    paid = router.payments.filter(status=Payment.Status.PAID)
    nas = router.nas_identifier or ""
    context = {
        "router": router,
        "form": form,
        "summary": sales_summary(router.payments.all()),
        "chart": bar_chart(daily_totals(paid, "paid_at", "amount", days=14, now=now)),
        "live_vouchers": Voucher.objects.filter(router=router, activated_at__isnull=False, expires_at__gt=now).count(),
        "unused_vouchers": Voucher.objects.filter(router=router, activated_at__isnull=True).count(),
        "commands": router.commands.order_by("-created_at")[:10],
        "recent_sales": paid.select_related("package").order_by("-paid_at")[:6],
        "setup_command": routeros.provision_command(router) if nas else "",
        "portal_url": request.build_absolute_uri(reverse("portal:home", args=[router.slug])),
        "warnings": [w for w in status.radius_warnings() if nas and f"'{nas}'" in w["message"]][:8],
    }
    return render_control(request, "control/router_detail.html", context, "routers", router.name)


@superuser_required
def system_status(request):
    checks = status.run_checks()
    return render_control(
        request, "control/status.html",
        {"checks": checks, "system_state": status.overall(checks),
         "warnings": status.radius_warnings(), "env": status.environment_facts()},
        "status", "Hali ya mfumo",
    )


@superuser_required
@require_http_methods(["GET", "POST"])
def platform_config(request):
    row = PlatformConfig.load()
    form = PlatformConfigForm(request.POST or None, instance=row)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.updated_by = request.user
        saved.save()
        messages.success(request, "Mipangilio imehifadhiwa na inafanya kazi sasa hivi.")
        return redirect("control:config")
    return render_control(
        request, "control/config.html",
        {"form": form, "row": row, "effective": config.current()},
        "config", "Mipangilio ya jukwaa",
    )


@superuser_required
def payments(request):
    status = request.GET.get("hali", Payment.Status.PAID)
    qs = Payment.objects.select_related("router__owner", "package").order_by("-created_at")
    if status in Payment.Status.values:
        qs = qs.filter(status=status)
    page = Paginator(qs, 30).get_page(request.GET.get("ukurasa"))
    return render_control(
        request, "control/payments.html",
        {"page": page, "status": status, "statuses": Payment.Status.choices},
        "payments", "Malipo ya wateja",
    )
