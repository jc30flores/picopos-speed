from django.urls import path
from apps.orders import views

urlpatterns = [
    path("", views.OrderCreateView.as_view(), name="orders-create"),
    path("active/", views.ActiveOrderListView.as_view(), name="orders-active"),
    path("<int:pk>/status/", views.OrderStatusUpdateView.as_view(), name="orders-status"),
]
