from django.urls import path
from apps.reports import views

urlpatterns = [
    path("sales/", views.SalesReportListView.as_view(), name="reports-sales"),
    path("sales-timeseries/", views.SalesTimeseriesView.as_view(), name="reports-sales-timeseries"),
    path("sales-breakdown/", views.SalesBreakdownView.as_view(), name="reports-sales-breakdown"),
    path("sales-book/json/", views.SalesBookJsonView.as_view(), name="reports-sales-book-json"),
    path("sales-book/pdf/", views.SalesBookPdfView.as_view(), name="reports-sales-book-pdf"),
    path("employee-worked-hours/", views.EmployeeWorkedHoursReportView.as_view(), name="reports-employee-worked-hours"),
    path("transactions/<int:payment_id>/ticket/", views.TransactionTicketView.as_view(), name="reports-transaction-ticket"),
    path("employee-hours/", views.EmployeeHoursReportView.as_view(), name="reports-employee-hours"),
    path("employee-hours/<int:employee_id>/", views.EmployeeHoursDetailView.as_view(), name="reports-employee-hours-detail"),
    path("employee-hours/cycles/", views.EmployeeHoursCycleCreateView.as_view(), name="reports-employee-hours-cycle-create"),
    path("employee-hours/cycles/<int:cycle_id>/", views.EmployeeHoursCycleUpdateView.as_view(), name="reports-employee-hours-cycle-update"),
]
