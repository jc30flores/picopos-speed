import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError

from apps.core.models import Branch, ServiceType
from apps.core.models import Customer
from apps.dte.client import DTEClient
from apps.dte.models import DTEBranchConfig, DTEControlCounter, DTERecord
from apps.dte.services.control import next_control_number
from apps.dte.services.dte_service import (
    DTEPreflightError,
    assert_no_string_numbers,
    build_payload_cf,
    get_mh_payment_info,
    interpret_dte_response,
    json_number,
    money,
    to_decimal,
)
from apps.dte.services.orchestrator import transmit_sale_dte
from apps.dte.services.emisor import get_emisor_config, get_emisor_nit
from apps.menu.models import Category, Product
from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment, PaymentMethod
from apps.users.models import UserProfile


@override_settings(ACTIVE_BRANCH_CODE="MAIN")
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
        self.branch_monaco = Branch.objects.create(name="Plaza Monaco", code="PLAZA_MONACO")

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

    def test_get_emisor_nit_falls_back_to_branch_nit(self):
        self.branch.nit = "1217-140990-106-3"
        self.branch.save(update_fields=["nit"])
        self.assertEqual(get_emisor_nit(self.branch), "12171409901063")

    def test_get_emisor_nit_invalid_value_reports_source(self):
        self.branch.nit = "048143931"
        self.branch.save(update_fields=["nit"])
        with self.assertRaisesMessage(ValidationError, "Branch.nit"):
            get_emisor_nit(self.branch)

    @override_settings(DTE_EMISOR_NIT="1217-140990-106-3")
    def test_get_emisor_nit_ignores_invalid_branch_config_and_uses_env(self):
        DTEBranchConfig.objects.create(branch=self.branch, emisor_nit="048143931", is_active=True)
        self.assertEqual(get_emisor_nit(self.branch), "12171409901063")

    @override_settings(ACTIVE_BRANCH_CODE="MAIN")
    def test_emisor_config_uses_active_branch_code_main(self):
        DTEBranchConfig.objects.create(
            branch=self.branch,
            emisor_nit="1217-140990-106-3",
            emisor_nombre_comercial="Sucursal Main",
            direccion_complemento="Dirección Main",
            cod_estable="M001",
            cod_punto_venta="P001",
            is_active=True,
        )
        DTEBranchConfig.objects.create(
            branch=self.branch_monaco,
            emisor_nit="1217-140990-106-3",
            emisor_nombre_comercial="Sucursal Monaco",
            direccion_complemento="Dirección Monaco",
            cod_estable="M002",
            cod_punto_venta="P002",
            is_active=True,
        )
        cfg = get_emisor_config(self.branch_monaco)
        self.assertEqual(cfg["nombreComercial"], "Sucursal Main")
        self.assertEqual(cfg["complemento"], "Dirección Main")
        self.assertEqual(cfg["codEstable"], "M001")
        self.assertEqual(cfg["codPuntoVenta"], "P001")

    @override_settings(ACTIVE_BRANCH_CODE="PLAZA_MONACO")
    def test_emisor_config_uses_active_branch_code_monaco_without_changing_order(self):
        DTEBranchConfig.objects.create(
            branch=self.branch,
            emisor_nit="1217-140990-106-3",
            emisor_nombre_comercial="Sucursal Main",
            direccion_complemento="Dirección Main",
            cod_estable="M001",
            cod_punto_venta="P001",
            is_active=True,
        )
        DTEBranchConfig.objects.create(
            branch=self.branch_monaco,
            emisor_nit="1217-140990-106-3",
            emisor_nombre_comercial="Sucursal Monaco",
            direccion_complemento="Dirección Monaco",
            cod_estable="M002",
            cod_punto_venta="P002",
            is_active=True,
        )
        original_order_branch_id = self.order.branch_id
        cfg = get_emisor_config(self.branch)
        self.assertEqual(cfg["nombreComercial"], "Sucursal Monaco")
        self.assertEqual(cfg["complemento"], "Dirección Monaco")
        self.assertEqual(cfg["codEstable"], "M002")
        self.assertEqual(cfg["codPuntoVenta"], "P002")
        self.order.refresh_from_db()
        self.assertEqual(self.order.branch_id, original_order_branch_id)

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

        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000001", "A" * 36, "00")
        first = payload["dte"]["cuerpoDocumento"][0]
        self.assertEqual(first["descripcion"], "Nombre histórico")
        self.assertEqual(first["precioUni"], 4.25)
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

        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000001", "B" * 36, "00")
        first = payload["dte"]["cuerpoDocumento"][0]
        self.assertEqual(first["descripcion"], "Producto con ajuste")
        self.assertEqual(first["precioUni"], 2.1)
        self.assertEqual(first["codigo"], "PROD-OVERRIDE")

    def test_build_payload_cf_sets_discount_summary_from_item_discounts(self):
        category = Category.objects.create(name="DESCUENTOS")
        product = Product.objects.create(name="Con descuento", description="", price=Decimal("5.00"), category=category, available=True)
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Item descontado",
            price_snapshot=Decimal("5.00"),
            quantity=2,
            discount_amount=Decimal("1.50"),
            snapshot_sku_or_code="DISC-1",
            is_custom=False,
        )

        payload = build_payload_cf(self.order, "DTE-01-S001P001-000000000000201", "H" * 36, "00")
        linea = payload["dte"]["cuerpoDocumento"][0]
        resumen = payload["dte"]["resumen"]

        self.assertEqual(round((linea["precioUni"] * linea["cantidad"]) - linea["montoDescu"], 2), round(linea["ventaGravada"], 2))
        self.assertEqual(resumen["totalGravada"], 8.5)
        self.assertEqual(resumen["subTotalVentas"], 10.0)
        self.assertEqual(resumen["subTotal"], 8.5)
        self.assertEqual(resumen["descuGravada"], 1.5)
        self.assertEqual(resumen["totalDescu"], 1.5)

    def test_build_payload_cf_with_special_price_and_global_discount_is_consistent(self):
        category = Category.objects.create(name="MIX")
        p1 = Product.objects.create(name="Coke", description="", price=Decimal("1.49"), category=category, available=True)
        p2 = Product.objects.create(name="Shrimp Tampico Burrito", description="", price=Decimal("9.99"), category=category, available=True)
        p3 = Product.objects.create(name="Grilled Chicken Burrito", description="", price=Decimal("6.99"), category=category, available=True)
        OrderItem.objects.create(order=self.order, product=p1, product_name_snapshot="Coke", price_snapshot=Decimal("1.49"), quantity=1, discount_amount=Decimal("0.74"))
        OrderItem.objects.create(order=self.order, product=p2, product_name_snapshot="Shrimp Tampico Burrito", price_snapshot=Decimal("9.99"), quantity=1, discount_amount=Decimal("5.00"))
        OrderItem.objects.create(order=self.order, product=p3, product_name_snapshot="Grilled Chicken Burrito", price_snapshot=Decimal("5.00"), quantity=1, discount_amount=Decimal("2.50"))

        payload = build_payload_cf(self.order, "DTE-01-S001P001-000000000000203", "J" * 36, "00")
        cuerpo = payload["dte"]["cuerpoDocumento"]
        resumen = payload["dte"]["resumen"]
        for linea in cuerpo:
            self.assertEqual(round((linea["precioUni"] * linea["cantidad"]) - linea["montoDescu"], 2), round(linea["ventaGravada"], 2))
        descuentos_linea = sum(float(linea["montoDescu"]) for linea in cuerpo)
        self.assertEqual(round(descuentos_linea, 2), round(float(resumen["totalDescu"]), 2))
        self.assertEqual(round(float(resumen["totalPagar"]), 2), round(float(resumen["subTotal"]), 2))

    def test_build_payload_cf_without_discounts_keeps_subtotals_equal(self):
        category = Category.objects.create(name="SIN-DESC")
        product = Product.objects.create(name="Sin descuento", description="", price=Decimal("4.00"), category=category, available=True)
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Item normal",
            price_snapshot=Decimal("4.00"),
            quantity=2,
            discount_amount=Decimal("0.00"),
            snapshot_sku_or_code="NODISC-1",
            is_custom=False,
        )

        payload = build_payload_cf(self.order, "DTE-01-S001P001-000000000000202", "I" * 36, "00")
        resumen = payload["dte"]["resumen"]
        self.assertEqual(resumen["subTotalVentas"], 8.0)
        self.assertEqual(resumen["subTotal"], 8.0)
        self.assertEqual(resumen["totalDescu"], 0)

    def test_receptor_consumidor_final_uses_null_document_fields_and_no_empty_strings(self):
        self.order.customer = Customer.objects.create(
            name="CONSUMIDOR FINAL",
            full_name="CONSUMIDOR FINAL",
            client_type="CF",
            dui="00000000-0",
            tipo_documento="13",
            num_documento="00000000-0",
            correo="",
            is_consumer_final=True,
        )
        self.order.save(update_fields=["customer"])
        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000010", "D" * 36, "01")
        receptor = payload["dte"]["receptor"]
        self.assertIsNone(receptor["tipoDocumento"])
        self.assertIsNone(receptor["numDocumento"])
        self.assertIsNone(receptor["nrc"])
        self.assertTrue(receptor["correo"])
        self.assertNotEqual(receptor["correo"], "")

    def test_receptor_with_real_dui_uses_tipo_documento_13_and_dui(self):
        self.order.customer = Customer.objects.create(
            name="Cliente DUI",
            full_name="Cliente DUI",
            client_type="CF",
            dui="01234567-8",
            tipo_documento="13",
            num_documento="01234567-8",
            correo="cliente@correo.com",
        )
        self.order.save(update_fields=["customer"])
        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000011", "E" * 36, "01")
        receptor = payload["dte"]["receptor"]
        self.assertEqual(receptor["tipoDocumento"], "13")
        self.assertEqual(receptor["numDocumento"], "01234567-8")
        self.assertEqual(receptor["correo"], "cliente@correo.com")

    def test_receptor_uses_customer_email_when_present(self):
        self.order.customer = Customer.objects.create(
            name="Cliente con correo",
            full_name="Cliente con correo",
            client_type="CF",
            is_consumer_final=False,
            tipo_documento="13",
            num_documento="12345678-9",
            correo="realcliente@correo.com",
        )
        self.order.save(update_fields=["customer"])
        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000111", "G" * 36, "01")
        receptor = payload["dte"]["receptor"]
        self.assertEqual(receptor["correo"], "realcliente@correo.com")

    def test_receptor_optional_fields_never_send_empty_string(self):
        self.order.customer = Customer.objects.create(
            name="Cliente sin opcionales",
            full_name="Cliente sin opcionales",
            client_type="CCF",
            tipo_documento="36",
            num_documento="0614-010101-101-1",
            nrc="",
            correo="",
            telefono="",
        )
        self.order.save(update_fields=["customer"])
        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000012", "F" * 36, "01")
        receptor = payload["dte"]["receptor"]

        def _assert_no_empty_strings(value):
            if isinstance(value, dict):
                for nested in value.values():
                    _assert_no_empty_strings(nested)
            elif isinstance(value, list):
                for nested in value:
                    _assert_no_empty_strings(nested)
            elif isinstance(value, str):
                self.assertNotEqual(value, "")

        _assert_no_empty_strings(receptor)

    def test_numeric_fields_are_serialized_as_json_numbers(self):
        category = Category.objects.create(name="JSON")
        product = Product.objects.create(name="ItemJSON", description="", price=Decimal("1.00"), category=category, available=True)
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="JSON Item",
            price_snapshot=Decimal("4.25"),
            quantity=2,
            snapshot_sku_or_code="JSON-1",
            is_custom=True,
        )
        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000099", "C" * 36, "00")
        serialized = json.dumps(payload, ensure_ascii=False)

        first = payload["dte"]["cuerpoDocumento"][0]
        self.assertIsInstance(first["precioUni"], float)
        self.assertIsInstance(first["montoDescu"], int)
        self.assertIsInstance(payload["dte"]["resumen"]["totalPagar"], float)
        self.assertIsInstance(payload["dte"]["resumen"]["pagos"][0]["montoPago"], float)
        self.assertIn('"precioUni": 4.25', serialized)
        self.assertIn('"totalPagar": 8.5', serialized)

    def test_assert_no_string_numbers_reports_exact_path(self):
        payload = {"dte": {"resumen": {"totalPagar": "17.71"}}}
        with self.assertRaises(DTEPreflightError) as ctx:
            assert_no_string_numbers(payload)
        self.assertIn("dte.resumen.totalPagar", str(ctx.exception))

    def test_assert_no_string_numbers_allows_code_strings(self):
        payload = {
            "dte": {
                "identificacion": {"ambiente": "01"},
                "emisor": {"tipoEstablecimiento": "02"},
            }
        }
        assert_no_string_numbers(payload)

    def test_assert_no_string_numbers_rejects_pago_monto_string(self):
        payload = {"dte": {"resumen": {"pagos": [{"montoPago": "113.00"}]}}}
        with self.assertRaises(DTEPreflightError) as ctx:
            assert_no_string_numbers(payload)
        self.assertIn("dte.resumen.pagos[0].montoPago", str(ctx.exception))

    @patch("apps.dte.services.orchestrator.build_payload_cf")
    def test_preflight_failure_does_not_increment_control_counter(self, mock_build_payload):
        mock_build_payload.side_effect = DTEPreflightError("payload_preflight_error")
        self.order.dte_document_type = "CF"
        self.order.save(update_fields=["dte_document_type"])

        record = transmit_sale_dte(self.order.id)
        self.assertEqual(record.status, DTERecord.STATUS_REJECTED)
        self.assertFalse(DTEControlCounter.objects.filter(branch=self.branch).exists())

    def test_decimal_helpers(self):
        self.assertEqual(to_decimal("17.71"), Decimal("17.71"))
        self.assertEqual(money("17.715"), Decimal("17.72"))
        self.assertEqual(json_number(Decimal("10.00")), 10)
        self.assertEqual(json_number(Decimal("10.25")), 10.25)

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
        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000001", "A" * 36, "00")
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
            control_number="DTE-01-X001X001-000000000000001",
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
