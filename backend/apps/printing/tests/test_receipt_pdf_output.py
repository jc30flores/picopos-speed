from pathlib import Path
from io import BytesIO

from django.conf import settings
from django.test import SimpleTestCase
try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

from apps.printing.receipt_pdf import build_receipt_pdf


class ReceiptPdfOutputTests(SimpleTestCase):
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

        resources = reader.pages[0].get("/Resources", {})
        xobjects = resources.get("/XObject", {}) if resources else {}
        image_count = 0
        for xobj in xobjects.values():
            resolved = xobj.get_object()
            if resolved.get("/Subtype") == "/Image":
                image_count += 1
        self.assertGreaterEqual(image_count, 1)
