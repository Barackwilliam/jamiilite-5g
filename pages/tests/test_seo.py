import json
import re

from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(JAMIILITE_MONTHLY_FEE=10000, JAMIILITE_TRIAL_DAYS=14)
class SeoTests(TestCase):
    def head(self, url, **headers):
        html = self.client.get(url, **headers).content.decode()
        return html.split("</head>", 1)[0]

    def test_canonical_and_hreflang_for_each_language(self):
        head = self.head(reverse("pages:home") + "?lang=en")
        self.assertIn('<link rel="canonical" href="http://testserver/?lang=en">', head)
        self.assertIn('hreflang="sw" href="http://testserver/?lang=sw"', head)
        self.assertIn('hreflang="en" href="http://testserver/?lang=en"', head)
        self.assertIn('hreflang="x-default" href="http://testserver/"', head)
        self.assertIn('<html lang="en">', self.client.get("/?lang=en").content.decode())

    def test_lang_param_is_remembered(self):
        self.client.get("/?lang=en")
        self.assertIn('<html lang="en">', self.client.get(reverse("pages:mahitaji")).content.decode())

    def test_unknown_lang_param_is_ignored(self):
        self.assertEqual(self.client.get("/?lang=fr").status_code, 200)

    def test_open_graph_and_icons(self):
        head = self.head("/")
        self.assertIn('property="og:image"', head)
        self.assertIn('content="1200"', head)
        self.assertIn('name="twitter:card" content="summary_large_image"', head)
        self.assertIn('rel="icon"', head)

    def test_structured_data_matches_page(self):
        html = self.client.get("/").content.decode()
        raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
        app, faq = json.loads(raw)
        self.assertEqual(app["@type"], "SoftwareApplication")
        self.assertEqual(app["offers"]["price"], "10000")
        self.assertEqual(app["offers"]["priceCurrency"], "TZS")
        # Kila swali la JSON-LD linaonekana pia kwenye ukurasa wenyewe.
        self.assertEqual(faq["@type"], "FAQPage")
        self.assertEqual(len(faq["mainEntity"]), 4)
        for q in faq["mainEntity"]:
            self.assertIn(q["name"], html)
            self.assertNotIn("<a", q["acceptedAnswer"]["text"])

    def test_faq_answers_are_translated(self):
        html = self.client.get("/?lang=en").content.decode()
        self.assertIn("How does customers&#x27; money reach me?", html)
        self.assertNotIn("Pesa za wateja zinanifikiaje?", html)

    def test_robots_and_sitemap(self):
        robots = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /control/", robots)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", robots)
        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap["Content-Type"], "application/xml; charset=utf-8")
        body = sitemap.content.decode()
        self.assertIn("<loc>http://testserver/mahitaji/?lang=en</loc>", body)
        self.assertIn('hreflang="x-default" href="http://testserver/mwongozo/"', body)

    def test_favicon_redirects_to_png(self):
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 301)
        self.assertIn("favicon-32", response["Location"])
