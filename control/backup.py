"""
Backup ya data yote ya biashara, inayopakuliwa na Super Admin kutoka kwenye mfumo wenyewe
(haihitaji GitHub wala huduma nyingine). Kurudisha: `python manage.py loaddata <faili>.json.gz`.
"""

import gzip
import io

from django.core.management import call_command
from django.utils import timezone

# Data ya muda (vikao, hesabu za majaribio, matukio ya ramani ya Live) na vitu ambavyo
# Django inavitengeneza yenyewe kwenye migrate havihitajiki kwenye backup.
EXCLUDE = [
    "contenttypes",
    "auth.permission",
    "sessions",
    "admin.logentry",
    "core.ratelimit",
    "core.networkevent",
]


def filename(now=None):
    return f"jamiilite-{timezone.localtime(now or timezone.now()):%Y-%m-%d-%H%M}.json.gz"


def build():
    """Data yote kama JSON iliyobanwa (gzip)."""
    out = io.StringIO()
    call_command(
        "dumpdata", natural_foreign=True, natural_primary=True, exclude=EXCLUDE, stdout=out,
    )
    return gzip.compress(out.getvalue().encode("utf-8"))
