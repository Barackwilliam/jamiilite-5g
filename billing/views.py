import uuid

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Payment
from .services import sync_with_provider


@csrf_exempt  # Inaitwa na Pesapal, si browser. Hatuamini maudhui yake: tunamuuliza Pesapal mwenyewe.
@require_http_methods(["GET", "POST"])
def pesapal_ipn(request):
    params = request.GET if request.method == "GET" else request.POST
    tracking_id = params.get("OrderTrackingId", "")
    reference = params.get("OrderMerchantReference", "")
    reply = {
        "orderNotificationType": params.get("OrderNotificationType", "IPNCHANGE"),
        "orderTrackingId": tracking_id,
        "orderMerchantReference": reference,
        "status": 500,
    }
    payment = Payment.objects.filter(pk=reference, provider_reference=tracking_id).first() if _is_uuid(reference) and tracking_id else None
    if payment is not None:
        sync_with_provider(payment, throttle=False)
        reply["status"] = 200
    return JsonResponse(reply)


def _is_uuid(value):
    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True
