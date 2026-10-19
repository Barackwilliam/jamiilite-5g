import logging

from django.core.management.base import BaseCommand

from radius.server import RadiusServer


class Command(BaseCommand):
    help = "Washa RADIUS server ambayo MikroTik inaiuliza kuhusu vocha."

    def add_arguments(self, parser):
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--auth-port", type=int, default=1812)
        parser.add_argument("--acct-port", type=int, default=1813)

    def handle(self, *args, **options):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        server = RadiusServer(options["host"], options["auth_port"], options["acct_port"])
        for host, port in server.addresses:
            self.stdout.write(self.style.SUCCESS(f"RADIUS inasikiliza {host}:{port}"))
        self.stdout.write("Bonyeza Ctrl+C kuisimamisha.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            self.stdout.write("\nRADIUS imesimamishwa.")
        finally:
            server.close()
