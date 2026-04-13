from unittest.mock import patch

from django.test import TestCase

from apps.core.models import Branch, Customer, ServiceType
from apps.dte.models import DTERecord, DteDeliveryAttempt
from apps.dte.services.orchestrator import _maybe_auto_send_email
from apps.orders.models import Order


class DteAutoEmailDispatchTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine_in", label="En local")

    def _build_record(self, email: str | None) -> DTERecord:
        customer = Customer.objects.create(
            name="Cliente",
            full_name="Cliente",
            client_type="CF",
            correo=email,
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
    def test_auto_email_dispatches_for_valid_customer_email(self, mock_deliver):
        record = self._build_record("Cliente.Externo@correo.com ")
        mock_deliver.return_value = {"results": {"email": {"ok": True}}, "summary": "ok"}

        _maybe_auto_send_email(record)

        mock_deliver.assert_called_once_with(record, channels=("email",), mode="automatic")

    @patch("apps.dte.services.orchestrator.deliver_dte_to_client")
    def test_auto_email_skips_for_internal_billing_email(self, mock_deliver):
        record = self._build_record(" facturasPDG23@gmail.com ")

        _maybe_auto_send_email(record)

        mock_deliver.assert_not_called()

    @patch("apps.dte.services.orchestrator.deliver_dte_to_client")
    def test_auto_email_skips_when_already_sent(self, mock_deliver):
        record = self._build_record("cliente@correo.com")
        DteDeliveryAttempt.objects.create(
            dte_record=record,
            delivery_type=DteDeliveryAttempt.TYPE_EMAIL,
            status="SENT",
            provider_body={"to_email": "cliente@correo.com"},
            retries=1,
        )

        _maybe_auto_send_email(record)

        mock_deliver.assert_not_called()
