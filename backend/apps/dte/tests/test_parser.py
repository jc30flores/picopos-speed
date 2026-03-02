from django.test import SimpleTestCase

from apps.dte.models import DTERecord
from apps.dte.services.interpreter import interpret_response


class DTEParserTests(SimpleTestCase):
    def test_maps_accepted(self):
        parsed = interpret_response({"ok": True, "status": "ACEPTADO", "uuid": "U1", "selloRecibido": "S1"})
        self.assertEqual(parsed["status"], DTERecord.STATUS_ACCEPTED)
        self.assertEqual(parsed["hacienda_uuid"], "U1")

    def test_maps_rejected(self):
        parsed = interpret_response({"ok": False, "status": "RECHAZADO", "error": "bad"})
        self.assertEqual(parsed["status"], DTERecord.STATUS_REJECTED)
