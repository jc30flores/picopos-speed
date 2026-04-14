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
            request_payload={
                "dte": {
                    "identificacion": {"tipoDte": "01", "fecEmi": "2026-01-10"},
                    "receptor": {"nombre": "Cliente DTE"},
                    "resumen": {"totalIva": 1.30},
                }
            },
            response_payload={"respuesta_hacienda": {"selloRecibido": "SELLO-X"}},
            sello_recibido="SELLO-X",
            total_amount=Decimal("10.00"),
        )

    def test_build_email_payload_exact_keys(self):
        payload = build_email_payload(self.record)
        self.assertEqual(payload["to_email"], "cliente@example.com")
        self.assertEqual(payload["subject"], "DTE DTE-01-S001P001-000000000000001")
        self.assertIn("Adjuntamos comprobante DTE", payload["body_text"])
        self.assertEqual(payload["flags"]["attach_pdf"], True)
        self.assertEqual(payload["flags"]["attach_json"], True)
        self.assertEqual(payload["metadata"], {"dte_type": "CF_01", "status": "ACEPTADO"})
        self.assertIn("identificacion", payload["invoice_json"])

    def test_build_whatsapp_payload_exact_keys(self):
        payload = build_whatsapp_payload(self.record)
        self.assertEqual(payload["num_receptor"], "50370000000")
        self.assertTrue(payload["send_json"])
        self.assertEqual(payload["tipo_dte"], "01")
        self.assertEqual(payload["doc_type"], "CF")
        self.assertIn("descripcion_msg", payload)

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
                "invalidacion": {
                    "identificacion": {
                        "version": 2,
                        "ambiente": payload["invalidacion"]["identificacion"]["ambiente"],
                        "codigoGeneracion": payload["invalidacion"]["identificacion"]["codigoGeneracion"],
                        "fecAnula": payload["invalidacion"]["identificacion"]["fecAnula"],
                        "horAnula": payload["invalidacion"]["identificacion"]["horAnula"],
                    },
                    "documento": {
                        "tipoDocumento": "01",
                        "numDocumento": "DTE-01-S001P001-000000000000001",
                        "codigoGeneracionR": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                        "selloRecibido": "SELLO-X",
                        "montoIva": "1.30",
                        "nombre": "Cliente DTE",
                        "fecEmi": "2026-01-10",
                    },
                    "emisor": payload["invalidacion"]["emisor"],
                    "motivo": {
                        "tipoAnulacion": 2,
                        "motivoAnulacion": "Cliente solicita anulación",
                        "nombreResponsable": "Responsable",
                        "tipDocResponsable": "13",
                        "numDocResponsable": "01234567-8",
                        "nombreSolicita": "Solicitante",
                        "tipDocSolicita": "13",
                        "numDocSolicita": "98765432-1",
                    },
                }
            },
        )
