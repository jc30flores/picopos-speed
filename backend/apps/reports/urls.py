from django.urls import path
from apps.reports import views

urlpatterns = [
    path("sales/", views.SalesReportListView.as_view(), name="reports-sales"),
    path("sales-timeseries/", views.SalesTimeseriesView.as_view(), name="reports-sales-timeseries"),
    path("sales-breakdown/", views.SalesBreakdownView.as_view(), name="reports-sales-breakdown"),
    path("sales-book/json/", views.SalesBookJsonView.as_view(), name="reports-sales-book-json"),
    path("sales-book/pdf/", views.SalesBookPdfView.as_view(), name="reports-sales-book-pdf"),
]
