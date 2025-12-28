from rest_framework import generics
from apps.employees.models import Employee, Attendance
from apps.employees.serializers import EmployeeSerializer, AttendanceSerializer


class EmployeeListCreateView(generics.ListCreateAPIView):
    queryset = Employee.objects.select_related("branch").all()
    serializer_class = EmployeeSerializer


class AttendanceListView(generics.ListAPIView):
    queryset = Attendance.objects.select_related("employee").all()
    serializer_class = AttendanceSerializer
