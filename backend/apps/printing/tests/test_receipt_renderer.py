from datetime import datetime, timezone
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.printing.services.renderers import render_customer_ticket


class ReceiptRendererTests(SimpleTestCase):
    def test_render_customer_ticket_does_not_fail_when_logo_missing(self):
        mock_ctx = {
            "tagline": "Pico de Gallo POS",
            "restaurant_name": "Sucursal Centro",
            "address": "San Salvador",
            "phone": "2222-2222",
            "service_type_label": "DINE IN",
            "cashier_name": "cajero",
            "order_number": 123,
            "order_datetime": datetime(2026, 3, 31, 12, 0, tzinfo=timezone.utc),
            "items": [{"qty": 1, "name": "Taco", "unit_price": 2.50, "line_total": 2.50}],
            "totals": {"subtotal": 2.50, "iva": 0.29, "iva_rete1": 0, "total": 2.50},
            "payment": {
                "method_label_es": "Efectivo",
                "method_code_cat017": "01",
                "amount_paid": 2.50,
                "change_due": 0,
                "reference": "",
            },
            "dte": {"numero_control": "NC", "codigo_generacion": "CG", "fecha_dte": "2026-03-31"},
            "public_url": "https://admin.factura.gob.sv/consultaPublica?ambiente=00&codGen=CG&fechaEmi=2026-03-31",
            "logo_path": "backend/assets/receipt/logo_pdg.png",
            "logo_exists": False,
        }

        with patch("apps.printing.services.renderers.build_receipt_context", return_value=mock_ctx):
            order = type("Order", (), {"id": 1, "payment_status": "paid"})()
            payload = render_customer_ticket(order)

        self.assertIn("Gracias por su visita", payload["text"])
        self.assertIn("consultaPubli", payload["text"])
        self.assertFalse(payload["meta"]["logo_exists"])
