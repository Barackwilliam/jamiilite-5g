from django.contrib import admin

from .models import LedgerEntry, Payment, SubscriptionCharge, Voucher, Withdrawal


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


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "owner", "kind", "amount", "description")
    list_filter = ("kind", "owner")
    search_fields = ("owner__business_name", "description")
    list_select_related = ("owner",)
    # Rekodi za salio hazibadilishwi: kosa linarekebishwa kwa rekodi mpya ya marekebisho.
    readonly_fields = ("owner", "kind", "amount", "description", "payment", "withdrawal", "created_at")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ("created_at", "owner", "amount", "phone", "status", "processed_at")
    list_filter = ("status",)
    search_fields = ("owner__business_name", "phone", "reference")
    list_select_related = ("owner",)
    readonly_fields = ("id", "owner", "amount", "phone", "status", "created_at", "processed_at", "processed_by")


@admin.register(SubscriptionCharge)
class SubscriptionChargeAdmin(admin.ModelAdmin):
    list_display = ("created_at", "owner", "months", "amount", "source", "period_end")
    list_filter = ("source",)
    search_fields = ("owner__business_name",)
    list_select_related = ("owner",)
    readonly_fields = ("owner", "months", "amount", "source", "period_end", "created_at", "created_by")
