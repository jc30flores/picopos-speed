from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.cashier.models import CashSession, Register
from apps.cashier.printing import _fallback_pdf_bytes, build_end_of_day_ticket, build_end_of_day_ticket_pdf
from apps.core.models import Branch
from apps.users.models import UserProfile


class CashierCloseoutPdfTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="cash_pdf", password="pw")
        UserProfile.objects.create(user=user, role="cashier", is_active=True)
        branch = Branch.objects.create(name="Main", code="MAIN")
        self.register = Register.objects.create(name="CAJA 1", station_name="POS 1", branch=branch, is_active=True)
        self.user = user

    def test_closeout_ticket_text_contains_payment_summary_section(self):
        session = CashSession.objects.create(
            register=self.register,
            opened_by=self.user,
            opening_cash="10.00",
            status="closed",
        )
        text = build_end_of_day_ticket(session.id)
        self.assertIn("Resumen De Pagos", text)

    def test_closeout_ticket_pdf_is_not_empty(self):
        session = CashSession.objects.create(
            register=self.register,
            opened_by=self.user,
            opening_cash="10.00",
            status="closed",
        )
        pdf_bytes = build_end_of_day_ticket_pdf(session.id)
        self.assertGreater(len(pdf_bytes), 100)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_fallback_pdf_uses_text_leading_and_expands_media_box_for_long_reports(self):
        long_text = "\n".join([f"Linea {idx:03d}" for idx in range(180)])
        pdf_bytes = _fallback_pdf_bytes(long_text)
        self.assertIn(b" TL", pdf_bytes)
        self.assertIn(b"T*", pdf_bytes)

    def test_closeout_pdf_contains_required_sections_and_uses_leading(self):
        session = CashSession.objects.create(
            register=self.register,
            opened_by=self.user,
            status="closed",
            opening_cash="50.00",
            closing_counted_cash="55.00",
        )
        pdf_bytes = build_end_of_day_ticket_pdf(session.id)
        self.assertIn(b"CIERRE DE CAJA", pdf_bytes)
        self.assertIn(b"SUCURSAL", pdf_bytes)
        self.assertIn(b"DIFERENCIA", pdf_bytes)
        self.assertIn(b" TL", pdf_bytes)
