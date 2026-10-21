from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.i18n import JavaScriptCatalog

from core.health import healthz
from pages.views import favicon, robots_txt, sitemap_xml

admin.site.site_header = "JamiiLite 5G"
admin.site.site_title = "JamiiLite 5G"
admin.site.index_title = "Usimamizi"

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("robots.txt", robots_txt, name="robots"),
    path("sitemap.xml", sitemap_xml, name="sitemap"),
    path("favicon.ico", favicon),
    path("admin/", admin.site.urls),
    path("p/", include("portal.urls")),
    path("r/", include("radius.urls")),
    path("control/", include("control.urls")),
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    path("", include("ui.urls")),
    path("", include("dashboard.urls")),
    path("", include("pages.urls")),
]

if settings.DEBUG and not settings.USE_SUPABASE_STORAGE:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
