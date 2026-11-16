from django.test import Client, TestCase
from django.urls import reverse


class CsrfFailureTests(TestCase):
    def test_stale_form_gets_a_friendly_retry_page(self):
        client = Client(enforce_csrf_checks=True)
        login = reverse("dashboard:login")
        client.get(login)
        response = client.post(
            login, {"phone": "0712345678", "password": "x", "csrfmiddlewaretoken": "stale" * 8},
            HTTP_REFERER="http://testserver" + login,
        )
        self.assertEqual(response.status_code, 403)
        html = response.content.decode()
        self.assertIn(f'href="http://testserver{login}"', html)
        self.assertNotIn("CSRF verification failed", html)

    def test_outside_referer_is_not_followed(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("dashboard:login"), {}, HTTP_REFERER="https://evil.example/")
        self.assertIn('href="/"', response.content.decode())

    def test_form_pages_are_revalidated(self):
        response = self.client.get(reverse("dashboard:login"))
        self.assertIn("no-cache", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])
