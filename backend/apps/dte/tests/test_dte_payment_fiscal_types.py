from decimal import Decimal

from django.test import TestCase

from apps.core.models import Branch, ServiceType
from apps.dte.services.dte_service import get_mh_payment_info
from apps.dte.services.payment_methods import get_cat017_code_and_label
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentMethod


class DTEPaymentFiscalTypeTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="delivery", label="Delivery")
        self.order = Order.objects.create(
            order_number=9200,
            branch=self.branch,
            service_type=self.service_type,
            subtotal=Decimal("30.00"),
            tax=Decimal("0.00"),
            total=Decimal("30.00"),
        )

    def test_custom_methods_emit_only_allowed_cat017_codes(self):
        pedidos_ya = PaymentMethod.objects.create(code="pedidos_ya", name="Pedidos Ya", fiscal_payment_type="CARD")
        paypal = PaymentMethod.objects.create(code="paypal", name="PayPal", fiscal_payment_type="TRANSFER")
        cash = PaymentMethod.objects.create(code="cash", name="Efectivo", fiscal_payment_type="CASH", is_cash=True)

        self.assertEqual(get_cat017_code_and_label(type("P", (), {"payment_method": pedidos_ya, "method": "transfer"})())[0], "03")
        self.assertEqual(get_cat017_code_and_label(type("P", (), {"payment_method": paypal, "method": "card"})())[0], "05")
        self.assertEqual(get_cat017_code_and_label(type("P", (), {"payment_method": cash, "method": "transfer"})())[0], "01")

    def test_dte_groups_by_fiscal_payment_type_not_custom_code(self):
        pedidos_ya = PaymentMethod.objects.create(code="pedidos_ya", name="Pedidos Ya", fiscal_payment_type="CARD")
        Payment.objects.create(order=self.order, payment_method=pedidos_ya, method="card", amount=Decimal("30.00"), amount_applied=Decimal("30.00"))

        pagos = get_mh_payment_info(self.order)

        self.assertEqual(pagos, [{"codigo": "03", "montoPago": 30, "referencia": None, "plazo": None, "periodo": None}])
