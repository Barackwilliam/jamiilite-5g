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

    @property
    def template(self):
        return f"pages/makala/{self.slug}.html"


ARTICLES = [
    Article(
        slug="jinsi-ya-kuanzisha-biashara-ya-wifi",
        title="Jinsi ya kuanzisha biashara ya WiFi Tanzania: hatua 7",
        description=(
            "Mwongozo kamili wa kuanzisha biashara ya kuuza WiFi Tanzania: mahali, internet, router ya "
            "MikroTik, vifurushi, malipo ya M-Pesa na Mixx, na jinsi ya kupata wateja wa kwanza."
        ),
        published=date(2026, 11, 5),
        updated=date(2026, 11, 5),
        minutes=7,
    ),
    Article(
        slug="mikrotik-hotspot-malipo-ya-simu",
        title="MikroTik Hotspot: jinsi ya kuuza WiFi kwa malipo ya M-Pesa, Mixx na Airtel Money",
        description=(
            "Jinsi MikroTik Hotspot inavyofanya kazi, router ipi ya kununua, na jinsi ya kuunganisha "
            "malipo ya simu ili mteja alipe na kuunganishwa papo hapo bila wewe kuwepo."
        ),
        published=date(2026, 11, 5),
        updated=date(2026, 11, 5),
        minutes=6,
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
    ),
]

BY_SLUG = {article.slug: article for article in ARTICLES}


def related(article, count=3):
    return [other for other in ARTICLES if other.slug != article.slug][:count]
