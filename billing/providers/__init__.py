from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import PaymentProvider, PaymentRequestResult, PaymentStatusResult
from .pesapal import PesapalProvider
from .sandbox import SandboxProvider

PROVIDERS = {
    SandboxProvider.name: SandboxProvider,
    PesapalProvider.name: PesapalProvider,
}


def get_provider():
    name = settings.PAYMENT_PROVIDER
    provider_class = PROVIDERS.get(name)
    if provider_class is None:
        raise ImproperlyConfigured(f"PAYMENT_PROVIDER '{name}' haijulikani.")
    if provider_class is SandboxProvider and not settings.ALLOW_SANDBOX_PAYMENTS:
        raise ImproperlyConfigured(
            "Sandbox inathibitisha malipo bila pesa halisi. Weka ALLOW_SANDBOX_PAYMENTS=True "
            "kama unataka kuitumia nje ya DEBUG."
        )
    if provider_class is PesapalProvider and not (settings.PESAPAL_CONSUMER_KEY and settings.PESAPAL_CONSUMER_SECRET):
        raise ImproperlyConfigured("Weka PESAPAL_CONSUMER_KEY na PESAPAL_CONSUMER_SECRET.")
    return provider_class()


__all__ = ["PaymentProvider", "PaymentRequestResult", "PaymentStatusResult", "get_provider"]
