from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("<slug:slug>/", views.home, name="home"),
    path("<slug:slug>/lipa/", views.pay, name="pay"),
    path("<slug:slug>/malipo/<uuid:payment_id>/", views.payment_status, name="payment_status"),
]
