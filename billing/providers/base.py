from dataclasses import dataclass


@dataclass
class PaymentRequestResult:
    """Jibu la mtoa huduma baada ya kuomba malipo (USSD push)."""

    reference: str = ""
    # True kama mtoa huduma amethibitisha malipo papo hapo (sandbox tu).
    # Watoa huduma halisi wanathibitisha baadaye kupitia callback.
    confirmed: bool = False
    error: str = ""
    # Ukurasa wa mtoa huduma ambao mteja anakamilishia malipo (mfano Pesapal).
    # Tunauweka ndani ya ukurasa wetu wenyewe, si kumpeleka mteja huko.
    checkout_url: str = ""


@dataclass
class PaymentStatusResult:
    """Hali ya malipo kama mtoa huduma anavyoiona."""

    state: str  # "paid", "failed" au "pending"
    amount: int = 0
    currency: str = ""
    confirmation: str = ""
    reason: str = ""


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

    def check_status(self, payment):
        """Muulize mtoa huduma hali ya malipo. None: mtoa huduma huyu hana njia hiyo."""
        return None

    def walled_garden_hosts(self):
        """Hosts ambazo mteja wa hotspot anahitaji kufungua kabla ya kulipa."""
        return []
