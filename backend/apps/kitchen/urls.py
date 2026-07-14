from django.urls import path
from apps.kitchen import views
from apps.orders import table_views

urlpatterns = [
    path("orders/", views.KitchenOrderListView.as_view(), name="kitchen-orders"),
    path("items/<int:pk>/complete/", table_views.TableOrderItemKitchenStatusView.as_view(), {"target_status": "ready"}, name="kitchen-items-complete"),
]
