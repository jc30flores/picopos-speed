from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from apps.core.models import Branch
from apps.employees.models import Employee, AttendanceRecord, AttendanceCycle, AttendanceBreak, Schedule
from apps.employees.attendance_utils import sum_cycle_break_seconds
from apps.users.models import UserProfile
from apps.users.pin_utils import find_active_users_matching_pin, is_valid_pin_format


class EmployeeUserSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES)

    def validate_role(self, value: str) -> str:
        if value == "superadmin":
            raise serializers.ValidationError("No se puede crear ni asignar superadmin desde la interfaz.")
        return value


class EmployeeSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    branch_name_input = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    create_user = serializers.BooleanField(write_only=True, required=False, default=False)
    user = EmployeeUserSerializer(write_only=True, required=False)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_role = serializers.SerializerMethodField()
    has_user = serializers.SerializerMethodField()
    days_worked = serializers.SerializerMethodField()
    hours_worked = serializers.SerializerMethodField()
    late_arrivals = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id",
            "full_name",
            "email",
            "phone",
            "role",
            "branch",
            "branch_name",
            "branch_name_input",
            "status",
            "is_deleted",
            "create_user",
            "user",
            "user_id",
            "user_username",
            "user_email",
            "user_role",
            "has_user",
            "created_at",
            "updated_at",
            "days_worked",
            "hours_worked",
            "late_arrivals",
        ]

    def validate_full_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Full name cannot be empty")
        return value.strip()

    def validate_role(self, value: str) -> str:
        roles = {choice[0] for choice in Employee.ROLE_CHOICES}
        if value not in roles:
            raise serializers.ValidationError("Invalid role")
        return value

    def validate_status(self, value: str) -> str:
        statuses = {choice[0] for choice in Employee.STATUS_CHOICES}
        if value not in statuses:
            raise serializers.ValidationError("Invalid status")
        return value

    def get_days_worked(self, obj: Employee) -> int:
        month_start, month_end = self._current_month_range()
        return obj.attendance_records.filter(date__range=(month_start, month_end)).count()

    def get_user_role(self, obj: Employee) -> str | None:
        if not obj.user:
            return None
        profile = UserProfile.objects.filter(user=obj.user).first()
        return profile.role if profile else None

    def get_has_user(self, obj: Employee) -> bool:
        return bool(obj.user_id)

    def get_hours_worked(self, obj: Employee) -> Decimal:
        month_start, month_end = self._current_month_range()
        total_minutes = 0
        records = obj.attendance_records.filter(date__range=(month_start, month_end))
        for record in records:
            if record.check_in and record.check_out:
                delta = record.check_out - record.check_in
                total_minutes += int(delta.total_seconds() // 60)
        return (Decimal(total_minutes) / Decimal("60")).quantize(Decimal("0.01"))

    def get_late_arrivals(self, obj: Employee) -> int:
        month_start, month_end = self._current_month_range()
        return obj.attendance_records.filter(
            date__range=(month_start, month_end),
            minutes_late__gt=0,
        ).count()

    def _current_month_range(self):
        today = timezone.localdate()
        month_start = today.replace(day=1)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        month_end = next_month - timedelta(days=1)
        return month_start, month_end

    @transaction.atomic
    def create(self, validated_data):
        validated_data["branch"] = self._get_branch(validated_data, current_branch=validated_data.get("branch"))
        create_user = validated_data.pop("create_user", False)
        user_data = validated_data.pop("user", None)
        employee = super().create(validated_data)
        if create_user:
            if not user_data:
                raise serializers.ValidationError({"user": "User payload is required"})
            employee.user = self._create_user(employee, user_data)
            employee.save(update_fields=["user"])
        return employee

    @transaction.atomic
    def update(self, instance, validated_data):
        validated_data["branch"] = self._get_branch(validated_data, current_branch=instance.branch)
        create_user = validated_data.pop("create_user", False)
        user_data = validated_data.pop("user", None)
        employee = super().update(instance, validated_data)
        if employee.user and "status" in validated_data:
            profile, _ = UserProfile.objects.get_or_create(
                user=employee.user,
                defaults={"role": "cashier", "is_active": employee.status == "active"},
            )
            profile.is_active = employee.status == "active"
            profile.save(update_fields=["is_active"])
        if create_user and not employee.user:
            if not user_data:
                raise serializers.ValidationError({"user": "User payload is required"})
            employee.user = self._create_user(employee, user_data)
            employee.save(update_fields=["user"])
        elif user_data and employee.user:
            self._update_user(employee, user_data)
        return employee

    def _create_user(self, employee: Employee, user_data: dict):
        user_model = get_user_model()
        username = user_data.get("username")
        email = user_data.get("email") or ""
        password = user_data.get("password")
        role = user_data.get("role")
        if role == "superadmin":
            raise serializers.ValidationError({"user": {"role": "No se puede crear superadmin desde la interfaz."}})
        if not username:
            raise serializers.ValidationError({"user": {"username": "Username is required"}})
        if not role:
            raise serializers.ValidationError({"user": {"role": "Role is required"}})
        if user_model.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError({"user": {"username": "Username already exists"}})
        if email and user_model.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({"user": {"email": "Email already exists"}})
        if not is_valid_pin_format(password):
            raise serializers.ValidationError({"user": {"password": "El PIN debe tener exactamente 6 dígitos numéricos"}})
        if find_active_users_matching_pin(password):
            raise serializers.ValidationError({"user": {"password": "PIN ya usado por otro usuario"}})
        user = user_model.objects.create(username=username, email=email)
        user.set_password(password)
        user.save(update_fields=["password"])
        UserProfile.objects.update_or_create(
            user=user,
            defaults={"role": role, "is_active": employee.status == "active"},
        )
        return user

    def _update_user(self, employee: Employee, user_data: dict) -> None:
        user = employee.user
        if not user:
            return
        user_model = get_user_model()
        username = user_data.get("username")
        email = user_data.get("email")
        password = user_data.get("password")
        role = user_data.get("role")
        if username and user_model.objects.filter(username__iexact=username).exclude(id=user.id).exists():
            raise serializers.ValidationError({"user": {"username": "Username already exists"}})
        if email and user_model.objects.filter(email__iexact=email).exclude(id=user.id).exists():
            raise serializers.ValidationError({"user": {"email": "Email already exists"}})
        if username is not None:
            user.username = username
        if email is not None:
            user.email = email or ""
        if password:
            if not is_valid_pin_format(password):
                raise serializers.ValidationError({"user": {"password": "El PIN debe tener exactamente 6 dígitos numéricos"}})
            if find_active_users_matching_pin(password, exclude_user_id=user.id):
                raise serializers.ValidationError({"user": {"password": "PIN ya usado por otro usuario"}})
            user.set_password(password)
        user.save()
        if role:
            if role == "superadmin":
                raise serializers.ValidationError({"user": {"role": "No se puede asignar superadmin desde la interfaz."}})
            profile, _ = UserProfile.objects.get_or_create(user=user, defaults={"role": role, "is_active": True})
            profile.role = role
            profile.is_active = employee.status == "active"
            profile.save(update_fields=["role", "is_active"])

    def _get_branch(self, validated_data, current_branch=None):
        branch_name = validated_data.pop("branch_name_input", None)
        if branch_name:
            branch = Branch.objects.filter(name=branch_name).first()
            if branch is None:
                raise serializers.ValidationError({"branch_name_input": "Branch not found"})
            return branch
        if current_branch is not None:
            return current_branch
        return Branch.objects.order_by("id").first()


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    role = serializers.CharField(source="employee.role", read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "employee",
            "employee_name",
            "role",
            "date",
            "check_in",
            "check_out",
            "minutes_late",
            "notes",
            "created_at",
        ]
        validators = [
            UniqueTogetherValidator(
                queryset=AttendanceRecord.objects.all(),
                fields=["employee", "date"],
                message="Attendance record for this employee and date already exists.",
            )
        ]

    def validate_minutes_late(self, value: int) -> int:
        if value < 0:
            raise serializers.ValidationError("Minutes late cannot be negative")
        return value

    def validate(self, attrs):
        check_in = attrs.get("check_in")
        check_out = attrs.get("check_out")
        if check_in and check_out and check_out < check_in:
            raise serializers.ValidationError("Check out cannot be before check in")
        return attrs


class ScheduleSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = Schedule
        fields = [
            "id",
            "employee",
            "employee_name",
            "schedule_type",
            "day_of_week",
            "start_time",
            "end_time",
            "break_minutes",
            "allows_overtime",
            "is_active",
            "created_at",
        ]

    def validate_schedule_type(self, value: str) -> str:
        choices = {choice[0] for choice in Schedule.TYPE_CHOICES}
        if value not in choices:
            raise serializers.ValidationError("Invalid schedule type")
        return value

    def validate_break_minutes(self, value: int) -> int:
        if value < 0:
            raise serializers.ValidationError("Break minutes cannot be negative")
        return value

    def validate(self, attrs):
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        day_of_week = attrs.get("day_of_week", getattr(self.instance, "day_of_week", None))
        if day_of_week is not None and day_of_week not in range(0, 7):
            raise serializers.ValidationError("Day of week must be between 0 and 6")
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError("End time must be after start time")

        employee = attrs.get("employee") or self.instance.employee
        if employee and day_of_week is not None and start_time and end_time:
            overlaps = Schedule.objects.filter(employee=employee, day_of_week=day_of_week)
            if self.instance:
                overlaps = overlaps.exclude(id=self.instance.id)
            overlaps = overlaps.filter(start_time__lt=end_time, end_time__gt=start_time)
            if overlaps.exists():
                raise serializers.ValidationError("Schedule overlaps with an existing entry")
        return attrs


class AttendanceStateSerializer(serializers.Serializer):
    employee = serializers.DictField()
    date = serializers.DateField()
    clock_in = serializers.DateTimeField(allow_null=True)
    break_start = serializers.DateTimeField(allow_null=True)
    break_end = serializers.DateTimeField(allow_null=True)
    clock_out = serializers.DateTimeField(allow_null=True)
    has_active_session = serializers.BooleanField()
    latest_event = serializers.ChoiceField(choices=["CLOCK_IN", "CLOCK_OUT", "NONE"])
    last_clock_in = serializers.DateTimeField(allow_null=True)
    last_clock_out = serializers.DateTimeField(allow_null=True)
    total_entries_today = serializers.IntegerField()
    total_exits_today = serializers.IntegerField()
    can_clock_in = serializers.BooleanField()
    can_break_start = serializers.BooleanField()
    can_break_end = serializers.BooleanField()
    can_clock_out = serializers.BooleanField()
    state = serializers.ChoiceField(choices=["OFF_SHIFT", "WORKING", "ON_BREAK"])
    access_allowed = serializers.BooleanField()
    active_cycle = serializers.DictField()
    cycles_today = serializers.ListField(child=serializers.DictField())


class AttendanceHistoryRowSerializer(serializers.Serializer):
    date = serializers.DateField()
    clock_in = serializers.DateTimeField(allow_null=True)
    break_start = serializers.DateTimeField(allow_null=True)
    break_end = serializers.DateTimeField(allow_null=True)
    clock_out = serializers.DateTimeField(allow_null=True)


def _break_minutes_for_cycle(cycle: AttendanceCycle) -> tuple[float, int, list[dict], bool]:
    now = timezone.now()
    rows = []
    opened = False
    breaks = list(cycle.breaks.all()) if getattr(cycle, "pk", None) else []
    if breaks:
        for br in breaks:
            end = br.end_at or now
            seconds = max(0, int((end - br.start_at).total_seconds()))
            rows.append({"start_at": br.start_at, "end_at": br.end_at, "minutes": seconds / 60, "seconds": seconds})
            if br.end_at is None:
                opened = True
    elif cycle.break_start_at:
        seconds = sum_cycle_break_seconds(cycle, include_open=True, now=now)
        rows.append({"start_at": cycle.break_start_at, "end_at": cycle.break_end_at, "minutes": seconds / 60, "seconds": seconds})
        opened = cycle.break_end_at is None
    total_seconds = sum_cycle_break_seconds(cycle, include_open=True, now=now)
    return total_seconds / 60, total_seconds, rows, opened


def build_attendance_state(record: AttendanceRecord | None, employee: Employee) -> dict:
    today_local = timezone.localdate()
    record_date = today_local
    cycles_qs: list[AttendanceCycle] = []
    if record is not None:
        record_date = record.date
        if record.pk:
            cycles_qs = list(record.cycles.prefetch_related("breaks").all().order_by("sequence", "id"))
    if record is not None and not cycles_qs and (record.clock_in or record.check_in):
        cycles_qs = [AttendanceCycle(attendance_record=record, sequence=1, clock_in_at=record.clock_in or record.check_in, break_start_at=record.break_start, break_end_at=record.break_end, clock_out_at=record.clock_out or record.check_out)]

    active_cycle = (
        AttendanceCycle.objects.filter(attendance_record__employee=employee, clock_out_at__isnull=True)
        .select_related("attendance_record")
        .prefetch_related("breaks")
        .order_by("-clock_in_at", "-id")
        .first()
    ) or next((cycle for cycle in reversed(cycles_qs) if cycle.clock_out_at is None), None)
    current_cycle = active_cycle or (cycles_qs[-1] if cycles_qs else None)
    has_active_session = active_cycle is not None
    break_minutes = 0
    break_seconds = 0
    current_break_started_at = None
    if current_cycle:
        break_minutes, break_seconds, _, opened = _break_minutes_for_cycle(current_cycle)
        if opened:
            b = list(current_cycle.breaks.all()) if getattr(current_cycle, "pk", None) else []
            current_break_started_at = (b[-1].start_at if b else current_cycle.break_start_at)

    if not has_active_session:
        state = "OFF_SHIFT"
    elif current_break_started_at:
        state = "ON_BREAK"
    else:
        state = "WORKING"

    cycle_rows = []
    for cycle in cycles_qs:
        br_minutes, br_seconds, br_rows, opened = _break_minutes_for_cycle(cycle)
        shift_minutes = max(0, int(((cycle.clock_out_at or timezone.now()) - cycle.clock_in_at).total_seconds() // 60)) if cycle.clock_in_at else 0
        cycle_rows.append({"sequence": cycle.sequence, "clock_in_at": cycle.clock_in_at, "clock_out_at": cycle.clock_out_at, "break_minutes": br_minutes, "break_seconds": br_seconds, "net_minutes": max(0, shift_minutes-br_minutes), "breaks_count": len(br_rows), "breaks": br_rows, "current_break_started_at": br_rows[-1]["start_at"] if opened and br_rows else None})

    started_prev = bool(current_cycle and timezone.localtime(current_cycle.clock_in_at).date() < today_local)
    active_cycle_payload = next((r for r in cycle_rows if r["clock_out_at"] is None), None) or {}
    if active_cycle and not active_cycle_payload:
        br_minutes, br_seconds, br_rows, opened = _break_minutes_for_cycle(active_cycle)
        active_cycle_payload = {
            "id": active_cycle.id,
            "sequence": active_cycle.sequence,
            "clock_in_at": active_cycle.clock_in_at,
            "clock_out_at": active_cycle.clock_out_at,
            "break_minutes": br_minutes,
            "break_seconds": br_seconds,
            "breaks_count": len(br_rows),
            "breaks": br_rows,
            "current_break_started_at": br_rows[-1]["start_at"] if opened and br_rows else None,
        }
    active_cycle_payload = {**active_cycle_payload, "break_seconds": break_seconds, "break_minutes": break_minutes, "started_on_previous_day": started_prev}
    return {"employee": {"id": employee.id, "name": employee.full_name, "role": employee.role}, "date": record_date, "clock_in": current_cycle.clock_in_at if current_cycle else None, "break_start": current_break_started_at, "break_end": None if current_break_started_at else (record.break_end if record else None), "clock_out": current_cycle.clock_out_at if current_cycle else None, "has_active_session": has_active_session, "latest_event": "CLOCK_IN" if state in {"WORKING", "ON_BREAK"} else "CLOCK_OUT", "last_clock_in": current_cycle.clock_in_at if current_cycle else None, "last_clock_out": current_cycle.clock_out_at if current_cycle else None, "total_entries_today": len(cycles_qs), "total_exits_today": len([c for c in cycles_qs if c.clock_out_at is not None]), "can_clock_in": state=="OFF_SHIFT", "can_break_start": state=="WORKING", "can_break_end": state=="ON_BREAK", "can_clock_out": state=="WORKING", "state": state, "access_allowed": state=="WORKING", "active_cycle": active_cycle_payload, "cycles_today": cycle_rows}
