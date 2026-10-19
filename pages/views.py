import math
from urllib.parse import quote

from django.utils.translation import gettext, ngettext
from django.views.generic import TemplateView

from core import config

# Bei ya kifurushi kidogo kinachotumika kwenye mfano wa "ada inajilipia".
EXAMPLE_PACKAGE_PRICE = 500


def landing_strings():
    """Maandishi ya landing.js, yamewekwa ndani ya ukurasa ili kusiwe na ombi la ziada."""
    strings = {
        "Saa 1": gettext("Saa 1"),
        "Siku 1": gettext("Siku 1"),
        "Wiki": gettext("Wiki"),
        "Muda umeisha · mteja ametoka": gettext("Muda umeisha · mteja ametoka"),
        "Mteja ameingia · Neema WiFi": gettext("Mteja ameingia · Neema WiFi"),
        "Lipa Tsh %(amount)s kwa NEEMA WIFI? Weka PIN yako ya M-Pesa.": gettext(
            "Lipa Tsh %(amount)s kwa NEEMA WIFI? Weka PIN yako ya M-Pesa."
        ),
        "Cheza": gettext("Cheza"),
        "Simamisha": gettext("Simamisha"),
    }
    # Wingi: [moja, nyingi]
    strings["siku %(n)s"] = [ngettext("siku %(n)s", "siku %(n)s", 1), ngettext("siku %(n)s", "siku %(n)s", 2)]
    return strings


class PublicPage(TemplateView):
    """Kurasa za hadhara za kuwavutia na kuwaelekeza wamiliki wa WiFi."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cfg = config.current()
        number = cfg.whatsapp_number
        message = quote(gettext("Habari, nataka kuanza kutumia JamiiLite 5G kwenye WiFi yangu."))
        fee = cfg.monthly_fee
        context.update(
            whatsapp_url=f"https://wa.me/{number}?text={message}" if number else "",
            monthly_fee=f"{fee:,}",
            monthly_fee_value=fee,
            trial_days=cfg.trial_days,
            daily_fee=f"{math.ceil(fee / 30):,}",
            example_package_price=f"{EXAMPLE_PACKAGE_PRICE:,}",
            breakeven_packages=math.ceil(fee / EXAMPLE_PACKAGE_PRICE),
            landing_i18n=landing_strings(),
        )
        return context
