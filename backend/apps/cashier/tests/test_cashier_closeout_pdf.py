from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.cashier.models import CashSession, Register
from apps.cashier.printing import build_end_of_day_ticket, build_end_of_day_ticket_pdf
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
