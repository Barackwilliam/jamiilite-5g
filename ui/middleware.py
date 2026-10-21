from django.conf import settings
from django.utils import translation


class UserLanguageMiddleware:
    """
    Mmiliki aliyeingia anaona dashboard kwa lugha aliyochagua, hata kama
    browser yake au cookie inasema vinginevyo. Wengine wanabaki na uamuzi wa
    LocaleMiddleware (cookie, kisha lugha ya browser).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        owner = getattr(user, "owner", None) if user is not None and user.is_authenticated else None
        if owner is not None and owner.language:
            translation.activate(owner.language)
            request.LANGUAGE_CODE = owner.language
        return self.get_response(request)


class UrlLanguageMiddleware:
    """
    ?lang=sw au ?lang=en kwenye anwani inachagua lugha, na inakumbukwa kwa cookie.
    Hivyo kila lugha ina anwani yake ambayo Google inaweza kuitembelea (hreflang).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = request.GET.get("lang", "")
        if lang not in dict(settings.LANGUAGES):
            return self.get_response(request)
        translation.activate(lang)
        request.LANGUAGE_CODE = lang
        response = self.get_response(request)
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME, lang, max_age=settings.LANGUAGE_COOKIE_AGE,
            samesite="Lax", secure=request.is_secure(),
        )
        return response
