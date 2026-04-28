from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
import json
from concurrent.futures import ThreadPoolExecutor
from rest_framework.test import APIClient

from apps.core.models import Branch, FeatureFlag
from apps.users.models import UserProfile
from apps.cashier.models import CashSession, Register
from apps.orders.models import Order
from apps.cashier.serializers import CashTransactionSerializer
from apps.cashier.printing import build_end_of_day_ticket_pdf
from apps.dte.models import DTEBranchConfig
from apps.core.models import ServiceType


class CashierFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        user = user_model.objects.create_user(username='cash', password='pw')
        self.admin = user_model.objects.create_user(username='admin_cash', password='pw')
        self.manager = user_model.objects.create_user(username='manager_cash', password='pw')
        UserProfile.objects.create(user=user, role='cashier', is_active=True)
        UserProfile.objects.create(user=self.admin, role='admin', is_active=True)
        UserProfile.objects.create(user=self.manager, role='manager', is_active=True)
        Branch.objects.create(name='Main', code='MAIN')
        self.service_type = ServiceType.objects.create(key="dine-in", label="En local")
        self.client.force_authenticate(user)

    def test_open_session_ok(self):
        res = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data.get('has_open_session'), True)
        self.assertIsNone(res.data.get('session', {}).get('opening_amount'))

    def test_open_session_rejects_second_open_while_active_session_exists(self):
        first = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        second = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '50.00'}, format='json')

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data.get("code"), "CASH_SESSION_ALREADY_OPEN")
        self.assertEqual(CashSession.objects.filter(opened_by_id=first.data['session']['opened_by'], status='open').count(), 1)

    def test_open_close_open_again_same_day_is_allowed(self):
        first_open = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        self.assertEqual(first_open.status_code, 201)

        first_close = self.client.post(
            '/api/cashier/session/close/',
            {'total_billetes': '80.00', 'total_monedas': '20.00', 'total_contado': '100.00'},
            format='json',
        )
        self.assertEqual(first_close.status_code, 200)

        second_open = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '20.00'}, format='json')
        self.assertEqual(second_open.status_code, 201)
        self.assertNotEqual(first_open.data['session']['id'], second_open.data['session']['id'])

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
        self.assertEqual(statuses.count(409), 7)
        self.assertEqual(CashSession.objects.filter(opened_by=user, status='open').count(), 1)

    def test_current_session_hides_sensitive_summary_for_cashier(self):
        user_model = get_user_model()
        opener = user_model.objects.create_user(username='cash_other', password='pw')
        UserProfile.objects.create(user=opener, role='cashier', is_active=True)
        opener_client = APIClient()
        opener_client.force_authenticate(opener)
        open_response = opener_client.post('/api/cashier/session/open/', {'opening_cash_amount': '50.00'}, format='json')
        self.assertIn(open_response.status_code, {200, 201})

        current = self.client.get('/api/cashier/session/current/')
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.data.get('has_open_session'), True)
        self.assertIsNotNone(current.data.get('session'))
        self.assertIsNone(current.data.get('summary'))
        self.assertIsNone(current.data.get('session', {}).get('opening_amount'))

    def test_current_session_returns_sensitive_summary_for_admin(self):
        admin_client = APIClient()
        admin_client.force_authenticate(self.admin)
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '50.00'}, format='json')
        current = admin_client.get('/api/cashier/session/current/')
        self.assertEqual(current.status_code, 200)
        self.assertIsNotNone(current.data.get('summary'))
        self.assertIsNotNone(current.data.get('session', {}).get('opening_amount'))

    def test_current_session_returns_has_open_session_false_when_none(self):
        current = self.client.get('/api/cashier/session/current/')
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.data.get('has_open_session'), False)
        self.assertIsNone(current.data.get('session'))

    def test_open_session_returns_409_if_register_already_open(self):
        first = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        self.assertEqual(first.status_code, 201)

        user_model = get_user_model()
        user2 = user_model.objects.create_user(username='cash_second', password='pw')
        UserProfile.objects.create(user=user2, role='cashier', is_active=True)
        second_client = APIClient()
        second_client.force_authenticate(user2)
        second = second_client.post('/api/cashier/session/open/', {'opening_cash_amount': '10.00'}, format='json')

        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data.get('code'), "CASH_SESSION_ALREADY_OPEN")

    def test_close_session_blocked_when_pending_orders_exist(self):
        open_res = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        self.assertEqual(open_res.status_code, 201)
        session_branch_id = open_res.data["session"]["branch"]
        Order.objects.create(
            order_number=999,
            branch_id=session_branch_id,
            service_type=self.service_type,
            status="waiting_payment",
            payment_status="unpaid",
            subtotal="5.00",
            tax="0.00",
            total="5.00",
            is_pending=True,
            pending_state="pending_payment",
        )
        close = self.client.post('/api/cashier/session/close/', {'total_billetes': '95.00', 'total_monedas': '5.00', 'total_contado': '100.00'}, format='json')
        self.assertEqual(close.status_code, 409)
        self.assertEqual(close.data.get("code"), "PENDING_ORDERS_BLOCK_CASH_CLOSE")

    def test_create_expense_ok(self):
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        res = self.client.post('/api/cashier/transactions/', {'type': 'cash_out', 'amount': '5.00', 'description': 'Proveedor'}, format='json')
        self.assertEqual(res.status_code, 201)

    def test_close_session_allows_pending_orders_when_feature_flag_enabled(self):
        FeatureFlag.objects.create(
            key="FF_CASH_CLOSE_ALLOW_PENDING_ORDERS",
            label="Cierre de caja con órdenes pendientes",
            is_enabled=True,
        )
        open_res = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        self.assertEqual(open_res.status_code, 201)
        session_branch_id = open_res.data["session"]["branch"]
        Order.objects.create(
            order_number=1001,
            branch_id=session_branch_id,
            service_type=self.service_type,
            status="waiting_payment",
            payment_status="unpaid",
            subtotal="10.00",
            tax="0.00",
            total="10.00",
            is_pending=True,
            pending_state="pending_payment",
        )

        close = self.client.post('/api/cashier/session/close/', {'total_billetes': '90.00', 'total_monedas': '10.00', 'total_contado': '100.00'}, format='json')
        self.assertEqual(close.status_code, 200)

    def test_transactions_include_all_contains_cash_in_when_requested(self):
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        self.client.post('/api/cashier/transactions/', {'type': 'cash_in', 'amount': '3.00', 'description': 'Ajuste entrada'}, format='json')

        admin_client = APIClient()
        admin_client.force_authenticate(self.admin)

        default_res = admin_client.get('/api/cashier/transactions/')
        self.assertEqual(default_res.status_code, 200)
        self.assertEqual(default_res.data, [])

        all_res = admin_client.get('/api/cashier/transactions/?include=all')
        self.assertEqual(all_res.status_code, 200)
        self.assertEqual(len(all_res.data), 1)
        self.assertEqual(all_res.data[0]["type"], "cash_in")

    def test_transactions_include_all_without_open_session_returns_200(self):
        admin_client = APIClient()
        admin_client.force_authenticate(self.admin)

        response = admin_client.get('/api/cashier/transactions/?include=all')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_cash_transaction_serializer_accepts_payment_id_without_assertion(self):
        payload = {
            "id": 1,
            "session": 1,
            "type": "cash_in",
            "display_type": "Pago",
            "impacts_cash": True,
            "amount": "10.00",
            "description": "Prueba",
            "payment_id": 10,
            "refund_id": None,
            "order_id": 20,
            "created_by": self.admin.id,
            "created_by_username": self.admin.username,
            "created_at": timezone.now(),
        }

        serializer = CashTransactionSerializer(payload)
        data = serializer.data
        self.assertEqual(data["payment_id"], 10)
        self.assertIsNone(data["refund_id"])

    def test_close_and_ticket_pdf(self):
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        close = self.client.post(
            '/api/cashier/session/close/',
            {
                'counted_cash_amount': '95.00',
                'total_bills': '80.00',
                'total_coins': '15.00',
                'total_pos_tarjetas': '42.50',
                'total_pedidos_ya': '18.25',
            },
            format='json',
        )
        self.assertEqual(close.status_code, 200)
        session_id = close.data['session']['id']
        session = CashSession.objects.get(id=session_id)
        json.dumps(session.summary_snapshot)
        self.assertEqual(str(session.closing_total_bills), "80.00")
        self.assertEqual(str(session.closing_total_coins), "15.00")
        self.assertEqual(str(session.closing_total_pos_cards), "42.50")
        self.assertEqual(str(session.closing_total_pedidos_ya), "18.25")
        self.assertEqual(session.summary_snapshot.get("counted_pos_cards"), "42.50")
        self.assertEqual(session.summary_snapshot.get("counted_pedidos_ya"), "18.25")
        pdf = self.client.get(f'/api/cashier/sessions/{session_id}/ticket.pdf')
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertRegex(pdf['Content-Disposition'], r'attachment; filename=\"end_of_day_\\d{4}-\\d{2}-\\d{2}_\\d{2}-\\d{2}-\\d{2}\\.pdf\"')
        self.assertIn(b"CIERRE DE CAJA", pdf.content)
        self.assertIn(b"ESPERADO", pdf.content)
        self.assertIn(b"CONTADO", pdf.content)
        self.assertIn(b"DIFERENCIA", pdf.content)


    def test_ticket_pdf_regression_no_missing_branch_helper_nameerror(self):
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        close = self.client.post('/api/cashier/session/close/', {'total_billetes': '95.00', 'total_monedas': '5.00', 'total_contado': '100.00'}, format='json')
        self.assertEqual(close.status_code, 200)
        session_id = close.data['session']['id']

        response = self.client.get(f'/api/cashier/sessions/{session_id}/ticket.pdf')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_ticket_pdf_ignores_accept_header_html_and_returns_pdf(self):
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        close = self.client.post('/api/cashier/session/close/', {'total_billetes': '90.00', 'total_monedas': '5.00', 'total_contado': '95.00'}, format='json')
        session_id = close.data['session']['id']
        pdf = self.client.get(
            f'/api/cashier/sessions/{session_id}/ticket.pdf',
            HTTP_ACCEPT='text/html',
        )
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertTrue(pdf.content.startswith(b'%PDF'))

    @override_settings(BRANCH_ID=999999)
    def test_ticket_pdf_endpoint_falls_back_and_returns_valid_pdf_headers(self):
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        close = self.client.post('/api/cashier/session/close/', {'total_billetes': '95.00', 'total_monedas': '5.00', 'total_contado': '100.00'}, format='json')
        session_id = close.data['session']['id']
        pdf = self.client.get(f'/api/cashier/sessions/{session_id}/ticket.pdf')
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertTrue(pdf.content.startswith(b'%PDF'))

    def test_ticket_pdf_uses_branch_from_env_when_available(self):
        branch_monaco = Branch.objects.create(name='Plaza Monaco', code='PLAZA_MONACO')
        DTEBranchConfig.objects.create(branch=branch_monaco, is_active=True, direccion_complemento='Avenida Monaco, San Salvador')
        register = Register.objects.create(name='CAJA M', station_name='POS M', branch=branch_monaco, is_active=True)
        session = CashSession.objects.create(register=register, opened_by=get_user_model().objects.get(username='cash'), status='closed', opening_cash='10.00')
        with override_settings(BRANCH_ID=branch_monaco.id):
            pdf_bytes = build_end_of_day_ticket_pdf(session.id)
        pdf_upper = pdf_bytes.upper()
        self.assertIn(b"PLAZA MONACO", pdf_upper)
        self.assertIn(b"AVENIDA MONACO", pdf_upper)
        for label in [b"EFECTIVO", b"TARJETA", b"TRANSFERENCIA", b"PAYPAL", b"PEDIDOS YA"]:
            self.assertIn(label, pdf_upper)


    def test_ticket_pdf_supports_zero_difference_and_empty_notes(self):
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        close = self.client.post(
            '/api/cashier/session/close/',
            {'total_billetes': '70.00', 'total_monedas': '30.00', 'total_contado': '100.00', 'notes': ''},
            format='json',
        )
        self.assertEqual(close.status_code, 200)
        session_id = close.data['session']['id']

        pdf = self.client.get(f'/api/cashier/sessions/{session_id}/ticket.pdf')
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        self.assertGreater(len(pdf.content), 200)

    def test_ticket_pdf_supports_positive_difference(self):
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        close = self.client.post(
            '/api/cashier/session/close/',
            {'total_billetes': '90.00', 'total_monedas': '20.00', 'total_contado': '110.00'},
            format='json',
        )
        self.assertEqual(close.status_code, 200)
        session_id = close.data['session']['id']

        pdf = self.client.get(f'/api/cashier/sessions/{session_id}/ticket.pdf')
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))

    def test_ticket_pdf_handles_legacy_snapshot_currency_strings(self):
        open_response = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        self.assertEqual(open_response.status_code, 201)
        session_id = open_response.data['session']['id']
        session = CashSession.objects.get(id=session_id)
        session.status = 'closed'
        session.closed_by = get_user_model().objects.get(username='cash')
        session.closed_at = timezone.now()
        session.summary_snapshot = {
            'opening_cash': '$100.00',
            'expected_cash_in_drawer': '$95.00',
            'counted_cash': '$95.00',
            'difference': '$0.00',
        }
        session.save(update_fields=['status', 'closed_by', 'closed_at', 'summary_snapshot'])

        pdf = self.client.get(f'/api/cashier/sessions/{session_id}/ticket.pdf')
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertTrue(pdf.content.startswith(b'%PDF'))

    def test_ticket_pdf_returns_404_for_missing_session(self):
        response = self.client.get('/api/cashier/sessions/999999/ticket.pdf')
        self.assertEqual(response.status_code, 404)

    def test_ticket_pdf_returns_403_for_forbidden_role(self):
        user_model = get_user_model()
        worker = user_model.objects.create_user(username='worker_cash', password='pw')
        UserProfile.objects.create(user=worker, role='worker', is_active=True)

        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        close = self.client.post('/api/cashier/session/close/', {'total_billetes': '95.00', 'total_monedas': '5.00', 'total_contado': '100.00'}, format='json')
        session_id = close.data['session']['id']

        worker_client = APIClient()
        worker_client.force_authenticate(worker)
        response = worker_client.get(f'/api/cashier/sessions/{session_id}/ticket.pdf')
        self.assertEqual(response.status_code, 403)

    def test_manager_can_close_session(self):
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        manager_client = APIClient()
        manager_client.force_authenticate(self.manager)
        close = manager_client.post('/api/cashier/session/close/', {'counted_cash_amount': '95.00', 'total_bills': '90.00', 'total_coins': '5.00'}, format='json')
        self.assertEqual(close.status_code, 200)

    def test_close_without_open_session_returns_400(self):
        close = self.client.post('/api/cashier/session/close/', {'total_billetes': '90.00', 'total_monedas': '5.00', 'total_contado': '95.00'}, format='json')
        self.assertEqual(close.status_code, 400)
        self.assertIn('No hay caja abierta', str(close.data))

    def test_close_with_invalid_amount_returns_400(self):
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        close = self.client.post('/api/cashier/session/close/', {'total_billetes': '80.00', 'total_monedas': '20.00', 'total_contado': 'abc'}, format='json')
        self.assertEqual(close.status_code, 400)
        self.assertIn('total_contado', str(close.data.get('errors', {})))

    def test_close_requires_bill_and_coin_fields(self):
        self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        close = self.client.post('/api/cashier/session/close/', {'total_contado': '95.00'}, format='json')
        self.assertEqual(close.status_code, 400)
        self.assertIn('total_billetes', str(close.data.get('errors', {})))
        self.assertIn('total_monedas', str(close.data.get('errors', {})))

    def test_close_uses_same_branch_scope_as_current_session(self):
        branch_secondary = Branch.objects.create(name='Secondary', code='SECONDARY')
        Register.objects.create(name='CAJA 2', station_name='POS 2', branch=branch_secondary, is_active=True)
        open_response = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '120.00', 'branch_id': branch_secondary.id}, format='json')
        self.assertEqual(open_response.status_code, 201)
        session_id = open_response.data['session']['id']

        current = self.client.get(f'/api/cashier/session/current/?branch_id={branch_secondary.id}')
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.data['session']['id'], session_id)

        close = self.client.post(
            '/api/cashier/session/close/',
            {'total_billetes': '100.00', 'total_monedas': '20.00', 'total_contado': '120.00', 'branch_id': branch_secondary.id},
            format='json',
        )
        self.assertEqual(close.status_code, 200)
        self.assertEqual(close.data['session']['id'], session_id)

    def test_close_with_session_id_uses_same_session_as_current(self):
        open_response = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '100.00'}, format='json')
        self.assertEqual(open_response.status_code, 201)
        session_id = open_response.data['session']['id']

        current = self.client.get('/api/cashier/session/current/')
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.data['session']['id'], session_id)

        close = self.client.post(
            '/api/cashier/session/close/',
            {'session_id': session_id, 'total_billetes': '90.00', 'total_monedas': '10.00', 'total_contado': '100.00'},
            format='json',
        )
        self.assertEqual(close.status_code, 200)
        self.assertEqual(close.data['session']['id'], session_id)

    def test_close_with_session_id_from_other_user_context_is_allowed(self):
        opener = get_user_model().objects.create_user(username='cash_opener', password='pw')
        closer = get_user_model().objects.create_user(username='cash_closer', password='pw')
        UserProfile.objects.create(user=opener, role='cashier', is_active=True)
        UserProfile.objects.create(user=closer, role='cashier', is_active=True)

        opener_client = APIClient()
        opener_client.force_authenticate(opener)
        opened = opener_client.post('/api/cashier/session/open/', {'opening_cash_amount': '45.00'}, format='json')
        self.assertIn(opened.status_code, {200, 201})
        session_id = opened.data['session']['id']

        closer_client = APIClient()
        closer_client.force_authenticate(closer)
        close = closer_client.post(
            '/api/cashier/session/close/',
            {'session_id': session_id, 'total_billetes': '40.00', 'total_monedas': '5.00', 'total_contado': '45.00'},
            format='json',
        )
        self.assertEqual(close.status_code, 200)
        self.assertEqual(close.data['session']['id'], session_id)

    def test_close_with_session_id_and_wrong_branch_returns_explicit_error(self):
        primary_branch = Branch.objects.get(code='MAIN')
        secondary = Branch.objects.create(name='Secondary for mismatch', code='MISMATCH')
        Register.objects.create(name='CAJA MISMATCH', station_name='POS MISMATCH', branch=secondary, is_active=True)

        opened = self.client.post('/api/cashier/session/open/', {'opening_cash_amount': '10.00', 'branch_id': primary_branch.id}, format='json')
        self.assertEqual(opened.status_code, 201)
        session_id = opened.data['session']['id']

        close = self.client.post(
            '/api/cashier/session/close/',
            {'session_id': session_id, 'branch_id': secondary.id, 'total_billetes': '5.00', 'total_monedas': '5.00', 'total_contado': '10.00'},
            format='json',
        )
        self.assertEqual(close.status_code, 400)
        self.assertIn('sucursal', str(close.data.get('detail', '')).lower())

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
