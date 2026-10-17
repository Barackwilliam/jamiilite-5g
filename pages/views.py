from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.views.generic import TemplateView

EXAMPLE_SALES = 100_000


class PublicPage(TemplateView):
    """Kurasa za hadhara za kuwavutia na kuwaelekeza wamiliki wa WiFi."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        number = settings.JAMIILITE_WHATSAPP_NUMBER
        message = quote("Habari, nataka kuanza kutumia JamiiLite 5G kwenye WiFi yangu.")
        percent = Decimal(settings.JAMIILITE_COMMISSION_PERCENT)
        fee = int(EXAMPLE_SALES * percent / 100)
        context.update(
            whatsapp_url=f"https://wa.me/{number}?text={message}" if number else "",
            commission_percent=f"{percent.normalize():f}",
            example_sales=f"{EXAMPLE_SALES:,}",
            example_fee=f"{fee:,}",
            example_net=f"{EXAMPLE_SALES - fee:,}",
        )
        return context
