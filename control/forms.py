from django import forms
from django.conf import settings
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from core.models import PlatformConfig, Router

ENV_DEFAULTS = {
    "monthly_fee": ("JAMIILITE_MONTHLY_FEE", "Tsh {:,}"),
    "trial_days": ("JAMIILITE_TRIAL_DAYS", "{}"),
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
        labels = {
            "monthly_fee": _("Ada ya mwezi (Tsh)"),
            "trial_days": _("Siku za majaribio"),
            "min_withdrawal": _("Kiasi cha chini cha kutoa (Tsh)"),
            "sale_fee_percent": _("Makato kwa kila mauzo (%)"),
            "whatsapp_number": _("Namba ya WhatsApp ya msaada"),
            "signups_open": _("Usajili wa wamiliki wapya uko wazi"),
            "announcement": _("Tangazo kwa wamiliki wote"),
        }
        help_texts = {
            "signups_open": _("Ukiondoa tiki, ukurasa wa kujisajili unafungwa kwa muda."),
            "announcement": _("Linaonekana juu ya dashboard ya kila mmiliki. Acha tupu kuliondoa."),
        }
        widgets = {
            "announcement": forms.Textarea(attrs={"rows": 3, "placeholder": _("mfano: Kesho saa 2 usiku mfumo utakuwa kwenye matengenezo kwa dakika 10.")}),
            "whatsapp_number": forms.TextInput(attrs={"inputmode": "tel", "placeholder": "255712345678"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, (setting, fmt) in ENV_DEFAULTS.items():
            default = getattr(settings, setting)
            shown = fmt.format(default) if default not in ("", None) else gettext("haijawekwa")
            field = self.fields[name]
            field.widget.attrs.setdefault("placeholder", str(default) if default not in ("", None) else "")
            field.help_text = gettext("Ukiacha tupu: %(value)s (kutoka .env).") % {"value": shown}
        self.fields["sale_fee_percent"].help_text += " " + gettext("Inakatwa kwenye kila mauzo kufidia ada za malipo.")

    def clean_sale_fee_percent(self):
        value = self.cleaned_data["sale_fee_percent"]
        if value is not None and value > 20:
            raise forms.ValidationError(_("Weka asilimia kati ya 0 na 20."))
        return value

    def clean_trial_days(self):
        value = self.cleaned_data["trial_days"]
        if value is not None and value > 90:
            raise forms.ValidationError(_("Siku za majaribio zisizidi 90."))
        return value

    def clean_whatsapp_number(self):
        value = "".join(ch for ch in self.cleaned_data["whatsapp_number"] if ch.isdigit())
        if value and not (value.startswith("255") and len(value) == 12):
            raise forms.ValidationError(_("Andika namba kamili, mfano 255712345678."))
        return value


class AdminRouterForm(forms.ModelForm):
    class Meta:
        model = Router
        fields = ["name", "location", "wifi_name", "nas_identifier", "login_url"]
        labels = {
            "name": _("Jina"), "location": _("Mahali"), "wifi_name": _("Jina la WiFi (SSID)"),
            "nas_identifier": _("NAS identifier"), "login_url": _("Login URL ya hotspot"),
        }
        help_texts = {
            "nas_identifier": _("Ukibadilisha, router itatumiwa usanidi upya yenyewe."),
            "wifi_name": _("Ukibadilisha, router itatumiwa usanidi upya na WiFi itakuwa wazi (bila password)."),
            "login_url": _("Acha tupu kutumia link inayotumwa na MikroTik."),
        }
