from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.dte.client import DTEClient
from apps.dte.models import DTEBranchConfig, DTERecord
from apps.dte.services.control import next_control_number
from apps.dte.services.dte_service import build_payload_cf, interpret_dte_response, get_mh_payment_info
from apps.dte.services.emisor import get_emisor_nit
from apps.menu.models import Category, Product
from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment, PaymentMethod
from apps.users.models import UserProfile


class DTECoreTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine-in", label="En local")
        self.order = Order.objects.create(
            order_number=1001,
            branch=self.branch,
            service_type=self.service_type,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
        )

    def test_counter_is_incremental(self):
        first = next_control_number(self.order)
        second = next_control_number(self.order)
        self.assertNotEqual(first, second)

    def test_interpret_dte_response_json_accepted(self):
        parsed = interpret_dte_response(
            {
                "http_status": 200,
                "success": True,
                "respuesta_hacienda": {
                    "estado": "PROCESADO",
                    "selloRecibido": "SELLO-OK",
                    "fhProcesamiento": "2026-01-01T12:00:00",
                },
                "uuid": "abc-uuid",
            }
        )
        self.assertEqual(parsed["status"], DTERecord.STATUS_ACCEPTED)
        self.assertEqual(parsed["sello_recibido"], "SELLO-OK")

    def test_interpret_dte_response_html_502(self):
        parsed = interpret_dte_response({"http_status": 502, "raw": "<html>bad gateway</html>"})
        self.assertEqual(parsed["status"], DTERecord.STATUS_PENDING)
        self.assertIn("html", parsed["response_text"].lower())

    def test_get_emisor_nit_uses_branch_config(self):
        DTEBranchConfig.objects.create(branch=self.branch, emisor_nit="1217-140990-106-3", is_active=True)
        self.assertEqual(get_emisor_nit(self.branch), "12171409901063")

    def test_build_payload_cf_uses_order_item_snapshots(self):
        DTEBranchConfig.objects.create(
            branch=self.branch,
            emisor_nit="1217-140990-106-3",
            emisor_nrc="123",
            emisor_nombre="Empresa",
            emisor_nombre_comercial="Empresa",
            cod_actividad="56101",
            desc_actividad="Restaurantes",
            is_active=True,
        )
        category = Category.objects.create(name="PRUEBA")
        product = Product.objects.create(name="MenuItem", description="", price=Decimal("1.00"), category=category, available=True)
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Nombre histórico",
            price_snapshot=Decimal("4.25"),
            quantity=2,
            snapshot_sku_or_code="MANUAL-CODE-1",
            is_custom=True,
        )

        payload = build_payload_cf(self.order, "DTE-01-M001P001-000000000000001", "A" * 36, "00")
        first = payload["dte"]["cuerpoDocumento"][0]
        self.assertEqual(first["descripcion"], "Nombre histórico")
        self.assertEqual(first["precioUni"], "4.25")
        self.assertEqual(first["codigo"], "MANUAL-CODE-1")
        self.assertEqual(payload["dte"]["emisor"]["nit"], "12171409901063")

    def test_build_payload_cf_uses_unit_price_override_when_present(self):
        category = Category.objects.create(name="PRUEBA2")
        product = Product.objects.create(name="MenuItem2", description="", price=Decimal("3.00"), category=category, available=True)
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Producto con ajuste",
            price_snapshot=Decimal("3.00"),
            unit_price_override=Decimal("2.10"),
            quantity=1,
            snapshot_sku_or_code="PROD-OVERRIDE",
            is_custom=False,
        )

        payload = build_payload_cf(self.order, "DTE-01-M001P001-000000000000001", "B" * 36, "00")
        first = payload["dte"]["cuerpoDocumento"][0]
        self.assertEqual(first["descripcion"], "Producto con ajuste")
        self.assertEqual(first["precioUni"], "2.10")
        self.assertEqual(first["codigo"], "PROD-OVERRIDE")

    def test_get_mh_payment_info_cash(self):
        Payment.objects.create(order=self.order, method="cash", amount=Decimal("10.00"), tip_amount=Decimal("0.00"))
        code, reference = get_mh_payment_info(self.order)
        self.assertEqual(code, "01")
        self.assertIsNone(reference)

    def test_get_mh_payment_info_card_debit_and_credit(self):
        Payment.objects.create(order=self.order, method="card", card_type="debit", amount=Decimal("10.00"), tip_amount=Decimal("0.00"))
        code, _ = get_mh_payment_info(self.order)
        self.assertEqual(code, "02")
        self.order.payments.all().delete()
        Payment.objects.create(order=self.order, method="card", card_type="credit", amount=Decimal("10.00"), tip_amount=Decimal("0.00"))
        code, _ = get_mh_payment_info(self.order)
        self.assertEqual(code, "03")

    def test_get_mh_payment_info_transfer_aliases(self):
        transfer_method = PaymentMethod.objects.create(code="TRANSFER", name="Transferencia")
        py_method = PaymentMethod.objects.create(code="PEDIDOS_YA", name="Pedidos Ya")
        pp_method = PaymentMethod.objects.create(code="PAYPAL", name="PayPal")
        Payment.objects.create(order=self.order, method="transfer", payment_method=transfer_method, amount=Decimal("10.00"), tip_amount=Decimal("0.00"))
        code, _ = get_mh_payment_info(self.order)
        self.assertEqual(code, "05")
        self.order.payments.all().delete()
        Payment.objects.create(order=self.order, method="transfer", payment_method=py_method, amount=Decimal("10.00"), tip_amount=Decimal("0.00"))
        code, _ = get_mh_payment_info(self.order)
        self.assertEqual(code, "05")
        self.order.payments.all().delete()
        Payment.objects.create(order=self.order, method="transfer", payment_method=pp_method, amount=Decimal("10.00"), tip_amount=Decimal("0.00"))
        code, _ = get_mh_payment_info(self.order)
        self.assertEqual(code, "05")

    def test_get_mh_payment_info_unknown_uses_99_and_reference(self):
        unknown_method = PaymentMethod.objects.create(code="CRYPTO", name="Crypto")
        Payment.objects.create(order=self.order, method="transfer", payment_method=unknown_method, amount=Decimal("10.00"), tip_amount=Decimal("0.00"))
        code, reference = get_mh_payment_info(self.order)
        self.assertEqual(code, "99")
        self.assertTrue(reference)

    @patch("apps.dte.client.DTEClient._build_url")
    @patch("apps.dte.client.requests.Session.post")
    def test_client_blocks_send_on_emisor_nit_mismatch(self, mock_post, mock_build_url):
        DTEBranchConfig.objects.create(branch=self.branch, emisor_nit="12171409901063", is_active=True)
        payload = build_payload_cf(self.order, "DTE-01-M001P001-000000000000001", "A" * 36, "00")
        payload["dte"]["emisor"]["nit"] = "00000000000000"
        mock_build_url.return_value = "https://example.test/api/v1/dte/factura"

        result = DTEClient(base_url="https://example.test").send(
            path="/api/v1/dte/factura",
            payload=payload,
            order_id=self.order.id,
            branch_id=self.branch.id,
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "EMISOR_NIT_MISMATCH")
        mock_post.assert_not_called()


class DTEResendEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="cash2", password="pw")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)
        branch = Branch.objects.create(name="Main", code="M2")
        service_type = ServiceType.objects.create(key="takeout", label="Para llevar")
        order = Order.objects.create(order_number=901, branch=branch, service_type=service_type, subtotal=Decimal("2.00"), tax=Decimal("0.00"), total=Decimal("2.00"))
        self.record = DTERecord.objects.create(
            order=order,
            branch=branch,
            dte_type="CF_01",
            status=DTERecord.STATUS_PENDING,
            control_number="DTE-01-M001P001-000000000000001",
            generation_code="A" * 36,
            codigo_generacion="A" * 36,
            send_attempts=0,
            attempts=0,
        )

    @patch("apps.dte.services.dte_retry.send_to_bridge")
    def test_resend_updates_attempts(self, mock_send):
        mock_send.return_value = {"http_status": 200, "success": True, "respuesta_hacienda": {"estado": "PROCESADO"}}
        self.client.force_authenticate(self.user)
        response = self.client.post(f"/api/dte/issued/{self.record.id}/resend/")
        self.assertEqual(response.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.send_attempts, 1)
        self.assertIn(self.record.status, {DTERecord.STATUS_ACCEPTED, DTERecord.STATUS_PENDING})
