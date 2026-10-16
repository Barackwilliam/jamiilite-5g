from dataclasses import dataclass


@dataclass
class PaymentRequestResult:
    """Jibu la mtoa huduma baada ya kuomba malipo (USSD push)."""

    reference: str = ""
    # True kama mtoa huduma amethibitisha malipo papo hapo (sandbox tu).
    # Watoa huduma halisi wanathibitisha baadaye kupitia callback.
    confirmed: bool = False
    error: str = ""


class PaymentProvider:
    """
    Kiolesura cha watoa huduma wa malipo (Selcom, AzamPay, ClickPesa...).

    Kila mtoa huduma anaanzisha malipo kwa `request_payment`. Akishathibitisha
    (papo hapo au kupitia callback), mfumo unaita
    `billing.services.confirm_payment`.
    """

    name = ""

    def request_payment(self, payment) -> PaymentRequestResult:
        raise NotImplementedError
