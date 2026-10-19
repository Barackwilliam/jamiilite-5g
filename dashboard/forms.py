from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.core.exceptions import ValidationError

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
        kwargs.setdefault("label", "Namba ya simu")
        kwargs.setdefault("max_length", 20)
        kwargs.setdefault(
            "widget",
            forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel", "placeholder": "0712 345 678"}),
        )
        super().__init__(**kwargs)

    def clean(self, value):
        return clean_phone_value(super().clean(value))


class SignupForm(forms.Form):
    business_name = forms.CharField(
        label="Jina la biashara yako", max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "mfano Neema WiFi", "autocomplete": "organization"}),
    )
    phone = PhoneField(help_text="Utaitumia kuingia, na kupokea pesa zako.")
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Rudia password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        if get_user_model().objects.filter(username=phone).exists():
            raise forms.ValidationError("Namba hii tayari ina akaunti. Ingia badala yake.")
        return phone

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Password hazilingani.")
        elif p1:
            try:
                password_validation.validate_password(p1)
            except ValidationError:
                self.add_error("password1", "Tumia password ya angalau herufi 8, isiyo rahisi kukisia.")
        return cleaned


class LoginForm(forms.Form):
    phone = PhoneField()
    password = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        phone, password = cleaned.get("phone"), cleaned.get("password")
        if phone and password:
            self.user = authenticate(self.request, username=phone, password=password)
            if self.user is None:
                raise forms.ValidationError("Namba ya simu au password si sahihi.")
        return cleaned


class RouterForm(forms.ModelForm):
    class Meta:
        model = Router
        fields = ["name", "location", "wifi_name"]
        labels = {"name": "Jina la eneo", "location": "Mahali (si lazima)", "wifi_name": "Jina la WiFi (si lazima)"}
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "mfano Duka la Kati"}),
            "location": forms.TextInput(attrs={"placeholder": "mfano Sinza, Dar es Salaam"}),
            "wifi_name": forms.TextInput(attrs={"placeholder": "mfano Neema WiFi"}),
        }


class WifiNameForm(forms.ModelForm):
    class Meta:
        model = Router
        fields = ["wifi_name"]
        labels = {"wifi_name": "Jina la WiFi"}
        widgets = {"wifi_name": forms.TextInput(attrs={"placeholder": "mfano Neema WiFi"})}


DURATION_UNITS = [(1, "Dakika"), (60, "Saa"), (60 * 24, "Siku"), (60 * 24 * 7, "Wiki"), (60 * 24 * 30, "Mwezi")]
SPEED_CHOICES = [
    ("", "Bila kikomo"),
    ("512k/1M", "Hadi 1 Mbps"),
    ("1M/2M", "Hadi 2 Mbps"),
    ("1M/3M", "Hadi 3 Mbps"),
    ("2M/5M", "Hadi 5 Mbps"),
    ("3M/10M", "Hadi 10 Mbps"),
]


class PackageForm(forms.ModelForm):
    duration_value = forms.IntegerField(label="Muda", min_value=1, max_value=1000)
    duration_unit = forms.TypedChoiceField(label="Kipimo", choices=DURATION_UNITS, coerce=int, initial=60)
    rate_limit = forms.ChoiceField(label="Kasi", choices=SPEED_CHOICES, required=False)

    class Meta:
        model = Package
        fields = ["name", "price", "rate_limit", "shared_users", "is_active"]
        labels = {"name": "Jina la kifurushi", "price": "Bei (Tsh)", "shared_users": "Simu ngapi kwa vocha moja", "is_active": "Kinauzwa"}
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "mfano Siku 1"}),
            "price": forms.NumberInput(attrs={"inputmode": "numeric", "min": 1}),
            "shared_users": forms.NumberInput(attrs={"min": 1, "max": 10}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        minutes = self.instance.duration_minutes if self.instance.pk else None
        if minutes:
            for unit, _ in reversed(DURATION_UNITS):
                if minutes % unit == 0:
                    self.initial.update(duration_value=minutes // unit, duration_unit=unit)
                    break
        current = self.instance.rate_limit if self.instance.pk else ""
        if current and current not in dict(SPEED_CHOICES):
            self.fields["rate_limit"].choices = SPEED_CHOICES + [(current, f"Maalum ({current})")]

    def clean_shared_users(self):
        value = self.cleaned_data["shared_users"]
        if not 1 <= value <= 10:
            raise forms.ValidationError("Weka namba kati ya 1 na 10.")
        return value

    def save(self, commit=True):
        self.instance.duration_minutes = self.cleaned_data["duration_value"] * self.cleaned_data["duration_unit"]
        return super().save(commit)


class VoucherBatchForm(forms.Form):
    package = forms.ModelChoiceField(label="Kifurushi", queryset=Package.objects.none(), empty_label=None)
    router = forms.ModelChoiceField(label="Eneo (router)", queryset=Router.objects.none(), empty_label=None)
    count = forms.IntegerField(label="Idadi ya vocha", min_value=1, max_value=100, initial=10)

    def __init__(self, owner, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["package"].queryset = owner.packages.filter(is_active=True)
        self.fields["router"].queryset = owner.routers.filter(is_active=True)


class WithdrawForm(forms.Form):
    amount = forms.IntegerField(
        label="Kiasi (Tsh)", min_value=1,
        widget=forms.NumberInput(attrs={"inputmode": "numeric", "placeholder": "mfano 20000"}),
    )
    phone = PhoneField(label="Tuma kwenda namba")

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        minimum = config.current().min_withdrawal
        if amount < minimum:
            raise forms.ValidationError(f"Kiasi cha chini ni Tsh {minimum:,}.")
        return amount


class OwnerSettingsForm(forms.ModelForm):
    class Meta:
        model = Owner
        fields = ["business_name", "phone", "logo"]
        labels = {
            "business_name": "Jina la biashara",
            "phone": "Namba ya kupokea pesa",
            "logo": "Logo (inaonekana kwenye ukurasa wa kulipia)",
        }
        widgets = {"phone": forms.TextInput(attrs={"inputmode": "tel"})}

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data["phone"])

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo and hasattr(logo, "size") and logo.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Picha isizidi MB 2.")
        return logo
