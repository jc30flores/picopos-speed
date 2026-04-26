from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
import requests

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.dte.client import DTEClientResult
from apps.dte.models import DTEBranchConfig, DTEOutbox, DTERecord
from apps.dte.outbox import process_pending_outbox, send_or_queue_dte
from apps.dte.services.dte_retry import resend_record
from apps.orders.models import Order
from apps.users.models import UserProfile


@dataclass
class _HealthUp:
    state: str = "UP"
    health_status_code: int = 200
    health_body: str = "ok"
    factura_code: int = 422
    factura_body: str = "validation"


class DTEResendEndpointAndOutboxTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="cash3", password="pw")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)
        self.branch = Branch.objects.create(name="Main", code="MAIN3")
        service_type = ServiceType.objects.create(key="takeout-3", label="Para llevar")
        self.order = Order.objects.create(
            order_number=1901,
            branch=self.branch,
            service_type=service_type,
            subtotal=Decimal("2.00"),
            tax=Decimal("0.00"),
            total=Decimal("2.00"),
        )
        self.record = DTERecord.objects.create(
            order=self.order,
            branch=self.branch,
            dte_type="CF_01",
            status=DTERecord.STATUS_PENDING,
            control_number="DTE-01-X001X001-000000000000101",
            generation_code="B" * 36,
            codigo_generacion="B" * 36,
            request_payload={"dte": {"identificacion": {"tipoDte": "01"}}},
            send_attempts=0,
            attempts=0,
        )
        self.payload = {
            "dte": {
                "identificacion": {
                    "tipoDte": "01",
                    "numeroControl": "DTE-01-X001X001-000000000000101",
                    "codigoGeneracion": "B" * 36,
                },
                "emisor": {"nit": "12171409901063"},
            }
        }
        DTEBranchConfig.objects.create(
            branch=self.branch,
            emisor_nit="12171409901063",
            emisor_nrc="123",
            emisor_nombre="Empresa",
            emisor_nombre_comercial="Empresa",
            cod_actividad="56101",
            desc_actividad="Restaurantes",
            is_active=True,
        )

    def test_resend_requires_auth_or_valid_csrf(self):
        csrf_client = APIClient(enforce_csrf_checks=True)
        csrf_client.login(username="cash3", password="pw")
        response = csrf_client.post(f"/api/dte/issued/{self.record.id}/resend/")
        self.assertEqual(response.status_code, 403)

    @patch("apps.dte.views.resend_record")
    def test_resend_returns_200_and_updates_attempts(self, mock_resend):
        self.client.force_authenticate(self.user)
        self.record.send_attempts = 1
        self.record.attempts = 1
        self.record.status = DTERecord.STATUS_ACCEPTED
        self.record.response_payload = {"http_status": 200}
        self.record.response_text = json.dumps({"ok": True})
        mock_resend.return_value = self.record

        response = self.client.post(f"/api/dte/issued/{self.record.id}/resend/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body.get("success"))
        self.assertEqual(body.get("dte_record_id"), self.record.id)

    @patch("apps.dte.views.resend_record")
    def test_resend_returns_success_false_when_business_status_is_rejected(self, mock_resend):
        self.client.force_authenticate(self.user)
        self.record.status = DTERecord.STATUS_REJECTED
        self.record.response_payload = {"http_status": 422}
        self.record.response_text = json.dumps({"detail": "validation error"})
        mock_resend.return_value = self.record

        response = self.client.post(f"/api/dte/issued/{self.record.id}/resend/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body.get("success"))
        self.assertFalse(body.get("pending"))

    @patch("apps.dte.services.dte_retry.send_or_queue_dte")
    @patch("apps.dte.services.dte_retry.build_payload_cf")
    def test_resend_rebuilds_payload_when_record_payload_is_empty(self, mock_build_payload, mock_send_or_queue):
        self.record.request_payload = {}
        self.record.control_number = ""
        self.record.codigo_generacion = ""
        self.record.generation_code = ""
        self.record.save(update_fields=["request_payload", "control_number", "codigo_generacion", "generation_code"])
        rebuilt_payload = {
            "dte": {
                "identificacion": {
                    "tipoDte": "01",
                    "numeroControl": "DTE-01-X001X001-000000000000999",
                    "codigoGeneracion": "Z" * 36,
                },
                "cuerpoDocumento": [{"numItem": 1}],
                "resumen": {"totalPagar": 2},
            }
        }
        mock_build_payload.return_value = rebuilt_payload
        mock_send_or_queue.return_value = DTEOutbox(
            id=88,
            order=self.order,
            payment=None,
            dte_record=self.record,
            status=DTEOutbox.STATUS_FAILED,
            attempts=1,
        )

        resend_record(self.record)
        self.record.refresh_from_db()
        self.assertEqual(self.record.control_number, "DTE-01-X001X001-000000000000999")
        self.assertEqual(self.record.codigo_generacion, "Z" * 36)
        self.assertEqual(self.record.request_payload["dte"]["identificacion"]["numeroControl"], "DTE-01-X001X001-000000000000999")
        sent_payload = mock_send_or_queue.call_args.kwargs["payload"]
        self.assertTrue(sent_payload.get("dte"))

    @patch("apps.dte.services.dte_retry.send_or_queue_dte")
    def test_resend_fails_without_correlatives_and_does_not_send(self, mock_send_or_queue):
        self.record.request_payload = {}
        self.record.control_number = ""
        self.record.codigo_generacion = ""
        self.record.generation_code = ""
        self.record.save(update_fields=["request_payload", "control_number", "codigo_generacion", "generation_code"])

        updated = resend_record(self.record)
        self.assertEqual(updated.status, DTERecord.STATUS_REJECTED)
        self.assertEqual(updated.error_code, "PRECHECK")
        self.assertIn("faltan correlativos", (updated.error_message or "").lower())
        mock_send_or_queue.assert_not_called()

    @patch("apps.dte.services.dte_retry.send_or_queue_dte")
    def test_resend_normalizes_extension_for_consumer_final_snapshot(self, mock_send_or_queue):
        self.order.customer = None
        self.order.customer_name = "CONSUMIDOR FINAL"
        self.order.save(update_fields=["customer_name"])
        self.record.request_payload = {
            "dte": {
                "identificacion": {
                    "tipoDte": "01",
                    "numeroControl": "DTE-01-X001X001-000000000000101",
                    "codigoGeneracion": "B" * 36,
                },
                "receptor": {"nombre": "CONSUMIDOR FINAL", "numDocumento": None},
                "emisor": {"nit": "12171409901063", "nombreComercial": "Pico de Gallo Centro"},
                "cuerpoDocumento": [{"numItem": 1}],
                "resumen": {"totalPagar": 2},
                "extension": {"docuRecibe": "", "nombRecibe": "", "docuEntrega": "", "nombEntrega": ""},
            }
        }
        self.record.save(update_fields=["request_payload"])
        mock_send_or_queue.return_value = DTEOutbox(
            id=89,
            order=self.order,
            payment=None,
            dte_record=self.record,
            status=DTEOutbox.STATUS_PENDING,
            attempts=1,
        )

        resend_record(self.record)

        sent_payload = mock_send_or_queue.call_args.kwargs["payload"]
        ext = sent_payload["dte"]["extension"]
        self.assertEqual(ext["docuRecibe"], "00000000-0")
        self.assertEqual(ext["nombRecibe"], "CONSUMIDOR FINAL")
        self.assertEqual(ext["docuEntrega"], "12171409901063")
        self.assertEqual(ext["nombEntrega"], "Pico de Gallo Centro")

    @patch("apps.dte.outbox._health_snapshot", return_value=_HealthUp())
    @patch("apps.dte.outbox.DTEClient.send")
    def test_outbox_enqueue_on_5xx(self, mock_send, _health):
        mock_send.return_value = DTEClientResult(
            status_code=502,
            json_body={"error": {"message": "bad gateway"}},
            text_body='{"error":"bad gateway"}',
            success=False,
            remote_uuid="",
            sello_recibido="",
            error_message="bad gateway",
            error_type="SERVER_ERROR",
            elapsed_ms=10,
        )
        outbox = send_or_queue_dte(self.order, None, self.payload, dte_record=self.record)
        self.assertEqual(outbox.status, DTEOutbox.STATUS_PENDING)
        self.assertIsNotNone(outbox.next_attempt_at)

    @patch("apps.dte.outbox.DTEClient.send")
    def test_outbox_async_only_does_not_send_in_request_thread(self, mock_send):
        outbox = send_or_queue_dte(self.order, None, self.payload, dte_record=self.record, attempt_immediate=False)
        self.assertEqual(outbox.status, DTEOutbox.STATUS_PENDING)
        self.assertIsNotNone(outbox.next_attempt_at)
        mock_send.assert_not_called()

    @patch("apps.dte.outbox._health_snapshot", return_value=_HealthUp())
    @patch("apps.dte.outbox.DTEClient.send")
    def test_outbox_no_retry_on_4xx_authorization_error(self, mock_send, _health):
        mock_send.return_value = DTEClientResult(
            status_code=403,
            json_body={"error": {"message": "authorization_error"}},
            text_body='{"error":"authorization_error"}',
            success=False,
            remote_uuid="",
            sello_recibido="",
            error_message="authorization_error",
            error_type="AUTH",
            elapsed_ms=10,
        )
        outbox = send_or_queue_dte(self.order, None, self.payload, dte_record=self.record)
        self.assertEqual(outbox.status, DTEOutbox.STATUS_FAILED)
        self.assertIsNone(outbox.next_attempt_at)

    @patch("apps.dte.outbox._health_snapshot", return_value=_HealthUp())
    @patch("apps.dte.outbox.DTEClient.send")
    def test_outbox_no_retry_on_422_validation_error(self, mock_send, _health):
        mock_send.return_value = DTEClientResult(
            status_code=422,
            json_body={"error": {"message": "missing field dte"}},
            text_body='{"error":"missing field dte"}',
            success=False,
            remote_uuid="",
            sello_recibido="",
            error_message="validation_error",
            error_type="VALIDATION",
            elapsed_ms=10,
        )
        outbox = send_or_queue_dte(self.order, None, self.payload, dte_record=self.record)
        self.assertEqual(outbox.status, DTEOutbox.STATUS_FAILED)
        self.assertIsNone(outbox.next_attempt_at)

    @patch("apps.dte.outbox._health_snapshot", return_value=_HealthUp())
    @patch("apps.dte.outbox.DTEClient.send")
    def test_outbox_422_already_processed_is_treated_as_accepted(self, mock_send, _health):
        mock_send.return_value = DTEClientResult(
            status_code=422,
            json_body={"detail": "Documento ya fue procesado en Hacienda"},
            text_body='{"detail":"Documento ya fue procesado en Hacienda"}',
            success=False,
            remote_uuid="",
            sello_recibido="",
            error_message="already processed",
            error_type="VALIDATION",
            elapsed_ms=10,
        )
        outbox = send_or_queue_dte(self.order, None, self.payload, dte_record=self.record)
        self.assertEqual(outbox.status, DTEOutbox.STATUS_ACCEPTED)

    @patch("apps.dte.outbox._health_snapshot", return_value=_HealthUp())
    @patch("apps.dte.outbox.DTEClient.send")
    def test_outbox_marks_accepted_on_http_200(self, mock_send, _health):
        mock_send.return_value = DTEClientResult(
            status_code=200,
            json_body={"success": True, "estado": "ACEPTADO"},
            text_body='{"success":true,"estado":"ACEPTADO"}',
            success=True,
            remote_uuid="uuid-1",
            sello_recibido="sello",
            error_message="",
            error_type="",
            elapsed_ms=10,
        )
        outbox = send_or_queue_dte(self.order, None, self.payload, dte_record=self.record)
        self.assertEqual(outbox.status, DTEOutbox.STATUS_ACCEPTED)
        self.assertIsNone(outbox.next_attempt_at)

    @patch("apps.dte.outbox._health_snapshot", return_value=_HealthUp())
    @patch("apps.dte.outbox.DTEClient.send")
    def test_outbox_timeout_keeps_pending(self, mock_send, _health):
        mock_send.return_value = DTEClientResult(
            status_code=0,
            json_body={"success": False, "offline": True, "error": {"type": "TIMEOUT", "message": "Read timed out"}},
            text_body='{"success":false,"offline":true,"error":{"type":"TIMEOUT"}}',
            success=False,
            remote_uuid="",
            sello_recibido="",
            error_message="Read timed out",
            error_type="TIMEOUT",
            elapsed_ms=30001,
        )
        outbox = send_or_queue_dte(self.order, None, self.payload, dte_record=self.record)
        self.assertEqual(outbox.status, DTEOutbox.STATUS_PENDING)
        self.assertIsNotNone(outbox.next_attempt_at)
        self.assertNotEqual(outbox.status, DTEOutbox.STATUS_SENT)

    @patch("apps.dte.outbox._health_snapshot", return_value=_HealthUp())
    @patch("apps.dte.client.DTEClient._build_url", return_value="https://api.example.com/api/v1/dte/factura")
    @patch("apps.dte.client.requests.Session.post")
    def test_outbox_timeout_from_requests_post_keeps_pending(self, mock_post, _build_url, _health):
        mock_post.side_effect = requests.ReadTimeout("Read timed out. (read timeout=120)")
        outbox = send_or_queue_dte(self.order, None, self.payload, dte_record=self.record)
        self.assertEqual(outbox.status, DTEOutbox.STATUS_PENDING)
        self.assertIsNotNone(outbox.next_attempt_at)
        self.assertNotEqual(outbox.status, DTEOutbox.STATUS_SENT)

    @patch("apps.dte.outbox._health_snapshot", return_value=_HealthUp())
    @patch("apps.dte.outbox.DTEClient.send")
    def test_outbox_repairs_invalid_payload_nit_before_send(self, mock_send, _health):
        bad_payload = json.loads(json.dumps(self.payload))
        bad_payload["dte"]["emisor"]["nit"] = "048143931"
        mock_send.return_value = DTEClientResult(
            status_code=200,
            json_body={"success": True, "estado": "ACEPTADO"},
            text_body='{"success":true,"estado":"ACEPTADO"}',
            success=True,
            remote_uuid="uuid-2",
            sello_recibido="ok",
            error_message="",
            error_type="",
            elapsed_ms=10,
        )
        outbox = send_or_queue_dte(self.order, None, bad_payload, dte_record=self.record)
        self.assertEqual(outbox.status, DTEOutbox.STATUS_ACCEPTED)
        sent_payload = mock_send.call_args.kwargs["payload"]
        self.assertEqual(sent_payload["dte"]["emisor"]["nit"], "12171409901063")

    @patch("apps.dte.outbox._health_snapshot", return_value=_HealthUp())
    @patch("apps.dte.outbox.DTEClient.send")
    def test_outbox_marks_failed_when_nit_payload_cannot_be_repaired(self, mock_send, _health):
        bad_payload = {"dte": {"identificacion": {}, "emisor": {"nit": "048143931"}}}
        outbox = send_or_queue_dte(self.order, None, bad_payload, dte_record=self.record)
        self.assertEqual(outbox.status, DTEOutbox.STATUS_FAILED)
        self.assertIn("INVALID_EMISOR_NIT_PAYLOAD", outbox.error_message)
        mock_send.assert_not_called()

    @patch("apps.dte.outbox._health_snapshot", return_value=_HealthUp())
    @patch("apps.dte.outbox._resend_existing_outbox")
    def test_process_outbox_picks_pending_by_next_attempt_at(self, mock_resend, _health):
        due = DTEOutbox.objects.create(
            order=self.order,
            payment=None,
            dte_record=self.record,
            status=DTEOutbox.STATUS_PENDING,
            payload=self.payload,
            payload_json=self.payload,
            next_attempt_at=timezone.now() - timedelta(seconds=1),
        )
        DTEOutbox.objects.create(
            order=self.order,
            payment=None,
            dte_record=self.record,
            status=DTEOutbox.STATUS_PENDING,
            payload=self.payload,
            payload_json=self.payload,
            next_attempt_at=timezone.now() + timedelta(minutes=10),
        )
        mock_resend.return_value = due

        processed = process_pending_outbox(limit=10)
        self.assertEqual(processed, 1)
        self.assertEqual(mock_resend.call_count, 1)
