import gzip
import json
import tempfile

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from billing.models import Payment
from core.models import Owner, Package, RateLimit, Router
from core.tests.factories import make_owner, make_package, make_router


class BackupTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("bosi", password=None)
        owner = make_owner()
        router = make_router(owner, slug="neema")
        package = make_package(owner)
        Payment.objects.create(router=router, package=package, phone="255712345678", amount=500, status=Payment.Status.PAID)
        RateLimit.objects.create(key="x", count=1, reset_at="2030-01-01T00:00:00Z")

    def download(self):
        self.client.force_login(self.admin)
        return self.client.post(reverse("control:backup"))

    def test_superadmin_downloads_all_business_data(self):
        response = self.download()
        self.assertEqual(response["Content-Type"], "application/gzip")
        self.assertIn("attachment; filename=\"jamiilite-", response["Content-Disposition"])
        models = {row["model"] for row in json.loads(gzip.decompress(response.content))}
        self.assertTrue({"core.owner", "core.router", "core.package", "billing.payment", "auth.user"} <= models)
        self.assertNotIn("core.ratelimit", models)
        self.assertNotIn("sessions.session", models)

    def test_backup_restores_with_loaddata(self):
        content = self.download().content
        Payment.objects.all().delete()  # malipo yanalinda wamiliki wasifutwe kwanza
        Owner.objects.all().delete()
        get_user_model().objects.exclude(pk=self.admin.pk).delete()
        self.assertFalse(Router.objects.exists())
        with tempfile.NamedTemporaryFile(suffix=".json.gz") as handle:
            handle.write(content)
            handle.flush()
            call_command("loaddata", handle.name, verbosity=0)
        self.assertEqual((Owner.objects.count(), Router.objects.count(), Package.objects.count(), Payment.objects.count()), (1, 1, 1, 1))

    def test_owners_and_get_requests_are_refused(self):
        owner = make_owner(username="mwingine", business_name="Mwingine")
        self.client.force_login(owner.user)
        self.assertEqual(self.client.post(reverse("control:backup")).status_code, 404)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("control:backup")).status_code, 405)
