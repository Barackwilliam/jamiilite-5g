import secrets
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase


def run():
    out = StringIO()
    call_command("ensure_superuser", stdout=out)
    return out.getvalue()


# Inatengenezwa wakati wa jaribio, ili password isiandikwe kwenye code.
PASSWORD = secrets.token_urlsafe(16)
OTHER_PASSWORD = secrets.token_urlsafe(16)


class EnsureSuperuserTests(TestCase):
    def test_skips_without_variables(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertIn("imerukwa", run())
        self.assertFalse(get_user_model().objects.exists())

    def test_creates_once_and_keeps_existing_password(self):
        env = {"DJANGO_SUPERUSER_USERNAME": "admin", "DJANGO_SUPERUSER_PASSWORD": PASSWORD}
        with mock.patch.dict("os.environ", env, clear=True):
            self.assertIn("ametengenezwa", run())
        user = get_user_model().objects.get(username="admin")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password(PASSWORD))

        with mock.patch.dict("os.environ", {**env, "DJANGO_SUPERUSER_PASSWORD": OTHER_PASSWORD}, clear=True):
            self.assertIn("yupo tayari", run())
        user.refresh_from_db()
        self.assertTrue(user.check_password(PASSWORD))
