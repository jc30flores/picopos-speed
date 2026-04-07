from django.test import SimpleTestCase

from apps.dte.services.hacienda import build_hacienda_consulta_publica_url
from apps.dte.services.payment_methods import get_cat017_code_and_label


class HaciendaConsultaPublicaUrlTests(SimpleTestCase):
    def test_builds_expected_url(self):
        url = build_hacienda_consulta_publica_url("2026-03-31", "ABC-123")
        self.assertEqual(
            url,
            "https://admin.factura.gob.sv/consultaPublica?ambiente=00&codGen=ABC-123&fechaEmi=2026-03-31",
        )


class Cat017MappingTests(SimpleTestCase):
    def test_maps_supported_methods(self):
        class P:
            def __init__(self, method, card_type="", code=""):
                self.method = method
                self.card_type = card_type
                self.payment_method = type("PM", (), {"code": code})() if code else None

        self.assertEqual(get_cat017_code_and_label(P("cash")), ("01", "Efectivo"))
        self.assertEqual(get_cat017_code_and_label(P("card_debit")), ("03", "Tarjeta"))
        self.assertEqual(get_cat017_code_and_label(P("card_credit")), ("03", "Tarjeta"))
        self.assertEqual(get_cat017_code_and_label(P("transfer")), ("05", "Transferencia"))
        self.assertEqual(get_cat017_code_and_label(P("pedidosya")), ("03", "Pedidos Ya (Tarjeta)"))
        self.assertEqual(get_cat017_code_and_label(P("transfer", code="PEDIDOS_YA")), ("03", "Pedidos Ya (Tarjeta)"))
        self.assertEqual(get_cat017_code_and_label(P("transfer", code="DELIVERY")), ("03", "Pedidos Ya (Tarjeta)"))
        self.assertEqual(get_cat017_code_and_label(P("paypal")), ("05", "PayPal (Transferencia)"))

    def test_maps_unknown_to_99_with_other_label(self):
        class P:
            method = "crypto_wallet"
            card_type = ""
            payment_method = None

        code, label = get_cat017_code_and_label(P())
        self.assertEqual(code, "99")
        self.assertIn("Otro:", label)
