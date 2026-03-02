from django.test import SimpleTestCase

from apps.dte.services.dte_parser import parse_hacienda_response


class DTEParserTests(SimpleTestCase):
    def test_maps_accepted(self):
        parsed = parse_hacienda_response({"ok": True, "status": "ACEPTADO", "uuid": "U1", "selloRecibido": "S1"})
        self.assertEqual(parsed["status"], "aceptado")
        self.assertEqual(parsed["hacienda_uuid"], "U1")

    def test_maps_rejected(self):
        parsed = parse_hacienda_response({"ok": False, "status": "RECHAZADO", "error": "bad"})
        self.assertEqual(parsed["status"], "rechazado")
