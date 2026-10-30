from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("pesapal/ipn/", views.pesapal_ipn, name="pesapal_ipn"),
]
