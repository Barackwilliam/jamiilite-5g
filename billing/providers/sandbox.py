import secrets

from .base import PaymentProvider, PaymentRequestResult


class SandboxProvider(PaymentProvider):
    """Mtoa huduma wa majaribio: kila ombi la malipo linafanikiwa papo hapo."""

    name = "sandbox"

    def request_payment(self, payment):
        return PaymentRequestResult(reference=f"SBX-{secrets.token_hex(6)}", confirmed=True)
