from django.urls import path

from .views import ArticleDetail, ArticleIndex, LegalPage, PublicPage

app_name = "pages"

urlpatterns = [
    path("", PublicPage.as_view(template_name="pages/home.html"), name="home"),
    path("mahitaji/", PublicPage.as_view(template_name="pages/mahitaji.html"), name="mahitaji"),
    path("mwongozo/", PublicPage.as_view(template_name="pages/mwongozo.html"), name="mwongozo"),
    path("masharti/", LegalPage.as_view(document="masharti"), name="masharti"),
    path("faragha/", LegalPage.as_view(document="faragha"), name="faragha"),
    path("makala/", ArticleIndex.as_view(), name="makala"),
    path("makala/<slug:slug>/", ArticleDetail.as_view(), name="makala_detail"),
]
