"""
Kurekodi matukio ya mtandao kwa ajili ya ramani ya "Live".

Kurekodi hakupaswi kamwe kuvunja kazi kuu (RADIUS au malipo), kwa hiyo kosa
lolote la database hapa linaandikwa kwenye log tu.
"""

import logging
from datetime import timedelta

from django.db import DatabaseError, transaction
from django.utils import timezone

from .models import NetworkEvent

logger = logging.getLogger("jamiilite.events")

Kind = NetworkEvent.Kind
KEEP_FOR = timedelta(hours=48)


def record(router, kind, *, mac="", detail="", amount=None):
    try:
        # savepoint: kosa hapa lisiharibu transaction ya anayetuita.
        with transaction.atomic():
            NetworkEvent.objects.create(
                router=router, kind=kind, mac=(mac or "")[:17], detail=(detail or "")[:160], amount=amount,
            )
    except DatabaseError:
        logger.exception("Imeshindwa kurekodi tukio %s", kind)


def prune(now=None):
    return NetworkEvent.objects.filter(created_at__lt=(now or timezone.now()) - KEEP_FOR).delete()[0]


def megabytes(octets, gigawords=0):
    total = (gigawords or 0) * 2**32 + (octets or 0)
    return total / 1_000_000
