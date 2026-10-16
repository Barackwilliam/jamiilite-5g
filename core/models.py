import secrets

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils.text import slugify

rate_limit_validator = RegexValidator(
    regex=r"^\d+[kKmM]?/\d+[kKmM]?$",
    message="Andika kasi kama upload/download, mfano 2M/2M au 512k/1M.",
)


def generate_radius_secret():
    return secrets.token_urlsafe(24)


class Owner(models.Model):
    """Mmiliki wa WiFi, yaani mteja wa JamiiLite 5G."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owner",
        verbose_name="akaunti",
    )
    business_name = models.CharField("jina la biashara", max_length=120)
    phone = models.CharField("namba ya simu", max_length=20)
    logo = models.ImageField("logo", upload_to="owners/logos/", blank=True)
    commission_percent = models.DecimalField(
        "kamisheni (%)",
        max_digits=5,
        decimal_places=2,
        default=5,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField("yuko hai", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "mmiliki"
        verbose_name_plural = "wamiliki"
        ordering = ["business_name"]

    def __str__(self):
        return self.business_name


class Router(models.Model):
    """MikroTik moja ya mmiliki. Kila router ina ukurasa wake wa kulipia."""

    owner = models.ForeignKey(
        Owner, on_delete=models.CASCADE, related_name="routers", verbose_name="mmiliki"
    )
    name = models.CharField("jina", max_length=80)
    slug = models.SlugField(
        "kitambulisho cha ukurasa",
        max_length=60,
        unique=True,
        blank=True,
        help_text="Inatumika kwenye link ya ukurasa wa kulipia: /p/<kitambulisho>/",
    )
    location = models.CharField("mahali", max_length=120, blank=True)
    radius_secret = models.CharField(
        "RADIUS secret", max_length=64, default=generate_radius_secret
    )
    login_url = models.URLField(
        "login URL ya hotspot",
        blank=True,
        help_text=(
            "Mfano http://login.wifi.test/login. Ikiwekwa, vocha zinatumwa hapa tu "
            "na link-login-only inayotumwa na MikroTik inapuuzwa."
        ),
    )
    is_active = models.BooleanField("iko hai", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "router"
        verbose_name_plural = "routers"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.owner})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f"{self.owner.business_name}-{self.name}")[:50] or "router"
            slug = base
            while Router.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{secrets.token_hex(2)}"
            self.slug = slug
        super().save(*args, **kwargs)


class Package(models.Model):
    """Kifurushi cha internet ambacho mmiliki anauza, mfano saa 1 kwa Tsh 500."""

    owner = models.ForeignKey(
        Owner, on_delete=models.CASCADE, related_name="packages", verbose_name="mmiliki"
    )
    name = models.CharField("jina", max_length=60)
    price = models.PositiveIntegerField("bei (Tsh)", validators=[MinValueValidator(1)])
    duration_minutes = models.PositiveIntegerField(
        "muda (dakika)", validators=[MinValueValidator(1)]
    )
    rate_limit = models.CharField(
        "kasi", max_length=20, blank=True, validators=[rate_limit_validator]
    )
    shared_users = models.PositiveSmallIntegerField(
        "vifaa kwa vocha moja", default=1, validators=[MinValueValidator(1)]
    )
    is_active = models.BooleanField("kinauzwa", default=True)
    sort_order = models.PositiveSmallIntegerField("mpangilio", default=0)

    class Meta:
        verbose_name = "kifurushi"
        verbose_name_plural = "vifurushi"
        ordering = ["sort_order", "price"]
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gt=0), name="package_price_positive"),
            models.CheckConstraint(
                condition=models.Q(duration_minutes__gt=0), name="package_duration_positive"
            ),
        ]

    def __str__(self):
        return f"{self.name} - Tsh {self.price_display}"

    @property
    def price_display(self):
        return f"{self.price:,}"

    @property
    def summary(self):
        """Maelezo mafupi kwa mteja, bila kurudia jina la kifurushi."""
        parts = []
        if self.name.strip().lower() != self.duration_label:
            parts.append(self.duration_label)
        if self.rate_limit:
            parts.append(f"kasi {self.rate_limit}")
        return " · ".join(parts)

    @property
    def duration_label(self):
        minutes = self.duration_minutes
        if minutes % (60 * 24 * 7) == 0:
            count, unit = minutes // (60 * 24 * 7), "wiki"
        elif minutes % (60 * 24) == 0:
            count, unit = minutes // (60 * 24), "siku"
        elif minutes % 60 == 0:
            count, unit = minutes // 60, "saa"
        else:
            count, unit = minutes, "dakika"
        return f"{unit} {count}"
