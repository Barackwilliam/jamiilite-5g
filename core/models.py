import secrets
from datetime import timedelta

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

rate_limit_validator = RegexValidator(
    regex=r"^\d+[kKmM]?/\d+[kKmM]?$",
    message="Andika kasi kama upload/download, mfano 2M/2M au 512k/1M.",
)


ssid_validator = RegexValidator(
    regex=r"^[\x20-\x7e]{1,32}$",
    message="Tumia herufi za kawaida tu (bila emoji), zisizozidi 32.",
)


def generate_radius_secret():
    return secrets.token_urlsafe(24)


def generate_provision_token():
    return secrets.token_urlsafe(32)


# Router inaripoti kila dakika. Ikikaa kimya zaidi ya hapa, tunaiona offline.
ONLINE_THRESHOLD = timedelta(minutes=3)


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
    is_active = models.BooleanField(
        "yuko hai",
        default=True,
        help_text="Ukiondoa tiki, mmiliki amesitishwa: hawezi kuingia wala kuuza.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Usajili: siku za majaribio, kisha ada ya kila mwezi.
    trial_ends_at = models.DateTimeField("majaribio yanaisha", null=True, blank=True)
    paid_until = models.DateTimeField("amelipia hadi", null=True, blank=True)

    class Meta:
        verbose_name = "mmiliki"
        verbose_name_plural = "wamiliki"
        ordering = ["business_name"]

    def __str__(self):
        return self.business_name

    @property
    def subscription_ends_at(self):
        dates = [d for d in (self.trial_ends_at, self.paid_until) if d]
        return max(dates) if dates else None

    def is_in_trial(self, now=None):
        now = now or timezone.now()
        return bool(self.trial_ends_at and now < self.trial_ends_at) and not (
            self.paid_until and now < self.paid_until
        )

    def has_active_subscription(self, now=None):
        ends = self.subscription_ends_at
        return ends is not None and (now or timezone.now()) < ends

    def can_sell(self, now=None):
        return self.is_active and self.has_active_subscription(now)


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
    wifi_name = models.CharField(
        "jina la WiFi (SSID)",
        max_length=32,
        blank=True,
        validators=[ssid_validator],
        help_text="Jina linaloonekana kwenye simu za wateja. Acha tupu kutobadilisha WiFi ya router.",
    )
    nas_identifier = models.CharField(
        "NAS identifier",
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        help_text=(
            "Jina la MikroTik (/system identity), mfano wifi-majaribio. "
            "RADIUS server inalitumia kujua ombi limetoka router ipi."
        ),
    )
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
    provision_token = models.CharField(
        "token ya usanidi",
        max_length=64,
        unique=True,
        default=generate_provision_token,
        editable=False,
        help_text="Siri iliyo kwenye link ya usanidi na ripoti za router. Usiitoe hadharani.",
    )
    is_active = models.BooleanField("iko hai", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Taarifa zinazoletwa na router yenyewe kila inaporipoti (check-in).
    last_seen_at = models.DateTimeField("ilionekana mara ya mwisho", null=True, blank=True)
    routeros_version = models.CharField("toleo la RouterOS", max_length=60, blank=True)
    uptime = models.CharField("muda iliowaka", max_length=40, blank=True)
    active_clients = models.PositiveIntegerField("wateja online", default=0)

    class Meta:
        verbose_name = "router"
        verbose_name_plural = "routers"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.owner})"

    @property
    def is_online(self):
        if self.last_seen_at is None:
            return False
        return timezone.now() - self.last_seen_at <= ONLINE_THRESHOLD

    def save(self, *args, **kwargs):
        # Thamani tupu ihifadhiwe kama NULL ili unique isizuie routers nyingi zisizo nayo.
        self.nas_identifier = (self.nas_identifier or "").strip() or None
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


class RouterCommand(models.Model):
    """Agizo linalosubiri router ilichukue kwenye ripoti yake inayofuata."""

    class Action(models.TextChoices):
        REBOOT = "reboot", "Washa upya (reboot)"
        REAPPLY_SETUP = "reapply_setup", "Weka upya usanidi wa JamiiLite"

    router = models.ForeignKey(
        Router, on_delete=models.CASCADE, related_name="commands", verbose_name="router"
    )
    action = models.CharField("agizo", max_length=20, choices=Action.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField("lilipokelewa", null=True, blank=True)

    class Meta:
        verbose_name = "agizo la router"
        verbose_name_plural = "maagizo ya router"
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["router", "created_at"],
                condition=models.Q(delivered_at__isnull=True),
                name="routercommand_pending_idx",
            ),
        ]

    def __str__(self):
        return f"{self.get_action_display()} → {self.router.name}"


class PlatformConfig(models.Model):
    """
    Mipangilio ya jukwaa inayobadilishwa na Super Admin bila kugusa server.

    Kuna safu moja tu (pk=1). Sehemu ikiachwa tupu, thamani ya `.env`
    (settings.JAMIILITE_*) inatumika. Soma kupitia core.config, si moja kwa moja.
    """

    monthly_fee = models.PositiveIntegerField("ada ya mwezi (Tsh)", null=True, blank=True)
    trial_days = models.PositiveSmallIntegerField("siku za majaribio", null=True, blank=True)
    min_withdrawal = models.PositiveIntegerField("kiasi cha chini cha kutoa (Tsh)", null=True, blank=True)
    sale_fee_percent = models.PositiveSmallIntegerField(
        "makato kwa kila mauzo (%)", null=True, blank=True,
        help_text="Kufidia ada za mtoa huduma wa malipo. 0 = mmiliki anapata kiasi chote.",
    )
    whatsapp_number = models.CharField("namba ya WhatsApp ya msaada", max_length=15, blank=True)
    signups_open = models.BooleanField(
        "usajili wa wamiliki wapya uko wazi", default=True,
        help_text="Ukiondoa tiki, ukurasa wa kujisajili unafungwa kwa muda.",
    )
    announcement = models.CharField(
        "tangazo kwa wamiliki wote", max_length=280, blank=True,
        help_text="Linaonekana juu ya dashboard ya kila mmiliki. Acha tupu kuliondoa.",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        verbose_name = "mipangilio ya jukwaa"
        verbose_name_plural = "mipangilio ya jukwaa"

    def __str__(self):
        return "Mipangilio ya JamiiLite"

    @classmethod
    def load(cls):
        return cls.objects.filter(pk=1).first() or cls(pk=1)


class ServiceHeartbeat(models.Model):
    """Huduma inayoendeshwa kando (mfano RADIUS server) inaripoti kuwa iko hai."""

    name = models.CharField("huduma", max_length=40, unique=True)
    host = models.CharField("kompyuta", max_length=120, blank=True)
    pid = models.PositiveIntegerField(null=True, blank=True)
    started_at = models.DateTimeField("ilianza")
    last_seen_at = models.DateTimeField("ilionekana mwisho")
    stats = models.JSONField("takwimu", default=dict, blank=True)

    class Meta:
        verbose_name = "mapigo ya huduma"
        verbose_name_plural = "mapigo ya huduma"

    def __str__(self):
        return self.name
