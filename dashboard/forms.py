from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _

from billing.phone import normalize_tz_phone
from core import config
from core.models import Owner, Package, Router


def clean_phone_value(raw):
    try:
        return normalize_tz_phone(raw)
    except ValidationError as exc:
        raise forms.ValidationError(exc.messages) from exc


class PhoneField(forms.CharField):
    def __init__(self, **kwargs):
        kwargs.setdefault("label", _("Namba ya simu"))
        kwargs.setdefault("max_length", 20)
        kwargs.setdefault(
            "widget",
            forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel", "placeholder": "0712 345 678"}),
        )
        super().__init__(**kwargs)

    def clean(self, value):
        return clean_phone_value(super().clean(value))


class LanguageField(forms.ChoiceField):
    def __init__(self, **kwargs):
        kwargs.setdefault("label", _("Lugha ya dashboard yako"))
        kwargs.setdefault("choices", settings.LANGUAGES)
        kwargs.setdefault("widget", forms.RadioSelect(attrs={"class": "choice-pills"}))
        super().__init__(**kwargs)


class SignupForm(forms.Form):
    business_name = forms.CharField(
        label=_("Jina la biashara yako"), max_length=120,
        widget=forms.TextInput(attrs={"placeholder": _("mfano Neema WiFi"), "autocomplete": "organization"}),
    )
    phone = PhoneField(help_text=_("Utaitumia kuingia, na kupokea pesa zako."))
    password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label=_("Rudia nenosiri"), widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    language = LanguageField(required=False, help_text=_("Unaweza kubadilisha baadaye wakati wowote."))

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        if get_user_model().objects.filter(username=phone).exists():
            raise forms.ValidationError(_("Namba hii tayari ina akaunti. Ingia badala yake."))
        return phone

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", _("Password hazilingani."))
        elif p1:
            try:
                password_validation.validate_password(p1)
            except ValidationError:
                self.add_error("password1", _("Tumia password ya angalau herufi 8, isiyo rahisi kukisia."))
        return cleaned


class LoginForm(forms.Form):
    # Wamiliki wanaingia kwa namba ya simu. Super Admin ana jina (mfano "admin"), kwa hiyo
    # thamani isiyo namba inakubaliwa, lakini kwa akaunti ya superuser tu.
    phone = forms.CharField(
        label=_("Namba ya simu"), max_length=150,
        widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "username", "placeholder": "0712 345 678"}),
    )
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        raw, password = cleaned.get("phone"), cleaned.get("password")
        if raw and password:
            try:
                username, staff_only = normalize_tz_phone(raw), False
            except ValidationError:
                username, staff_only = raw.strip(), True
            user = authenticate(self.request, username=username, password=password)
            if user is None or (staff_only and not user.is_superuser):
                raise forms.ValidationError(_("Namba ya simu au password si sahihi."))
            self.user = user
        return cleaned


class RouterForm(forms.ModelForm):
    class Meta:
        model = Router
        fields = ["name", "location", "wifi_name"]
        labels = {"name": _("Jina la eneo"), "location": _("Mahali (si lazima)"), "wifi_name": _("Jina la WiFi (si lazima)")}
        help_texts = {"wifi_name": _("Jina linaloonekana kwenye simu za wateja. Acha tupu kutobadilisha WiFi ya router.")}
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("mfano Duka la Kati")}),
            "location": forms.TextInput(attrs={"placeholder": _("mfano Sinza, Dar es Salaam")}),
            "wifi_name": forms.TextInput(attrs={"placeholder": _("mfano Neema WiFi")}),
        }

    def clean_name(self):
        # Mstari mmoja tu: jina linaingia kwenye script ya router na kwenye vocha zinazochapishwa.
        return " ".join(self.cleaned_data["name"].split())

    def clean_location(self):
        return " ".join(self.cleaned_data["location"].split())


class WifiNameForm(forms.ModelForm):
    class Meta:
        model = Router
        fields = ["wifi_name"]
        labels = {"wifi_name": _("Jina la WiFi")}
        help_texts = {"wifi_name": _("Jina linaloonekana kwenye simu za wateja. Acha tupu kutobadilisha WiFi ya router.")}
        widgets = {"wifi_name": forms.TextInput(attrs={"placeholder": _("mfano Neema WiFi")})}


DURATION_UNITS = [(1, _("Dakika")), (60, _("Saa")), (60 * 24, _("Siku")), (60 * 24 * 7, _("Wiki")), (60 * 24 * 30, _("Mwezi"))]
SPEED_CHOICES = [
    ("", _("Bila kikomo")),
    ("512k/1M", _("Hadi 1 Mbps")),
    ("1M/2M", _("Hadi 2 Mbps")),
    ("1M/3M", _("Hadi 3 Mbps")),
    ("2M/5M", _("Hadi 5 Mbps")),
    ("3M/10M", _("Hadi 10 Mbps")),
]


class PackageForm(forms.ModelForm):
    duration_value = forms.IntegerField(label=_("Muda"), min_value=1, max_value=1000)
    duration_unit = forms.TypedChoiceField(label=_("Kipimo"), choices=DURATION_UNITS, coerce=int, initial=60)
    rate_limit = forms.ChoiceField(label=_("Kasi"), choices=SPEED_CHOICES, required=False)

    class Meta:
        model = Package
        fields = ["name", "price", "rate_limit", "shared_users", "is_active"]
        labels = {
            "name": _("Jina la kifurushi"), "price": _("Bei (Tsh)"),
            "shared_users": _("Simu ngapi kwa vocha moja"), "is_active": _("Kinauzwa"),
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("mfano Siku 1")}),
            "price": forms.NumberInput(attrs={"inputmode": "numeric", "min": 1}),
            "shared_users": forms.NumberInput(attrs={"min": 1, "max": 10}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        minutes = self.instance.duration_minutes if self.instance.pk else None
        if minutes:
            for unit, _label in reversed(DURATION_UNITS):
                if minutes % unit == 0:
                    self.initial.update(duration_value=minutes // unit, duration_unit=unit)
                    break
        current = self.instance.rate_limit if self.instance.pk else ""
        if current and current not in dict(SPEED_CHOICES):
            self.fields["rate_limit"].choices = SPEED_CHOICES + [(current, _("Maalum (%(speed)s)") % {"speed": current})]

    def clean_shared_users(self):
        value = self.cleaned_data["shared_users"]
        if not 1 <= value <= 10:
            raise forms.ValidationError(_("Weka namba kati ya 1 na 10."))
        return value

    def save(self, commit=True):
        self.instance.duration_minutes = self.cleaned_data["duration_value"] * self.cleaned_data["duration_unit"]
        return super().save(commit)


class VoucherBatchForm(forms.Form):
    package = forms.ModelChoiceField(label=_("Kifurushi"), queryset=Package.objects.none(), empty_label=None)
    router = forms.ModelChoiceField(label=_("Eneo (router)"), queryset=Router.objects.none(), empty_label=None)
    count = forms.IntegerField(label=_("Idadi ya vocha"), min_value=1, max_value=100, initial=10)

    def __init__(self, owner, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["package"].queryset = owner.packages.filter(is_active=True)
        self.fields["router"].queryset = owner.routers.filter(is_active=True)


class WithdrawForm(forms.Form):
    amount = forms.IntegerField(
        label=_("Kiasi (Tsh)"), min_value=1,
        widget=forms.NumberInput(attrs={"inputmode": "numeric", "placeholder": _("mfano 20000")}),
    )
    phone = PhoneField(label=_("Tuma kwenda namba"))

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        minimum = config.current().min_withdrawal
        if amount < minimum:
            raise forms.ValidationError(_("Kiasi cha chini ni Tsh %(amount)s.") % {"amount": f"{minimum:,}"})
        return amount


class OwnerSettingsForm(forms.ModelForm):
    language = LanguageField()

    class Meta:
        model = Owner
        fields = ["business_name", "phone", "logo", "language"]
        labels = {
            "business_name": _("Jina la biashara"),
            "phone": _("Namba ya kupokea pesa"),
            "logo": _("Logo (inaonekana kwenye ukurasa wa kulipia)"),
        }
        widgets = {"phone": forms.TextInput(attrs={"inputmode": "tel"})}

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data["phone"])

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        # Faili jipya tu: logo iliyopo (FieldFile) ikikosekana kwenye storage, .size ingeleta 500.
        if isinstance(logo, UploadedFile) and logo.size > 2 * 1024 * 1024:
            raise forms.ValidationError(_("Picha isizidi MB 2."))
        return logo
