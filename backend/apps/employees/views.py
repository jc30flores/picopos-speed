from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics
from apps.core.audit import log_audit
from apps.core.permissions import IsAdminOrManager
from rest_framework.response import Response
from apps.employees.models import Employee, AttendanceRecord, Schedule
from apps.employees.serializers import EmployeeSerializer, AttendanceSerializer, ScheduleSerializer


class EmployeeListCreateView(generics.ListCreateAPIView):
    serializer_class = EmployeeSerializer

    def get_queryset(self):
        queryset = Employee.objects.select_related("branch").all()
        search = (self.request.query_params.get("search") or "").strip()
        role = (self.request.query_params.get("role") or "").strip()
        status = self.request.query_params.get("status")
        if search:
            queryset = queryset.filter(Q(full_name__icontains=search) | Q(email__icontains=search))
        if role:
            queryset = queryset.filter(role=role)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    permission_classes = [IsAdminOrManager]

    def perform_create(self, serializer):
        employee = serializer.save()
        log_audit(self.request, "employees.create", "Employee", employee.id, {"full_name": employee.full_name})


class EmployeeDetailView(generics.RetrieveUpdateAPIView):
    queryset = Employee.objects.select_related("branch").all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAdminOrManager]

    def perform_update(self, serializer):
        employee = serializer.save()
        log_audit(self.request, "employees.update", "Employee", employee.id, {"full_name": employee.full_name})


class EmployeeStatsView(generics.GenericAPIView):
    permission_classes = [IsAdminOrManager]
    def get(self, request, *args, **kwargs):
        today = timezone.localdate()
        total_employees = Employee.objects.count()
        active_employees = Employee.objects.filter(status="active").count()
        inactive_employees = Employee.objects.filter(status="inactive").count()
        attendance_today = AttendanceRecord.objects.filter(date=today)
        attendance_today_count = attendance_today.values("employee_id").distinct().count()
        late_today_count = attendance_today.filter(minutes_late__gt=0).count()

        return Response(
            {
                "total_employees": total_employees,
                "active_employees": active_employees,
                "inactive_employees": inactive_employees,
                "attendance_today_count": attendance_today_count,
                "late_today_count": late_today_count,
            }
        )


class AttendanceListCreateView(generics.ListCreateAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        queryset = AttendanceRecord.objects.select_related("employee")
        date_from = parse_date(self.request.query_params.get("date_from") or "")
        date_to = parse_date(self.request.query_params.get("date_to") or "")
        employee_id = self.request.query_params.get("employee_id")

        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        return queryset.order_by("-date")


class AttendanceDetailView(generics.RetrieveUpdateAPIView):
    queryset = AttendanceRecord.objects.select_related("employee")
    serializer_class = AttendanceSerializer
    permission_classes = [IsAdminOrManager]


class ScheduleListCreateView(generics.ListCreateAPIView):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        queryset = Schedule.objects.select_related("employee")
        employee_id = self.request.query_params.get("employee_id")
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        return queryset.order_by("employee_id", "day_of_week", "start_time")


class ScheduleDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Schedule.objects.select_related("employee")
    serializer_class = ScheduleSerializer
    permission_classes = [IsAdminOrManager]

    def perform_destroy(self, instance):
        log_audit(self.request, "schedules.delete", "Schedule", instance.id, {"employee": instance.employee_id})
        instance.delete()
