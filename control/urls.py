from django.urls import path

from . import views

app_name = "control"

urlpatterns = [
    path("", views.home, name="home"),
    path("wamiliki/", views.owners, name="owners"),
    path("wamiliki/<int:pk>/", views.owner_detail, name="owner_detail"),
    path("kutoa-pesa/", views.withdrawals, name="withdrawals"),
    path("kutoa-pesa/<uuid:pk>/", views.withdrawal_action, name="withdrawal_action"),
    path("routers/", views.routers, name="routers"),
    path("routers/<int:pk>/", views.router_detail, name="router_detail"),
    path("hali/", views.system_status, name="status"),
    path("mipangilio/", views.platform_config, name="config"),
    path("malipo/", views.payments, name="payments"),
]
