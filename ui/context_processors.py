from django.conf import settings


def payment_methods(request):
    """Njia za malipo za mteja (kupitia Pesapal), zinaonyeshwa kwenye ukurasa wa kulipia na tovuti."""
    return {"payment_methods": settings.JAMIILITE_PAYMENT_METHODS}
