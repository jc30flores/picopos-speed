from datetime import datetime
from django.contrib.auth import get_user_model
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from apps.employees.models import Employee, AttendanceRecord, AttendanceCycle
from apps.users.models import UserProfile

@override_settings(TIME_ZONE='America/El_Salvador', USE_TZ=True)
class EmployeeHoursCardTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin = get_user_model().objects.create_user(username='admin_hours', password='pw')
        UserProfile.objects.create(user=admin, role='admin', is_active=True)
        self.client.force_authenticate(admin)
        self.employee = Employee.objects.create(full_name='Ana', role='cashier', status='active')

    def _cycle(self, d, hour):
        rec, _ = AttendanceRecord.objects.get_or_create(employee=self.employee, date=d)
        return AttendanceCycle.objects.create(attendance_record=rec, sequence=rec.cycles.count()+1, clock_in_at=timezone.make_aware(datetime(d.year,d.month,d.day,hour,0)), clock_out_at=timezone.make_aware(datetime(d.year,d.month,d.day,hour+8,0)))

    def test_filter_excludes_april_30(self):
        self._cycle(datetime(2026,4,30).date(), 8)
        self._cycle(datetime(2026,5,1).date(), 8)
        resp = self.client.get(f'/api/reports/employee-hours/{self.employee.id}/?date_from=2026-05-01&date_to=2026-05-31')
        self.assertEqual(resp.status_code, 200)
        may_days = [d['date'] for d in resp.data['days']]
        self.assertNotIn('2026-04-30', may_days)
        self.assertIn('2026-05-01', may_days)

    def test_days_complete_in_range(self):
        resp = self.client.get(f'/api/reports/employee-hours/{self.employee.id}/?date_from=2026-05-01&date_to=2026-05-03')
        self.assertEqual([d['date'] for d in resp.data['days']], ['2026-05-01', '2026-05-02', '2026-05-03'])

    def test_create_and_patch_cycle(self):
        post = self.client.post('/api/reports/employee-hours/cycles/', {'employee_id': self.employee.id, 'date': '2026-05-05', 'clock_in_time': '08:00', 'shift_seconds': 28800, 'break_seconds': 1800, 'reason': 'Registro manual'}, format='json')
        self.assertEqual(post.status_code, 200)
        cid = post.data['cycle']['id']
        patch = self.client.patch(f'/api/reports/employee-hours/cycles/{cid}/', {'date':'2026-05-05','clock_in_time':'08:00','clock_out_time':'16:00','break_seconds':1800,'reason':'Corrección'}, format='json')
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(patch.data['cycle']['shift_seconds'], 28800)
        self.assertEqual(patch.data['cycle']['net_seconds'], 27000)

    def test_break_gt_shift_is_400(self):
        resp = self.client.post('/api/reports/employee-hours/cycles/', {'employee_id': self.employee.id, 'date': '2026-05-05', 'clock_in_time': '08:00', 'shift_seconds': 3600, 'break_seconds': 7200}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_non_admin_403(self):
        cashier = get_user_model().objects.create_user(username='cashier', password='pw')
        UserProfile.objects.create(user=cashier, role='cashier', is_active=True)
        self.client.force_authenticate(cashier)
        resp = self.client.post('/api/reports/employee-hours/cycles/', {'employee_id': self.employee.id, 'date': '2026-05-05', 'clock_in_time': '08:00', 'shift_seconds': 3600, 'break_seconds': 60}, format='json')
        self.assertEqual(resp.status_code, 403)


    @patch("apps.reports.views.timezone.localdate")
    def test_days_do_not_include_future(self, mock_localdate):
        mock_localdate.return_value = datetime(2026,5,4).date()
        resp = self.client.get(f'/api/reports/employee-hours/{self.employee.id}/?date_from=2026-05-01&date_to=2026-05-31')
        self.assertEqual([d['date'] for d in resp.data['days']], ['2026-05-01','2026-05-02','2026-05-03','2026-05-04'])

    @patch("apps.reports.views.timezone.localdate")
    def test_block_future_manual_cycle(self, mock_localdate):
        mock_localdate.return_value = datetime(2026,5,4).date()
        resp = self.client.post('/api/reports/employee-hours/cycles/', {'employee_id': self.employee.id, 'date': '2026-05-20', 'clock_in_time': '08:00', 'shift_seconds': 3600, 'break_seconds': 60}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_block_manual_when_open_cycle_exists(self):
        rec = AttendanceRecord.objects.create(employee=self.employee, date=datetime(2026,5,3).date())
        AttendanceCycle.objects.create(attendance_record=rec, sequence=1, clock_in_at=timezone.make_aware(datetime(2026,5,3,23,50)))
        resp = self.client.post('/api/reports/employee-hours/cycles/', {'employee_id': self.employee.id, 'date': '2026-05-04', 'clock_in_time': '08:00', 'shift_seconds': 3600, 'break_seconds': 60}, format='json')
        self.assertEqual(resp.status_code, 400)
