from decimal import Decimal

from django.test import TestCase, override_settings

from apps.core.models import Branch, Customer, ServiceType
from apps.dte.models import DTERecord
from apps.dte.services.dte_service import build_invalidation_payload
from apps.dte.services.email_dte_service import build_email_payload
from apps.dte.services.whatsapp_dte_service import build_whatsapp_payload
from apps.orders.models import Order


@override_settings(WHATSAPP_DEFAULT_TO_PHONE="50370000000")
class DTEPayloadBuildersTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine-in", label="En local")
        self.customer = Customer.objects.create(
            nombre="Cliente DTE",
            correo="cliente@example.com",
            telefono="50371112222",
            tipo_cliente="CF",
        )
        self.order = Order.objects.create(
            order_number=99001,
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
            control_number="DTE-01-S001P001-000000000000001",
            generation_code="A" * 36,
            codigo_generacion="A" * 36,
            total_amount=Decimal("10.00"),
        )

    def test_build_email_payload_exact_keys(self):
        payload = build_email_payload(self.record)
        self.assertEqual(
            payload,
            {
                "order_id": self.order.id,
                "dte_id": self.record.id,
                "to": "cliente@example.com",
                "subject": "DTE DTE-01-S001P001-000000000000001",
                "metadata": {"dte_type": "CF_01", "status": "ACEPTADO"},
            },
        )

    def test_build_whatsapp_payload_exact_keys(self):
        payload = build_whatsapp_payload(self.record)
        self.assertEqual(
            payload,
            {
                "order_id": self.order.id,
                "dte_id": self.record.id,
                "to": "50370000000",
                "message": "DTE DTE-01-S001P001-000000000000001 estado ACEPTADO",
            },
        )

    def test_build_invalidation_payload_exact_keys(self):
        payload = build_invalidation_payload(
            self.record,
            motivo="Cliente solicita anulación",
            responsable_dui="01234567-8",
            solicitante_dui="98765432-1",
            extra={"source": "registros"},
        )
        self.assertEqual(
            payload,
            {
                "dte": {
                    "identificacion": {
                        "tipoDte": "AN",
                        "numeroControl": "DTE-01-S001P001-000000000000001",
                        "codigoGeneracion": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                    },
                    "motivo": "Cliente solicita anulación",
                    "responsable": "01234567-8",
                    "solicitante": "98765432-1",
                    "extra": {"source": "registros"},
                }
            },
        )
