from django.contrib import admin

from .models import Owner, Package, Router


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


@admin.register(Router)
class RouterAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "slug", "nas_identifier", "location", "is_active")
    list_filter = ("is_active", "owner")
    search_fields = ("name", "slug", "nas_identifier", "owner__business_name")
    list_select_related = ("owner",)


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "price", "duration_minutes", "rate_limit", "is_active")
    list_filter = ("is_active", "owner")
    search_fields = ("name", "owner__business_name")
    list_select_related = ("owner",)
