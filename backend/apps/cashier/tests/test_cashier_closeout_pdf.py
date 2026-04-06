from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.cashier.models import CashSession, Register
from apps.cashier.printing import _fallback_pdf_bytes, build_end_of_day_ticket, build_end_of_day_ticket_pdf
from apps.core.models import Branch
from apps.dte.models import DTEBranchConfig
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentMethod
from apps.users.models import UserProfile


class CashierCloseoutPdfTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="cash_pdf", password="pw")
        UserProfile.objects.create(user=user, role="cashier", is_active=True)
        self.branch_centro = Branch.objects.create(id=1, name="Sucursal Centro", code="CENTRO")
        self.branch_monaco = Branch.objects.create(id=5, name="Plaza Monaco", code="PLAZA_MONACO")
        DTEBranchConfig.objects.create(branch=self.branch_centro, is_active=True, direccion_complemento="Centro histórico, San Salvador")
        DTEBranchConfig.objects.create(branch=self.branch_monaco, is_active=True, direccion_complemento="Plaza Monaco, Antiguo Cuscatlán")
        self.register = Register.objects.create(name="CAJA 1", station_name="POS 1", branch=self.branch_centro, is_active=True)
        self.user = user
        self.payment_methods = {
            "cash": PaymentMethod.objects.create(code="cash", name="Efectivo"),
            "card": PaymentMethod.objects.create(code="card", name="Tarjeta"),
            "transfer": PaymentMethod.objects.create(code="transfer", name="Transferencia"),
            "paypal": PaymentMethod.objects.create(code="paypal", name="PayPal"),
            "pedidos_ya": PaymentMethod.objects.create(code="pedidos_ya", name="PedidosYa"),
        }

    def _create_order(self, order_number: int = 1, total: str = "1.00") -> Order:
        return Order.objects.create(
            order_number=order_number,
            branch=self.register.branch,
            total=Decimal(total),
            subtotal=Decimal(total),
            tax=Decimal("0.00"),
            financial_status="paid",
            payment_status="paid",
        )

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

    @override_settings(BRANCH_ID=5)
    def test_closeout_pdf_uses_branch_from_env_and_dte_address(self):
        session = CashSession.objects.create(
            register=self.register,
            opened_by=self.user,
            status="closed",
            opening_cash="10.00",
        )
        pdf_bytes = build_end_of_day_ticket_pdf(session.id).upper()
        self.assertIn("PLAZA MONACO".encode("latin-1"), pdf_bytes)
        self.assertIn("ANTIGUO CUSCATL".encode("latin-1"), pdf_bytes)

    @override_settings(BRANCH_ID=1)
    def test_closeout_pdf_payment_breakdown_includes_all_methods_and_total_matches(self):
        session = CashSession.objects.create(
            register=self.register,
            opened_by=self.user,
            status="closed",
            opening_cash="10.00",
        )
        order = self._create_order(order_number=77, total="31.00")
        Payment.objects.create(order=order, payment_method=self.payment_methods["cash"], method="cash", amount="5.00", tip_amount="0.00", cash_session=session)
        Payment.objects.create(order=order, payment_method=self.payment_methods["card"], method="card", card_type="debit", amount="7.00", tip_amount="0.00", cash_session=session)
        Payment.objects.create(order=order, payment_method=self.payment_methods["card"], method="card", card_type="credit", amount="8.00", tip_amount="0.00", cash_session=session)
        Payment.objects.create(order=order, payment_method=self.payment_methods["transfer"], method="transfer", amount="4.00", tip_amount="0.00", cash_session=session)
        Payment.objects.create(order=order, payment_method=self.payment_methods["paypal"], method="transfer", amount="3.00", tip_amount="0.00", cash_session=session)
        Payment.objects.create(order=order, payment_method=self.payment_methods["pedidos_ya"], method="transfer", amount="4.00", tip_amount="0.00", cash_session=session)

        text = build_end_of_day_ticket(session.id).upper()
        self.assertIn("SUCURSAL CENTRO", text)
        self.assertIn("EFECTIVO(1)", text)
        self.assertIn("T. DEBITO(1)", text)
        self.assertIn("T. CREDITO(1)", text)
        self.assertIn("TRANSFERENCIA(1)", text)
        self.assertIn("PAYPAL(1)", text)
        self.assertIn("PEDIDOS YA(1)", text)
        self.assertIn("$31.00", text)
