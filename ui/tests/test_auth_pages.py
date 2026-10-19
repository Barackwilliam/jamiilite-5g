from django.test import TestCase
from django.urls import reverse


class AuthPagesTests(TestCase):
    def test_signup_has_live_owner_feed_and_steps(self):
        response = self.client.get(reverse("dashboard:signup"))
        self.assertContains(response, "data-auth-feed")
        self.assertContains(response, 'class="auth-steps"')
        self.assertContains(response, "data-strength=")
        self.assertContains(response, "ui/auth.js")
        self.assertContains(response, "Mixx by Yas")

    def test_login_in_english(self):
        response = self.client.get(reverse("dashboard:login"), HTTP_ACCEPT_LANGUAGE="en")
        self.assertContains(response, "Welcome back")
        self.assertContains(response, 'data-show-label="Show password"')
