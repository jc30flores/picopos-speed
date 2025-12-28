from django.urls import path
from apps.reports import views

urlpatterns = [
    path("sales/", views.SaleSnapshotListView.as_view(), name="reports-sales"),
]
