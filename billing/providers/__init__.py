from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import PaymentProvider, PaymentRequestResult
from .sandbox import SandboxProvider

PROVIDERS = {
    SandboxProvider.name: SandboxProvider,
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
    return provider_class()


__all__ = ["PaymentProvider", "PaymentRequestResult", "get_provider"]
