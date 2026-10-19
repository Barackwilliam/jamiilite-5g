import logging
import os
import selectors
import socket
import time
from collections import deque

from django.db import DatabaseError, close_old_connections
from django.utils import timezone

from core import events
from core.models import ServiceHeartbeat

from . import packet as rp
from .handlers import handle
from .packet import MAX_PACKET_SIZE

logger = logging.getLogger("jamiilite.radius")

HEARTBEAT_NAME = "radius"
HEARTBEAT_EVERY = 30  # sekunde
PRUNE_EVERY = 600  # sekunde: futa matukio ya zamani ya ramani ya Live
RECENT_WARNINGS = 20


class _WarningBuffer(logging.Handler):
    """Inaweka maonyo ya karibuni ili Super Admin ayaone kwenye "Hali ya mfumo"."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.items = deque(maxlen=RECENT_WARNINGS)

    def emit(self, record):
        self.items.appendleft({"at": timezone.now().isoformat(), "message": record.getMessage()[:300]})


class RadiusServer:
    """UDP server moja inayosikiliza port ya auth (1812) na ya accounting (1813)."""

    def __init__(self, host="0.0.0.0", auth_port=1812, acct_port=1813):
        self.selector = selectors.DefaultSelector()
        self.sockets = []
        for kind, port in (("auth", auth_port), ("acct", acct_port)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((host, port))
            sock.setblocking(False)
            self.selector.register(sock, selectors.EVENT_READ, kind)
            self.sockets.append(sock)
        self.started_at = timezone.now()
        self.counts = {"accept": 0, "reject": 0, "accounting": 0, "ignored": 0}
        self.warnings = _WarningBuffer()
        logger.addHandler(self.warnings)
        self._last_beat = 0.0
        self._last_prune = 0.0

    @property
    def addresses(self):
        return [sock.getsockname() for sock in self.sockets]

    def serve_once(self, timeout=None):
        for key, _ in self.selector.select(timeout):
            sock, kind = key.fileobj, key.data
            try:
                data, address = sock.recvfrom(MAX_PACKET_SIZE)
            except (BlockingIOError, ConnectionResetError):
                # Windows inaripoti ConnectionResetError kwenye UDP pale jibu
                # lililopita lilipokosa mpokeaji. Si kosa la seva.
                continue

            close_old_connections()
            try:
                response = handle(data, kind)
            except Exception:
                logger.exception("Hitilafu wakati wa kushughulikia packet kutoka %s", address)
                continue
            self._count(response)
            if response:
                sock.sendto(response, address)

    def _count(self, response):
        code = response[0] if response else None
        key = {rp.ACCESS_ACCEPT: "accept", rp.ACCESS_REJECT: "reject", rp.ACCOUNTING_RESPONSE: "accounting"}.get(code, "ignored")
        self.counts[key] += 1

    def heartbeat(self):
        """Andika kwenye database kuwa server iko hai, pamoja na takwimu zake."""
        self._last_beat = time.monotonic()
        try:
            close_old_connections()
            if time.monotonic() - self._last_prune >= PRUNE_EVERY:
                self._last_prune = time.monotonic()
                events.prune()
            ServiceHeartbeat.objects.update_or_create(
                name=HEARTBEAT_NAME,
                defaults={
                    "host": socket.gethostname()[:120],
                    "pid": os.getpid(),
                    "started_at": self.started_at,
                    "last_seen_at": timezone.now(),
                    "stats": {
                        "counts": self.counts,
                        "ports": [port for _, port in self.addresses],
                        "warnings": list(self.warnings.items),
                    },
                },
            )
        except DatabaseError:
            # Database ikiwa chini, RADIUS isisimame; tutajaribu tena baadaye.
            logger.exception("Imeshindwa kuandika heartbeat ya RADIUS")

    def serve_forever(self):
        # Timeout fupi ili Ctrl+C ifanye kazi kwenye Windows pia.
        while True:
            if time.monotonic() - self._last_beat >= HEARTBEAT_EVERY:
                self.heartbeat()
            self.serve_once(timeout=1.0)

    def close(self):
        logger.removeHandler(self.warnings)
        for sock in self.sockets:
            self.selector.unregister(sock)
            sock.close()
        self.selector.close()
