from unittest.mock import patch

from django.test import TestCase

from apps.core.models import Branch, Customer, ServiceType
from apps.dte.models import DTERecord, DteDeliveryAttempt
from apps.dte.services.orchestrator import _maybe_auto_send_delivery
from apps.orders.models import Order


class DteAutoDeliveryDispatchTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine_in", label="En local")

    def _build_record(self, email: str | None, *, is_consumer_final: bool, client_type: str = "CF") -> DTERecord:
        customer = Customer.objects.create(
            name="Cliente",
            full_name="Cliente",
            client_type=client_type,
            correo=email,
            is_consumer_final=is_consumer_final,
        )
        order = Order.objects.create(
            order_number=501,
            branch=self.branch,
            service_type=self.service_type,
            customer=customer,
            customer_name="Cliente",
            status="waiting_payment",
            payment_status="paid",
            subtotal="10.00",
            tax="0.00",
            total="10.00",
        )
        return DTERecord.objects.create(
            order=order,
            branch=self.branch,
            dte_type="CF_01",
            status=DTERecord.STATUS_ACCEPTED,
            control_number="DTE-01-X001X001-000000000000501",
        )

    @patch("apps.dte.services.orchestrator.deliver_dte_to_client")
    def test_auto_delivery_dispatches_email_and_whatsapp_for_non_consumer_final(self, mock_deliver):
        record = self._build_record("Cliente.Externo@correo.com ", is_consumer_final=False, client_type="CCF")
        mock_deliver.return_value = {"results": {"email": {"ok": True}, "whatsapp": {"ok": True}}, "summary": "ok"}

        _maybe_auto_send_delivery(record)

        mock_deliver.assert_called_once_with(record, channels=("email", "whatsapp"), mode="automatic")

    @patch("apps.dte.services.orchestrator.deliver_dte_to_client")
    def test_auto_delivery_skips_for_consumer_final(self, mock_deliver):
        record = self._build_record("cliente@correo.com", is_consumer_final=True)

        _maybe_auto_send_delivery(record)

        mock_deliver.assert_not_called()

    @patch("apps.dte.services.orchestrator.deliver_dte_to_client")
    def test_auto_delivery_skips_email_when_already_sent_but_keeps_whatsapp(self, mock_deliver):
        record = self._build_record("cliente@correo.com", is_consumer_final=False, client_type="CCF")
        DteDeliveryAttempt.objects.create(
            dte_record=record,
            delivery_type=DteDeliveryAttempt.TYPE_EMAIL,
            status="SENT",
            provider_body={"to_email": "cliente@correo.com"},
            retries=1,
        )

        _maybe_auto_send_delivery(record)

        mock_deliver.assert_called_once_with(record, channels=("whatsapp",), mode="automatic")
