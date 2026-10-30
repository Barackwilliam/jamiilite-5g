import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from core.models import Package, Router

# Hakuna herufi zinazochanganya (0/O, 1/I/L) ili mteja asikosee kuandika.
VOUCHER_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
VOUCHER_LENGTH = 8


def generate_voucher_code():
    return "".join(secrets.choice(VOUCHER_ALPHABET) for _ in range(VOUCHER_LENGTH))


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Inasubiri")
        PAID = "paid", _("Imelipwa")
        FAILED = "failed", _("Imeshindwa")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    router = models.ForeignKey(
        Router, on_delete=models.PROTECT, related_name="payments", verbose_name="router"
    )
    package = models.ForeignKey(
        Package, on_delete=models.PROTECT, related_name="payments", verbose_name="kifurushi"
    )
    phone = models.CharField("namba ya simu", max_length=12)
    amount = models.PositiveIntegerField("kiasi (Tsh)")
    status = models.CharField(
        "hali", max_length=10, choices=Status.choices, default=Status.PENDING
    )
    provider = models.CharField("mtoa huduma", max_length=30)
    provider_reference = models.CharField("kumbukumbu ya mtoa huduma", max_length=100, blank=True)
    # Ukurasa wa mtoa huduma (mfano Pesapal) unaowekwa ndani ya ukurasa wetu wa kulipia.
    checkout_url = models.URLField("ukurasa wa kulipia", max_length=500, blank=True)
    # Namba ya muamala kutoka kwa mtandao (mfano M-Pesa), kwa ajili ya kufuatilia malipo.
    confirmation_code = models.CharField("namba ya muamala", max_length=100, blank=True)
    last_checked_at = models.DateTimeField("ilikaguliwa mwisho", null=True, blank=True)
    failure_reason = models.CharField("sababu ya kushindwa", max_length=255, blank=True)
    client_mac = models.CharField("MAC ya kifaa", max_length=17, blank=True)
    client_ip = models.GenericIPAddressField("IP ya kifaa", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "malipo"
        verbose_name_plural = "malipo"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["router", "-created_at"], name="payment_router_recent_idx"),
            models.Index(fields=["status", "-created_at"], name="payment_status_recent_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_reference"],
                condition=~models.Q(provider_reference=""),
                name="payment_provider_reference_unique",
            ),
        ]

    def __str__(self):
        return f"{self.phone} - Tsh {self.amount_display} ({self.get_status_display()})"

    @property
    def phone_display(self):
        """255712345678 → 0712 345 678, kama watu wanavyoiandika."""
        local = "0" + self.phone[3:] if self.phone.startswith("255") else self.phone
        return f"{local[:4]} {local[4:7]} {local[7:]}".strip()

    @property
    def amount_display(self):
        return f"{self.amount:,}"


class Voucher(models.Model):
    code = models.CharField(
        "namba ya vocha", max_length=16, unique=True, default=generate_voucher_code
    )
    router = models.ForeignKey(
        Router, on_delete=models.PROTECT, related_name="vouchers", verbose_name="router"
    )
    package = models.ForeignKey(
        Package, on_delete=models.PROTECT, related_name="vouchers", verbose_name="kifurushi"
    )
    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="voucher",
        verbose_name="malipo",
    )
    # Vocha zilizotengenezwa kwa mkono na mmiliki (kuuza kwa pesa taslimu) zina
    # kundi lake, ili zichapishwe pamoja.
    batch = models.CharField("kundi", max_length=32, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField("ilianza kutumika", null=True, blank=True)
    expires_at = models.DateTimeField("inaisha", null=True, blank=True)

    class Meta:
        verbose_name = "vocha"
        verbose_name_plural = "vocha"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["router", "-created_at"], name="voucher_router_recent_idx"),
        ]

    def __str__(self):
        return self.code

    def activate(self, now=None):
        """Anza kuhesabu muda (wa kalenda) mara ya kwanza vocha inapotumika."""
        if self.activated_at is None:
            now = now or timezone.now()
            self.activated_at = now
            self.expires_at = now + timedelta(minutes=self.package.duration_minutes)
            self.save(update_fields=["activated_at", "expires_at"])

    def is_expired(self, now=None):
        if self.expires_at is None:
            return False
        return (now or timezone.now()) >= self.expires_at

    def remaining_seconds(self, now=None):
        if self.expires_at is None:
            return self.package.duration_minutes * 60
        return max(0, int((self.expires_at - (now or timezone.now())).total_seconds()))


class VoucherDevice(models.Model):
    """Kifaa (MAC) kilichotumia vocha. Kinazuia vocha moja kugawiwa kwa watu wengi."""

    voucher = models.ForeignKey(
        Voucher, on_delete=models.CASCADE, related_name="devices", verbose_name="vocha"
    )
    mac_address = models.CharField("MAC", max_length=17)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "kifaa"
        verbose_name_plural = "vifaa"
        constraints = [
            models.UniqueConstraint(fields=["voucher", "mac_address"], name="voucher_device_unique"),
        ]

    def __str__(self):
        return self.mac_address


class RouterVoucher(models.Model):
    """
    Njia ya "local": vocha ambayo JamiiLite imeshaituma kwa router fulani.
    Kila ripoti ya router inalinganisha orodha hii na vocha zinazopaswa kuwepo.
    """

    router = models.ForeignKey(
        Router, on_delete=models.CASCADE, related_name="pushed_vouchers", verbose_name="router"
    )
    voucher = models.ForeignKey(
        Voucher, on_delete=models.CASCADE, related_name="router_copies", verbose_name="vocha"
    )
    pushed_at = models.DateTimeField("imetumwa", default=timezone.now)

    class Meta:
        verbose_name = "vocha kwenye router"
        verbose_name_plural = "vocha kwenye routers"
        constraints = [
            models.UniqueConstraint(fields=["router", "voucher"], name="router_voucher_unique"),
        ]

    def __str__(self):
        return f"{self.voucher} → {self.router_id}"


class LedgerEntry(models.Model):
    """
    Kila mabadiliko ya salio la mmiliki. Salio = jumla ya `amount` zote.

    Mauzo yanaongeza (+), ada ya mwezi na kutoa pesa vinapunguza (−). Hakuna
    kufuta wala kubadilisha rekodi: kosa linarekebishwa kwa rekodi mpya.
    """

    class Kind(models.TextChoices):
        SALE = "sale", _("Mauzo")
        SUBSCRIPTION = "subscription", _("Ada ya mwezi")
        WITHDRAWAL = "withdrawal", _("Kutoa pesa")
        WITHDRAWAL_REVERSAL = "withdrawal_reversal", _("Kutoa pesa kumerudishwa")
        ADJUSTMENT = "adjustment", _("Marekebisho")

    owner = models.ForeignKey(
        "core.Owner", on_delete=models.PROTECT, related_name="ledger", verbose_name="mmiliki"
    )
    kind = models.CharField("aina", max_length=24, choices=Kind.choices)
    amount = models.BigIntegerField("kiasi (Tsh)")
    description = models.CharField("maelezo", max_length=200, blank=True)
    payment = models.OneToOneField(
        Payment, on_delete=models.PROTECT, null=True, blank=True, related_name="ledger_entry"
    )
    withdrawal = models.ForeignKey(
        "Withdrawal", on_delete=models.PROTECT, null=True, blank=True, related_name="ledger_entries"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "rekodi ya salio"
        verbose_name_plural = "rekodi za salio"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["owner", "-created_at"], name="ledger_owner_recent_idx")]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.amount:+,}"


class Withdrawal(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Inasubiri")
        PAID = "paid", _("Imelipwa")
        REJECTED = "rejected", _("Imekataliwa")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        "core.Owner", on_delete=models.PROTECT, related_name="withdrawals", verbose_name="mmiliki"
    )
    amount = models.PositiveIntegerField("kiasi (Tsh)")
    phone = models.CharField("namba ya kupokea", max_length=12)
    status = models.CharField("hali", max_length=10, choices=Status.choices, default=Status.PENDING)
    reference = models.CharField("kumbukumbu ya malipo", max_length=100, blank=True)
    note = models.CharField("maelezo", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        verbose_name = "ombi la kutoa pesa"
        verbose_name_plural = "maombi ya kutoa pesa"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"], name="withdrawal_status_idx")]

    def __str__(self):
        return f"{self.owner} - Tsh {self.amount:,} ({self.get_status_display()})"


class SubscriptionCharge(models.Model):
    """Malipo ya ada ya mwezi. Ndiyo mapato ya JamiiLite."""

    class Source(models.TextChoices):
        BALANCE = "balance", _("Kutoka kwenye salio")
        CASH = "cash", _("Pesa taslimu / nje ya mfumo")

    owner = models.ForeignKey(
        "core.Owner", on_delete=models.PROTECT, related_name="subscription_charges", verbose_name="mmiliki"
    )
    months = models.PositiveSmallIntegerField("miezi", default=1)
    amount = models.PositiveIntegerField("kiasi (Tsh)")
    source = models.CharField("chanzo", max_length=10, choices=Source.choices)
    period_end = models.DateTimeField("muda mpya unaisha")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        verbose_name = "malipo ya ada"
        verbose_name_plural = "malipo ya ada"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.owner} - miezi {self.months}"
