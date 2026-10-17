from django.core.management.base import BaseCommand, CommandError

from core.models import Router
from radius import routeros


class Command(BaseCommand):
    help = "Chapisha mstari mmoja wa kusanidi MikroTik kwa JamiiLite 5G."

    def add_arguments(self, parser):
        parser.add_argument("slug", help="Kitambulisho cha router, mfano demo")
        parser.add_argument(
            "--full", action="store_true", help="Chapisha script nzima badala ya mstari mmoja"
        )

    def handle(self, *args, slug, full, **options):
        router = Router.objects.filter(slug=slug).first()
        if router is None:
            raise CommandError(f"Hakuna router yenye kitambulisho '{slug}'.")
        if not router.nas_identifier:
            raise CommandError("Router hii haina NAS identifier. Iweke kwenye admin kwanza.")

        if full:
            self.stdout.write(routeros.setup_script(router))
        else:
            self.stdout.write(routeros.provision_command(router))
