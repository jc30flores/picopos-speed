from unittest.mock import patch

from django.test import TestCase

from apps.core.models import Branch, Customer, ServiceType
from apps.dte.models import DTERecord
from apps.dte.services.orchestrator import _maybe_auto_send_delivery
from apps.orders.models import Order


class DteAutoDeliveryRulesTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine_in", label="En local")

    def _record(self, *, receptor_nombre="CONSUMIDOR FINAL", receptor_correo="cf@example.com", emisor_correo="facturasPDG23@gmail.com", receptor_telefono="0000-0000", extra=""):
        customer = Customer.objects.create(name="Cliente", full_name="Cliente", client_type="CF", correo=receptor_correo, telefono=receptor_telefono)
        order = Order.objects.create(
            order_number=900,
            branch=self.branch,
            service_type=self.service_type,
            customer=customer,
            customer_name="Cliente",
            status="waiting_payment",
            payment_status="paid",
            subtotal="10.00",
            tax="0.00",
            total="10.00",
            whatsapp_num_cliente=extra,
            whatsapp_num_cliente_country="ESA" if extra else "",
        )
        return DTERecord.objects.create(
            order=order,
            branch=self.branch,
            dte_type="CF_01",
            status=DTERecord.STATUS_ACCEPTED,
            control_number="DTE-01-X001X001-000000000000900",
            response_payload={"respuesta_hacienda": {"estado": "PROCESADO", "selloRecibido": "SELLO-1"}},
            request_payload={"dte": {"receptor": {"nombre": receptor_nombre, "correo": receptor_correo, "telefono": receptor_telefono}, "emisor": {"correo": emisor_correo}}},
        )

    @patch("apps.dte.services.orchestrator.deliver_dte_to_client")
    def test_email_rule_consumer_final_same_email_skips_email(self, mock_deliver):
        r = self._record(receptor_correo="facturasPDG23@gmail.com")
        _maybe_auto_send_delivery(r)
        mock_deliver.assert_called_once()
        self.assertEqual(mock_deliver.call_args.kwargs["channels"], ("whatsapp",))

    @patch("apps.dte.services.orchestrator.deliver_dte_to_client")
    def test_email_rule_consumer_final_different_email_sends(self, mock_deliver):
        r = self._record(receptor_correo="cliente@gmail.com")
        _maybe_auto_send_delivery(r)
        self.assertIn("email", mock_deliver.call_args.kwargs["channels"])

    @patch("apps.dte.services.orchestrator.deliver_dte_to_client")
    def test_email_rule_non_consumer_final_sends(self, mock_deliver):
        r = self._record(receptor_nombre="REDIFAR S.A DE C.V", receptor_correo="empresa@correo.com")
        _maybe_auto_send_delivery(r)
        self.assertIn("email", mock_deliver.call_args.kwargs["channels"])

    @patch("apps.dte.services.orchestrator.deliver_dte_to_client")
    def test_whatsapp_rule_placeholder_and_no_extra_skips(self, mock_deliver):
        r = self._record(receptor_telefono="0000-0000", extra="", receptor_correo="facturasPDG23@gmail.com")
        _maybe_auto_send_delivery(r)
        mock_deliver.assert_not_called()

    @patch("apps.dte.services.orchestrator.deliver_dte_to_client")
    def test_whatsapp_rule_placeholder_with_extra_sends_with_extra(self, mock_deliver):
        r = self._record(receptor_telefono="0000-0000", extra="+50378985990")
        _maybe_auto_send_delivery(r)
        self.assertIn("whatsapp", mock_deliver.call_args.kwargs["channels"])
        self.assertEqual(mock_deliver.call_args.kwargs["to_phone"], "+50378985990")

    @patch("apps.dte.services.orchestrator.deliver_dte_to_client")
    def test_whatsapp_rule_real_phone_no_extra_sends(self, mock_deliver):
        r = self._record(receptor_telefono="2222-3333")
        _maybe_auto_send_delivery(r)
        self.assertIn("whatsapp", mock_deliver.call_args.kwargs["channels"])

    @patch("apps.dte.services.orchestrator.deliver_dte_to_client")
    def test_rejected_dte_skips(self, mock_deliver):
        r = self._record()
        r.status = DTERecord.STATUS_REJECTED
        r.save(update_fields=["status"])
        _maybe_auto_send_delivery(r)
        mock_deliver.assert_not_called()
