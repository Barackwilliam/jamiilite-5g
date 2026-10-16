from django.contrib import admin

from .models import Payment, Voucher


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("phone", "amount", "status", "package", "router", "provider", "created_at")
    list_filter = ("status", "provider", "router__owner")
    search_fields = ("phone", "provider_reference")
    list_select_related = ("package", "router")
    readonly_fields = ("id", "created_at", "paid_at")


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ("code", "package", "router", "activated_at", "expires_at", "created_at")
    list_filter = ("router__owner", "router")
    search_fields = ("code",)
    list_select_related = ("package", "router")
    readonly_fields = ("created_at",)
