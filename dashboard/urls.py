from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("jisajili/", views.signup, name="signup"),
    path("ingia/", views.login_view, name="login"),
    path("toka/", views.logout_view, name="logout"),
    path("dashboard/", views.home, name="home"),
    path("dashboard/routers/", views.routers, name="routers"),
    path("dashboard/routers/<int:pk>/", views.router_detail, name="router_detail"),
    path("dashboard/vifurushi/", views.packages, name="packages"),
    path("dashboard/vifurushi/<int:pk>/", views.package_edit, name="package_edit"),
    path("dashboard/vocha/", views.vouchers, name="vouchers"),
    path("dashboard/vocha/chapisha/<str:batch>/", views.voucher_print, name="voucher_print"),
    path("dashboard/mauzo/", views.sales, name="sales"),
    path("dashboard/salio/", views.wallet_view, name="wallet"),
    path("dashboard/usajili/", views.subscription, name="subscription"),
    path("dashboard/mipangilio/", views.settings_view, name="settings"),
]
