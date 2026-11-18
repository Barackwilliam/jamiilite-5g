from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import PlatformConfig

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "page-cache-tests"}}


@override_settings(JAMIILITE_CACHE_PAGES=True, CACHES=LOCMEM, LANGUAGE_CODE="en")
class PublicPageCacheTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_second_visit_is_served_from_cache_without_queries(self):
        first = self.client.get("/")
        self.assertEqual(first.status_code, 200)
        self.assertNotIn("X-Page-Cache", first)
        with self.assertNumQueries(0):
            second = self.client.get("/")
        self.assertEqual(second["X-Page-Cache"], "hit")
        self.assertEqual(second.content, first.content)

    def test_public_pages_carry_no_csrf_form_or_cookie(self):
        response = self.client.get("/")
        self.assertNotContains(response, "csrfmiddlewaretoken")
        self.assertNotIn("csrftoken", response.cookies)
        self.assertNotIn("no-cache", response.get("Cache-Control", ""))
        self.assertContains(response, 'href="/?lang=sw"')

    def test_each_language_has_its_own_copy(self):
        self.client.get("/")
        swahili = self.client.get("/?lang=sw")
        self.assertContains(swahili, "WiFi yako")
        english = self.client.get("/?lang=en")
        self.assertContains(english, "Your WiFi")

    def test_saving_platform_settings_refreshes_cached_pages(self):
        self.client.get("/")
        row = PlatformConfig.load()
        row.trial_days = 45
        row.save()
        response = self.client.get("/")
        self.assertNotIn("X-Page-Cache", response)
        self.assertContains(response, "45")

    def test_signed_in_owner_is_never_served_a_cached_page(self):
        from core.tests.factories import make_owner

        self.client.get("/")
        owner = make_owner()
        self.client.force_login(owner.user)
        response = self.client.get("/")
        self.assertNotIn("X-Page-Cache", response)
