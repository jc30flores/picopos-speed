from django.urls import path
from apps.employees import views

urlpatterns = [
    path("", views.EmployeeListCreateView.as_view(), name="employees"),
    path("stats/", views.EmployeeStatsView.as_view(), name="employees-stats"),
    path("<int:pk>/", views.EmployeeDetailView.as_view(), name="employees-detail"),
    path("attendance/", views.AttendanceListCreateView.as_view(), name="employees-attendance"),
    path("attendance/<int:pk>/", views.AttendanceDetailView.as_view(), name="employees-attendance-detail"),
    path("attendance/today/", views.AttendanceTodayView.as_view(), name="employees-attendance-today"),
    path("attendance/clock-in/", views.AttendanceClockInView.as_view(), name="employees-attendance-clock-in"),
    path("attendance/break-start/", views.AttendanceBreakStartView.as_view(), name="employees-attendance-break-start"),
    path("attendance/break-end/", views.AttendanceBreakEndView.as_view(), name="employees-attendance-break-end"),
    path("attendance/clock-out/", views.AttendanceClockOutView.as_view(), name="employees-attendance-clock-out"),
    path("me/attendance/", views.AttendanceMeHistoryView.as_view(), name="employees-attendance-me-history"),
    path("<int:employee_id>/attendance/", views.AttendanceEmployeeHistoryView.as_view(), name="employees-attendance-employee-history"),
    path("schedules/", views.ScheduleListCreateView.as_view(), name="employees-schedules"),
    path("schedules/<int:pk>/", views.ScheduleDetailView.as_view(), name="employees-schedules-detail"),
]
