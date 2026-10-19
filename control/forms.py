from django import forms
from django.conf import settings

from core.models import PlatformConfig, Router

ENV_DEFAULTS = {
    "monthly_fee": ("JAMIILITE_MONTHLY_FEE", "Tsh {:,}"),
    "trial_days": ("JAMIILITE_TRIAL_DAYS", "siku {}"),
    "min_withdrawal": ("JAMIILITE_MIN_WITHDRAWAL", "Tsh {:,}"),
    "sale_fee_percent": ("JAMIILITE_SALE_FEE_PERCENT", "{}%"),
    "whatsapp_number": ("JAMIILITE_WHATSAPP_NUMBER", "{}"),
}


class PlatformConfigForm(forms.ModelForm):
    class Meta:
        model = PlatformConfig
        fields = [
            "monthly_fee", "trial_days", "min_withdrawal", "sale_fee_percent",
            "whatsapp_number", "signups_open", "announcement",
        ]
        widgets = {
            "announcement": forms.Textarea(attrs={"rows": 3, "placeholder": "mfano: Kesho saa 2 usiku mfumo utakuwa kwenye matengenezo kwa dakika 10."}),
            "whatsapp_number": forms.TextInput(attrs={"inputmode": "tel", "placeholder": "255712345678"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, (setting, fmt) in ENV_DEFAULTS.items():
            default = getattr(settings, setting)
            shown = fmt.format(default) if default not in ("", None) else "haijawekwa"
            field = self.fields[name]
            field.widget.attrs.setdefault("placeholder", str(default) if default not in ("", None) else "")
            field.help_text = f"Ukiacha tupu: {shown} (kutoka .env)."
        self.fields["sale_fee_percent"].help_text += " Inakatwa kwenye kila mauzo kufidia ada za malipo."

    def clean_sale_fee_percent(self):
        value = self.cleaned_data["sale_fee_percent"]
        if value is not None and value > 20:
            raise forms.ValidationError("Weka asilimia kati ya 0 na 20.")
        return value

    def clean_trial_days(self):
        value = self.cleaned_data["trial_days"]
        if value is not None and value > 90:
            raise forms.ValidationError("Siku za majaribio zisizidi 90.")
        return value

    def clean_whatsapp_number(self):
        value = "".join(ch for ch in self.cleaned_data["whatsapp_number"] if ch.isdigit())
        if value and not (value.startswith("255") and len(value) == 12):
            raise forms.ValidationError("Andika namba kamili, mfano 255712345678.")
        return value


class AdminRouterForm(forms.ModelForm):
    class Meta:
        model = Router
        fields = ["name", "location", "nas_identifier", "login_url"]
        labels = {"name": "Jina", "location": "Mahali", "nas_identifier": "NAS identifier", "login_url": "Login URL ya hotspot"}
        help_texts = {
            "nas_identifier": "Ukibadilisha, router itatumiwa usanidi upya yenyewe.",
            "login_url": "Acha tupu kutumia link inayotumwa na MikroTik.",
        }
