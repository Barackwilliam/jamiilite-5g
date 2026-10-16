from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "JamiiLite 5G"
admin.site.site_title = "JamiiLite 5G"
admin.site.index_title = "Usimamizi"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("p/", include("portal.urls")),
]

if settings.DEBUG and not settings.USE_SUPABASE_STORAGE:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
