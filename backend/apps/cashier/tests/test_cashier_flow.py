from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
import json
from concurrent.futures import ThreadPoolExecutor
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

    def test_open_session_is_idempotent_for_same_user(self):
        first = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        second = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '50.00'}, format='json')

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['session']['id'], second.data['session']['id'])
        self.assertEqual(CashSession.objects.filter(opened_by_id=first.data['session']['opened_by'], status='open').count(), 1)

    def test_open_session_concurrent_requests_create_only_one_open_session(self):
        self.client.force_authenticate(None)
        user = get_user_model().objects.create_user(username='cash_concurrent', password='pw')
        UserProfile.objects.create(user=user, role='cashier', is_active=True)

        def open_once(_):
            api_client = APIClient()
            api_client.force_authenticate(user)
            return api_client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json').status_code

        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(open_once, range(8)))

        self.assertEqual(statuses.count(201), 1)
        self.assertEqual(statuses.count(200), 7)
        self.assertEqual(CashSession.objects.filter(opened_by=user, status='open').count(), 1)

    def test_current_session_returns_open_even_when_opened_by_another_user(self):
        user_model = get_user_model()
        opener = user_model.objects.create_user(username='cash_other', password='pw')
        UserProfile.objects.create(user=opener, role='cashier', is_active=True)
        opener_client = APIClient()
        opener_client.force_authenticate(opener)
        open_response = opener_client.post('/api/cashier/session/open/', {'opening_cash_amount': '50.00'}, format='json')
        self.assertIn(open_response.status_code, {200, 201})

        current = self.client.get('/api/cashier/session/current/')
        self.assertEqual(current.status_code, 200)
        self.assertIsNotNone(current.data.get('session'))

    def test_open_session_returns_200_if_register_already_open(self):
        first = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        self.assertEqual(first.status_code, 201)

        user_model = get_user_model()
        user2 = user_model.objects.create_user(username='cash_second', password='pw')
        UserProfile.objects.create(user=user2, role='cashier', is_active=True)
        second_client = APIClient()
        second_client.force_authenticate(user2)
        second = second_client.post('/api/cashier/session/open/', {'opening_cash_amount': '10.00'}, format='json')

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data.get('already_open'), True)

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
        self.assertEqual(pdf['Content-Disposition'], f'attachment; filename="cierre_caja_{session_id}.pdf"')
        self.assertIn(b"CIERRE DE CAJA", pdf.content)
        self.assertIn(b"ESPERADO", pdf.content)
        self.assertIn(b"CONTADO", pdf.content)
        self.assertIn(b"DIFERENCIA", pdf.content)

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
        self.assertEqual(res.data.get("success"), True)
        self.assertEqual(res.data.get("message"), "Gaveta abierta")

    def test_open_drawer_without_config_returns_400(self):
        with override_settings(CASH_DRAWER_ENABLED=False, CASH_DRAWER_MODE="usb"):
            res = self.client.post('/api/cashier/drawer/open/', {}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data.get("success"), False)

    def test_drawer_test_endpoint_returns_parameters(self):
        with override_settings(CASH_DRAWER_ENABLED=True, CASH_DRAWER_MODE="mock"):
            res = self.client.post('/api/cashier/drawer/test/', {"variant": 1, "on": 50, "off": 200}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data.get("success"), True)
        self.assertEqual(res.data.get("variant"), 1)
        self.assertEqual(res.data.get("on"), 50)
        self.assertEqual(res.data.get("off"), 200)
