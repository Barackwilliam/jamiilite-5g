"""
Makala za Kiswahili kwa wanaotafuta jinsi ya kuuza WiFi Tanzania.
Kila makala ina template yake kwenye pages/templates/pages/makala/<slug>.html.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Article:
    slug: str
    title: str
    description: str
    published: date
    updated: date
    minutes: int  # muda wa kusoma
    related_slugs: tuple = ()  # makala za mada inayofanana, kwa "Soma pia"

    @property
    def template(self):
        return f"pages/makala/{self.slug}.html"


ARTICLES = [
    Article(
        slug="jinsi-ya-kuanzisha-biashara-ya-wifi",
        title="Jinsi ya kuanzisha biashara ya WiFi Tanzania: hatua 7",
        description=(
            "Mwongozo kamili wa kuanzisha biashara ya kuuza WiFi Tanzania: mahali, internet, router ya "
            "MikroTik, vifurushi, malipo ya simu na kadi, na jinsi ya kupata wateja wa kwanza."
        ),
        published=date(2026, 11, 5),
        updated=date(2026, 11, 5),
        minutes=7,
        related_slugs=("router-ya-4g-5g-au-fiber", "jinsi-ya-kupata-wateja-wa-wifi", "faida-ya-biashara-ya-wifi"),
    ),
    Article(
        slug="mikrotik-hotspot-malipo-ya-simu",
        title="MikroTik Hotspot: jinsi ya kuuza WiFi kwa malipo ya simu na kadi",
        description=(
            "Jinsi MikroTik Hotspot inavyofanya kazi, router ipi ya kununua, na jinsi ya kuunganisha "
            "malipo ya simu ili mteja alipe na kuunganishwa papo hapo bila wewe kuwepo."
        ),
        published=date(2026, 11, 5),
        updated=date(2026, 11, 5),
        minutes=6,
        related_slugs=("usalama-wa-wifi-ya-biashara", "vocha-za-wifi", "kasi-ya-internet-kwa-wateja"),
    ),
    Article(
        slug="vocha-za-wifi",
        title="Vocha za WiFi: jinsi ya kuuza internet kwa vocha",
        description=(
            "Vocha za WiFi ni nini, zinatengenezwaje na kuchapishwa, na lini utumie vocha za karatasi "
            "au malipo ya simu. Pamoja na makosa ya kuepuka."
        ),
        published=date(2026, 11, 5),
        updated=date(2026, 11, 5),
        minutes=5,
        related_slugs=("mikrotik-hotspot-malipo-ya-simu", "usalama-wa-wifi-ya-biashara", "jinsi-ya-kupata-wateja-wa-wifi"),
    ),
    Article(
        slug="bei-za-vifurushi-vya-wifi",
        title="Bei za vifurushi vya WiFi: jinsi ya kupanga bei zinazouza",
        description=(
            "Jinsi ya kupanga vifurushi vya saa, siku, wiki na mwezi, kuweka bei kulingana na wateja wako, "
            "na kutumia kasi na idadi ya simu kutofautisha vifurushi."
        ),
        published=date(2026, 11, 5),
        updated=date(2026, 11, 5),
        minutes=5,
        related_slugs=("faida-ya-biashara-ya-wifi", "kasi-ya-internet-kwa-wateja", "wifi-kwa-hosteli-na-nyumba-za-kupanga"),
    ),
    Article(
        slug="faida-ya-biashara-ya-wifi",
        title="Faida ya biashara ya WiFi: jinsi ya kukokotoa mapato na gharama",
        description=(
            "Hesabu rahisi ya mapato, gharama za internet na umeme, na muda wa kurudisha mtaji wa "
            "biashara ya WiFi, kwa mfano unaoweza kubadilisha kwa namba zako."
        ),
        published=date(2026, 11, 5),
        updated=date(2026, 11, 5),
        minutes=6,
        related_slugs=("bei-za-vifurushi-vya-wifi", "jinsi-ya-kupata-wateja-wa-wifi", "jinsi-ya-kuanzisha-biashara-ya-wifi"),
    ),
    Article(
        slug="kasi-ya-internet-kwa-wateja",
        title="Kasi ya internet kiasi gani kwa wateja wangapi wa WiFi?",
        description=(
            "Jinsi ya kukadiria kasi ya internet unayohitaji kulingana na idadi ya wateja na matumizi yao, "
            "na jinsi ya kugawa kasi ili kila mteja apate internet nzuri."
        ),
        published=date(2026, 11, 5),
        updated=date(2026, 11, 5),
        minutes=5,
        related_slugs=("router-ya-4g-5g-au-fiber", "bei-za-vifurushi-vya-wifi", "mikrotik-hotspot-malipo-ya-simu"),
    ),
    Article(
        slug="router-ya-4g-5g-au-fiber",
        title="Router ya 4G, 5G au fiber: ipi bora kwa biashara ya WiFi?",
        description=(
            "Faida na hasara za internet ya 4G, 5G na fiber kwa biashara ya kuuza WiFi, na jinsi ya "
            "kuchagua kulingana na eneo lako na idadi ya wateja."
        ),
        published=date(2026, 11, 5),
        updated=date(2026, 11, 5),
        minutes=5,
        related_slugs=("kasi-ya-internet-kwa-wateja", "mikrotik-hotspot-malipo-ya-simu", "jinsi-ya-kuanzisha-biashara-ya-wifi"),
    ),
    Article(
        slug="wifi-kwa-hosteli-na-nyumba-za-kupanga",
        title="WiFi kwa hosteli na nyumba za kupanga: jinsi ya kuuza internet kwa wapangaji",
        description=(
            "Jinsi ya kuweka WiFi ya kulipia kwenye hosteli, nyumba za kupanga na gesti: vifurushi vya "
            "wiki na mwezi, kufika kila chumba, na kuepuka migogoro na wapangaji."
        ),
        published=date(2026, 11, 5),
        updated=date(2026, 11, 5),
        minutes=6,
        related_slugs=("bei-za-vifurushi-vya-wifi", "kasi-ya-internet-kwa-wateja", "faida-ya-biashara-ya-wifi"),
    ),
    Article(
        slug="jinsi-ya-kupata-wateja-wa-wifi",
        title="Jinsi ya kupata wateja wengi wa WiFi yako",
        description=(
            "Njia za kuwajulisha watu kuhusu WiFi yako na kuwafanya warudi: jina la WiFi, mabango, "
            "vifurushi vya kujaribu, vocha na huduma nzuri."
        ),
        published=date(2026, 11, 5),
        updated=date(2026, 11, 5),
        minutes=5,
        related_slugs=("bei-za-vifurushi-vya-wifi", "vocha-za-wifi", "faida-ya-biashara-ya-wifi"),
    ),
    Article(
        slug="usalama-wa-wifi-ya-biashara",
        title="Usalama wa WiFi ya biashara: linda router na mapato yako",
        description=(
            "Hatua rahisi za kulinda router ya MikroTik, vocha na mapato ya WiFi yako dhidi ya wizi wa "
            "internet na watu wasioruhusiwa."
        ),
        published=date(2026, 11, 5),
        updated=date(2026, 11, 5),
        minutes=5,
        related_slugs=("mikrotik-hotspot-malipo-ya-simu", "vocha-za-wifi", "kasi-ya-internet-kwa-wateja"),
    ),
]

BY_SLUG = {article.slug: article for article in ARTICLES}


def related(article, count=3):
    """Makala za mada inayofanana kwanza, kisha nyingine mpaka zifike `count`."""
    chosen = [BY_SLUG[slug] for slug in article.related_slugs if slug in BY_SLUG and slug != article.slug]
    for other in ARTICLES:
        if len(chosen) >= count:
            break
        if other.slug != article.slug and other not in chosen:
            chosen.append(other)
    return chosen[:count]
