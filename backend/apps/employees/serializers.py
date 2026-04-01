from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from apps.core.models import Branch
from apps.employees.models import Employee, AttendanceRecord, Schedule
from apps.users.models import UserProfile
from apps.users.pin_utils import find_active_users_matching_pin, is_valid_pin_format


class EmployeeUserSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES)


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
        branch = self._get_branch(validated_data)
        if branch is not None:
            validated_data["branch"] = branch
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
        branch = self._get_branch(validated_data)
        if branch is not None:
            validated_data["branch"] = branch
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
        if not username:
            raise serializers.ValidationError({"user": {"username": "Username is required"}})
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
            profile, _ = UserProfile.objects.get_or_create(user=user, defaults={"role": role, "is_active": True})
            profile.role = role
            profile.is_active = employee.status == "active"
            profile.save(update_fields=["role", "is_active"])

    def _get_branch(self, validated_data):
        branch_name = validated_data.pop("branch_name_input", None)
        if branch_name is None:
            return None
        if not branch_name:
            return None
        branch = Branch.objects.filter(name=branch_name).first()
        if branch is None:
            raise serializers.ValidationError({"branch_name_input": "Branch not found"})
        return branch


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
