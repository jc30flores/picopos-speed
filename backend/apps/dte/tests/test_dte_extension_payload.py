from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.dte.services.dte_service import normalize_dte_extension_for_hacienda


class DTEExtensionPayloadTests(SimpleTestCase):
    def test_case_a_default_consumer_final_with_customer_document(self):
        dte = {
            "receptor": {"nombre": "CONSUMIDOR FINAL", "numDocumento": None},
            "emisor": {"nit": "12171409901063", "nombreComercial": "Pico de Gallo Centro"},
            "extension": {"docuRecibe": "", "nombRecibe": "", "docuEntrega": "", "nombEntrega": ""},
        }
        customer = SimpleNamespace(name="CONSUMIDOR FINAL", documento="00000000-0", is_consumer_final=True)

        normalized, _ = normalize_dte_extension_for_hacienda(dte, client=customer)
        ext = normalized["extension"]

        self.assertEqual(ext["docuRecibe"], "00000000-0")
        self.assertEqual(ext["nombRecibe"], "CONSUMIDOR FINAL")
        self.assertEqual(ext["docuEntrega"], "12171409901063")
        self.assertEqual(ext["nombEntrega"], "Pico de Gallo Centro")
        self.assertNotEqual(ext["docuRecibe"], "")

    def test_case_b_default_consumer_final_without_customer_object(self):
        dte = {
            "receptor": {"nombre": "CONSUMIDOR FINAL", "numDocumento": None},
            "emisor": {"nit": "12171409901063", "nombreComercial": "Pico de Gallo Centro"},
            "extension": {"docuRecibe": None, "nombRecibe": None, "docuEntrega": "", "nombEntrega": ""},
        }

        normalized, _ = normalize_dte_extension_for_hacienda(dte, client=None)
        ext = normalized["extension"]

        self.assertEqual(ext["docuRecibe"], "00000000-0")
        self.assertEqual(ext["nombRecibe"], "CONSUMIDOR FINAL")

    def test_case_c_real_customer_with_document(self):
        dte = {
            "receptor": {"nombre": "CLIENTE REAL", "numDocumento": "06142108081040"},
            "emisor": {"nit": "12171409901063", "nombreComercial": "Pico de Gallo Centro"},
            "extension": {"docuRecibe": "", "nombRecibe": "", "docuEntrega": "", "nombEntrega": ""},
        }

        normalized, _ = normalize_dte_extension_for_hacienda(dte, client=None)
        ext = normalized["extension"]

        self.assertEqual(ext["docuRecibe"], "06142108081040")
        self.assertNotEqual(ext["docuRecibe"], "00000000-0")

    def test_case_d_real_customer_without_document_uses_null_not_empty(self):
        dte = {
            "receptor": {"nombre": "CLIENTE REAL", "numDocumento": None},
            "emisor": {"nit": "12171409901063", "nombreComercial": "Pico de Gallo Centro"},
            "extension": {"docuRecibe": "", "nombRecibe": "CLIENTE REAL", "docuEntrega": "", "nombEntrega": ""},
        }

        normalized, meta = normalize_dte_extension_for_hacienda(dte, client=None)
        ext = normalized["extension"]

        self.assertIsNone(ext["docuRecibe"])
        self.assertEqual(meta["source_docuRecibe"], "null")
        self.assertNotEqual(ext["docuRecibe"], "")
