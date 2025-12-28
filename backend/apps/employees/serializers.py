from rest_framework import serializers
from apps.employees.models import Employee, Attendance


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            "id",
            "name",
            "email",
            "role",
            "phone",
            "branch_id",
            "status",
            "days_worked",
            "hours_worked",
            "late_arrivals",
        ]


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.name", read_only=True)
    role = serializers.CharField(source="employee.role", read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id",
            "employee_id",
            "employee_name",
            "role",
            "date",
            "entry_time",
            "exit_time",
            "hours_worked",
            "notes",
        ]
