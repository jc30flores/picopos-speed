import io
import json
import zipfile
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Branch, Customer, ServiceType
from apps.dte.models import DTERecord
from apps.orders.models import Order
from apps.reports.dte_export import (
    build_csv_without_bom,
    format_date_for_hacienda,
    format_money_for_f07,
    get_export_zip_name,
    is_exportable_dte,
    sanitize_csv_value,
    validate_no_bom,
)
from apps.users.models import UserProfile


SELLO = "A" * 40


class DTEExportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="dte_export", password="pw")
        UserProfile.objects.create(user=self.user, role="manager", is_active=True)
        self.client.force_authenticate(self.user)
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service = ServiceType.objects.create(key="dine-in", label="En local")
        self.customer = Customer.objects.create(
            name="Cliente Contribuyente",
            full_name="Cliente Contribuyente",
            company_name="Cliente SA",
            client_type="CCF",
            nit="0614-010190-102-0",
            nrc="123456-7",
            dui="01234567-8",
        )

    def _order(self, number, total="11.30", subtotal="10.00", tax="1.30", customer=None):
        return Order.objects.create(
            order_number=number,
            branch=self.branch,
            service_type=self.service,
            status="delivered",
            customer=customer,
            customer_name=(customer.name if customer else f"Cliente {number}"),
            subtotal=Decimal(subtotal),
            tax=Decimal(tax),
            total=Decimal(total),
            payment_status="paid",
            financial_status="paid",
            net_paid=Decimal(total),
        )

    def _dte(self, *, number, dte_type="CF_01", status="ACEPTADO", issue_date=date(2026, 4, 5), code=None, control=None, sello=SELLO, customer=None, total="11.30"):
        tipo = {"CF_01": "01", "CCF_03": "03", "NC_05": "05", "ND_06": "06", "SE_14": "14"}.get(dte_type, "01")
        code = code or f"00000000-0000-0000-0000-{number:012d}"
        control = control or f"DTE-{tipo}-0001-000000000000{number:03d}"
        return DTERecord.objects.create(
            order=self._order(number, customer=customer, total=total),
            branch=self.branch,
            dte_type=dte_type,
            status=status,
            control_number=control,
            generation_code=code,
            codigo_generacion=code,
            sello_recibido=sello,
            recibido_at=timezone.make_aware(datetime(2026, 4, 5, 12, 0, 0)),
            estado_mh="PROCESADO" if status == "ACEPTADO" else status,
            mh_response_json={
                "estado": "PROCESADO" if status == "ACEPTADO" else status,
                "selloRecibido": sello,
                "fhProcesamiento": "2026-04-05T12:00:00",
                "codigoMsg": "001",
                "descripcionMsg": "OK",
                "observaciones": [],
            },
            request_payload={
                "identificacion": {"tipoDte": tipo, "numeroControl": control, "codigoGeneracion": code},
                "receptor": {"nombre": "Cliente", "nit": "06140101901020"},
                "Authorization": "Bearer secret",
            },
            response_payload={"token": "secret", "respuesta_hacienda": {"selloRecibido": sello}},
            receiver_name="Cliente",
            receiver_nit="0614-010190-102-0" if customer else "",
            issue_date=issue_date,
            total_amount=Decimal(total),
        )

    def _post_export(self, export_type):
        return self.client.post("/api/reports/dte/export/", {"year": 2026, "month": 4, "type": export_type}, format="json")

    def test_helpers_zip_name_and_csv_formatting(self):
        self.assertEqual(get_export_zip_name(4, 2026, "json"), "abril_json_2026.zip")
        self.assertEqual(format_date_for_hacienda("2026-04-05"), "05/04/2026")
        self.assertEqual(format_money_for_f07("1234.5"), "1234.50")
        self.assertEqual(sanitize_csv_value("\ufeff hola\n mundo\u200b "), "hola mundo")
        csv = build_csv_without_bom([["a", "b"], ["1", "2"]])
        self.assertEqual(csv, "a;b\n1;2")
        validate_no_bom(csv)

    def test_json_export_zip_includes_only_exportable_and_strips_secrets(self):
        accepted = self._dte(number=1, dte_type="CF_01", status="ACEPTADO")
        self._dte(number=2, dte_type="CF_01", status="RECHAZADO")
        self._dte(number=3, dte_type="CCF_03", status="PENDIENTE")
        invalid = self._dte(number=4, dte_type="CF_01", status="INVALIDADO")

        response = self._post_export("json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn("abril_json_2026.zip", response["Content-Disposition"])

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            names = sorted(zf.namelist())
            self.assertEqual(names, [f"CF/{accepted.codigo_generacion}.json", f"INVALIDADOS/{invalid.codigo_generacion}.json"])
            payload = json.loads(zf.read(f"CF/{accepted.codigo_generacion}.json"))
            self.assertEqual(payload["metadata"]["system"], "GastroPOSV")
            self.assertEqual(payload["respuesta_hacienda"]["selloRecibido"], SELLO)
            self.assertEqual(payload["respuesta_hacienda"]["fhProcesamiento"], "2026-04-05T12:00:00")
            serialized = json.dumps(payload)
            self.assertNotIn("Authorization", serialized)
            self.assertNotIn("Bearer secret", serialized)
            self.assertNotIn("token", serialized)

    def test_f07_export_csv_files_have_official_shapes_and_no_bom(self):
        self._dte(number=10, dte_type="CF_01", status="ACEPTADO", issue_date=date(2026, 4, 5), total="11.30")
        ccf = self._dte(number=11, dte_type="CCF_03", status="ACEPTADO", issue_date=date(2026, 4, 6), customer=self.customer, total="11.30")
        invalid = self._dte(number=12, dte_type="CF_01", status="INVALIDADO", issue_date=date(2026, 4, 7), total="11.30")
        self._dte(number=13, dte_type="CF_01", status="RECHAZADO", issue_date=date(2026, 4, 8), total="99.99")
        self._dte(number=14, dte_type="CCF_03", status="PENDIENTE", issue_date=date(2026, 4, 8), total="99.99")

        response = self._post_export("f07")
        self.assertEqual(response.status_code, 200)
        self.assertIn("abril_f07_2026.zip", response["Content-Disposition"])
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            names = sorted(zf.namelist())
            self.assertEqual(names, ["CCF_NC_OFICIAL_2026_04.csv", "CF_OFICIAL_2026_04.csv", "INVALIDADOS_OFICIAL_2026_04.csv"])
            self.assertFalse(any("CONTROL" in name or name.endswith(".xlsx") for name in names))
            cf_raw = zf.read("CF_OFICIAL_2026_04.csv")
            self.assertFalse(cf_raw.startswith(b"\xef\xbb\xbf"))
            cf = cf_raw.decode("utf-8")
            ccf_csv = zf.read("CCF_NC_OFICIAL_2026_04.csv").decode("utf-8")
            invalid_csv = zf.read("INVALIDADOS_OFICIAL_2026_04.csv").decode("utf-8")
            cf_cols = cf.split(";")
            ccf_cols = ccf_csv.split(";")
            invalid_cols = invalid_csv.split(";")
            self.assertEqual(len(cf_cols), 23)
            self.assertEqual(cf_cols[13], "11.30")
            self.assertEqual(cf_cols[19], "11.30")
            self.assertEqual(cf_cols[22], "2")
            self.assertEqual(len(ccf_cols), 20)
            self.assertEqual(ccf_cols[3], ccf.control_number.replace("-", ""))
            self.assertEqual(ccf_cols[4], SELLO)
            self.assertEqual(ccf_cols[5], ccf.codigo_generacion.replace("-", ""))
            self.assertEqual(ccf_cols[19], "1")
            self.assertEqual(len(invalid_cols), 10)
            self.assertEqual(invalid_cols[5], "D")
            self.assertEqual(invalid_cols[9], invalid.codigo_generacion)

    def test_no_empty_files_for_only_cf(self):
        self._dte(number=20, dte_type="CF_01", status="ACEPTADO")
        response = self._post_export("f07")
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            self.assertEqual(zf.namelist(), ["CF_OFICIAL_2026_04.csv"])

    def test_pdf_returns_501_and_accepted_without_sello_is_not_exportable(self):
        no_sello = self._dte(number=30, dte_type="CF_01", status="ACEPTADO", sello="")
        self.assertFalse(is_exportable_dte(no_sello))
        pdf = self._post_export("pdf")
        self.assertEqual(pdf.status_code, 501)
        empty = self._post_export("json")
        self.assertEqual(empty.status_code, 404)
        self.assertIn("No hay DTE", empty.data["detail"])
