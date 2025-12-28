from django.urls import path
from apps.employees import views

urlpatterns = [
    path("", views.EmployeeListCreateView.as_view(), name="employees"),
    path("attendance/", views.AttendanceListView.as_view(), name="employees-attendance"),
]
