from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.dte.client import DTEClientResult
from apps.dte.models import DTEOutbox, DTERecord
from apps.dte.outbox import process_pending_outbox, send_or_queue_dte
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
            control_number="DTE-01-M001P001-000000000000101",
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
                    "numeroControl": "DTE-01-M001P001-000000000000101",
                    "codigoGeneracion": "B" * 36,
                },
                "emisor": {"nit": "12171409901063"},
            }
        }

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
        self.assertEqual(outbox.status, DTEOutbox.STATUS_REJECTED)
        self.assertIsNone(outbox.next_attempt_at)

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
