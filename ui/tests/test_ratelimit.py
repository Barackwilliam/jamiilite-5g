import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing.models import Payment
from core.models import RateLimit
from core.tests.factories import make_owner, make_package, make_router
from ui import ratelimit

# Password isiyo sahihi; inatengenezwa kila mara ili isiwe siri iliyoandikwa kwenye code.
WRONG = secrets.token_urlsafe(12)


class LimiterTests(TestCase):
    def test_counts_reset_after_window(self):
        now = timezone.now()
        self.assertEqual(ratelimit.hit("k", timedelta(minutes=1), now=now), 1)
        self.assertEqual(ratelimit.hit("k", timedelta(minutes=1), now=now), 2)
        self.assertTrue(ratelimit.is_blocked("k", 2, now=now))
        later = now + timedelta(minutes=2)
        self.assertFalse(ratelimit.is_blocked("k", 2, now=later))
        self.assertEqual(ratelimit.hit("k", timedelta(minutes=1), now=later), 1)

    @override_settings(JAMIILITE_PROXY_HOPS=1)
    def test_client_ip_ignores_addresses_written_by_the_client(self):
        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="1.1.1.1, 41.59.0.7", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(ratelimit.client_ip(request), "41.59.0.7")

    @override_settings(JAMIILITE_PROXY_HOPS=0)
    def test_client_ip_without_proxy(self):
        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="1.1.1.1", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(ratelimit.client_ip(request), "10.0.0.1")


class OwnerLoginLimitTests(TestCase):
    def setUp(self):
        self.owner = make_owner(username="255712345678")
        self.password = secrets.token_urlsafe(12)
        self.owner.user.set_password(self.password)
        self.owner.user.save()
        self.url = reverse("dashboard:login")

    def login(self, password, phone="0712345678"):
        return self.client.post(self.url, {"phone": phone, "password": password})

    def test_five_wrong_passwords_lock_the_number(self):
        for _ in range(5):
            self.assertEqual(self.login(WRONG).status_code, 200)
        response = self.login(self.password)
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Umejaribu mara nyingi", status_code=429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_success_clears_the_count(self):
        for _ in range(4):
            self.login(WRONG)
        self.assertEqual(self.login(self.password).status_code, 302)
        self.assertFalse(RateLimit.objects.filter(key="login:phone:255712345678").exists())

    def test_many_numbers_from_one_address_are_limited(self):
        for i in range(30):
            self.login(WRONG, phone=f"07123450{i:02d}")
        self.assertEqual(self.login(self.password).status_code, 429)


class SignupLimitTests(TestCase):
    def test_signups_from_one_address_are_limited(self):
        url = reverse("dashboard:signup")
        for _ in range(10):
            self.client.post(url, {"business_name": "x"})
        response = self.client.post(url, {"business_name": "x"})
        self.assertContains(response, "Akaunti nyingi", status_code=429)


class AdminLoginLimitTests(TestCase):
    def test_failed_admin_logins_are_limited(self):
        get_user_model().objects.create_superuser("bosi", password=secrets.token_urlsafe(12))
        url = reverse("admin:login")
        for _ in range(20):
            self.assertEqual(self.client.post(url, {"username": "bosi", "password": WRONG}).status_code, 200)
        self.assertEqual(self.client.post(url, {"username": "bosi", "password": WRONG}).status_code, 429)


class PayLimitTests(TestCase):
    def setUp(self):
        owner = make_owner()
        self.router = make_router(owner)
        self.package = make_package(owner)
        self.url = reverse("portal:pay", args=[self.router.slug])

    def pay(self, phone="0712345678"):
        return self.client.post(self.url, {"package": self.package.pk, "phone": phone})

    def test_one_number_gets_three_requests_then_waits(self):
        for _ in range(3):
            self.assertEqual(self.pay().status_code, 302)
        response = self.pay()
        self.assertContains(response, "Maombi mengi", status_code=429)
        self.assertEqual(Payment.objects.count(), 3)
        self.assertEqual(self.pay(phone="0754000111").status_code, 302)
