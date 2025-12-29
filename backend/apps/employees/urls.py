from django.urls import path
from apps.employees import views

urlpatterns = [
    path("", views.EmployeeListCreateView.as_view(), name="employees"),
    path("stats/", views.EmployeeStatsView.as_view(), name="employees-stats"),
    path("<int:pk>/", views.EmployeeDetailView.as_view(), name="employees-detail"),
    path("attendance/", views.AttendanceListCreateView.as_view(), name="employees-attendance"),
    path("attendance/<int:pk>/", views.AttendanceDetailView.as_view(), name="employees-attendance-detail"),
    path("schedules/", views.ScheduleListCreateView.as_view(), name="employees-schedules"),
    path("schedules/<int:pk>/", views.ScheduleDetailView.as_view(), name="employees-schedules-detail"),
]
