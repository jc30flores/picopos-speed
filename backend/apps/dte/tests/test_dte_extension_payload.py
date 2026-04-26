from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.dte.services.dte_service import _resolve_extension_payload


class DTEExtensionPayloadTests(SimpleTestCase):
    def test_resolve_extension_payload_uses_clean_fallbacks(self):
        order = SimpleNamespace(iva_exempt=False, employee=None, cashier_name="", created_by=None)
        emisor = {"nombreComercial": "Empresa Test", "nombre": "Empresa", "nit": "0614-010101-001-1"}
        receptor = {"nombre": "", "numDocumento": None}

        extension = _resolve_extension_payload(order=order, customer=None, emisor_payload=emisor, receptor=receptor)

        self.assertEqual(extension["nombEntrega"], "Empresa Test")
        self.assertEqual(extension["docuEntrega"], "0614-010101-001-1")
        self.assertEqual(extension["nombRecibe"], "CONSUMIDOR FINAL")
        self.assertEqual(extension["docuRecibe"], "")
        self.assertNotIn(None, extension.values())
