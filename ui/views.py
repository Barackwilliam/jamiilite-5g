from django.conf import settings
from django.shortcuts import redirect
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
    response = redirect(next_url)
    if language not in dict(settings.LANGUAGES):
        return response
    if request.user.is_authenticated:
        Owner.objects.filter(user=request.user).update(language=language)
    translation.activate(language)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME, language,
        max_age=settings.LANGUAGE_COOKIE_AGE, samesite="Lax", secure=request.is_secure(),
    )
    return response
