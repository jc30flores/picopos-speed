from django.urls import path
from apps.orders import views
from apps.dte import views as dte_views

urlpatterns = [
    path("", views.OrderCreateView.as_view(), name="orders-create"),
    path("validate-price-pin/", views.ValidatePricePinView.as_view(), name="orders-validate-price-pin"),
    path("active/", views.ActiveOrderListView.as_view(), name="orders-active"),
    path("pending/", views.PendingOrderListView.as_view(), name="orders-pending"),
    path("kitchen/", views.KitchenOrderListView.as_view(), name="orders-kitchen"),
    path("<int:pk>/", views.OrderDetailView.as_view(), name="orders-detail"),
    path("<int:pk>/status/", views.OrderStatusUpdateView.as_view(), name="orders-status"),
    path("<int:pk>/send-to-kitchen/", views.OrderSendToKitchenView.as_view(), name="orders-send-to-kitchen"),
    path("<int:pk>/pending/", views.PendingOrderToggleView.as_view(), name="orders-pending-toggle"),
    path("<int:pk>/void/", views.OrderVoidView.as_view(), name="orders-void"),
    path("<int:pk>/receipt.pdf", views.OrderReceiptPDFView.as_view(), name="orders-receipt-pdf"),
    path("<int:pk>/credit-note/", dte_views.OrderCreditNoteView.as_view(), name="orders-credit-note"),
    path("<int:pk>/credit-note/preview/", dte_views.OrderCreditNotePreviewView.as_view(), name="orders-credit-note-preview"),
    path("customer-display/", views.CustomerDisplayOrderListView.as_view(), name="orders-customer-display"),
    path("customer-board/", views.CustomerBoardListView.as_view(), name="orders-customer-board"),
]
