from django.test import TestCase

from .factories import make_owner, make_package, make_router


class RouterTests(TestCase):
    def test_slug_is_generated_and_unique(self):
        owner = make_owner()
        first = make_router(owner, name="Duka la Kati")
        second = make_router(owner, name="Duka la Kati")

        self.assertEqual(first.slug, "mama-neema-wifi-duka-la-kati")
        self.assertNotEqual(first.slug, second.slug)
        self.assertTrue(second.slug.startswith(first.slug))

    def test_each_router_gets_its_own_radius_secret(self):
        owner = make_owner()
        self.assertNotEqual(make_router(owner).radius_secret, make_router(owner).radius_secret)


class PackageTests(TestCase):
    def test_duration_label(self):
        owner = make_owner()
        cases = {30: "dakika 30", 60: "saa 1", 180: "saa 3", 1440: "siku 1", 10080: "wiki 1"}
        for minutes, label in cases.items():
            with self.subTest(minutes=minutes):
                package = make_package(owner, duration_minutes=minutes)
                self.assertEqual(package.duration_label, label)

    def test_summary_does_not_repeat_name(self):
        owner = make_owner()
        same = make_package(owner, name="Saa 1", duration_minutes=60, rate_limit="1M/2M")
        different = make_package(owner, name="Usiku", duration_minutes=480)

        self.assertEqual(same.summary, "kasi 1M/2M")
        self.assertEqual(different.summary, "saa 8")
        self.assertEqual(make_package(owner, price=7000).price_display, "7,000")
