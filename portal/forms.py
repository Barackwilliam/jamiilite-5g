from django import forms
from django.core.exceptions import ValidationError

from billing.phone import normalize_tz_phone


class PayForm(forms.Form):
    package = forms.ModelChoiceField(queryset=None, widget=forms.RadioSelect, empty_label=None,
                                     error_messages={"required": "Chagua kifurushi."})
    phone = forms.CharField(
        label="Namba ya simu",
        max_length=20,
        widget=forms.TextInput(
            attrs={"placeholder": "0712 345 678", "inputmode": "tel", "autocomplete": "tel"}
        ),
        error_messages={"required": "Weka namba ya simu utakayolipia."},
    )

    def __init__(self, *args, packages, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["package"].queryset = packages

    def clean_phone(self):
        try:
            return normalize_tz_phone(self.cleaned_data["phone"])
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages)
