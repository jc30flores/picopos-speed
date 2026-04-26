from pathlib import Path
from io import BytesIO
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase
try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

from apps.printing.receipt_pdf import build_receipt_pdf, build_receipt_pdf_from_text, build_sale_receipt_pdf


class ReceiptPdfOutputTests(SimpleTestCase):
    def test_fallback_pdf_trims_trailing_blank_lines_to_avoid_extra_page(self):
        text = "ORDEN #171\nTOTAL: $10.00\n" + ("\n" * 40)
        result = build_receipt_pdf_from_text(
            text=text,
            filename="venta_171.pdf",
            receipt_context={"order_number": 171},
        )
        page_markers = result.pdf_bytes.count(b"/Type /Page")
        self.assertEqual(page_markers, 1)

    def test_ticket_pdf_contains_images_and_single_page(self):
        if PdfReader is None:
            self.skipTest("pypdf no está instalado en el entorno de pruebas")
        result = build_receipt_pdf(
            lines=[
                "ORDEN #105",
                "------------------------------------------",
                "Subtotal: $10.00",
                "IVA (13%): $1.30",
                "Total: $11.30",
            ],
            filename="venta_105_2026-04-06_12-30.pdf",
            logo_path=str(Path(settings.BASE_DIR) / "assets" / "receipt" / "logo_pdg.png"),
            qr_value="https://admin.factura.gob.sv/consultaPublica?ambiente=00&codGen=CG-TEST&fechaEmi=2026-04-06",
            suppress_qr_url_lines=True,
        )

        reader = PdfReader(BytesIO(result.pdf_bytes))
        self.assertEqual(len(reader.pages), 1)
        text = (reader.pages[0].extract_text() or "").upper()
        self.assertIn("SUBTOTAL", text)
        self.assertIn("IVA", text)
        self.assertIn("TOTAL", text)
        self.assertNotIn("CONSULTAPUBLICA", text)
        self.assertNotIn("<<CENTER>>", text)
        self.assertNotIn("<<ITEM>>", text)

        resources = reader.pages[0].get("/Resources", {})
        xobjects = resources.get("/XObject", {}) if resources else {}
        image_count = 0
        for xobj in xobjects.values():
            resolved = xobj.get_object()
            if resolved.get("/Subtype") == "/Image":
                image_count += 1
        self.assertGreaterEqual(image_count, 1)

    def test_build_receipt_pdf_from_text_falls_back_when_reportlab_missing_for_sale_layout(self):
        with patch("apps.printing.receipt_pdf.build_sale_receipt_pdf", side_effect=ModuleNotFoundError("No module named 'reportlab'")):
            result = build_receipt_pdf_from_text(
                text="ORDEN #200\nTOTAL: $10.00",
                filename="venta_200.pdf",
                receipt_context={"order_number": 200},
            )
        self.assertTrue(result.pdf_bytes.startswith(b"%PDF"))

    def test_sale_pdf_displays_hacienda_values_and_hides_none(self):
        if PdfReader is None:
            self.skipTest("pypdf no está instalado en el entorno de pruebas")
        result = build_sale_receipt_pdf(
            receipt_context={
                "restaurant_name": "Pico de Gallo",
                "tagline": "Pico de Gallo POS",
                "address": "San Salvador",
                "service_type_label": "DINE IN",
                "cashier_name": "Caja 1",
                "order_number": 999,
                "items": [{"qty": 1, "name": "Combo", "unit_price": "10.00", "line_total": "10.00"}],
                "totals": {"subtotal": "8.85", "iva": "1.15", "total": "10.00"},
                "payment": {"method_label_es": "Efectivo", "amount_paid": "10.00"},
                "dte": {
                    "numero_control": "DTE-01-X001X001-000000000000001",
                    "codigo_generacion": "A" * 36,
                    "fecha_dte": "2026-04-25",
                    "estado_hacienda": "PROCESADO",
                    "sello_recibido": "SELLO_TEST",
                    "fh_procesamiento": "25/04/2026 17:00:57",
                    "responsable_emisor_nombre": None,
                    "responsable_emisor_documento": "0614-010101-001-1",
                    "responsable_receptor_nombre": None,
                    "responsable_receptor_documento": None,
                },
            },
            filename="venta_999.pdf",
        )
        reader = PdfReader(BytesIO(result.pdf_bytes))
        text = (reader.pages[0].extract_text() or "").upper()
        self.assertIn("SELLO_TEST", text)
        self.assertIn("PROCESADO", text)
        self.assertIn("25/04/2026 17:00:57", text)
        self.assertNotIn("NONE", text)
        self.assertNotIn("SELLO DE RECEPCION: -", text)
