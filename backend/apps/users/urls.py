from django.urls import path
from apps.users import views

urlpatterns = [
    path("csrf/", views.csrf_view, name="auth-csrf"),
    path("login/", views.login_view, name="auth-login"),
    path("pin-login/", views.pin_login_view, name="auth-pin-login"),
    path("verify-privileged-pin/", views.verify_privileged_pin_view, name="auth-verify-privileged-pin"),
    path("logout/", views.logout_view, name="auth-logout"),
    path("me/", views.me_view, name="auth-me"),
]
