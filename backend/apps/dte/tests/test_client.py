from __future__ import annotations

from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from apps.dte.client import DTEClient
from apps.dte.models import DTETransmissionLog


class DTEClientTests(TestCase):
    @override_settings(
        DTE_BASE_URL="https://factura.cheros.dev",
        DTE_API_TOKEN="api_key_1234567890",
        DTE_API_AUTH_HEADER="Authorization",
        DTE_API_AUTH_PREFIX="Bearer",
    )
    @patch("apps.dte.client.requests.Session.post")
    def test_send_persists_transmission_log(self, mock_post):
        response = Mock()
        response.status_code = 200
        response.text = '{"success": true, "uuid": "abc", "respuesta_hacienda": {"estado": "PROCESADO", "selloRecibido": "SELLO-REAL"}}'
        response.json.return_value = {
            "success": True,
            "uuid": "abc",
            "respuesta_hacienda": {"estado": "PROCESADO", "selloRecibido": "SELLO-REAL"},
        }
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        result = DTEClient().send(path="/api/v1/dte/factura", payload={"dte": {}}, order_id=10, payment_id=20, branch_id=30)

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.success)
        self.assertEqual(result.remote_uuid, "abc")
        self.assertEqual(result.sello_recibido, "SELLO-REAL")

        log = DTETransmissionLog.objects.latest("id")
        self.assertEqual(log.order_id, 10)
        self.assertEqual(log.payment_id, 20)
        self.assertEqual(log.branch_id, 30)
        self.assertEqual(log.response_status, 200)
        self.assertTrue(log.success)
