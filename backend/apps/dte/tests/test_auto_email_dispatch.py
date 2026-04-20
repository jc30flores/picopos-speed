from unittest.mock import patch

from django.test import TestCase

from apps.core.models import Branch, Customer, ServiceType
from apps.dte.models import DTERecord
from apps.dte.services.orchestrator import _maybe_auto_send_delivery
from apps.orders.models import Order


class DteAutoDeliveryDispatchTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine_in", label="En local")

    def _build_record(
        self,
        *,
        email: str | None = "cliente@correo.com",
        is_consumer_final: bool = False,
        phone_override: str = "",
    ) -> DTERecord:
        customer = Customer.objects.create(
            name="Cliente",
            full_name="Cliente",
            client_type="CCF",
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
            whatsapp_num_cliente=phone_override,
            whatsapp_num_cliente_country="ESA" if phone_override else "",
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
        record = self._build_record(email="cliente@correo.com", phone_override="+50379378279")
        mock_deliver.return_value = {"results": {"email": {"ok": True}, "whatsapp": {"ok": True}}, "summary": "ok", "success": True}
        _maybe_auto_send_delivery(record)
        mock_deliver.assert_called_once_with(record, channels=("email", "whatsapp"), mode="automatic")

    @patch("apps.dte.services.orchestrator.deliver_dte_to_client")
    def test_auto_delivery_skips_consumer_final(self, mock_deliver):
        record = self._build_record(is_consumer_final=True)
        _maybe_auto_send_delivery(record)
        mock_deliver.assert_not_called()

    @patch("apps.dte.services.orchestrator.deliver_dte_to_client")
    def test_auto_delivery_skips_email_channel_when_internal_or_missing(self, mock_deliver):
        record = self._build_record(email="facturasPDG23@gmail.com")
        mock_deliver.return_value = {"results": {"whatsapp": {"ok": True}}, "summary": "ok", "success": True}
        _maybe_auto_send_delivery(record)
        mock_deliver.assert_called_once_with(record, channels=("whatsapp",), mode="automatic")
