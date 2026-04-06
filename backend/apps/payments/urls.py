from django.urls import path
from apps.payments import views

urlpatterns = [
    path("", views.PaymentListCreateView.as_view(), name="payments"),
    path("<int:pk>/ticket.pdf", views.PaymentTicketPDFView.as_view(), name="payment-ticket-pdf"),
    path("<int:pk>/internal-payment-method/", views.PaymentInternalMethodUpdateView.as_view(), name="payment-internal-method"),
    path("<int:pk>/record-refund/", views.PaymentRecordRefundView.as_view(), name="payment-record-refund"),
    path("<int:pk>/print-ticket/", views.PaymentPrintTicketView.as_view(), name="payment-print-ticket"),
    path("methods/", views.PaymentMethodListView.as_view(), name="payment-methods"),
]
