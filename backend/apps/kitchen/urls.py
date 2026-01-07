from django.urls import path
from apps.kitchen import views

urlpatterns = [
    path("orders/", views.KitchenOrderListView.as_view(), name="kitchen-orders"),
]
