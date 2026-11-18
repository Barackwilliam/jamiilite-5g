from django.test import TestCase
from django.urls import reverse

from billing.models import Payment
from core.tests.factories import make_owner, make_package, make_router


class PortalDesignTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.router = make_router(self.owner)
        self.hour = make_package(self.owner, name="Saa 1", price=500, duration_minutes=60)
        self.day = make_package(self.owner, name="Siku 1", price=1000, duration_minutes=60 * 24)
        self.week = make_package(self.owner, name="Wiki 1", price=5000, duration_minutes=60 * 24 * 7)
        self.month = make_package(self.owner, name="Mwezi 1", price=20000, duration_minutes=60 * 24 * 30)
        self.url = reverse("portal:home", args=[self.router.slug])

    def _sell(self, package, times, status=Payment.Status.PAID):
        for _ in range(times):
            Payment.objects.create(router=self.router, package=package, phone="255712345678",
                                   amount=package.price, status=status, provider="test")

    def test_speed_meter_tabs_and_pay_bar(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('class="meter"', html)
        for group in ("saa", "siku", "wiki", "mwezi"):
            self.assertIn(f'data-tab="{group}"', html)
        self.assertIn("data-pay-button", html)
        self.assertIn('class="pay-bar"', html)

    def test_no_tabs_when_few_packages(self):
        self.week.delete()
        self.month.delete()
        self.assertNotIn("data-tab=", self.client.get(self.url).content.decode())

    def test_popular_badge_follows_real_sales(self):
        self.assertNotIn("Maarufu", self.client.get(self.url).content.decode())
        self._sell(self.day, 3)
        self._sell(self.hour, 2)
        self._sell(self.hour, 5, status=Payment.Status.FAILED)
        html = self.client.get(self.url).content.decode()
        self.assertEqual(html.count('class="badge"'), 1)
        day_box = html.split('data-name="Siku 1"')[1].split("</label>")[0]
        self.assertIn("Maarufu", day_box)

    def test_no_discount_badges(self):
        self.assertNotIn("Okoa", self.client.get(self.url).content.decode())
