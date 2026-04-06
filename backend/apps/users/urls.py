from django.urls import path
from apps.users import views

urlpatterns = [
    path("csrf/", views.csrf_view, name="auth-csrf"),
    path("csrf", views.csrf_view),
    path("login/", views.login_view, name="auth-login"),
    path("login", views.login_view),
    path("pin-login/", views.pin_login_view, name="auth-pin-login"),
    path("pin-login", views.pin_login_view),
    path("verify-privileged-pin/", views.verify_privileged_pin_view, name="auth-verify-privileged-pin"),
    path("authorize-price-change/", views.authorize_price_change_view, name="auth-authorize-price-change"),
    path("logout/", views.logout_view, name="auth-logout"),
    path("me/", views.me_view, name="auth-me"),
]
