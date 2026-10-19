"""
Sehemu ndogo ya itifaki ya RADIUS (RFC 2865, 2866 na 3579) tunayohitaji kwa
MikroTik hotspot: kusoma maombi, kufungua password ya PAP, na kujibu kwa
authenticators sahihi pamoja na Message-Authenticator.
"""

import hashlib
import hmac
import struct
from dataclasses import dataclass, field

# Packet codes
ACCESS_REQUEST = 1
ACCESS_ACCEPT = 2
ACCESS_REJECT = 3
ACCOUNTING_REQUEST = 4
ACCOUNTING_RESPONSE = 5

# Attribute types
USER_NAME = 1
USER_PASSWORD = 2
REPLY_MESSAGE = 18
VENDOR_SPECIFIC = 26
SESSION_TIMEOUT = 27
CALLING_STATION_ID = 31
NAS_IDENTIFIER = 32
ACCT_STATUS_TYPE = 40
ACCT_INPUT_OCTETS = 42
ACCT_OUTPUT_OCTETS = 43
ACCT_SESSION_TIME = 46
ACCT_INPUT_GIGAWORDS = 52
ACCT_OUTPUT_GIGAWORDS = 53
ACCT_INTERIM_INTERVAL = 85
MESSAGE_AUTHENTICATOR = 80

# Acct-Status-Type values
ACCT_START = 1
ACCT_STOP = 2
ACCT_INTERIM_UPDATE = 3

MIKROTIK_VENDOR_ID = 14988
MIKROTIK_RATE_LIMIT = 8

HEADER = struct.Struct("!BBH16s")
MAX_PACKET_SIZE = 4096
_ZERO_AUTHENTICATOR = bytes(16)


class PacketError(ValueError):
    """Packet haieleweki au imeharibika."""


@dataclass
class Packet:
    code: int
    identifier: int
    authenticator: bytes
    attributes: list = field(default_factory=list)  # [(type, bytes)]
    raw: bytes = b""

    def get(self, attr_type):
        for current, value in self.attributes:
            if current == attr_type:
                return value
        return None

    def get_str(self, attr_type):
        value = self.get(attr_type)
        return value.decode("utf-8", errors="replace") if value is not None else None

    def get_int(self, attr_type):
        value = self.get(attr_type)
        if value is None or len(value) != 4:
            return None
        return struct.unpack("!I", value)[0]


def parse(data):
    if len(data) < HEADER.size:
        raise PacketError("packet ni fupi mno")
    code, identifier, length, authenticator = HEADER.unpack_from(data)
    if length < HEADER.size or length > len(data) or length > MAX_PACKET_SIZE:
        raise PacketError("urefu wa packet si sahihi")

    data = data[:length]
    attributes = []
    offset = HEADER.size
    while offset < length:
        if offset + 2 > length:
            raise PacketError("attribute imekatika")
        attr_type, attr_len = data[offset], data[offset + 1]
        if attr_len < 2 or offset + attr_len > length:
            raise PacketError("urefu wa attribute si sahihi")
        attributes.append((attr_type, data[offset + 2 : offset + attr_len]))
        offset += attr_len
    return Packet(code, identifier, authenticator, attributes, raw=data)


def encode_attributes(attributes):
    out = bytearray()
    for attr_type, value in attributes:
        if len(value) > 253:
            raise PacketError(f"attribute {attr_type} ni ndefu mno")
        out += bytes([attr_type, len(value) + 2]) + value
    return bytes(out)


def int_attr(value):
    return struct.pack("!I", value)


def mikrotik_attr(vendor_type, value):
    vsa = bytes([vendor_type, len(value) + 2]) + value
    return struct.pack("!I", MIKROTIK_VENDOR_ID) + vsa


def decrypt_pap_password(encrypted, secret, request_authenticator):
    if not encrypted or len(encrypted) % 16 or len(encrypted) > 128:
        raise PacketError("User-Password si sahihi")
    result = bytearray()
    previous = request_authenticator
    for start in range(0, len(encrypted), 16):
        block = encrypted[start : start + 16]
        key = hashlib.md5(secret + previous).digest()
        result += bytes(a ^ b for a, b in zip(block, key))
        previous = block
    return bytes(result).rstrip(b"\x00")


def encrypt_pap_password(password, secret, request_authenticator):
    """Kinyume cha decrypt. Kinatumika kwenye majaribio kuiga MikroTik."""
    padding = 16 if not password else -len(password) % 16
    padded = password + b"\x00" * padding
    result = bytearray()
    previous = request_authenticator
    for start in range(0, len(padded), 16):
        key = hashlib.md5(secret + previous).digest()
        block = bytes(a ^ b for a, b in zip(padded[start : start + 16], key))
        result += block
        previous = block
    return bytes(result)


def _with_zeroed_message_authenticator(packet):
    """Nakala ya packet ikiwa na Message-Authenticator iliyojazwa sifuri."""
    data = bytearray(packet.raw)
    offset = HEADER.size
    while offset < len(data):
        attr_type, attr_len = data[offset], data[offset + 1]
        if attr_type == MESSAGE_AUTHENTICATOR:
            data[offset + 2 : offset + attr_len] = bytes(attr_len - 2)
        offset += attr_len
    return bytes(data)


def verify_message_authenticator(packet, secret):
    """True kama ipo na ni sahihi, False kama ni batili, None kama haipo."""
    received = packet.get(MESSAGE_AUTHENTICATOR)
    if received is None:
        return None
    if len(received) != 16:
        return False
    expected = hmac.new(secret, _with_zeroed_message_authenticator(packet), hashlib.md5).digest()
    return hmac.compare_digest(expected, received)


def verify_accounting_request(packet, secret):
    data = packet.raw
    expected = hashlib.md5(data[:4] + _ZERO_AUTHENTICATOR + data[HEADER.size :] + secret).digest()
    return hmac.compare_digest(expected, packet.authenticator)


def build_response(code, request, secret, attributes=()):
    """
    Jenga jibu kwa request. Message-Authenticator inawekwa kama attribute ya
    kwanza (RFC 3579, na kinga dhidi ya BlastRADIUS), kisha Response
    Authenticator inakokotolewa juu ya packet nzima.
    """
    body = list(attributes)
    with_message_auth = code in (ACCESS_ACCEPT, ACCESS_REJECT)
    if with_message_auth:
        body.insert(0, (MESSAGE_AUTHENTICATOR, bytes(16)))

    encoded = encode_attributes(body)
    length = HEADER.size + len(encoded)
    header = HEADER.pack(code, request.identifier, length, request.authenticator)

    if with_message_auth:
        message_auth = hmac.new(secret, header + encoded, hashlib.md5).digest()
        # Attribute ya kwanza: aina (1 byte) + urefu (1 byte) + thamani (16).
        encoded = encoded[:2] + message_auth + encoded[18:]

    response_auth = hashlib.md5(header + encoded + secret).digest()
    return HEADER.pack(code, request.identifier, length, response_auth) + encoded


def build_request(code, identifier, authenticator, secret, attributes, message_authenticator=True):
    """Jenga request kama MikroTik ingefanya. Kinatumika kwenye majaribio."""
    if code == ACCOUNTING_REQUEST:
        message_authenticator = False
    body = list(attributes)
    if message_authenticator:
        body.insert(0, (MESSAGE_AUTHENTICATOR, bytes(16)))
    encoded = encode_attributes(body)
    length = HEADER.size + len(encoded)

    if code == ACCOUNTING_REQUEST:
        authenticator = hashlib.md5(
            HEADER.pack(code, identifier, length, _ZERO_AUTHENTICATOR) + encoded + secret
        ).digest()

    header = HEADER.pack(code, identifier, length, authenticator)
    if message_authenticator:
        message_auth = hmac.new(secret, header + encoded, hashlib.md5).digest()
        encoded = encoded[:2] + message_auth + encoded[18:]
    return header + encoded
