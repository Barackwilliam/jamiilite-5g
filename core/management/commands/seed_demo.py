from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Owner, Package, Router

DEMO_PACKAGES = [
    ("Saa 1", 500, 60, "1M/2M"),
    ("Saa 6", 1000, 6 * 60, "1M/2M"),
    ("Siku 1", 1500, 24 * 60, "2M/3M"),
    ("Wiki 1", 7000, 7 * 24 * 60, "2M/3M"),
]


class Command(BaseCommand):
    help = "Tengeneza mmiliki, router na vifurushi vya mfano kwa majaribio."

    @transaction.atomic
    def handle(self, *args, **options):
        user, _ = get_user_model().objects.get_or_create(username="demo")
        owner, _ = Owner.objects.get_or_create(
            user=user, defaults={"business_name": "JamiiLite Demo", "phone": "255712345678"}
        )
        router, _ = Router.objects.get_or_create(
            owner=owner,
            name="MikroTik ya Majaribio",
            defaults={"slug": "demo", "location": "VirtualBox"},
        )
        for order, (name, price, minutes, rate) in enumerate(DEMO_PACKAGES):
            Package.objects.update_or_create(
                owner=owner,
                name=name,
                defaults={
                    "price": price,
                    "duration_minutes": minutes,
                    "rate_limit": rate,
                    "sort_order": order,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"Tayari. Fungua /p/{router.slug}/"))
