from django.urls import path

from .views import PublicPage

app_name = "pages"

urlpatterns = [
    path("", PublicPage.as_view(template_name="pages/home.html"), name="home"),
    path("mahitaji/", PublicPage.as_view(template_name="pages/mahitaji.html"), name="mahitaji"),
    path("mwongozo/", PublicPage.as_view(template_name="pages/mwongozo.html"), name="mwongozo"),
]
