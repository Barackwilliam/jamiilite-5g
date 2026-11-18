import math
import os
from datetime import date
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import escape
from django.utils import translation
from django.utils.translation import get_language, gettext, ngettext
from django.views.decorators.cache import cache_control
from django.views.generic import TemplateView

from core import config

from . import seo
from .articles import ARTICLES, BY_SLUG, related

# Bei ya kifurushi kidogo kinachotumika kwenye mfano wa "ada inajilipia".
EXAMPLE_PACKAGE_PRICE = 500


def landing_strings():
    """Maandishi ya landing.js, yamewekwa ndani ya ukurasa ili kusiwe na ombi la ziada."""
    strings = {
        "Saa 1": gettext("Saa 1"),
        "Siku 1": gettext("Siku 1"),
        "Wiki": gettext("Wiki"),
        "Muda umeisha · mteja ametoka": gettext("Muda umeisha · mteja ametoka"),
        "Mteja ameingia · JamiiTek WiFi": gettext("Mteja ameingia · JamiiTek WiFi"),
        "Lipa Tsh %(amount)s kwa JAMIITEK WIFI? Weka PIN yako.": gettext(
            "Lipa Tsh %(amount)s kwa JAMIITEK WIFI? Weka PIN yako."
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


# Kurasa za hadhara zinahifadhiwa (cache) kwa dakika hizi, kwa kila lugha. Mipangilio ikihifadhiwa,
# zote zinaanza upya (core.config.forget).
PAGE_CACHE_SECONDS = 600
BUILD_ID = (os.environ.get("RENDER_GIT_COMMIT") or "dev")[:12]


def page_cache_key(request):
    language = (get_language() or settings.LANGUAGE_CODE)[:2]
    url = request.build_absolute_uri(request.path)
    return f"jl:page:{BUILD_ID}:{config.pages_version()}:{language}:{url}"


class CachedPublicPage:
    """
    Mgeni asiyeingia anapata ukurasa uliokwisha kutengenezwa: hakuna database, hakuna template.
    Ukurasa hauna fomu wala cookie ya mtu binafsi, kwa hiyo ni ule ule kwa kila mtu wa lugha hiyo.
    """

    def dispatch(self, request, *args, **kwargs):
        if (
            not settings.JAMIILITE_CACHE_PAGES
            or request.method not in ("GET", "HEAD")
            or request.user.is_authenticated
            or len(messages.get_messages(request))
        ):
            return super().dispatch(request, *args, **kwargs)
        key = page_cache_key(request)
        hit = cache.get(key)
        if hit is not None:
            content, content_type = hit
            response = HttpResponse(content, content_type=content_type)
            response["X-Page-Cache"] = "hit"
            return response
        response = super().dispatch(request, *args, **kwargs)
        if response.status_code == 200 and hasattr(response, "add_post_render_callback"):
            def store(rendered):
                cache.set(key, (rendered.content, rendered["Content-Type"]), PAGE_CACHE_SECONDS)
            response.add_post_render_callback(store)
        return response


class PublicPage(CachedPublicPage, TemplateView):
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


# Masharti na faragha: kila hati imeandikwa kamili kwa kila lugha (si sentensi moja moja kwenye .po).
LEGAL_UPDATED = date(2026, 11, 4)


class LegalPage(PublicPage):
    document = ""

    def get_template_names(self):
        language = "sw" if (get_language() or "en").startswith("sw") else "en"
        return [f"pages/legal/{self.document}_{language}.html"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cfg = config.current()
        context.update(
            updated=LEGAL_UPDATED,
            min_withdrawal=f"{cfg.min_withdrawal:,}",
            sale_fee_percent=cfg.sale_fee_percent,
            contact_email=settings.JAMIILITE_CONTACT_EMAIL,
        )
        return context


class SwahiliPage(PublicPage):
    """Makala zimeandikwa kwa Kiswahili tu, kwa hiyo ukurasa wote unaonyeshwa kwa Kiswahili."""

    def dispatch(self, request, *args, **kwargs):
        translation.activate("sw")
        request.LANGUAGE_CODE = "sw"
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["seo"] = seo.swahili_only_urls(self.request)
        return context


class ArticleIndex(SwahiliPage):
    template_name = "pages/makala/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["articles"] = ARTICLES
        context["schema"] = seo.articles_index_schema(self.request, ARTICLES)
        return context


class ArticleDetail(SwahiliPage):
    def get_article(self):
        article = BY_SLUG.get(self.kwargs["slug"])
        if article is None:
            raise Http404
        return article

    def get_template_names(self):
        return [self.get_article().template]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = self.get_article()
        context.update(article=article, related=related(article), schema=seo.article_schema(self.request, article))
        return context


# Kurasa ambazo Google inapaswa kuzijua, kwa kila lugha.
SITEMAP_PAGES = [
    "pages:home", "pages:mahitaji", "pages:mwongozo", "dashboard:signup", "pages:masharti", "pages:faragha",
]


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
        default = settings.LANGUAGE_CODE[:2]
        urls = {code: base if code == default else f"{base}?lang={code}" for code in langs}
        alternates = "".join(
            f'<xhtml:link rel="alternate" hreflang="{code}" href="{url}"/>' for code, url in urls.items()
        ) + f'<xhtml:link rel="alternate" hreflang="x-default" href="{base}"/>'
        for url in urls.values():
            entries.append(f"<url><loc>{url}</loc>{alternates}</url>")
    # Makala ni za Kiswahili tu: anwani moja kila moja, pamoja na tarehe ya kusasishwa.
    entries.append(f"<url><loc>{escape(request.build_absolute_uri(reverse('pages:makala')))}</loc></url>")
    for article in ARTICLES:
        loc = escape(request.build_absolute_uri(reverse("pages:makala_detail", args=[article.slug])))
        entries.append(f"<url><loc>{loc}</loc><lastmod>{article.updated.isoformat()}</lastmod></url>")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")


def favicon(request):
    return redirect(static("img/favicon-32.png"), permanent=True)
