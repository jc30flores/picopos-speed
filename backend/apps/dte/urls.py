from django.urls import path
from apps.dte import views

urlpatterns = [
    path("issued/", views.DTEIssuedListView.as_view(), name="dte-issued-list"),
    path("issued/<int:pk>/", views.DTEIssuedDetailView.as_view(), name="dte-issued-detail"),
    path("issued/<int:pk>/resend/", views.DTEResendView.as_view(), name="dte-issued-resend"),
    path("issued/<int:pk>/deliver/", views.DTEBulkDeliveryView.as_view(), name="dte-issued-deliver"),
    path("issued/<int:pk>/send-email/", views.DTESendEmailView.as_view(), name="dte-issued-send-email"),
    path("issued/<int:pk>/send-whatsapp/", views.DTESendWhatsAppView.as_view(), name="dte-issued-send-whatsapp"),
    path("issued/<int:pk>/invalidate/", views.DTEInvalidateView.as_view(), name="dte-issued-invalidate"),
    path("issued/<int:pk>/credit-note/", views.DTECreditNoteView.as_view(), name="dte-issued-credit-note"),
    path("invalidate/preview/", views.DTEInvalidatePreviewView.as_view(), name="dte-invalidate-preview"),
    path("credit-note/preview/", views.DTECreditNotePreviewView.as_view(), name="dte-credit-note-preview"),
    path("orders/<int:order_id>/deliver/", views.DTEOrderBulkDeliveryView.as_view(), name="dte-order-deliver"),
]
