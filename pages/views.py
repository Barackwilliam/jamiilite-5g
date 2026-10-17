import math
from urllib.parse import quote

from django.conf import settings
from django.views.generic import TemplateView

# Bei ya kifurushi kidogo kinachotumika kwenye mfano wa "ada inajilipia".
EXAMPLE_PACKAGE_PRICE = 500


class PublicPage(TemplateView):
    """Kurasa za hadhara za kuwavutia na kuwaelekeza wamiliki wa WiFi."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        number = settings.JAMIILITE_WHATSAPP_NUMBER
        message = quote("Habari, nataka kuanza kutumia JamiiLite 5G kwenye WiFi yangu.")
        fee = settings.JAMIILITE_MONTHLY_FEE
        context.update(
            whatsapp_url=f"https://wa.me/{number}?text={message}" if number else "",
            monthly_fee=f"{fee:,}",
            trial_days=settings.JAMIILITE_TRIAL_DAYS,
            daily_fee=f"{math.ceil(fee / 30):,}",
            example_package_price=f"{EXAMPLE_PACKAGE_PRICE:,}",
            breakeven_packages=math.ceil(fee / EXAMPLE_PACKAGE_PRICE),
        )
        return context
