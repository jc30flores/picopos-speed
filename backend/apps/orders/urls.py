from django.urls import path
from apps.orders import views

urlpatterns = [
    path("", views.OrderCreateView.as_view(), name="orders-create"),
    path("active/", views.ActiveOrderListView.as_view(), name="orders-active"),
    path("<int:pk>/", views.OrderDetailView.as_view(), name="orders-detail"),
    path("<int:pk>/status/", views.OrderStatusUpdateView.as_view(), name="orders-status"),
    path("<int:pk>/void/", views.OrderVoidView.as_view(), name="orders-void"),
    path("customer-display/", views.CustomerDisplayOrderListView.as_view(), name="orders-customer-display"),
    path("customer-board/", views.CustomerBoardListView.as_view(), name="orders-customer-board"),
]
