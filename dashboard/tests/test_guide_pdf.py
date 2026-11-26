from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse

from core.tests.factories import make_owner, make_router


class SetupGuidePdfTests(TestCase):
    def test_guide_files_exist(self):
        for lang in ("sw", "en"):
            path = finders.find(f"docs/mwongozo-jamiilite-{lang}.pdf")
            self.assertTrue(path, lang)
            with open(path, "rb") as f:
                self.assertEqual(f.read(4), b"%PDF")

    def test_new_owner_sees_guide_in_their_language(self):
        owner = make_owner(language="sw")
        self.client.force_login(owner.user)
        html = self.client.get(reverse("dashboard:home")).content.decode()
        self.assertIn("docs/mwongozo-jamiilite-sw.pdf", html)

    @override_settings(LANGUAGE_CODE="en")
    def test_english_owner_gets_english_guide_on_router_page(self):
        owner = make_owner(language="en")
        router = make_router(owner)
        self.client.force_login(owner.user)
        html = self.client.get(reverse("dashboard:router_detail", args=[router.pk])).content.decode()
        self.assertIn("docs/mwongozo-jamiilite-en.pdf", html)
