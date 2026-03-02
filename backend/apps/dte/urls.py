from django.urls import path
from apps.dte import views

urlpatterns = [
    path("issued/", views.DTEIssuedListView.as_view(), name="dte-issued-list"),
    path("issued/<int:pk>/", views.DTEIssuedDetailView.as_view(), name="dte-issued-detail"),
    path("issued/<int:pk>/resend/", views.DTEResendView.as_view(), name="dte-issued-resend"),
    path("issued/<int:pk>/send-email/", views.DTESendEmailView.as_view(), name="dte-issued-send-email"),
    path("issued/<int:pk>/send-whatsapp/", views.DTESendWhatsAppView.as_view(), name="dte-issued-send-whatsapp"),
    path("invalidate/preview/", views.DTEInvalidatePreviewView.as_view(), name="dte-invalidate-preview"),
    path("invalidate/", views.DTEInvalidateView.as_view(), name="dte-invalidate"),
    path("credit-note/preview/", views.DTECreditNotePreviewView.as_view(), name="dte-credit-note-preview"),
    path("credit-note/", views.DTECreditNoteCreateView.as_view(), name="dte-credit-note"),
]
