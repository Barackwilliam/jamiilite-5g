import logging
import selectors
import socket

from django.db import close_old_connections

from .handlers import handle
from .packet import MAX_PACKET_SIZE

logger = logging.getLogger("jamiilite.radius")


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
            if response:
                sock.sendto(response, address)

    def serve_forever(self):
        # Timeout fupi ili Ctrl+C ifanye kazi kwenye Windows pia.
        while True:
            self.serve_once(timeout=1.0)

    def close(self):
        for sock in self.sockets:
            self.selector.unregister(sock)
            sock.close()
        self.selector.close()
