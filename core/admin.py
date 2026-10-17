from django.contrib import admin, messages
from django.utils.html import format_html

from radius import routeros

from .models import Owner, Package, Router, RouterCommand


class RouterInline(admin.TabularInline):
    model = Router
    extra = 0
    fields = ("name", "slug", "location", "is_active")


class PackageInline(admin.TabularInline):
    model = Package
    extra = 0
    fields = ("name", "price", "duration_minutes", "rate_limit", "shared_users", "is_active", "sort_order")


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ("business_name", "phone", "commission_percent", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("business_name", "phone", "user__username")
    inlines = [RouterInline, PackageInline]


class RouterCommandInline(admin.TabularInline):
    model = RouterCommand
    extra = 0
    fields = ("action", "created_at", "delivered_at")
    readonly_fields = ("action", "created_at", "delivered_at")
    can_delete = False
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Router)
class RouterAdmin(admin.ModelAdmin):
    list_display = (
        "name", "owner", "online_status", "active_clients", "last_seen_at", "nas_identifier", "is_active",
    )
    list_filter = ("is_active", "owner")
    search_fields = ("name", "slug", "nas_identifier", "owner__business_name")
    list_select_related = ("owner",)
    readonly_fields = (
        "setup_command", "online_status", "last_seen_at", "routeros_version", "uptime", "active_clients",
    )
    fieldsets = (
        (None, {"fields": ("owner", "name", "slug", "location", "nas_identifier", "is_active")}),
        ("Usanidi", {
            "fields": ("setup_command", "radius_secret", "login_url"),
            "description": "Bandika mstari huu kwenye terminal ya MikroTik ili kuiunganisha na JamiiLite.",
        }),
        ("Hali ya router", {
            "fields": ("online_status", "last_seen_at", "routeros_version", "uptime", "active_clients"),
        }),
    )
    inlines = [RouterCommandInline]
    actions = ["send_reboot", "send_reapply_setup"]

    @admin.display(description="hali")
    def online_status(self, obj):
        if obj.is_online:
            return format_html('<span style="color:#1a7f37;font-weight:600">● Online</span>')
        return format_html('<span style="color:#b42318">● Offline</span>')

    @admin.display(description="mstari wa usanidi")
    def setup_command(self, obj):
        if not obj.pk:
            return "Hifadhi router kwanza."
        if not obj.nas_identifier:
            return "Weka NAS identifier kwanza, kisha hifadhi."
        return format_html(
            '<code style="display:block;white-space:pre-wrap;word-break:break-all">{}</code>',
            routeros.provision_command(obj),
        )

    def _queue(self, request, queryset, action):
        RouterCommand.objects.bulk_create(RouterCommand(router=r, action=action) for r in queryset)
        self.message_user(
            request,
            f"Agizo limetumwa kwa routers {queryset.count()}. "
            "Litatekelezwa router ikiripoti (ndani ya dakika 1 kama iko online).",
            messages.SUCCESS,
        )

    @admin.action(description="Washa upya (reboot) routers zilizochaguliwa")
    def send_reboot(self, request, queryset):
        self._queue(request, queryset, RouterCommand.Action.REBOOT)

    @admin.action(description="Weka upya usanidi wa JamiiLite kwenye routers zilizochaguliwa")
    def send_reapply_setup(self, request, queryset):
        self._queue(request, queryset, RouterCommand.Action.REAPPLY_SETUP)


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "price", "duration_minutes", "rate_limit", "is_active")
    list_filter = ("is_active", "owner")
    search_fields = ("name", "owner__business_name")
    list_select_related = ("owner",)
