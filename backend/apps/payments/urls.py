from django.urls import path
from apps.payments import views

urlpatterns = [
    path("", views.PaymentListCreateView.as_view(), name="payments"),
    path("methods/", views.PaymentMethodListView.as_view(), name="payment-methods"),
]
