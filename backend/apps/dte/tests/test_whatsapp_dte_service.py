from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.core.models import Branch, Customer, ServiceType
from apps.dte.models import DTERecord
from apps.dte.services.whatsapp_dte_service import (
    build_whatsapp_payload,
    resolve_whatsapp_destination,
    send_dte_whatsapp,
    validate_whatsapp_target,
)
from apps.orders.models import Order


class DTEWhatsAppServiceTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine_in", label="En local")
        self.customer = Customer.objects.create(
            nombre="Cliente",
            correo="cliente@example.com",
            telefono="50370001111",
            tipo_cliente="CF",
        )
        self.order = Order.objects.create(
            order_number=779,
            branch=self.branch,
            service_type=self.service_type,
            customer=self.customer,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
        )
        self.record = DTERecord.objects.create(
            order=self.order,
            branch=self.branch,
            dte_type="CF_01",
            status=DTERecord.STATUS_ACCEPTED,
            control_number="DTE-TEST-WA",
            generation_code="A" * 36,
            codigo_generacion="A" * 36,
            total_amount=Decimal("10.00"),
        )

    @override_settings(WHATSAPP_DEFAULT_TO_PHONE="50370000000")
    def test_build_whatsapp_payload_uses_gateway_contract(self):
        destination = resolve_whatsapp_destination(self.record)
        payload = build_whatsapp_payload(self.record, destination)
        self.assertEqual(payload["num_receptor"], "50370001111")
        self.assertNotIn("num_cliente", payload)
        self.assertTrue(payload["send_json"])
        self.assertEqual(payload["tipo_dte"], "01")
        self.assertEqual(payload["doc_type"], "CF")
        self.assertIn("descripcion_msg", payload)
        self.assertNotIn("Numero de telefono del cliente", payload["descripcion_msg"])
        self.assertEqual(payload["empresa"], payload["empresa_nombre"])
        self.assertIsInstance(payload["invoice_json"]["respuesta_hacienda"], dict)
        self.assertNotIn("sello_recibido", payload)
        self.assertNotIn("fhProcesamiento", payload)

    def test_build_whatsapp_payload_includes_optional_num_cliente_without_changing_num_receptor(self):
        self.order.whatsapp_num_cliente = "+50379378279"
        self.order.whatsapp_num_cliente_country = "ESA"
        self.order.save(update_fields=["whatsapp_num_cliente", "whatsapp_num_cliente_country"])
        destination = resolve_whatsapp_destination(self.record, to_phone="50378889999")
        payload = build_whatsapp_payload(self.record, destination)
        self.assertEqual(payload["num_receptor"], "50378889999")
        self.assertEqual(payload["num_cliente"], "+50379378279")

    def test_validate_whatsapp_target_rejects_invalid_number(self):
        ok, error, phone = validate_whatsapp_target(self.record, to_phone="abc", allow_default_fallback=False)
        self.assertFalse(ok)
        self.assertIn("inválido", error.lower())
        self.assertEqual(phone, "")

    @override_settings(WHATSAPP_DEFAULT_TO_PHONE="50370000000")
    def test_valid_client_phone_does_not_use_default_even_when_default_exists(self):
        destination = resolve_whatsapp_destination(self.record, to_phone="50379998888")
        self.assertTrue(destination.is_valid)
        self.assertEqual(destination.normalized_phone, "50379998888")
        self.assertEqual(destination.source, "client_phone")

    @override_settings(WHATSAPP_DEFAULT_TO_PHONE="50370000000", WHATSAPP_ALLOW_DEFAULT_FALLBACK="false")
    def test_missing_phone_without_fallback_returns_error(self):
        self.customer.telefono = ""
        self.customer.save(update_fields=["telefono"])
        ok, error, phone = validate_whatsapp_target(self.record, allow_default_fallback=None)
        self.assertFalse(ok)
        self.assertIn("fallback", error.lower())
        self.assertEqual(phone, "")

    @override_settings(WHATSAPP_DEFAULT_TO_PHONE="50370000000", WHATSAPP_ALLOW_DEFAULT_FALLBACK="true")
    def test_missing_phone_with_explicit_fallback_uses_default(self):
        self.customer.telefono = ""
        self.customer.save(update_fields=["telefono"])
        destination = resolve_whatsapp_destination(self.record)
        self.assertTrue(destination.is_valid)
        self.assertEqual(destination.normalized_phone, "50370000000")
        self.assertEqual(destination.source, "default_fallback")

    def test_resolve_whatsapp_destination_uses_receptor_phone_from_dte_when_manual_empty(self):
        self.customer.telefono = ""
        self.customer.save(update_fields=["telefono"])
        self.record.request_payload = {"dte": {"receptor": {"telefono": "50379990000"}}}
        self.record.save(update_fields=["request_payload"])
        destination = resolve_whatsapp_destination(self.record)
        self.assertTrue(destination.is_valid)
        self.assertEqual(destination.normalized_phone, "50379990000")
        self.assertEqual(destination.source, "dte_receptor_phone")

    @override_settings(WHATSAPP_DTE_API_BASE="https://wa.example", WHATSAPP_DTE_API_KEY="k1")
    @patch("apps.dte.services.whatsapp_dte_service.time.sleep", return_value=None)
    @patch("apps.dte.services.whatsapp_dte_service.requests.post")
    def test_provider_allowed_list_error_fails_without_default_retry(self, mock_post, _mock_sleep):
        response = MagicMock()
        response.status_code = 400
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"message": "(#131030) Recipient phone number not in allowed list"}
        response.text = '{"message":"(#131030) Recipient phone number not in allowed list"}'
        mock_post.return_value = response

        attempt = send_dte_whatsapp(self.record, to_phone="50379998888")

        self.assertEqual(attempt.status, "FAILED")
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["data"]["num_receptor"], "50379998888")
        self.assertIn("json_file", kwargs["files"])
        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(attempt.provider_body.get("to_phone"), "50379998888")
        self.assertEqual(attempt.provider_body.get("destination_source"), "client_phone")
        self.assertIn("http_400", str(attempt.provider_body.get("error") or ""))

    def test_build_payload_handles_missing_receptor_direccion(self):
        self.record.request_payload = {"dte": {"receptor": {"nombre": "Cliente sin direccion"}}}
        self.record.save(update_fields=["request_payload"])
        destination = resolve_whatsapp_destination(self.record)
        payload = build_whatsapp_payload(self.record, destination)
        self.assertIn("direccion", payload["dte"]["receptor"])
        self.assertEqual(payload["dte"]["receptor"]["direccion"]["complemento"], "")
        self.assertEqual(payload["dte"]["receptor"]["telefono"], destination.normalized_phone)

    @override_settings(WHATSAPP_DTE_API_BASE="https://wa.example", WHATSAPP_DTE_API_KEY="k1")
    @patch("apps.dte.services.whatsapp_dte_service.time.sleep", return_value=None)
    @patch("apps.dte.services.whatsapp_dte_service.requests.post")
    def test_send_whatsapp_uses_same_builder_shape(self, mock_post, _mock_sleep):
        response = MagicMock()
        response.status_code = 200
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"status": "queued", "message": "queued", "job_id": "J1"}
        response.text = '{"status":"queued","message":"queued","job_id":"J1"}'
        mock_post.return_value = response

        attempt = send_dte_whatsapp(self.record, to_phone="50379998888")

        self.assertEqual(attempt.status, "QUEUED")
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["data"]["num_receptor"], "50379998888")
        self.assertEqual(kwargs["data"]["send_json"], "true")
        self.assertIn("dte", kwargs["data"])
        self.assertIn("invoice_json", kwargs["data"])
        self.assertIn("json_file", kwargs["files"])
        self.assertIn("pdf_file", kwargs["files"])

    @override_settings(WHATSAPP_DTE_API_BASE="https://wa.example", WHATSAPP_DTE_API_KEY="k1")
    @patch("apps.dte.services.whatsapp_dte_service.time.sleep", return_value=None)
    @patch("apps.dte.services.whatsapp_dte_service.requests.post")
    def test_send_whatsapp_includes_num_cliente_when_order_has_override(self, mock_post, _mock_sleep):
        self.order.whatsapp_num_cliente = "+50379378279"
        self.order.whatsapp_num_cliente_country = "ESA"
        self.order.save(update_fields=["whatsapp_num_cliente", "whatsapp_num_cliente_country"])
        response = MagicMock()
        response.status_code = 200
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"status": "queued", "message": "queued", "job_id": "J2"}
        response.text = '{"status":"queued","message":"queued","job_id":"J2"}'
        mock_post.return_value = response

        send_dte_whatsapp(self.record, to_phone="50379998888")

        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["data"]["num_receptor"], "50379998888")
        self.assertEqual(kwargs["data"]["num_cliente"], "+50379378279")

    @override_settings(WHATSAPP_DTE_API_BASE="https://wa.example", WHATSAPP_DTE_API_KEY="k1")
    @patch("apps.dte.services.whatsapp_dte_service.time.sleep", return_value=None)
    @patch("apps.dte.services.whatsapp_dte_service.requests.post")
    def test_send_whatsapp_marks_queued_when_provider_is_queued(self, mock_post, _mock_sleep):
        response = MagicMock()
        response.status_code = 200
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"ok": True, "queued": True, "status": "queued", "job_id": "job-123"}
        response.text = '{"ok":true,"queued":true,"status":"queued","job_id":"job-123"}'
        mock_post.return_value = response

        attempt = send_dte_whatsapp(self.record, to_phone="50379998888")

        self.assertEqual(attempt.status, "QUEUED")
        self.assertTrue(attempt.provider_body.get("queued"))
        self.assertEqual(attempt.provider_body.get("job_id"), "job-123")

    @override_settings(WHATSAPP_DTE_API_BASE="https://wa.example", WHATSAPP_DTE_API_KEY="k1")
    @patch("apps.dte.services.whatsapp_dte_service.time.sleep", return_value=None)
    @patch("apps.dte.services.whatsapp_dte_service.logger.warning")
    @patch("apps.dte.services.whatsapp_dte_service.requests.post")
    def test_send_whatsapp_warns_and_fails_when_200_has_no_job_signal(self, mock_post, mock_warning, _mock_sleep):
        response = MagicMock()
        response.status_code = 200
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"ok": True, "message": "accepted"}
        response.text = '{"ok":true,"message":"accepted"}'
        mock_post.return_value = response

        attempt = send_dte_whatsapp(self.record, to_phone="50379998888")

        self.assertEqual(attempt.status, "FAILED")
        self.assertEqual(mock_post.call_count, 3)
        self.assertIn("provider_2xx_without_job_signal", str(attempt.provider_body.get("error") or ""))
        self.assertTrue(mock_warning.called)

    @override_settings(WHATSAPP_DTE_API_BASE="https://wa.example", WHATSAPP_DTE_API_KEY="k1")
    @patch("apps.dte.services.whatsapp_dte_service.build_whatsapp_payload")
    def test_send_whatsapp_fails_fast_when_num_receptor_missing(self, mock_builder):
        destination = resolve_whatsapp_destination(self.record)
        payload = build_whatsapp_payload(self.record, destination)
        payload["num_receptor"] = ""
        mock_builder.return_value = payload

        attempt = send_dte_whatsapp(self.record, to_phone="50379998888")

        self.assertEqual(attempt.status, "FAILED")
        self.assertIn("payload_missing_required:num_receptor", str(attempt.provider_body.get("error") or ""))

    @override_settings(WHATSAPP_DTE_API_BASE="https://wa.example", WHATSAPP_DTE_API_KEY="k1")
    @patch("apps.dte.services.whatsapp_dte_service.time.sleep", return_value=None)
    @patch("apps.dte.services.whatsapp_dte_service.requests.post")
    @patch("apps.dte.services.whatsapp_dte_service.logger.info")
    def test_send_whatsapp_logs_when_respuesta_hacienda_missing(self, mock_info, mock_post, _mock_sleep):
        self.record.response_payload = {}
        self.record.save(update_fields=["response_payload"])
        response = MagicMock()
        response.status_code = 200
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"job_id": "job-222", "status": "queued", "queued": True}
        response.text = '{"job_id":"job-222","status":"queued","queued":true}'
        mock_post.return_value = response

        attempt = send_dte_whatsapp(self.record, to_phone="50379998888")

        self.assertEqual(attempt.status, "QUEUED")
        self.assertTrue(any("WHATSAPP_OUTGOING_REQUEST" in str(call.args[0]) for call in mock_info.call_args_list))
