"""
SEO ya kurasa za hadhara: anwani za kila lugha (hreflang), canonical, na data
iliyopangwa (JSON-LD) ambayo Google inaitumia kuonyesha bei na maswali.
"""

import json

from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.utils.translation import get_language, gettext


def language_urls(request):
    """Anwani kamili za ukurasa huu kwa kila lugha, pamoja na x-default (bila ?lang)."""
    path = request.path
    base = request.build_absolute_uri(path)
    urls = {code: f"{base}?lang={code}" for code, _name in settings.LANGUAGES}
    current = (get_language() or settings.LANGUAGE_CODE)[:2]
    return {
        "alternates": [{"code": code, "url": url} for code, url in urls.items()],
        "x_default": base,
        "canonical": urls.get(current, base),
        "og_locale": "en_TZ" if current == "en" else "sw_TZ",
        "og_locale_alt": "sw_TZ" if current == "en" else "en_TZ",
        "image": request.build_absolute_uri(static("img/og.jpg")),
    }


def faq_items(monthly_fee):
    """Maswali ya ukurasa wa mwanzo. Yanatumika kwenye ukurasa NA kwenye JSON-LD, ili yafanane."""
    links = {"mahitaji_url": reverse("pages:mahitaji"), "mwongozo_url": reverse("pages:mwongozo")}
    items = [
        (
            gettext("Nina router ya kawaida (MiFi, 4G au fiber). Inafaa?"),
            gettext(
                "Ndiyo, kama chanzo cha internet. Utahitaji kuongeza router ndogo ya MikroTik nyuma yake, "
                "ambayo ndiyo inayowaonyesha wateja ukurasa wa kulipia. Ukurasa wa "
                '<a href="%(mahitaji_url)s">Mahitaji</a> unakuonyesha hasa unachohitaji.'
            ) % links,
        ),
        (
            gettext("Sijui mambo ya kompyuta. Nitaweza?"),
            gettext(
                'Ndiyo. Unabandika mstari mmoja tu ukifuata <a href="%(mwongozo_url)s">mwongozo wetu</a>. '
                "Ukikwama, tunakusaidia."
            ) % links,
        ),
        (
            gettext("Pesa za wateja zinanifikiaje?"),
            gettext(
                "Wateja wanalipa kwa simu, na kila mauzo yanaongezwa kwenye salio lako. Unaliona kwenye "
                "dashboard, na unatoa pesa kwenda namba yako ya simu wakati wowote unaotaka. Ada ya mwezi "
                "(Tsh %(fee)s) inakatwa yenyewe kutoka kwenye salio hilo."
            ) % {"fee": monthly_fee},
        ),
        (
            gettext("Internet ikikatika au umeme ukikatika?"),
            gettext(
                "Router ikiwaka tena, inajiunganisha yenyewe. Vocha za wateja hazipotei, na muda wao "
                "unaendelea kama ulivyokuwa."
            ),
        ),
    ]
    # Maandishi ni yetu wenyewe (msgid na tafsiri zake), kwa hiyo HTML yake ni salama.
    return [{"question": q, "answer": mark_safe(a)} for q, a in items]


def home_schema(request, *, monthly_fee_value, trial_days, faqs):
    """JSON-LD ya ukurasa wa mwanzo: huduma yenyewe, bei yake, na maswali."""
    home = request.build_absolute_uri(reverse("pages:home"))
    data = [
        {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "JamiiLite 5G",
            "url": home,
            "applicationCategory": "BusinessApplication",
            "operatingSystem": "Web, MikroTik RouterOS",
            "description": gettext(
                "Mfumo wa kuuza WiFi kwa vifurushi: wateja wanalipa kwa simu, wanapata vocha, "
                "na wanakatwa muda ukiisha."
            ),
            "inLanguage": ["sw", "en"],
            "offers": {
                "@type": "Offer",
                "price": str(monthly_fee_value),
                "priceCurrency": "TZS",
                "description": gettext("Kwa mwezi, siku %(days)s za majaribio bure") % {"days": trial_days},
            },
            "publisher": {"@type": "Organization", "name": "JamiiTek", "url": "https://www.jamiitek.com/"},
        },
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item["question"],
                    "acceptedAnswer": {"@type": "Answer", "text": strip_tags(item["answer"])},
                }
                for item in faqs
            ],
        },
    ]
    # "</" isiweze kufunga <script> mapema.
    return mark_safe(json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
