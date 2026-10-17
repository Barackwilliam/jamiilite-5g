from django.urls import path

from . import views

app_name = "radius"

urlpatterns = [
    path("<str:token>/setup.rsc", views.setup_script, name="setup_script"),
    path("<str:token>/checkin", views.checkin, name="checkin"),
]
