import secrets
import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone

from core.models import Package, Router

# Hakuna herufi zinazochanganya (0/O, 1/I/L) ili mteja asikosee kuandika.
VOUCHER_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
VOUCHER_LENGTH = 8


def generate_voucher_code():
    return "".join(secrets.choice(VOUCHER_ALPHABET) for _ in range(VOUCHER_LENGTH))


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Inasubiri"
        PAID = "paid", "Imelipwa"
        FAILED = "failed", "Imeshindwa"

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
