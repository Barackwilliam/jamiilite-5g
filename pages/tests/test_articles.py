import json
import re

from django.test import TestCase
from django.urls import reverse

from pages.articles import ARTICLES


class ArticleTests(TestCase):
    def test_index_lists_every_article(self):
        response = self.client.get(reverse("pages:makala"))
        self.assertEqual(response.status_code, 200)
        for article in ARTICLES:
            self.assertContains(response, reverse("pages:makala_detail", args=[article.slug]))

    def test_each_article_renders_with_seo(self):
        for article in ARTICLES:
            with self.subTest(article.slug):
                url = reverse("pages:makala_detail", args=[article.slug])
                html = self.client.get(url).content.decode()
                head = html.split("</head>", 1)[0]
                self.assertIn(f"<title>{article.title} · JamiiLite 5G</title>", head)
                self.assertIn(f'<link rel="canonical" href="http://testserver{url}">', head)
                self.assertNotIn("?lang=en", head)
                self.assertEqual(html.count("<h1>"), 1)
                raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
                data, crumbs = json.loads(raw)
                self.assertEqual(data["@type"], "Article")
                self.assertEqual(data["headline"], article.title)
                self.assertEqual(data["inLanguage"], "sw")
                self.assertEqual(crumbs["@type"], "BreadcrumbList")

    def test_articles_are_swahili_even_for_english_visitors(self):
        self.client.get("/?lang=en")
        html = self.client.get(reverse("pages:makala_detail", args=[ARTICLES[0].slug])).content.decode()
        self.assertIn('<html lang="sw">', html)

    def test_unknown_article_is_404(self):
        self.assertEqual(self.client.get("/makala/haipo/").status_code, 404)

    def test_articles_in_sitemap(self):
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("<loc>http://testserver/makala/</loc>", body)
        for article in ARTICLES:
            self.assertIn(f"<loc>http://testserver/makala/{article.slug}/</loc>", body)
