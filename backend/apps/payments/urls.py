from django.urls import path
from apps.payments import views

urlpatterns = [
    path("", views.PaymentListCreateView.as_view(), name="payments"),
    path("<int:pk>/print-ticket/", views.PaymentPrintTicketView.as_view(), name="payment-print-ticket"),
    path("methods/", views.PaymentMethodListView.as_view(), name="payment-methods"),
]
