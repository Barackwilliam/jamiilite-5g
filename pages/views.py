import math
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import escape
from django.utils.translation import gettext, ngettext
from django.views.decorators.cache import cache_control
from django.views.generic import TemplateView

from core import config

from . import seo

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
        "Mauzo mapya": gettext("Mauzo mapya"),
        "sasa hivi": gettext("sasa hivi"),
        "Router imemkata yenyewe": gettext("Router imemkata yenyewe"),
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
            seo=seo.language_urls(self.request),
        )
        if self.template_name == "pages/home.html":
            context["faqs"] = seo.faq_items(context["monthly_fee"])
            context["schema"] = seo.home_schema(
                self.request, monthly_fee_value=fee, trial_days=cfg.trial_days, faqs=context["faqs"],
            )
        return context


# Kurasa ambazo Google inapaswa kuzijua, kwa kila lugha.
SITEMAP_PAGES = ["pages:home", "pages:mahitaji", "pages:mwongozo", "dashboard:signup"]


@cache_control(max_age=3600, public=True)
def robots_txt(request):
    lines = [
        "User-agent: *",
        # Maeneo ya ndani, ya routers na ya malipo hayana maana kwenye matokeo ya utafutaji.
        "Disallow: /control/",
        "Disallow: /admin/",
        "Disallow: /r/",
        "Disallow: /p/",
        "Disallow: /lugha/",
        "Disallow: /healthz/",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


@cache_control(max_age=3600, public=True)
def sitemap_xml(request):
    langs = [code for code, _name in settings.LANGUAGES]
    entries = []
    for name in SITEMAP_PAGES:
        base = escape(request.build_absolute_uri(reverse(name)))
        alternates = "".join(
            f'<xhtml:link rel="alternate" hreflang="{code}" href="{base}?lang={code}"/>' for code in langs
        ) + f'<xhtml:link rel="alternate" hreflang="x-default" href="{base}"/>'
        for code in langs:
            entries.append(f"<url><loc>{base}?lang={code}</loc>{alternates}</url>")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")


def favicon(request):
    return redirect(static("img/favicon-32.png"), permanent=True)
