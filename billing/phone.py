import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# Namba za simu za Tanzania: 06x au 07x, zikihifadhiwa kama 255XXXXXXXXX.
_TZ_MOBILE = re.compile(r"^255[67]\d{8}$")


def normalize_tz_phone(raw):
    """Badilisha 0712..., +255712..., 255 712 ... kuwa 255712345678."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0") and len(digits) == 10:
        digits = "255" + digits[1:]
    elif len(digits) == 9 and digits[0] in "67":
        digits = "255" + digits
    if not _TZ_MOBILE.match(digits):
        raise ValidationError(_("Weka namba sahihi ya simu, mfano 0712 345 678."))
    return digits
