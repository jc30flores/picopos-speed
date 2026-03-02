from django.test import SimpleTestCase

from apps.dte.models import DTERecord
from apps.dte.services.interpreter import interpret_dte_response


class DTEParserTests(SimpleTestCase):
    def test_maps_accepted_from_success_and_hacienda_state(self):
        parsed = interpret_dte_response(
            {
                "success": True,
                "uuid": "U1",
                "respuesta_hacienda": {"estado": "PROCESADO", "selloRecibido": "S1"},
            }
        )
        self.assertEqual(parsed["status"], DTERecord.STATUS_ACCEPTED)
        self.assertEqual(parsed["hacienda_uuid"], "U1")

    def test_maps_rejected_when_success_false_with_hacienda(self):
        parsed = interpret_dte_response(
            {
                "success": False,
                "respuesta_hacienda": {"estado": "RECHAZADO", "descripcionMsg": "Error"},
            }
        )
        self.assertEqual(parsed["status"], DTERecord.STATUS_REJECTED)

    def test_maps_pending_for_processing(self):
        parsed = interpret_dte_response(
            {
                "success": True,
                "respuesta_hacienda": {"status": "PROCESSING"},
            }
        )
        self.assertEqual(parsed["status"], DTERecord.STATUS_PENDING)
