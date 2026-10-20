"""
Tengeneza Super Admin wa kwanza kutoka kwenye mazingira (environment), kwa
server zisizo na terminal (mfano Render Free). Inaendeshwa kwenye kila deploy:
akiwepo tayari, au vigezo havijawekwa, haifanyi kitu.

    DJANGO_SUPERUSER_USERNAME=<jina>
    DJANGO_SUPERUSER_PASSWORD=<password ndefu>
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Tengeneza Super Admin kutoka DJANGO_SUPERUSER_USERNAME na DJANGO_SUPERUSER_PASSWORD (ikiwa hayupo)."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        if not username or not password:
            self.stdout.write("ensure_superuser: vigezo havijawekwa, imerukwa.")
            return
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"ensure_superuser: '{username}' yupo tayari.")
            return
        User.objects.create_superuser(username=username, email=os.environ.get("DJANGO_SUPERUSER_EMAIL", ""), password=password)
        self.stdout.write(self.style.SUCCESS(f"ensure_superuser: Super Admin '{username}' ametengenezwa."))
