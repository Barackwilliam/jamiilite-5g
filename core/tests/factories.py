from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Owner, Package, Router


def make_owner(username="mmiliki", business_name="Mama Neema WiFi", **kwargs):
    user = get_user_model().objects.create_user(username=username, password="test-pass-123")
    kwargs.setdefault("phone", "255712345678")
    kwargs.setdefault("trial_ends_at", timezone.now() + timedelta(days=14))
    return Owner.objects.create(user=user, business_name=business_name, **kwargs)


def make_router(owner=None, **kwargs):
    owner = owner or make_owner()
    kwargs.setdefault("name", "Duka la Kati")
    return Router.objects.create(owner=owner, **kwargs)


def make_package(owner, **kwargs):
    kwargs.setdefault("name", "Saa 1")
    kwargs.setdefault("price", 500)
    kwargs.setdefault("duration_minutes", 60)
    return Package.objects.create(owner=owner, **kwargs)
