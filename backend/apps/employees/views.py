from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
import logging
from rest_framework import generics, status
from apps.core.audit import log_audit
from apps.core.permissions import IsAdminOrManager, IsAuthenticatedAndActive
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.employees.models import Employee, AttendanceRecord, AttendanceCycle, Schedule
from apps.employees.serializers import (
    EmployeeSerializer,
    AttendanceSerializer,
    ScheduleSerializer,
    AttendanceStateSerializer,
    AttendanceHistoryRowSerializer,
    build_attendance_state,
)

logger = logging.getLogger(__name__)


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


def _get_employee_for_user(user):
    return Employee.objects.select_related("user").filter(user=user).first()


def _today_record_for_employee(employee: Employee) -> AttendanceRecord:
    today = timezone.localdate()
    record, _ = AttendanceRecord.objects.get_or_create(employee=employee, date=today)
    return record

def _today_record_if_exists(employee: Employee) -> AttendanceRecord | None:
    today = timezone.localdate()
    return AttendanceRecord.objects.filter(employee=employee, date=today).first()


class AttendanceTodayView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, *args, **kwargs):
        employee = _get_employee_for_user(request.user)
        if not employee:
            logger.info("attendance.today.no_employee user_id=%s", request.user.id)
            return Response({"attendance": None, "state": "NO_EMPLOYEE"}, status=status.HTTP_200_OK)
        record = _today_record_if_exists(employee)
        if not record:
            empty_record = AttendanceRecord(employee=employee, date=timezone.localdate())
            payload = build_attendance_state(empty_record, employee)
            logger.info("attendance.today.no_record user_id=%s employee_id=%s payload=%s", request.user.id, employee.id, payload)
            return Response(
                {
                    "attendance": AttendanceStateSerializer(payload).data,
                    "state": "NO_RECORD_TODAY",
                },
                status=status.HTTP_200_OK,
            )
        payload = build_attendance_state(record, employee)
        logger.info("attendance.today.ok user_id=%s employee_id=%s payload=%s", request.user.id, employee.id, payload)
        return Response({"attendance": AttendanceStateSerializer(payload).data, "state": "OK"}, status=status.HTTP_200_OK)


class AttendanceActionView(APIView):
    permission_classes = [IsAuthenticatedAndActive]
    action = ""

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        employee = _get_employee_for_user(request.user)
        if not employee:
            logger.info("attendance.action.no_employee user_id=%s action=%s", request.user.id, self.action)
            return Response(
                {"detail": "Empleado no asociado al usuario.", "state": "NO_EMPLOYEE"},
                status=status.HTTP_404_NOT_FOUND,
            )
        today = timezone.localdate()
        record, _ = AttendanceRecord.objects.select_for_update().get_or_create(employee=employee, date=today)
        now = timezone.now()
        active_cycle = (
            AttendanceCycle.objects.select_for_update()
            .filter(attendance_record=record, clock_out_at__isnull=True)
            .order_by("-sequence", "-id")
            .first()
        )
        if not active_cycle and (record.clock_in or record.check_in) and not (record.clock_out or record.check_out):
            next_sequence = (AttendanceCycle.objects.filter(attendance_record=record).order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
            active_cycle = AttendanceCycle.objects.create(
                attendance_record=record,
                sequence=next_sequence,
                clock_in_at=record.clock_in or record.check_in,
                break_start_at=record.break_start,
                break_end_at=record.break_end,
            )
        clock_in = active_cycle.clock_in_at if active_cycle else (record.clock_in or record.check_in)
        clock_out = active_cycle.clock_out_at if active_cycle else (record.clock_out or record.check_out)
        has_active_session = active_cycle is not None
        break_start = active_cycle.break_start_at if active_cycle else None
        break_end = active_cycle.break_end_at if active_cycle else None
        logger.info(
            "attendance.action.start user_id=%s employee_id=%s action=%s clock_in=%s clock_out=%s has_active_session=%s break_start=%s break_end=%s",
            request.user.id,
            employee.id,
            self.action,
            clock_in,
            clock_out,
            has_active_session,
            break_start,
            break_end,
        )

        if self.action == "clock_in":
            if has_active_session:
                payload = build_attendance_state(record, employee)
                return Response(AttendanceStateSerializer(payload).data, status=status.HTTP_200_OK)
            next_sequence = (AttendanceCycle.objects.filter(attendance_record=record).order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
            active_cycle = AttendanceCycle.objects.create(attendance_record=record, sequence=next_sequence, clock_in_at=now)
            record.clock_in = active_cycle.clock_in_at
            record.check_in = active_cycle.clock_in_at
            record.clock_out = None
            record.check_out = None
            record.break_start = None
            record.break_end = None
            record.total_clock_ins = int(record.total_clock_ins or 0) + 1
        elif self.action == "break_start":
            if not has_active_session:
                return Response({"detail": "Debes marcar entrada antes de salir a break."}, status=status.HTTP_400_BAD_REQUEST)
            if active_cycle.break_start_at and not active_cycle.break_end_at:
                return Response({"detail": "Ya estás en break."}, status=status.HTTP_400_BAD_REQUEST)
            if active_cycle.break_start_at and active_cycle.break_end_at:
                return Response({"detail": "Ya completaste el break de este ciclo."}, status=status.HTTP_400_BAD_REQUEST)
            active_cycle.break_start_at = now
            active_cycle.save(update_fields=["break_start_at", "updated_at"])
            record.break_start = now
        elif self.action == "break_end":
            if not has_active_session:
                return Response({"detail": "La jornada ya está cerrada."}, status=status.HTTP_400_BAD_REQUEST)
            if not active_cycle.break_start_at:
                return Response({"detail": "Debes marcar salida a break primero."}, status=status.HTTP_400_BAD_REQUEST)
            if active_cycle.break_end_at:
                return Response({"detail": "Break ya finalizado."}, status=status.HTTP_400_BAD_REQUEST)
            active_cycle.break_end_at = now
            active_cycle.save(update_fields=["break_end_at", "updated_at"])
            record.break_end = now
        elif self.action == "clock_out":
            if not has_active_session:
                return Response({"detail": "Debes marcar entrada primero."}, status=status.HTTP_400_BAD_REQUEST)
            if not active_cycle.break_start_at:
                return Response({"detail": "Debes salir y regresar de break antes de marcar salida."}, status=status.HTTP_400_BAD_REQUEST)
            if not active_cycle.break_end_at:
                return Response({"detail": "Debes regresar del break antes de marcar salida."}, status=status.HTTP_400_BAD_REQUEST)
            if active_cycle.break_start_at and not active_cycle.break_end_at:
                return Response({"detail": "Debes regresar del break antes de marcar salida."}, status=status.HTTP_400_BAD_REQUEST)
            active_cycle.clock_out_at = now
            active_cycle.save(update_fields=["clock_out_at", "updated_at"])
            record.clock_out = now
            record.check_out = now
            record.total_clock_outs = int(record.total_clock_outs or 0) + 1

        record.save()
        payload = build_attendance_state(record, employee)
        logger.info("attendance.action.end user_id=%s employee_id=%s action=%s payload=%s", request.user.id, employee.id, self.action, payload)
        return Response(AttendanceStateSerializer(payload).data)


class AttendanceClockInView(AttendanceActionView):
    action = "clock_in"


class AttendanceBreakStartView(AttendanceActionView):
    action = "break_start"


class AttendanceBreakEndView(AttendanceActionView):
    action = "break_end"


class AttendanceClockOutView(AttendanceActionView):
    action = "clock_out"


class AttendanceMeHistoryView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, *args, **kwargs):
        employee = _get_employee_for_user(request.user)
        if not employee:
            return Response({"attendance": None, "rows": [], "state": "NO_EMPLOYEE"}, status=status.HTTP_200_OK)
        start = parse_date(request.query_params.get("start") or "")
        end = parse_date(request.query_params.get("end") or "")
        queryset = AttendanceRecord.objects.filter(employee=employee).order_by("-date")
        if start:
            queryset = queryset.filter(date__gte=start)
        if end:
            queryset = queryset.filter(date__lte=end)
        rows = []
        for row in queryset[:200]:
            cycles = list(row.cycles.all().order_by("sequence", "id"))
            if not cycles and (row.clock_in or row.check_in):
                rows.append(
                    {
                        "date": row.date,
                        "clock_in": row.clock_in or row.check_in,
                        "break_start": row.break_start,
                        "break_end": row.break_end,
                        "clock_out": row.clock_out or row.check_out,
                    }
                )
                continue
            for cycle in cycles:
                rows.append(
                    {
                        "date": row.date,
                        "clock_in": cycle.clock_in_at,
                        "break_start": cycle.break_start_at,
                        "break_end": cycle.break_end_at,
                        "clock_out": cycle.clock_out_at,
                    }
                )
        return Response(
            {
                "attendance": {"employee_id": employee.id},
                "rows": AttendanceHistoryRowSerializer(rows, many=True).data,
                "state": "OK",
            },
            status=status.HTTP_200_OK,
        )


class AttendanceEmployeeHistoryView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request, employee_id: int, *args, **kwargs):
        employee = Employee.objects.filter(pk=employee_id).first()
        if not employee:
            return Response({"detail": "Empleado no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        start = parse_date(request.query_params.get("start") or "")
        end = parse_date(request.query_params.get("end") or "")
        queryset = AttendanceRecord.objects.filter(employee=employee).order_by("-date")
        if start:
            queryset = queryset.filter(date__gte=start)
        if end:
            queryset = queryset.filter(date__lte=end)
        rows = []
        for row in queryset[:365]:
            cycles = list(row.cycles.all().order_by("sequence", "id"))
            if not cycles and (row.clock_in or row.check_in):
                rows.append(
                    {
                        "date": row.date,
                        "clock_in": row.clock_in or row.check_in,
                        "break_start": row.break_start,
                        "break_end": row.break_end,
                        "clock_out": row.clock_out or row.check_out,
                    }
                )
                continue
            for cycle in cycles:
                rows.append(
                    {
                        "date": row.date,
                        "clock_in": cycle.clock_in_at,
                        "break_start": cycle.break_start_at,
                        "break_end": cycle.break_end_at,
                        "clock_out": cycle.clock_out_at,
                    }
                )
        return Response(AttendanceHistoryRowSerializer(rows, many=True).data)


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
