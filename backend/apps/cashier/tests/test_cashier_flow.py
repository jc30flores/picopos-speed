from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
import json
from rest_framework.test import APIClient

from apps.core.models import Branch
from apps.users.models import UserProfile
from apps.cashier.models import CashSession


class CashierFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(username='cash', password='pw')
        UserProfile.objects.create(user=user, role='cashier', is_active=True)
        Branch.objects.create(name='Main', code='MAIN')
        self.client.force_authenticate(user)

    def test_open_session_ok(self):
        res = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        self.assertEqual(res.status_code, 201)

    def test_create_expense_ok(self):
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        res = self.client.post('/api/cashier/transactions/', {'type': 'cash_out', 'amount': '5.00', 'description': 'Proveedor'}, format='json')
        self.assertEqual(res.status_code, 201)

    def test_close_and_ticket_pdf(self):
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        close = self.client.post('/api/cashier/session/close/', {'counted_cash_amount': '95.00'}, format='json')
        self.assertEqual(close.status_code, 200)
        session_id = close.data['session']['id']
        session = CashSession.objects.get(id=session_id)
        json.dumps(session.summary_snapshot)
        pdf = self.client.get(f'/api/cashier/sessions/{session_id}/ticket.pdf')
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')

    def test_close_without_open_session_returns_400(self):
        close = self.client.post('/api/cashier/session/close/', {'counted_cash_amount': '95.00'}, format='json')
        self.assertEqual(close.status_code, 400)
        self.assertIn('No hay caja abierta', str(close.data))

    def test_close_with_invalid_amount_returns_400(self):
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        close = self.client.post('/api/cashier/session/close/', {'counted_cash_amount': 'abc'}, format='json')
        self.assertEqual(close.status_code, 400)
        self.assertIn('Monto contado inválido', str(close.data))

    def test_open_drawer_mock_mode_returns_ok(self):
        with override_settings(CASH_DRAWER_ENABLED=True, CASH_DRAWER_MODE="mock"):
            res = self.client.post('/api/cashier/drawer/open/', {}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data.get("ok"), True)

    def test_open_drawer_without_config_returns_400(self):
        with override_settings(CASH_DRAWER_ENABLED=False, CASH_DRAWER_MODE="usb"):
            res = self.client.post('/api/cashier/drawer/open/', {}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data.get("ok"), False)
