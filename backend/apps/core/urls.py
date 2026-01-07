from django.urls import path
from apps.core import views

urlpatterns = [
    path("service-types/", views.ServiceTypeListView.as_view(), name="service-types"),
    path("tax-config/active/", views.ActiveTaxConfigView.as_view(), name="tax-config-active"),
]
