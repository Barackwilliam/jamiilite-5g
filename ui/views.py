from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.shortcuts import redirect, render
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.models import Owner


@require_POST
def set_language(request):
    """Badilisha lugha: inahifadhiwa kwa mmiliki (ikiwa ameingia) na kwenye cookie."""
    language = request.POST.get("language", "")
    next_url = request.POST.get("next") or "/"
    if not url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
        next_url = "/"
    if language not in dict(settings.LANGUAGES):
        return redirect(next_url)
    # Ukurasa wenye ?lang=sw ungerudisha lugha ya zamani (UrlLanguageMiddleware); badilisha kwenda mpya.
    parts = urlsplit(next_url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    if any(key == "lang" for key, _value in query):
        query = [(key, language if key == "lang" else value) for key, value in query]
        next_url = urlunsplit(parts._replace(query=urlencode(query)))
    response = redirect(next_url)
    if request.user.is_authenticated:
        Owner.objects.filter(user=request.user).update(language=language)
    translation.activate(language)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME, language,
        max_age=settings.LANGUAGE_COOKIE_AGE, samesite="Lax", secure=request.is_secure(),
    )
    return response


def csrf_failure(request, reason=""):
    """
    Fomu ilitumwa na "tiketi" ya zamani (ukurasa ulikaa muda mrefu, au mtu aliingia kwenye tab
    nyingine). Badala ya ukurasa wa kiufundi, mrudishe kwenye ukurasa uleule aujaribu tena.
    """
    back = request.META.get("HTTP_REFERER", "")
    if not back or not url_has_allowed_host_and_scheme(back, {request.get_host()}, request.is_secure()):
        back = request.path if request.method == "GET" else "/"
    return render(request, "ui/csrf_failure.html", {"back_url": back}, status=403)
