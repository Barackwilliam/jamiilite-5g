from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.tests.factories import make_owner, make_package, make_router


class OnboardingTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.client.force_login(self.owner.user)

    def test_new_owner_sees_only_the_next_step(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.context["next_step"], 1)
        self.assertContains(response, "0 kati ya 4")
        self.assertNotContains(response, "Mapato ya leo")

    def test_next_step_moves_to_connecting_the_router(self):
        router = make_router(self.owner, slug="duka")
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.context["next_step"], 2)
        self.assertContains(response, reverse("dashboard:router_detail", args=[router.pk]))

    def test_online_router_shows_stats_and_customer_page(self):
        make_router(self.owner, slug="duka", last_seen_at=timezone.now())
        make_package(self.owner)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.context["next_step"], 4)
        self.assertContains(response, reverse("portal:home", args=["duka"]))
        self.assertContains(response, "Mapato ya leo")

    def test_trial_counts_today(self):
        self.owner.trial_ends_at = timezone.now() + timedelta(days=14)
        self.owner.save()
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, "zimebaki siku 14")


class StarterPackagesTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.client.force_login(self.owner.user)

    def test_one_click_creates_four_packages(self):
        response = self.client.post(reverse("dashboard:packages"), {"action": "starter"})
        self.assertRedirects(response, reverse("dashboard:packages"))
        packages = list(self.owner.packages.values_list("name", "price", "duration_minutes"))
        self.assertEqual(packages, [
            ("Saa 1", 500, 60), ("Siku 1", 1000, 1440), ("Wiki 1", 5000, 10080), ("Mwezi 1", 20000, 43200),
        ])

    def test_does_nothing_when_owner_already_has_packages(self):
        make_package(self.owner, name="Yangu")
        self.client.post(reverse("dashboard:packages"), {"action": "starter"})
        self.assertEqual(list(self.owner.packages.values_list("name", flat=True)), ["Yangu"])


class RouterConnectTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.client.force_login(self.owner.user)
        self.router = make_router(self.owner, slug="duka", nas_identifier="jl-duka")

    def test_new_router_page_waits_for_first_report(self):
        response = self.client.get(reverse("dashboard:router_detail", args=[self.router.pk]))
        self.assertContains(response, "data-router-wait")
        self.assertNotContains(response, "Simamia ukiwa mbali")

    def test_status_reports_first_sight(self):
        url = reverse("dashboard:router_status", args=[self.router.pk])
        self.assertEqual(self.client.get(url).json(), {"seen": False, "online": False})
        self.router.last_seen_at = timezone.now()
        self.router.save()
        self.assertEqual(self.client.get(url).json(), {"seen": True, "online": True})

    def test_connected_router_shows_management(self):
        self.router.last_seen_at = timezone.now()
        self.router.save()
        response = self.client.get(reverse("dashboard:router_detail", args=[self.router.pk]))
        self.assertNotContains(response, "data-router-wait")
        self.assertContains(response, "Simamia ukiwa mbali")

    def test_status_of_another_owners_router_is_hidden(self):
        other = make_router(make_owner(username="mwingine", business_name="Mwingine"), slug="x")
        self.assertEqual(self.client.get(reverse("dashboard:router_status", args=[other.pk])).status_code, 404)
