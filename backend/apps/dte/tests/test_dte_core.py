import json
from decimal import Decimal
from unittest.mock import patch
import os

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
    build_invalidation_payload,
    calculate_line_tax_breakdown,
    DTEPreflightError,
    _validate_dte_totals,
    validate_dte_preflight_payload,
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
from apps.orders.models import Order, OrderFee, OrderItem, OrderItemModifier
from apps.payments.models import Payment, PaymentMethod
from apps.users.models import UserProfile


@override_settings(ACTIVE_BRANCH_CODE="MAIN")
class DTECoreTests(TestCase):
    @staticmethod
    def _iva_from_gross(value: float) -> float:
        return round((value * 0.13) / 1.13, 2)

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

    def test_build_invalidation_payload_uses_resolved_ambiente(self):
        previous_mh = os.environ.get("MH_AMBIENTE")
        try:
            os.environ["MH_AMBIENTE"] = "01"
            record = DTERecord.objects.create(
                order=self.order,
                branch=self.branch,
                dte_type="CF_01",
                status=DTERecord.STATUS_ACCEPTED,
                control_number="DTE-01-S001P001-000000000000123",
                generation_code="A" * 36,
                codigo_generacion="A" * 36,
                sello_recibido="SELLO123",
                total_amount=Decimal("10.00"),
            )
            payload = build_invalidation_payload(record, "Prueba", "01234567-8", "98765432-1")
            self.assertEqual(payload["invalidacion"]["identificacion"]["ambiente"], "01")
            self.assertIn("fecAnula", payload["invalidacion"]["identificacion"])
            self.assertIn("horAnula", payload["invalidacion"]["identificacion"])
            self.assertNotIn("numeroControl", payload["invalidacion"]["identificacion"])
            self.assertNotIn("tipoDte", payload["invalidacion"]["identificacion"])
            self.assertEqual(payload["invalidacion"]["documento"]["tipoDte"], "01")
            self.assertEqual(payload["invalidacion"]["documento"]["numeroControl"], "DTE-01-S001P001-000000000000123")
            self.assertEqual(payload["invalidacion"]["documento"]["codigoGeneracion"], "A" * 36)
            self.assertEqual(payload["invalidacion"]["documento"]["tipoDocumento"], "13")
            self.assertEqual(payload["invalidacion"]["documento"]["numDocumento"], "00000000-0")
            self.assertIsInstance(payload["invalidacion"]["documento"]["montoIva"], float)
            self.assertNotIn("responsable", payload["invalidacion"])
            self.assertNotIn("solicitante", payload["invalidacion"])
            self.assertNotIn("extra", payload["invalidacion"])
        finally:
            if previous_mh is None:
                os.environ.pop("MH_AMBIENTE", None)
            else:
                os.environ["MH_AMBIENTE"] = previous_mh

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

    def test_build_payload_cf_reconciles_modifier_totals_with_quantity(self):
        category = Category.objects.create(name="MODQTY")
        product = Product.objects.create(name="Base", description="", price=Decimal("0.01"), category=category, available=True)
        item = OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Base",
            price_snapshot=Decimal("0.01"),
            quantity=3,
            discount_amount=Decimal("0.00"),
        )
        OrderItemModifier.objects.create(order_item=item, modifier_name_snapshot="Extra", modifier_price_snapshot=Decimal("0.99"))
        self.order.total = Decimal("3.00")
        self.order.save(update_fields=["total", "updated_at"])

        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000312", "B" * 36, "00")
        total_lineas = sum(Decimal(str(line["ventaGravada"])) + Decimal(str(line["ventaExenta"])) for line in payload["dte"]["cuerpoDocumento"])
        self.assertEqual(total_lineas.quantize(Decimal("0.01")), Decimal("3.00"))

    def test_build_payload_cf_preserves_fee_buckets(self):
        category = Category.objects.create(name="FEE")
        product = Product.objects.create(name="Producto", description="", price=Decimal("1.00"), category=category, available=True)
        OrderItem.objects.create(order=self.order, product=product, product_name_snapshot="Producto", price_snapshot=Decimal("1.00"), quantity=1)
        OrderFee.objects.create(order=self.order, fee_type="disposable", fee_name="Desechable A", unit_amount=Decimal("0.21"), quantity=5, total_amount=Decimal("1.05"))
        OrderFee.objects.create(order=self.order, fee_type="disposable", fee_name="Desechable B", unit_amount=Decimal("0.05"), quantity=3, total_amount=Decimal("0.15"))
        OrderFee.objects.create(order=self.order, fee_type="disposable", fee_name="Desechable C", unit_amount=Decimal("0.05"), quantity=2, total_amount=Decimal("0.10"))
        self.order.total = Decimal("2.30")
        self.order.save(update_fields=["total", "updated_at"])

        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000313", "C" * 36, "00")
        fee_lines = [line for line in payload["dte"]["cuerpoDocumento"] if str(line.get("codigo", "")).startswith("FEE-")]
        qty_unit_pairs = {(Decimal(str(line["cantidad"])), Decimal(str(line["precioUni"]))) for line in fee_lines}
        self.assertIn((Decimal("5"), Decimal("0.21")), qty_unit_pairs)
        self.assertIn((Decimal("3"), Decimal("0.05")), qty_unit_pairs)
        self.assertIn((Decimal("2"), Decimal("0.05")), qty_unit_pairs)

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
        self.assertEqual(round(linea["ivaItem"], 2), self._iva_from_gross(linea["ventaGravada"]))
        self.assertEqual(round(resumen["totalGravada"], 2), round(linea["ventaGravada"], 2))
        self.assertEqual(round(resumen["totalIva"], 2), round(linea["ivaItem"], 2))
        self.assertEqual(round(resumen["montoTotalOperacion"], 2), round(resumen["subTotal"], 2))
        self.assertEqual(round(resumen["totalPagar"], 2), round(resumen["montoTotalOperacion"], 2))

    def test_build_payload_cf_single_item_discount_keeps_subtotalventas_consistent(self):
        category = Category.objects.create(name="DESCUENTO-UNITARIO")
        product = Product.objects.create(name="Item 4.25", description="", price=Decimal("4.25"), category=category, available=True)
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Item ejemplo",
            price_snapshot=Decimal("4.25"),
            quantity=1,
            discount_amount=Decimal("2.13"),
            snapshot_sku_or_code="DISC-EXAMPLE",
            is_custom=False,
        )

        payload = build_payload_cf(self.order, "DTE-01-S001P001-000000000000205", "K" * 36, "00")
        linea = payload["dte"]["cuerpoDocumento"][0]
        resumen = payload["dte"]["resumen"]
        self.assertEqual(round((linea["precioUni"] * linea["cantidad"]) - linea["montoDescu"], 2), round(linea["ventaGravada"], 2))
        self.assertEqual(round(linea["ivaItem"], 2), self._iva_from_gross(linea["ventaGravada"]))
        self.assertEqual(round(resumen["totalGravada"], 2), round(linea["ventaGravada"], 2))
        self.assertEqual(round(resumen["totalIva"], 2), round(linea["ivaItem"], 2))
        self.assertEqual(round(resumen["totalPagar"], 2), round(resumen["subTotal"], 2))

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
            self.assertEqual(round(linea["ivaItem"], 2), self._iva_from_gross(linea["ventaGravada"]))
        descuentos_linea = sum(float(linea["montoDescu"]) for linea in cuerpo)
        self.assertEqual(round(descuentos_linea, 2), round(float(resumen["totalDescu"]), 2))
        self.assertEqual(round(float(resumen["totalIva"]), 2), round(sum(float(linea["ivaItem"]) for linea in cuerpo), 2))
        self.assertEqual(round(float(resumen["totalPagar"]), 2), round(float(resumen["subTotal"]), 2))

    def test_validate_dte_totals_with_global_discount_example(self):
        dte = {
            "cuerpoDocumento": [
                {"montoDescu": 25.0},
                {"montoDescu": 15.0},
                {"montoDescu": 5.0},
            ],
            "resumen": {
                "totalNoSuj": 0.0,
                "totalExenta": 35.0,
                "totalGravada": 610.0,
                "subTotalVentas": 645.0,
                "descuNoSuj": 0.0,
                "descuExenta": 3.5,
                "descuGravada": 61.0,
                "totalDescu": 109.5,
                "subTotal": 580.5,
                "totalIva": 75.47,
                "ivaRete1": 0.0,
                "reteRenta": 0.0,
                "montoTotalOperacion": 580.5,
                "totalPagar": 580.5,
            },
        }
        _validate_dte_totals(dte)

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
        self.assertEqual(round(resumen["subTotalVentas"], 2), round(resumen["totalGravada"] + resumen["totalExenta"], 2))
        self.assertEqual(round(resumen["totalPagar"], 2), round(resumen["subTotal"], 2))
        self.assertEqual(resumen["totalDescu"], 0)

    def test_calculate_line_tax_breakdown_discounted_line_keeps_real_total(self):
        line = calculate_line_tax_breakdown(
            unit_price_gross=Decimal("6.19"),
            quantity=Decimal("1.00"),
            discount_gross=Decimal("1.76"),
            taxable=True,
        )
        self.assertEqual(line["linea_total_objetivo"], Decimal("4.43"))
        self.assertEqual(line["precio_uni"], Decimal("6.19"))
        self.assertEqual(line["monto_descu"], Decimal("1.76"))
        self.assertEqual(line["venta_gravada"], Decimal("4.43"))
        self.assertEqual(line["iva_item"], Decimal("0.51"))
        self.assertEqual(line["linea_total"], Decimal("4.43"))
        self.assertEqual(line["venta_gravada"], line["linea_total_objetivo"])

    def test_build_payload_cf_discount_from_619_to_500_uses_final_charged_model(self):
        category = Category.objects.create(name="DESCUENTO-500")
        product = Product.objects.create(name="Caso 5.00", description="", price=Decimal("6.19"), category=category, available=True)
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Caso 6.19->5.00",
            price_snapshot=Decimal("6.19"),
            quantity=1,
            discount_amount=Decimal("1.19"),
            snapshot_sku_or_code="DISC-500",
            is_custom=False,
        )
        self.order.total = Decimal("5.00")
        self.order.subtotal = Decimal("5.00")
        self.order.tax = Decimal("0.58")
        self.order.save(update_fields=["total", "subtotal", "tax"])

        payload = build_payload_cf(self.order, "DTE-01-S001P001-000000000000299", "Z" * 36, "00")
        line = payload["dte"]["cuerpoDocumento"][0]
        resumen = payload["dte"]["resumen"]
        self.assertEqual(round(line["precioUni"], 2), 6.19)
        self.assertEqual(round(line["montoDescu"], 2), 1.19)
        self.assertEqual(round(line["ventaGravada"], 2), 5.00)
        self.assertEqual(round(line["ivaItem"], 2), 0.58)
        self.assertEqual(round(line["ventaGravada"], 2), 5.00)
        self.assertEqual(round(resumen["subTotal"], 2), 5.00)
        self.assertEqual(round(resumen["montoTotalOperacion"], 2), 5.00)
        self.assertEqual(round(resumen["totalPagar"], 2), 5.00)

    def test_build_payload_cf_rejects_when_source_totals_do_not_match_order_total(self):
        category = Category.objects.create(name="AJUSTE")
        product = Product.objects.create(name="Base", description="", price=Decimal("26.70"), category=category, available=True)
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Base",
            price_snapshot=Decimal("26.70"),
            quantity=1,
            discount_amount=Decimal("0.00"),
            snapshot_sku_or_code="BASE-2670",
            is_custom=False,
        )
        self.order.total = Decimal("28.49")
        self.order.subtotal = Decimal("28.49")
        self.order.save(update_fields=["total", "subtotal"])

        with self.assertRaises(DTEPreflightError):
            build_payload_cf(self.order, "DTE-01-S001P001-000000000000398", "Y" * 36, "00")

    def test_build_payload_cf_discount_line_reconciles_discount_before_adjustment_line(self):
        category = Category.objects.create(name="DISC-FIX")
        product = Product.objects.create(name="Promo", description="", price=Decimal("6.19"), category=category, available=True)
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Promo 6.19",
            price_snapshot=Decimal("6.19"),
            quantity=1,
            discount_amount=Decimal("1.77"),
            snapshot_sku_or_code="DISC-619",
            is_custom=False,
        )
        self.order.total = Decimal("5.00")
        self.order.subtotal = Decimal("5.00")
        self.order.save(update_fields=["total", "subtotal"])

        payload = build_payload_cf(self.order, "DTE-01-S001P001-000000000000399", "W" * 36, "00")
        cuerpo = payload["dte"]["cuerpoDocumento"]
        resumen = payload["dte"]["resumen"]
        line = cuerpo[0]
        self.assertEqual(round(line["ventaGravada"], 2), 5.00)
        self.assertEqual(round(line["montoDescu"], 2), 1.77)
        self.assertEqual(round(line["ivaItem"], 2), 0.58)
        self.assertEqual(round(line["ventaGravada"], 2), 5.00)
        self.assertFalse(any(l.get("codigo") == "AJUSTE-DTE" for l in cuerpo))
        self.assertEqual(round(resumen["totalPagar"], 2), 5.00)

    def test_build_payload_cf_modifier_without_discount_keeps_current_line_model(self):
        category = Category.objects.create(name="MODS")
        product = Product.objects.create(name="Base mod", description="", price=Decimal("5.00"), category=category, available=True)
        item = OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Base mod",
            price_snapshot=Decimal("5.00"),
            quantity=1,
            discount_amount=Decimal("0.00"),
            snapshot_sku_or_code="MOD-BASE",
            is_custom=False,
        )
        OrderItemModifier.objects.create(
            order_item=item,
            modifier_name_snapshot="Queso extra",
            modifier_price_snapshot=Decimal("1.00"),
        )
        self.order.total = Decimal("6.00")
        self.order.subtotal = Decimal("6.00")
        self.order.save(update_fields=["total", "subtotal"])

        payload = build_payload_cf(self.order, "DTE-01-S001P001-000000000000410", "N" * 36, "00")
        cuerpo = payload["dte"]["cuerpoDocumento"]
        self.assertEqual(len(cuerpo), 2)
        base_line = cuerpo[0]
        mod_line = cuerpo[1]
        self.assertEqual(round(base_line["ventaGravada"], 2), 5.00)
        self.assertEqual(round(mod_line["ventaGravada"], 2), 1.00)
        self.assertEqual(round(base_line["montoDescu"], 2), 0.00)
        self.assertEqual(round(mod_line["montoDescu"], 2), 0.00)

    def test_preflight_rejects_invalid_identificacion_fields(self):
        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000202", "A" * 36, "01")
        payload["dte"]["identificacion"]["numeroControl"] = "INVALID-CONTROL"
        with self.assertRaises(DTEPreflightError):
            validate_dte_preflight_payload(payload)

    def test_preflight_accepts_standard_numero_control_patterns(self):
        payload = build_payload_cf(self.order, "DTE-01-S001P001-000000000000203", "C" * 36, "01")
        validate_dte_preflight_payload(payload)

    def test_build_payload_includes_disposable_fees_in_totals(self):
        category = Category.objects.create(name="CON DESECHABLE")
        product = Product.objects.create(name="Promo", description="", price=Decimal("5.00"), category=category, available=True)
        item = OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Promo",
            price_snapshot=Decimal("5.00"),
            quantity=1,
            discount_amount=Decimal("0.00"),
            snapshot_sku_or_code="PROMO-1",
            is_custom=False,
        )
        OrderFee.objects.create(
            order=self.order,
            order_item=item,
            fee_type="disposable",
            fee_name="Desechables",
            unit_amount=Decimal("0.21"),
            quantity=1,
            total_amount=Decimal("0.21"),
        )
        OrderFee.objects.create(
            order=self.order,
            order_item=item,
            fee_type="disposable",
            fee_name="Desechables",
            unit_amount=Decimal("0.05"),
            quantity=1,
            total_amount=Decimal("0.05"),
        )
        self.order.disposable_total = Decimal("0.26")
        self.order.total = Decimal("5.26")
        self.order.save(update_fields=["disposable_total", "total"])
        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000204", "D" * 36, "01")
        resumen = payload["dte"]["resumen"]
        self.assertEqual(round(float(resumen["totalPagar"]), 2), 5.26)
        disposable_lines = [line for line in payload["dte"]["cuerpoDocumento"] if str(line.get("descripcion", "")).upper().startswith("DESECHABLE")]
        self.assertEqual(len(disposable_lines), 1)
        self.assertEqual(round(float(disposable_lines[0]["ventaGravada"]), 2), 0.26)

    def test_build_payload_reconciles_cent_differences_against_order_total(self):
        category = Category.objects.create(name="RECONCILIACION")
        product = Product.objects.create(name="Base", description="", price=Decimal("13.78"), category=category, available=True)
        item = OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Base",
            price_snapshot=Decimal("13.78"),
            quantity=1,
            discount_amount=Decimal("0.00"),
            snapshot_sku_or_code="BASE-1",
            is_custom=False,
        )
        OrderFee.objects.create(
            order=self.order,
            order_item=item,
            fee_type="disposable",
            fee_name="Desechables",
            unit_amount=Decimal("0.21"),
            quantity=1,
            total_amount=Decimal("0.21"),
        )
        self.order.disposable_total = Decimal("0.21")
        self.order.total = Decimal("13.99")
        self.order.save(update_fields=["disposable_total", "total"])
        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000205", "E" * 36, "01")
        resumen = payload["dte"]["resumen"]
        pagos = resumen["pagos"]
        self.assertEqual(round(float(resumen["totalPagar"]), 2), 13.99)
        self.assertEqual(round(float(pagos[0]["montoPago"]), 2), 13.99)

    def test_build_payload_cf_mixed_discount_modifiers_and_fees_keeps_line_and_total_consistency(self):
        category = Category.objects.create(name="MIX-DESC-FEE")
        p_no_discount = Product.objects.create(name="Sin descuento", description="", price=Decimal("5.00"), category=category, available=True)
        p_discount = Product.objects.create(name="Con descuento", description="", price=Decimal("6.19"), category=category, available=True)

        base_item = OrderItem.objects.create(
            order=self.order,
            product=p_no_discount,
            product_name_snapshot="Base",
            price_snapshot=Decimal("5.00"),
            quantity=1,
            discount_amount=Decimal("0.00"),
            snapshot_sku_or_code="MIX-BASE",
            is_custom=False,
        )
        OrderItemModifier.objects.create(
            order_item=base_item,
            modifier_name_snapshot="Queso extra",
            modifier_price_snapshot=Decimal("1.00"),
        )
        discount_item = OrderItem.objects.create(
            order=self.order,
            product=p_discount,
            product_name_snapshot="Promo 6.19",
            price_snapshot=Decimal("6.19"),
            quantity=1,
            discount_amount=Decimal("1.19"),
            snapshot_sku_or_code="MIX-DISC",
            is_custom=False,
        )
        OrderFee.objects.create(
            order=self.order,
            order_item=discount_item,
            fee_type="disposable",
            fee_name="Desechables bolsa",
            unit_amount=Decimal("0.21"),
            quantity=1,
            total_amount=Decimal("0.21"),
        )
        OrderFee.objects.create(
            order=self.order,
            order_item=discount_item,
            fee_type="disposable",
            fee_name="Desechables salsa",
            unit_amount=Decimal("0.05"),
            quantity=1,
            total_amount=Decimal("0.05"),
        )
        self.order.total = Decimal("11.26")
        self.order.subtotal = Decimal("11.26")
        self.order.save(update_fields=["total", "subtotal"])

        payload = build_payload_cf(self.order, "DTE-01-S001P001-000000000000450", "R" * 36, "00")
        cuerpo = payload["dte"]["cuerpoDocumento"]
        resumen = payload["dte"]["resumen"]

        for line in cuerpo:
            expected = round((line["precioUni"] * line["cantidad"]) - line["montoDescu"], 2)
            self.assertEqual(round(line["ventaGravada"] + line["ventaExenta"], 2), expected)
            if round(line["ventaGravada"], 2) > 0:
                self.assertEqual(round(line["ivaItem"], 2), self._iva_from_gross(line["ventaGravada"]))

        total_lineas = round(sum(float(line["ventaGravada"]) + float(line["ventaExenta"]) for line in cuerpo), 2)
        self.assertEqual(total_lineas, 11.26)
        self.assertEqual(round(float(resumen["totalPagar"]), 2), 11.26)
        self.assertEqual(round(float(resumen["totalIva"]), 2), round(sum(float(line["ivaItem"]) for line in cuerpo), 2))
        self.assertFalse(any(line.get("codigo") == "AJUSTE-DTE" for line in cuerpo))

    def test_regression_630_631_discounted_shell_plus_modifier_collapses_and_matches_total(self):
        category = Category.objects.create(name="REG-630")
        product = Product.objects.create(name="Chips and Guac", description="", price=Decimal("0.01"), category=category, available=True)
        item = OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Chips and Guac",
            price_snapshot=Decimal("0.01"),
            quantity=1,
            discount_amount=Decimal("2.35"),
            snapshot_sku_or_code="SHELL-001",
            is_custom=False,
        )
        OrderItemModifier.objects.create(order_item=item, modifier_name_snapshot="4OZ", modifier_price_snapshot=Decimal("4.69"))
        self.order.total = Decimal("2.35")
        self.order.subtotal = Decimal("2.35")
        self.order.save(update_fields=["total", "subtotal"])

        payload = build_payload_cf(self.order, "DTE-01-S001P001-000000000000630", "6" * 36, "00")
        cuerpo = payload["dte"]["cuerpoDocumento"]
        self.assertEqual(len(cuerpo), 1)
        line = cuerpo[0]
        self.assertEqual(round(line["precioUni"], 2), 4.70)
        self.assertEqual(round(line["montoDescu"], 2), 2.35)
        self.assertEqual(round(line["ventaGravada"], 2), 2.35)
        self.assertEqual(round(payload["dte"]["resumen"]["totalPagar"], 2), 2.35)

    def test_regression_633_simple_discount_keeps_final_model(self):
        category = Category.objects.create(name="REG-633")
        product = Product.objects.create(name="Promo 6.99", description="", price=Decimal("6.99"), category=category, available=True)
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Promo 6.99",
            price_snapshot=Decimal("6.99"),
            quantity=1,
            discount_amount=Decimal("3.50"),
            snapshot_sku_or_code="DISC-699",
            is_custom=False,
        )
        self.order.total = Decimal("3.49")
        self.order.subtotal = Decimal("3.49")
        self.order.save(update_fields=["total", "subtotal"])
        payload = build_payload_cf(self.order, "DTE-01-S001P001-000000000000633", "3" * 36, "00")
        line = payload["dte"]["cuerpoDocumento"][0]
        self.assertEqual(round(line["ventaGravada"], 2), 3.49)
        self.assertEqual(round(line["ivaItem"], 2), 0.40)

    def test_regression_635_placeholder_not_emitted_as_001_line(self):
        category = Category.objects.create(name="REG-635")
        coca = Product.objects.create(name="Coca Cola", description="", price=Decimal("1.29"), category=category, available=True)
        chips = Product.objects.create(name="Chips and Guac", description="", price=Decimal("0.01"), category=category, available=True)
        OrderItem.objects.create(
            order=self.order,
            product=coca,
            product_name_snapshot="Coca Cola",
            price_snapshot=Decimal("1.29"),
            quantity=1,
            discount_amount=Decimal("0.00"),
            snapshot_sku_or_code="COKE",
            is_custom=False,
        )
        chips_item = OrderItem.objects.create(
            order=self.order,
            product=chips,
            product_name_snapshot="Chips and Guac",
            price_snapshot=Decimal("0.01"),
            quantity=1,
            discount_amount=Decimal("0.00"),
            snapshot_sku_or_code="CHIPS",
            is_custom=False,
        )
        OrderItemModifier.objects.create(order_item=chips_item, modifier_name_snapshot="4OZ", modifier_price_snapshot=Decimal("3.28"))
        self.order.total = Decimal("4.58")
        self.order.subtotal = Decimal("4.58")
        self.order.save(update_fields=["total", "subtotal"])

        payload = build_payload_cf(self.order, "DTE-01-S001P001-000000000000635", "5" * 36, "00")
        cuerpo = payload["dte"]["cuerpoDocumento"]
        self.assertFalse(any(round(line["precioUni"], 2) == 0.01 for line in cuerpo))
        self.assertEqual(round(sum(line["ventaGravada"] + line["ventaExenta"] for line in cuerpo), 2), 4.58)

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

    def test_receptor_with_nit_14_uses_tipo_documento_36(self):
        self.order.customer = Customer.objects.create(
            name="Empresa NIT",
            full_name="Empresa NIT",
            client_type="CCF",
            nit="06141234567890",
            tipo_documento="36",
            num_documento="0614-123456-789-0",
            correo="empresa@correo.com",
        )
        self.order.save(update_fields=["customer"])
        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000013", "H" * 36, "01")
        receptor = payload["dte"]["receptor"]
        self.assertEqual(receptor["tipoDocumento"], "36")
        self.assertEqual(receptor["numDocumento"], "06141234567890")

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
        self.assertIn('"totalPagar"', serialized)

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

    def test_tax_rule_uses_base_for_venta_gravada_and_iva_item(self):
        category = Category.objects.create(name="IMPUESTO")
        product = Product.objects.create(name="Item impuesto", description="", price=Decimal("4.69"), category=category, available=True)
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name_snapshot="Caso IVA",
            price_snapshot=Decimal("4.69"),
            quantity=1,
            snapshot_sku_or_code="IVA-469",
        )

        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000210", "L" * 36, "00")
        linea = payload["dte"]["cuerpoDocumento"][0]
        resumen = payload["dte"]["resumen"]

        self.assertEqual(round(linea["ventaGravada"], 2), round((linea["precioUni"] * linea["cantidad"]) - linea["montoDescu"], 2))
        self.assertEqual(round(linea["ivaItem"], 2), self._iva_from_gross(linea["ventaGravada"]))
        self.assertEqual(round(resumen["totalIva"], 2), round(sum(float(row["ivaItem"]) for row in payload["dte"]["cuerpoDocumento"]), 2))

    def test_tiny_item_keeps_iva_consistent(self):
        category = Category.objects.create(name="TINY")
        product = Product.objects.create(name="Tiny", description="", price=Decimal("0.01"), category=category, available=True)
        OrderItem.objects.create(order=self.order, product=product, product_name_snapshot="Tiny", price_snapshot=Decimal("0.01"), quantity=1)
        payload = build_payload_cf(self.order, "DTE-01-X001X001-000000000000211", "M" * 36, "00")
        line = payload["dte"]["cuerpoDocumento"][0]
        self.assertEqual(round(line["ivaItem"], 2), self._iva_from_gross(line["ventaGravada"]))

    def test_preflight_blocks_discount_line_when_venta_gravada_is_not_final_charged(self):
        payload = {
            "dte": {
                "cuerpoDocumento": [
                    {
                        "numItem": 1,
                        "cantidad": 1,
                        "precioUni": 6.19,
                        "montoDescu": 1.77,
                        "ventaNoSuj": 0.0,
                        "ventaExenta": 0.0,
                        "ventaGravada": 4.42,
                        "psv": 0.0,
                        "noGravado": 0.0,
                        "ivaItem": 0.58,
                    }
                ],
                "resumen": {
                    "totalNoSuj": 0.0,
                    "totalExenta": 0.0,
                    "totalGravada": 4.42,
                    "subTotalVentas": 4.42,
                    "descuNoSuj": 0.0,
                    "descuExenta": 0.0,
                    "descuGravada": 0.0,
                    "totalDescu": 1.77,
                    "subTotal": 4.42,
                    "ivaRete1": 0.0,
                    "reteRenta": 0.0,
                    "montoTotalOperacion": 4.42,
                    "totalPagar": 4.42,
                    "totalIva": 0.58,
                },
            }
        }
        with self.assertRaises(DTEPreflightError):
            validate_dte_preflight_payload(payload)

    def test_preflight_blocks_total_pagar_mismatch_vs_monto_total_operacion(self):
        payload = {
            "dte": {
                "cuerpoDocumento": [
                    {
                        "numItem": 1,
                        "cantidad": 1,
                        "precioUni": 6.19,
                        "montoDescu": 1.77,
                        "ventaNoSuj": 0.0,
                        "ventaExenta": 0.0,
                        "ventaGravada": 4.42,
                        "psv": 0.0,
                        "noGravado": 0.0,
                        "ivaItem": 0.57,
                    }
                ],
                "resumen": {
                    "totalNoSuj": 0.0,
                    "totalExenta": 0.0,
                    "totalGravada": 4.42,
                    "subTotalVentas": 4.42,
                    "descuNoSuj": 0.0,
                    "descuExenta": 0.0,
                    "descuGravada": 0.0,
                    "totalDescu": 1.77,
                    "subTotal": 4.42,
                    "ivaRete1": 0.0,
                    "reteRenta": 0.0,
                    "montoTotalOperacion": 4.99,
                    "totalPagar": 5.0,
                    "totalIva": 0.57,
                },
            }
        }
        with self.assertRaises(DTEPreflightError):
            validate_dte_preflight_payload(payload)

    def test_preflight_accepts_final_charged_pattern_500(self):
        payload = {
            "dte": {
                "identificacion": {
                    "version": 1,
                    "ambiente": "00",
                    "tipoDte": "01",
                    "numeroControl": "DTE-01-S001P001-000000000000500",
                    "codigoGeneracion": "A" * 36,
                    "fecEmi": "2026-04-10",
                    "horEmi": "10:00:00",
                    "tipoOperacion": 1,
                    "tipoModelo": 1,
                    "tipoMoneda": "USD",
                },
                "emisor": {
                    "nit": "12171409901063",
                    "nrc": "123",
                    "nombre": "Empresa",
                    "nombreComercial": "Empresa",
                    "codActividad": "56101",
                    "descActividad": "Restaurantes",
                    "tipoEstablecimiento": "02",
                    "codEstableMH": "X001",
                    "codEstable": "X001",
                    "codPuntoVentaMH": "X001",
                    "codPuntoVenta": "X001",
                    "telefono": "00000000",
                    "correo": "facturas@example.com",
                    "direccion": {"departamento": "12", "municipio": "22", "complemento": "Dir"},
                },
                "receptor": {"nombre": "CONSUMIDOR FINAL", "direccion": {"departamento": "12", "municipio": "22", "complemento": "Dir"}, "telefono": "00000000", "correo": "cf@example.com"},
                "cuerpoDocumento": [
                    {
                        "numItem": 1,
                        "cantidad": 1,
                        "precioUni": 5.0,
                        "montoDescu": 0.0,
                        "ventaNoSuj": 0.0,
                        "ventaExenta": 0.0,
                        "ventaGravada": 5.0,
                        "psv": 0.0,
                        "noGravado": 0.0,
                        "ivaItem": 0.58,
                    }
                ],
                "resumen": {
                    "totalNoSuj": 0.0,
                    "totalExenta": 0.0,
                    "totalGravada": 5.0,
                    "subTotalVentas": 5.0,
                    "descuNoSuj": 0.0,
                    "descuExenta": 0.0,
                    "descuGravada": 0.0,
                    "totalDescu": 0.0,
                    "subTotal": 5.0,
                    "ivaRete1": 0.0,
                    "reteRenta": 0.0,
                    "montoTotalOperacion": 5.0,
                    "totalPagar": 5.0,
                    "totalIva": 0.58,
                    "pagos": [{"codigo": "01", "montoPago": 5.0, "referencia": None, "plazo": None, "periodo": None}],
                },
            }
        }
        validate_dte_preflight_payload(payload)

    def test_preflight_blocks_inconsistent_iva_item(self):
        payload = {
            "dte": {
                "cuerpoDocumento": [
                    {
                        "numItem": 1,
                        "cantidad": 1,
                        "precioUni": 1.0,
                        "montoDescu": 0.0,
                        "ventaNoSuj": 0.0,
                        "ventaExenta": 0.0,
                        "ventaGravada": 1.0,
                        "psv": 0.0,
                        "noGravado": 0.0,
                        "ivaItem": 0.0,
                    }
                ],
                "resumen": {
                    "totalNoSuj": 0.0,
                    "totalExenta": 0.0,
                    "totalGravada": 1.0,
                    "subTotalVentas": 1.0,
                    "descuNoSuj": 0.0,
                    "descuExenta": 0.0,
                    "descuGravada": 0.0,
                    "totalDescu": 0.0,
                    "subTotal": 1.0,
                    "ivaRete1": 0.0,
                    "reteRenta": 0.0,
                    "montoTotalOperacion": 1.13,
                    "totalPagar": 1.13,
                    "totalIva": 0.13,
                },
            }
        }
        with self.assertRaises(DTEPreflightError):
            _validate_dte_totals(payload["dte"])

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
        self.assertEqual(code, "03")
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
        self.assertEqual(code, "03")
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


class DTEInvalidateEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="cash-inv", password="pw")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)
        self.branch = Branch.objects.create(name="Main Inv", code="INV")
        self.service_type = ServiceType.objects.create(key="dinein-inv", label="En local Inv")
        self.order = Order.objects.create(
            order_number=1901,
            branch=self.branch,
            service_type=self.service_type,
            subtotal=Decimal("5.00"),
            tax=Decimal("0.00"),
            total=Decimal("5.00"),
        )
        self.record = DTERecord.objects.create(
            order=self.order,
            branch=self.branch,
            dte_type="CF_01",
            status=DTERecord.STATUS_ACCEPTED,
            control_number="",
            generation_code="105AD7EE-9DDA-411F-98EE-C0CA45D98810",
            codigo_generacion="105AD7EE-9DDA-411F-98EE-C0CA45D98810",
            request_payload={
                "dte": {
                    "identificacion": {
                        "numeroControl": "DTE-01-S001P001-000000000000357",
                        "codigoGeneracion": "105AD7EE-9DDA-411F-98EE-C0CA45D98810",
                        "fecEmi": "2026-01-01",
                    },
                    "emisor": {
                        "nit": "12171409901063",
                        "nrc": "123456",
                        "nombre": "Pico Emisor",
                        "codActividad": "56101",
                        "descActividad": "Restaurantes",
                    },
                    "receptor": {"nombre": "Cliente Demo"},
                    "resumen": {"totalIva": 0.57},
                }
            },
            response_payload={"respuesta_hacienda": {"selloRecibido": "SELLO-BASE-01"}},
            sello_recibido="SELLO-BASE-01",
            total_amount=Decimal("5.00"),
        )

    @patch("apps.dte.services.dte_service.send_to_bridge")
    def test_invalidate_endpoint_uses_shared_builder_and_fallback_control_number(self, mock_send):
        mock_send.return_value = {"http_status": 200, "success": True, "respuesta_hacienda": {"estado": "PROCESADO"}}
        self.client.force_authenticate(self.user)
        response = self.client.post(
            f"/api/dte/issued/{self.record.id}/invalidate/",
            {"motivo": "Prueba", "responsable_dui": "01234567-8", "solicitante_dui": "98765432-1"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["attempt"]["success"], True)
        sent_payload = mock_send.call_args.kwargs["payload"]
        self.assertNotIn("numeroControl", sent_payload["invalidacion"]["identificacion"])
        self.assertEqual(sent_payload["invalidacion"]["documento"]["tipoDte"], "01")
        self.assertEqual(
            sent_payload["invalidacion"]["documento"]["numeroControl"],
            "DTE-01-S001P001-000000000000357",
        )
        self.assertEqual(
            sent_payload["invalidacion"]["documento"]["numDocumento"],
            "00000000-0",
        )
        self.assertEqual(sent_payload["invalidacion"]["documento"]["tipoDocumento"], "13")
        self.assertIsInstance(sent_payload["invalidacion"]["documento"]["montoIva"], float)
        self.assertEqual(
            sent_payload["invalidacion"]["documento"]["codigoGeneracionR"],
            None,
        )
        self.assertEqual(sent_payload["invalidacion"]["emisor"]["nit"], "12171409901063")
        self.assertNotIn("nrc", sent_payload["invalidacion"]["emisor"])
        self.assertNotIn("codActividad", sent_payload["invalidacion"]["emisor"])
        self.assertNotIn("descActividad", sent_payload["invalidacion"]["emisor"])
        self.assertNotIn("nombreComercial", sent_payload["invalidacion"]["emisor"])
        self.assertEqual(sent_payload["invalidacion"]["motivo"]["numDocResponsable"], "01234567-8")
        self.assertEqual(sent_payload["invalidacion"]["motivo"]["numDocSolicita"], "01234567-8")
        self.assertEqual(sent_payload["invalidacion"]["motivo"]["tipDocResponsable"], "13")
        self.assertEqual(sent_payload["invalidacion"]["motivo"]["tipDocSolicita"], "13")
        self.assertNotIn("responsable", sent_payload["invalidacion"])
        self.assertNotIn("solicitante", sent_payload["invalidacion"])
        self.assertNotIn("extra", sent_payload["invalidacion"])

    def test_invalidate_endpoint_returns_422_when_base_document_missing_control_number(self):
        self.record.request_payload = {}
        self.record.save(update_fields=["request_payload"])
        self.client.force_authenticate(self.user)
        response = self.client.post(
            f"/api/dte/issued/{self.record.id}/invalidate/",
            {"motivo": "Prueba", "responsable_dui": "01234567-8", "solicitante_dui": "98765432-1"},
            format="json",
        )
        self.assertEqual(response.status_code, 422, response.data)
        self.assertIn("numDocumento", response.data["detail"])

    def test_invalidate_endpoint_returns_422_when_num_doc_responsable_missing(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            f"/api/dte/issued/{self.record.id}/invalidate/",
            {"motivo_anulacion": "Prueba", "num_doc_responsable": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 422, response.data)
        self.assertIn("número de documento responsable", response.data["detail"])

    def test_invalidate_endpoint_returns_422_when_motivo_anulacion_missing(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            f"/api/dte/issued/{self.record.id}/invalidate/",
            {"motivo_anulacion": "", "num_doc_responsable": "01234567-8"},
            format="json",
        )
        self.assertEqual(response.status_code, 422, response.data)
        self.assertIn("motivo de invalidación", response.data["detail"])

    def test_build_invalidation_payload_requires_sello_recibido(self):
        self.record.response_payload = {}
        self.record.sello_recibido = ""
        self.record.sello_recepcion = ""
        self.record.save(update_fields=["response_payload", "sello_recibido", "sello_recepcion"])
        with self.assertRaises(DTEPreflightError):
            payload = build_invalidation_payload(self.record, "Prueba", "01234567-8", "01234567-8", {})
            validate_dte_preflight_payload(payload)

    def test_build_invalidation_payload_requires_monto_iva(self):
        self.record.request_payload = {
            "dte": {
                "identificacion": {"numeroControl": "DTE-01-S001P001-000000000000357", "codigoGeneracion": "105AD7EE-9DDA-411F-98EE-C0CA45D98810"},
                "receptor": {"nombre": "Cliente Demo"},
                "resumen": {},
            }
        }
        self.record.save(update_fields=["request_payload"])
        with self.assertRaises(DTEPreflightError):
            build_invalidation_payload(self.record, "Prueba", "01234567-8", "01234567-8", {})

    def test_build_invalidation_payload_requires_numdocresponsable(self):
        with self.assertRaises(DTEPreflightError):
            payload = build_invalidation_payload(self.record, "Prueba", "", "01234567-8", {})
            validate_dte_preflight_payload(payload)

    def test_build_invalidation_payload_requires_numdocsolicita(self):
        with self.assertRaises(DTEPreflightError):
            payload = build_invalidation_payload(self.record, "Prueba", "01234567-8", "", {})
            validate_dte_preflight_payload(payload)

    def test_invalidation_schema_rejects_prohibited_fields(self):
        payload = build_invalidation_payload(self.record, "Prueba", "01234567-8", "01234567-8", {})
        payload["invalidacion"]["responsable"] = {"x": "1"}
        with self.assertRaises(DTEPreflightError):
            validate_dte_preflight_payload(payload)

    def test_invalidation_schema_rejects_legacy_dte_wrapper(self):
        payload = {
            "dte": {
                "identificacion": {
                    "tipoDte": "AN",
                    "ambiente": "00",
                    "codigoGeneracion": "105AD7EE-9DDA-411F-98EE-C0CA45D98810",
                    "fecAnula": "2026-01-10",
                    "horAnula": "10:00:00",
                }
            }
        }
        with self.assertRaises(DTEPreflightError):
            validate_dte_preflight_payload(payload)

    def test_build_invalidation_payload_snapshot(self):
        payload = build_invalidation_payload(self.record, "Prueba", "01234567-8", "01234567-8", {})
        normalized = json.dumps(payload["invalidacion"], sort_keys=True, ensure_ascii=False)
        self.assertIn("\"tipoDocumento\": \"01\"", normalized)
        self.assertIn("\"numDocResponsable\": \"01234567-8\"", normalized)
        self.assertIn("\"numDocSolicita\": \"01234567-8\"", normalized)
