import hashlib
import hmac
import os
import socket
import struct
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from billing.models import Voucher, VoucherDevice
from core.tests.factories import make_owner, make_package, make_router
from radius import packet as rp
from radius.handlers import (
    MSG_DEVICE_LIMIT,
    MSG_EXPIRED,
    MSG_INVALID,
    MSG_USE_PAP,
    handle,
)
from radius.server import RadiusServer

MAC_A = "08:00:27:50:4C:14"
MAC_B = "08:00:27:AA:BB:CC"


def access_request(secret, nas_id, username, password=None, mac=MAC_A, message_authenticator=True):
    authenticator = os.urandom(16)
    attributes = [(rp.NAS_IDENTIFIER, nas_id.encode()), (rp.USER_NAME, username.encode())]
    if password is not None:
        attributes.append(
            (rp.USER_PASSWORD, rp.encrypt_pap_password(password.encode(), secret, authenticator))
        )
    if mac:
        attributes.append((rp.CALLING_STATION_ID, mac.encode()))
    return rp.build_request(
        rp.ACCESS_REQUEST, 7, authenticator, secret, attributes, message_authenticator
    )


def assert_valid_response(test, response, request_bytes, secret):
    """Hakiki jibu kama MikroTik ingefanya: Response Authenticator na Message-Authenticator."""
    request = rp.parse(request_bytes)
    reply = rp.parse(response)
    test.assertEqual(reply.identifier, request.identifier)

    expected_auth = hashlib.md5(
        response[:4] + request.authenticator + response[rp.HEADER.size :] + secret
    ).digest()
    test.assertEqual(reply.authenticator, expected_auth, "Response Authenticator si sahihi")

    if reply.code in (rp.ACCESS_ACCEPT, rp.ACCESS_REJECT):
        test.assertEqual(reply.attributes[0][0], rp.MESSAGE_AUTHENTICATOR)
        zeroed = bytearray(response)
        zeroed[4:20] = request.authenticator
        zeroed[rp.HEADER.size + 2 : rp.HEADER.size + 18] = bytes(16)
        expected_ma = hmac.new(secret, bytes(zeroed), hashlib.md5).digest()
        test.assertEqual(reply.get(rp.MESSAGE_AUTHENTICATOR), expected_ma)
    return reply


def mikrotik_rate_limit(reply):
    value = reply.get(rp.VENDOR_SPECIFIC)
    if value is None:
        return None
    vendor_id, vendor_type, vendor_len = struct.unpack("!IBB", value[:6])
    assert vendor_id == rp.MIKROTIK_VENDOR_ID and vendor_type == rp.MIKROTIK_RATE_LIMIT
    return value[6:vendor_len + 4].decode()


class PacketTests(TestCase):
    def test_pap_round_trip(self):
        secret, authenticator = b"siri", os.urandom(16)
        for length in (1, 8, 15, 16, 17, 40):
            with self.subTest(length=length):
                password = b"A" * length
                encrypted = rp.encrypt_pap_password(password, secret, authenticator)
                self.assertEqual(len(encrypted) % 16, 0)
                self.assertEqual(rp.decrypt_pap_password(encrypted, secret, authenticator), password)

    def test_rejects_malformed_packets(self):
        for data in (b"", b"\x01\x02", b"\x01\x02\x00\x05" + bytes(16), b"\x01\x02\x00\x16" + bytes(16) + b"\x01\x09"):
            with self.subTest(data=data), self.assertRaises(rp.PacketError):
                rp.parse(data)


class AccessRequestTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.router = make_router(self.owner, nas_identifier="wifi-majaribio")
        self.secret = self.router.radius_secret.encode()
        self.package = make_package(self.owner, duration_minutes=60, rate_limit="1M/2M")
        self.voucher = Voucher.objects.create(router=self.router, package=self.package)

    def login(self, username=None, password=None, **kwargs):
        username = self.voucher.code if username is None else username
        password = username if password is None else password
        request = access_request(self.secret, "wifi-majaribio", username, password, **kwargs)
        return request, handle(request, "auth")

    def test_valid_voucher_is_accepted_with_time_and_speed(self):
        request, response = self.login()

        reply = assert_valid_response(self, response, request, self.secret)
        self.assertEqual(reply.code, rp.ACCESS_ACCEPT)
        self.assertAlmostEqual(reply.get_int(rp.SESSION_TIMEOUT), 3600, delta=2)
        self.assertEqual(mikrotik_rate_limit(reply), "1M/2M")

        self.voucher.refresh_from_db()
        self.assertIsNotNone(self.voucher.activated_at)
        self.assertEqual(list(self.voucher.devices.values_list("mac_address", flat=True)), [MAC_A])

    def test_lowercase_code_is_accepted(self):
        _, response = self.login(username=self.voucher.code.lower())
        self.assertEqual(rp.parse(response).code, rp.ACCESS_ACCEPT)

    def test_reconnect_gets_only_remaining_calendar_time(self):
        self.voucher.activate(now=timezone.now() - timedelta(minutes=45))

        request, response = self.login()
        reply = assert_valid_response(self, response, request, self.secret)
        self.assertAlmostEqual(reply.get_int(rp.SESSION_TIMEOUT), 15 * 60, delta=2)

    def test_expired_voucher_is_rejected_with_message(self):
        self.voucher.activate(now=timezone.now() - timedelta(minutes=61))

        request, response = self.login()
        reply = assert_valid_response(self, response, request, self.secret)
        self.assertEqual(reply.code, rp.ACCESS_REJECT)
        self.assertEqual(reply.get_str(rp.REPLY_MESSAGE), MSG_EXPIRED)

    def test_wrong_password_unknown_code_and_other_owner_are_rejected(self):
        other_owner = make_owner(username="mwingine", business_name="Duka Jingine")
        other_router = make_router(other_owner)
        foreign = Voucher.objects.create(
            router=other_router, package=make_package(other_owner)
        )
        cases = {
            "nenosiri-batili": (self.voucher.code, "BATILI"),
            "vocha-haipo": ("HAKUNAHII", "HAKUNAHII"),
            "vocha-ya-mmiliki-mwingine": (foreign.code, foreign.code),
        }
        for name, (username, password) in cases.items():
            with self.subTest(name):
                request, response = self.login(username=username, password=password)
                reply = assert_valid_response(self, response, request, self.secret)
                self.assertEqual(reply.code, rp.ACCESS_REJECT)
                self.assertEqual(reply.get_str(rp.REPLY_MESSAGE), MSG_INVALID)

    def test_voucher_of_same_owner_works_on_another_router(self):
        second = make_router(self.owner, name="Tawi la Pili", nas_identifier="tawi-2")
        secret = second.radius_secret.encode()
        request = access_request(secret, "tawi-2", self.voucher.code, self.voucher.code)

        reply = assert_valid_response(self, handle(request, "auth"), request, secret)
        self.assertEqual(reply.code, rp.ACCESS_ACCEPT)

    def test_device_limit(self):
        self.login(mac=MAC_A)
        request, response = self.login(mac=MAC_B)
        self.assertEqual(rp.parse(response).get_str(rp.REPLY_MESSAGE), MSG_DEVICE_LIMIT)

        _, again = self.login(mac=MAC_A)
        self.assertEqual(rp.parse(again).code, rp.ACCESS_ACCEPT)

        self.package.shared_users = 2
        self.package.save()
        _, second_device = self.login(mac=MAC_B)
        self.assertEqual(rp.parse(second_device).code, rp.ACCESS_ACCEPT)

    def test_chap_login_is_rejected_with_hint(self):
        request = access_request(self.secret, "wifi-majaribio", self.voucher.code, password=None)
        reply = rp.parse(handle(request, "auth"))
        self.assertEqual(reply.code, rp.ACCESS_REJECT)
        self.assertEqual(reply.get_str(rp.REPLY_MESSAGE), MSG_USE_PAP)

    def test_unknown_router_and_wrong_secret_are_ignored(self):
        code = self.voucher.code
        self.assertIsNone(handle(access_request(self.secret, "haijulikani", code, code), "auth"))
        self.assertIsNone(handle(access_request(b"secret-batili", "wifi-majaribio", code, code), "auth"))
        self.router.is_active = False
        self.router.save()
        self.assertIsNone(handle(access_request(self.secret, "wifi-majaribio", code, code), "auth"))

    def test_missing_message_authenticator(self):
        code = self.voucher.code
        request = access_request(self.secret, "wifi-majaribio", code, code, message_authenticator=False)
        self.assertIsNone(handle(request, "auth"))

        with override_settings(RADIUS_REQUIRE_MESSAGE_AUTHENTICATOR=False):
            reply = assert_valid_response(self, handle(request, "auth"), request, self.secret)
            self.assertEqual(reply.code, rp.ACCESS_ACCEPT)

    def test_accounting_is_acknowledged(self):
        self.login()
        attributes = [
            (rp.NAS_IDENTIFIER, b"wifi-majaribio"),
            (rp.USER_NAME, self.voucher.code.encode()),
            (rp.CALLING_STATION_ID, MAC_A.encode()),
            (rp.ACCT_STATUS_TYPE, rp.int_attr(rp.ACCT_INTERIM_UPDATE)),
        ]
        request = rp.build_request(rp.ACCOUNTING_REQUEST, 9, b"", self.secret, attributes)
        before = VoucherDevice.objects.get().last_seen_at

        reply = assert_valid_response(self, handle(request, "acct"), request, self.secret)
        self.assertEqual(reply.code, rp.ACCOUNTING_RESPONSE)
        self.assertGreaterEqual(VoucherDevice.objects.get().last_seen_at, before)

        tampered = bytearray(request)
        tampered[-1] ^= 0xFF
        self.assertIsNone(handle(bytes(tampered), "acct"))


class ServerSocketTests(TestCase):
    def test_answers_over_udp(self):
        owner = make_owner()
        router = make_router(owner, nas_identifier="wifi-majaribio")
        voucher = Voucher.objects.create(router=router, package=make_package(owner))
        secret = router.radius_secret.encode()

        server = RadiusServer("127.0.0.1", 0, 0)
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(5)
        try:
            request = access_request(secret, "wifi-majaribio", voucher.code, voucher.code)
            client.sendto(request, server.addresses[0])
            server.serve_once(timeout=5)
            response, _ = client.recvfrom(rp.MAX_PACKET_SIZE)
        finally:
            client.close()
            server.close()

        reply = assert_valid_response(self, response, request, secret)
        self.assertEqual(reply.code, rp.ACCESS_ACCEPT)
