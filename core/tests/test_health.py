from unittest import mock

from django.db.utils import OperationalError
from django.test import TestCase
from django.urls import reverse


class HealthzTests(TestCase):
    def test_ok_when_database_answers(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_503_when_database_is_down(self):
        with mock.patch("core.health.connection.cursor", side_effect=OperationalError):
            response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 503)
