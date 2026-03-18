from decimal import Decimal

from django.test import TestCase

from apps.core.models import Branch, ServiceType
from apps.orders.models import Order
from apps.payments.serializers import PaymentSerializer


class PosPaymentAmountTests(TestCase):
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

    def test_pos_payment_accepts_partial_amount(self):
        serializer = PaymentSerializer(
            data={
                "order": self.order.id,
                "method": "cash",
                "amount": "10.00",
                "cash_received": "10.00",
                "tip_amount": "0.00",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_pos_partial_then_remaining_payment_is_valid(self):
        first_payment = PaymentSerializer(
            data={
                "order": self.order.id,
                "method": "cash",
                "amount": "5.00",
                "cash_received": "5.00",
                "tip_amount": "0.00",
            }
        )
        self.assertTrue(first_payment.is_valid(), first_payment.errors)
        first_payment.save()

        second_payment = PaymentSerializer(
            data={
                "order": self.order.id,
                "method": "cash",
                "amount": "6.77",
                "cash_received": "7.00",
                "tip_amount": "0.00",
            }
        )
        self.assertTrue(second_payment.is_valid(), second_payment.errors)

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
