from decimal import Decimal

from django.test import TestCase

from apps.core.models import Branch, ServiceType
from apps.orders.models import Order
from apps.payments.serializers import PaymentSerializer


class PosFullPaymentTests(TestCase):
    def setUp(self):
        branch = Branch.objects.create(name="Main", code="MAIN")
        service_type = ServiceType.objects.create(key="dine-in", label="En local")
        self.order = Order.objects.create(
            order_number=700,
            branch=branch,
            service_type=service_type,
            status="waiting_payment",
            channel="pos",
            subtotal=Decimal("10.42"),
            tax=Decimal("1.35"),
            total=Decimal("11.77"),
        )

    def test_pos_payment_rejects_partial_amount(self):
        serializer = PaymentSerializer(
            data={
                "order": self.order.id,
                "method": "cash",
                "amount": "10.00",
                "cash_received": "10.00",
                "tip_amount": "0.00",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("POS payments must be full amount", str(serializer.errors))

    def test_pos_payment_accepts_exact_total_amount(self):
        serializer = PaymentSerializer(
            data={
                "order": self.order.id,
                "method": "cash",
                "amount": "11.77",
                "cash_received": "12.00",
                "tip_amount": "0.00",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
