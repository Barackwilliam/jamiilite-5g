from django.urls import path

from . import views

app_name = "ui"

urlpatterns = [
    path("lugha/", views.set_language, name="set_language"),
]
