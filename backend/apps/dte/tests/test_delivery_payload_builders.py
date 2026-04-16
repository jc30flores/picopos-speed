from decimal import Decimal

from django.test import TestCase, override_settings

from apps.core.models import Branch, Customer, ServiceType
from apps.dte.models import DTERecord
from apps.dte.services.delivery_payloads import build_delivery_base_payload
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
            response_payload={"respuesta_hacienda": {"selloRecibido": "SELLO-X", "fhProcesamiento": "2026-01-10T18:11:44"}},
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
        self.assertEqual(payload["sello_recibido"], "SELLO-X")
        self.assertEqual(payload["fhProcesamiento"], "2026-01-10T18:11:44")
        self.assertEqual(payload["metadata"]["sello_recibido"], "SELLO-X")
        self.assertEqual(payload["metadata"]["fhProcesamiento"], "2026-01-10T18:11:44")
        self.assertEqual(payload["metadata"]["control_number"], "DTE-01-S001P001-000000000000001")
        self.assertEqual(payload["metadata"]["generation_code"], "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        self.assertEqual(payload["metadata"]["dte_type"], "CF_01")
        self.assertEqual(payload["metadata"]["status"], "ACEPTADO")
        self.assertIn("identificacion", payload["invoice_json"])

    def test_build_whatsapp_payload_exact_keys(self):
        from apps.dte.services.whatsapp_dte_service import resolve_whatsapp_destination

        payload = build_whatsapp_payload(self.record, resolve_whatsapp_destination(self.record))
        self.assertEqual(payload["num_receptor"], "50371112222")
        self.assertTrue(payload["send_json"])
        self.assertEqual(payload["tipo_dte"], "01")
        self.assertEqual(payload["doc_type"], "CF")
        self.assertEqual(payload["sello_recibido"], "SELLO-X")
        self.assertEqual(payload["fhProcesamiento"], "2026-01-10T18:11:44")
        self.assertEqual(payload["generation_code"], "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        self.assertEqual(payload["control_number"], "DTE-01-S001P001-000000000000001")
        self.assertIsInstance(payload["respuesta_hacienda"], dict)
        self.assertIn("descripcion_msg", payload)

    def test_email_and_whatsapp_share_same_delivery_base(self):
        base = build_delivery_base_payload(self.record)
        from apps.dte.services.whatsapp_dte_service import resolve_whatsapp_destination

        wa_payload = build_whatsapp_payload(self.record, resolve_whatsapp_destination(self.record))
        email_payload = build_email_payload(self.record)
        self.assertEqual(email_payload["sello_recibido"], base["sello_recibido"])
        self.assertEqual(wa_payload["sello_recibido"], base["sello_recibido"])
        self.assertEqual(email_payload["fhProcesamiento"], base["fh_procesamiento"])
        self.assertEqual(wa_payload["fhProcesamiento"], base["fh_procesamiento"])
        self.assertEqual(email_payload["generation_code"], base["generation_code"])
        self.assertEqual(wa_payload["generation_code"], base["generation_code"])
        self.assertEqual(email_payload["control_number"], base["control_number"])
        self.assertEqual(wa_payload["control_number"], base["control_number"])

    def test_payloads_without_sello_do_not_break_and_leave_field_empty(self):
        self.record.sello_recibido = ""
        self.record.sello_recepcion = ""
        self.record.response_payload = {}
        self.record.save(update_fields=["sello_recibido", "sello_recepcion", "response_payload"])
        from apps.dte.services.whatsapp_dte_service import resolve_whatsapp_destination

        base = build_delivery_base_payload(self.record)
        wa_payload = build_whatsapp_payload(self.record, resolve_whatsapp_destination(self.record))
        email_payload = build_email_payload(self.record)
        self.assertEqual(base["sello_recibido"], "")
        self.assertEqual(wa_payload["sello_recibido"], "")
        self.assertEqual(email_payload["sello_recibido"], "")
        self.assertFalse(base["fh_procesamiento"])

    def test_extracts_fh_procesamiento_from_nested_hacienda_response(self):
        self.record.response_payload = {"respuesta_hacienda": {"fhProcesamiento": "2026-05-10T17:35:00", "selloRecibido": "SELLO-X"}}
        self.record.hacienda_processed_at = None
        self.record.recibido_at = None
        self.record.save(update_fields=["response_payload", "hacienda_processed_at", "recibido_at"])

        base = build_delivery_base_payload(self.record)
        self.assertEqual(base["fh_procesamiento"], "2026-05-10T17:35:00")

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
                        "tipoDte": "01",
                        "numeroControl": "DTE-01-S001P001-000000000000001",
                        "codigoGeneracion": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                        "tipoDocumento": "13",
                        "numDocumento": "00000000-0",
                        "codigoGeneracionR": None,
                        "selloRecibido": "SELLO-X",
                        "montoIva": 1.3,
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

    def test_build_invalidation_payload_regression_consumer_final_documento_mapping(self):
        payload = build_invalidation_payload(
            self.record,
            motivo="Cliente solicita anulación",
            responsable_dui="01234567-8",
            solicitante_dui="98765432-1",
            extra={"source": "dte_panel"},
        )
        invalidacion = payload["invalidacion"]
        self.assertIn("fecAnula", invalidacion["identificacion"])
        self.assertIn("horAnula", invalidacion["identificacion"])
        self.assertEqual(invalidacion["documento"]["tipoDte"], "01")
        self.assertEqual(invalidacion["documento"]["numeroControl"], "DTE-01-S001P001-000000000000001")
        self.assertEqual(invalidacion["documento"]["codigoGeneracion"], "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        self.assertIsInstance(invalidacion["documento"]["montoIva"], float)
        self.assertEqual(invalidacion["documento"]["tipoDocumento"], "13")
        self.assertLessEqual(len(invalidacion["documento"]["numDocumento"]), 20)
        self.assertEqual(invalidacion["documento"]["numDocumento"], "00000000-0")
        self.assertEqual(invalidacion["documento"]["nombre"], "Cliente DTE")
        self.assertIn("nomEstablecimiento", invalidacion["emisor"])
        self.assertEqual(invalidacion["motivo"]["numDocResponsable"], "01234567-8")
        self.assertEqual(invalidacion["motivo"]["numDocSolicita"], "98765432-1")

    def test_build_invalidation_payload_sets_codigo_generacion_r_as_null(self):
        specific_record = DTERecord.objects.create(
            order=self.order,
            branch=self.branch,
            dte_type="CF_01",
            status=DTERecord.STATUS_ACCEPTED,
            control_number="DTE-01-S001P001-000000000002035",
            generation_code="62D34A17-994B-4D69-8DAE-87B074984D8A",
            codigo_generacion="62D34A17-994B-4D69-8DAE-87B074984D8A",
            request_payload={
                "dte": {
                    "identificacion": {
                        "tipoDte": "01",
                        "numeroControl": "DTE-01-S001P001-000000000002035",
                        "codigoGeneracion": "62D34A17-994B-4D69-8DAE-87B074984D8A",
                        "fecEmi": "2026-01-10",
                    },
                    "receptor": {},
                    "resumen": {"totalIva": 1.35},
                }
            },
            response_payload={"respuesta_hacienda": {"selloRecibido": "202696A4871E1C39437A9D55A64F6A0F2A8B74OC"}},
            sello_recibido="202696A4871E1C39437A9D55A64F6A0F2A8B74OC",
            total_amount=Decimal("10.00"),
        )
        payload = build_invalidation_payload(
            specific_record,
            motivo="",
            responsable_dui="01234567-8",
            solicitante_dui="01234567-8",
            extra={},
        )
        self.assertEqual(payload["invalidacion"]["documento"]["codigoGeneracion"], "62D34A17-994B-4D69-8DAE-87B074984D8A")
        self.assertIsNone(payload["invalidacion"]["documento"]["codigoGeneracionR"])
        self.assertEqual(payload["invalidacion"]["motivo"]["motivoAnulacion"], "Rescindir de la operación realizada")

    def test_build_invalidation_payload_prefers_original_consumer_final_null_documents(self):
        self.order.customer.tipo_documento = "13"
        self.order.customer.num_documento = "00000000-0"
        self.order.customer.save(update_fields=["tipo_documento", "num_documento", "updated_at"])
        record = DTERecord.objects.create(
            order=self.order,
            branch=self.branch,
            dte_type="CF_01",
            status=DTERecord.STATUS_ACCEPTED,
            control_number="DTE-01-S001P001-000000000003333",
            generation_code="11111111-2222-3333-4444-555555555555",
            codigo_generacion="11111111-2222-3333-4444-555555555555",
            request_payload={
                "dte": {
                    "identificacion": {
                        "tipoDte": "01",
                        "numeroControl": "DTE-01-S001P001-000000000003333",
                        "codigoGeneracion": "11111111-2222-3333-4444-555555555555",
                        "fecEmi": "2026-01-12",
                    },
                    "receptor": {
                        "nombre": "CONSUMIDOR FINAL",
                        "tipoDocumento": None,
                        "numDocumento": None,
                    },
                    "resumen": {"totalIva": 1.00},
                }
            },
            response_payload={"respuesta_hacienda": {"selloRecibido": "SELLO-CF"}},
            sello_recibido="SELLO-CF",
            total_amount=Decimal("7.50"),
        )
        payload = build_invalidation_payload(record, "Prueba", "01234567-8", "01234567-8", {})
        self.assertIsNone(payload["invalidacion"]["documento"]["tipoDocumento"])
        self.assertIsNone(payload["invalidacion"]["documento"]["numDocumento"])
        self.assertEqual(payload["invalidacion"]["documento"]["nombre"], "CONSUMIDOR FINAL")
        self.assertIsNone(payload["invalidacion"]["documento"]["codigoGeneracionR"])

    def test_build_invalidation_payload_copies_identified_receptor_exactly(self):
        record = DTERecord.objects.create(
            order=self.order,
            branch=self.branch,
            dte_type="CCF_03",
            status=DTERecord.STATUS_ACCEPTED,
            control_number="DTE-03-S001P001-000000000004444",
            generation_code="AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
            codigo_generacion="AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
            request_payload={
                "dte": {
                    "identificacion": {
                        "tipoDte": "03",
                        "numeroControl": "DTE-03-S001P001-000000000004444",
                        "codigoGeneracion": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
                        "fecEmi": "2026-01-13",
                    },
                    "receptor": {
                        "nombre": "CLIENTE CCF",
                        "tipoDocumento": "36",
                        "numDocumento": "06141234567890",
                    },
                    "resumen": {"totalIva": 2.15},
                }
            },
            response_payload={"respuesta_hacienda": {"selloRecibido": "SELLO-CCF"}},
            sello_recibido="SELLO-CCF",
            total_amount=Decimal("16.50"),
        )
        payload = build_invalidation_payload(record, "Prueba", "01234567-8", "01234567-8", {})
        self.assertEqual(payload["invalidacion"]["documento"]["tipoDocumento"], "36")
        self.assertEqual(payload["invalidacion"]["documento"]["numDocumento"], "06141234567890")
        self.assertEqual(payload["invalidacion"]["documento"]["nombre"], "CLIENTE CCF")

    def test_build_invalidation_payload_has_no_legacy_structure(self):
        payload = build_invalidation_payload(self.record, "Prueba", "01234567-8", "01234567-8", {})
        self.assertNotIn("dte", payload)
        self.assertNotIn("responsable", payload["invalidacion"])
        self.assertNotIn("solicitante", payload["invalidacion"])
        self.assertNotIn("extra", payload["invalidacion"])
        self.assertNotIn("tipoDte", payload["invalidacion"]["identificacion"])
        self.assertNotIn("numeroControl", payload["invalidacion"]["identificacion"])

    def test_build_invalidation_payload_prefers_documento_firmado_over_request_payload(self):
        record = DTERecord.objects.create(
            order=self.order,
            branch=self.branch,
            dte_type="CF_01",
            status=DTERecord.STATUS_ACCEPTED,
            control_number="DTE-01-S001P001-000000000009999",
            generation_code="99999999-8888-7777-6666-555555555555",
            codigo_generacion="99999999-8888-7777-6666-555555555555",
            request_payload={
                "dte": {
                    "identificacion": {
                        "tipoDte": "01",
                        "numeroControl": "DTE-01-S001P001-000000000009999",
                        "codigoGeneracion": "99999999-8888-7777-6666-555555555555",
                        "fecEmi": "2026-01-01",
                    },
                    "receptor": {"nombre": "REQ", "tipoDocumento": "13", "numDocumento": "00000000-0"},
                    "resumen": {"totalIva": 1.00},
                }
            },
            response_payload={
                "respuesta_hacienda": {"selloRecibido": "SELLO-FIRMADO"},
                "documento_firmado": {
                    "identificacion": {
                        "tipoDte": "01",
                        "numeroControl": "DTE-01-S001P001-000000000009999",
                        "codigoGeneracion": "99999999-8888-7777-6666-555555555555",
                        "fecEmi": "2026-01-20",
                    },
                    "receptor": {"nombre": "FIRMADO", "tipoDocumento": None, "numDocumento": None},
                    "resumen": {"totalIva": 2.25},
                },
            },
            sello_recibido="SELLO-FIRMADO",
            total_amount=Decimal("18.00"),
        )
        payload = build_invalidation_payload(record, "Prueba", "01234567-8", "01234567-8", {})
        self.assertEqual(payload["invalidacion"]["documento"]["fecEmi"], "2026-01-20")
        self.assertEqual(payload["invalidacion"]["documento"]["montoIva"], 2.25)
        self.assertEqual(payload["invalidacion"]["documento"]["nombre"], "FIRMADO")
        self.assertIsNone(payload["invalidacion"]["documento"]["tipoDocumento"])
