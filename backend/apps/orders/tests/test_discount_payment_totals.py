from datetime import datetime, time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Discount, DiscountRuleTarget, Product
from apps.orders.models import DiningArea, Order, OrderItem, RestaurantTable, TableGuest, TableSession, TableSessionTable
from apps.orders.serializers import OrderCreateSerializer, OrderSerializer
from apps.orders.services.totals import calculate_order_totals, calculate_person_totals, split_cents_evenly
from apps.payments.models import PaymentMethod
from apps.printing.services.renderers import render_customer_ticket
from apps.users.models import UserProfile


class DiscountedPaymentTotalsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="discount_cashier", password="pw")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)
        self.client.force_authenticate(self.user)
        self.branch = Branch.objects.create(name="Sucursal", code="DISC")
        self.service_type = ServiceType.objects.create(key="MESA", label="Mesa")
        self.category = Category.objects.create(name="MARISCOS")
        self.shrimp = Product.objects.create(
            name="Camarones empanizados",
            description="",
            price=Decimal("5.99"),
            category=self.category,
            available=True,
            requires_kitchen=True,
        )
        self.ineligible = Product.objects.create(
            name="Agua mineral",
            description="",
            price=Decimal("2.00"),
            category=self.category,
            available=True,
        )
        self.person_one_plate = Product.objects.create(
            name="Consumo Persona 1",
            description="",
            price=Decimal("35.97"),
            category=self.category,
            available=True,
        )
        self.person_two_plate = Product.objects.create(
            name="Consumo Persona 2",
            description="",
            price=Decimal("11.99"),
            category=self.category,
            available=True,
        )
        self.discount = Discount.objects.create(
            name="DESCUENTO ESTUDIANTE",
            type="fixed",
            value=Decimal("1.50"),
            applies_to="products",
            is_active=True,
            auto_apply=False,
        )
        DiscountRuleTarget.objects.create(discount=self.discount, product=self.shrimp)
        self.card_method = PaymentMethod.objects.create(code="card", name="Tarjeta", fiscal_payment_type=PaymentMethod.FISCAL_CARD)
        self.cash_method = PaymentMethod.objects.create(code="cash", name="Efectivo", fiscal_payment_type=PaymentMethod.FISCAL_CASH)

    def _order(self, items, *, discount=True) -> Order:
        serializer = OrderCreateSerializer(
            data={
                "branch_id": self.branch.id,
                "service_type_key": self.service_type.key,
                "manual_discount_id": self.discount.id if discount else None,
                "discount_mode": "manual" if discount else None,
                "items": items,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        return Order.objects.get(pk=order.pk)

    def _shrimp_item(self, *, quantity=1, table_guest_id=None):
        return {
            "product_id": self.shrimp.id,
            "product_name_snapshot": self.shrimp.name,
            "price_snapshot": "5.99",
            "quantity": quantity,
            "table_guest_id": table_guest_id,
            "modifiers": [],
        }

    def _payment_payload(self, order, amount, method, payment_method, **extra):
        payload = {
            "order": order.id,
            "method": method,
            "payment_method": payment_method.id,
            "amount": str(amount),
            "amount_applied": str(amount),
            "tip_amount": "0.00",
        }
        if method == "cash":
            payload["cash_received"] = str(amount)
        payload.update(extra)
        return payload

    def test_single_discounted_product_totals_and_ticket(self):
        order = self._order([self._shrimp_item()])

        totals = calculate_order_totals(order)
        self.assertEqual(totals.subtotal, Decimal("5.99"))
        self.assertEqual(totals.discount_total, Decimal("1.50"))
        self.assertEqual(totals.total, Decimal("4.49"))
        self.assertEqual(totals.amount_due, Decimal("4.49"))

        payload = OrderSerializer(order).data
        self.assertEqual(Decimal(str(payload["discount_total"])), Decimal("1.50"))
        self.assertEqual(Decimal(str(payload["total_payable"])), Decimal("4.49"))
        self.assertEqual(Decimal(str(payload["remaining"])), Decimal("4.49"))

        ticket = render_customer_ticket(order)["text"]
        self.assertIn("Descuento", ticket)
        self.assertIn("$4.49", ticket)

    def test_two_discounted_products_preserve_discount_when_pending_and_kitchen_states_change(self):
        order = self._order([self._shrimp_item(), self._shrimp_item()])
        first, second = list(order.items.order_by("id"))
        first.kitchen_status = OrderItem.KITCHEN_STATUS_SENT
        first.save(update_fields=["kitchen_status"])

        response = self.client.post(
            f"/api/orders/{order.id}/pending/",
            {
                "is_pending": True,
                "pending_state": "pending_payment",
                "pending_reference": "CODEX smoke descuento",
                "items": [
                    {**self._shrimp_item(), "source_order_item_id": first.id},
                    {**self._shrimp_item(), "source_order_item_id": second.id},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        totals = calculate_order_totals(order)
        payload = OrderSerializer(order).data
        statuses = set(order.items.values_list("kitchen_status", flat=True))
        self.assertEqual(totals.subtotal, Decimal("11.98"))
        self.assertEqual(totals.discount_total, Decimal("3.00"))
        self.assertEqual(totals.total, Decimal("8.98"))
        self.assertEqual(Decimal(str(payload["subtotal_before_discounts"])), Decimal("11.98"))
        self.assertEqual(Decimal(str(payload["total_payable"])), Decimal("8.98"))
        self.assertEqual(order.amount_due_cents, 898)
        self.assertEqual(statuses, {OrderItem.KITCHEN_STATUS_PENDING, OrderItem.KITCHEN_STATUS_SENT})

    def test_quantity_change_and_item_delete_recalculate_discount(self):
        order = self._order([self._shrimp_item(quantity=2)])
        self.assertEqual(order.discount_total, Decimal("3.00"))
        self.assertEqual(order.total, Decimal("8.98"))

        item = order.items.first()
        response = self.client.post(
            f"/api/orders/{order.id}/pending/",
            {
                "is_pending": True,
                "pending_state": "pending_payment",
                "pending_reference": "CODEX smoke cantidad",
                "items": [{**self._shrimp_item(quantity=1), "source_order_item_id": item.id}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        self.assertEqual(order.discount_total, Decimal("1.50"))
        self.assertEqual(order.total, Decimal("4.49"))

        other = self._order([self._shrimp_item(), self._shrimp_item()])
        keep = other.items.order_by("id").first()
        response = self.client.post(
            f"/api/orders/{other.id}/pending/",
            {
                "is_pending": True,
                "pending_state": "pending_payment",
                "pending_reference": "CODEX smoke eliminar",
                "items": [{**self._shrimp_item(), "source_order_item_id": keep.id}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        other.refresh_from_db()
        self.assertEqual(other.discount_total, Decimal("1.50"))
        self.assertEqual(other.total, Decimal("4.49"))

    def test_partial_and_mixed_payments_use_net_balance_once(self):
        order = self._order([self._shrimp_item(), self._shrimp_item()])

        first = self.client.post(
            "/api/payments/",
            self._payment_payload(order, "4.00", "card", self.card_method),
            format="json",
        )
        self.assertEqual(first.status_code, 201, first.data)
        order.refresh_from_db()
        self.assertEqual(order.discount_total, Decimal("3.00"))
        self.assertEqual(order.payment_status, "partial")
        self.assertEqual(OrderSerializer(order).data["remaining"], Decimal("4.98"))

        second = self.client.post(
            "/api/payments/",
            self._payment_payload(order, "4.98", "cash", self.cash_method),
            format="json",
        )
        self.assertEqual(second.status_code, 201, second.data)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.net_paid, Decimal("8.98"))
        self.assertEqual(OrderSerializer(order).data["remaining"], Decimal("0.00"))

    def test_ineligible_product_does_not_receive_discount(self):
        order = self._order(
            [
                {
                    "product_id": self.ineligible.id,
                    "product_name_snapshot": self.ineligible.name,
                    "price_snapshot": "2.00",
                    "quantity": 1,
                    "modifiers": [],
                }
            ]
        )

        self.assertEqual(order.discount_total, Decimal("0.00"))
        self.assertEqual(order.total, Decimal("2.00"))

    def test_split_by_person_and_equal_parts_are_net_and_exact(self):
        area = DiningArea.objects.create(name="Salón")
        table = RestaurantTable.objects.create(area=area, name="Mesa 1", number=1, capacity=3)
        session = TableSession.objects.create(
            guests_count=3,
            order_mode=TableSession.ORDER_MODE_PER_PERSON,
            opened_by=self.user,
        )
        TableSessionTable.objects.create(session=session, table=table)
        guest_1 = TableGuest.objects.create(session=session, label="Persona 1", seat_number=1)
        guest_2 = TableGuest.objects.create(session=session, label="Persona 2", seat_number=2)

        order = self._order(
            [
                self._shrimp_item(table_guest_id=guest_1.id),
                self._shrimp_item(table_guest_id=guest_1.id),
                {
                    "product_id": self.ineligible.id,
                    "product_name_snapshot": self.ineligible.name,
                    "price_snapshot": "2.00",
                    "quantity": 1,
                    "table_guest_id": guest_2.id,
                    "modifiers": [],
                },
            ]
        )
        session.primary_order = order
        session.save(update_fields=["primary_order"])

        person_1 = calculate_person_totals(order, guest_1)
        person_2 = calculate_person_totals(order, guest_2)
        self.assertEqual(person_1["subtotal"], Decimal("11.98"))
        self.assertEqual(person_1["discount_total"], Decimal("3.00"))
        self.assertEqual(person_1["amount_due"], Decimal("8.98"))
        self.assertEqual(person_2["discount_total"], Decimal("0.00"))
        self.assertEqual(person_1["total"] + person_2["total"], calculate_order_totals(order).total)
        self.assertEqual(split_cents_evenly(898, 3), [299, 299, 300])

    def test_large_table_capture_case_uses_net_total_for_person_and_equal_splits(self):
        area = DiningArea.objects.create(name="Salón")
        table = RestaurantTable.objects.create(area=area, name="Mesa 1", number=1, capacity=3)
        session = TableSession.objects.create(
            guests_count=3,
            order_mode=TableSession.ORDER_MODE_PER_PERSON,
            opened_by=self.user,
        )
        TableSessionTable.objects.create(session=session, table=table)
        guest_1 = TableGuest.objects.create(session=session, label="Persona 1", seat_number=1)
        guest_2 = TableGuest.objects.create(session=session, label="Persona 2", seat_number=2)
        guest_3 = TableGuest.objects.create(session=session, label="Persona 3", seat_number=3)

        order = self._order(
            [
                {
                    "product_id": self.person_one_plate.id,
                    "product_name_snapshot": self.person_one_plate.name,
                    "price_snapshot": "35.97",
                    "quantity": 1,
                    "table_guest_id": guest_1.id,
                    "modifiers": [],
                },
                {
                    "product_id": self.person_two_plate.id,
                    "product_name_snapshot": self.person_two_plate.name,
                    "price_snapshot": "11.99",
                    "quantity": 1,
                    "table_guest_id": guest_2.id,
                    "modifiers": [],
                },
                self._shrimp_item(table_guest_id=guest_3.id),
            ]
        )
        session.primary_order = order
        session.save(update_fields=["primary_order"])

        totals = calculate_order_totals(order)
        payload = OrderSerializer(order).data
        person_1 = calculate_person_totals(order, guest_1)
        person_2 = calculate_person_totals(order, guest_2)
        person_3 = calculate_person_totals(order, guest_3)

        self.assertEqual(totals.subtotal, Decimal("53.95"))
        self.assertEqual(totals.discount_total, Decimal("1.50"))
        self.assertEqual(totals.total, Decimal("52.45"))
        self.assertEqual(totals.amount_due, Decimal("52.45"))
        self.assertEqual(Decimal(str(payload["gross_subtotal"])), Decimal("53.95"))
        self.assertEqual(Decimal(str(payload["discount_total"])), Decimal("1.50"))
        self.assertEqual(Decimal(str(payload["net_total"])), Decimal("52.45"))
        self.assertEqual(Decimal(str(payload["amount_due"])), Decimal("52.45"))
        self.assertEqual(person_1["amount_due"], Decimal("35.97"))
        self.assertEqual(person_2["amount_due"], Decimal("11.99"))
        self.assertEqual(person_3["amount_due"], Decimal("4.49"))
        self.assertEqual(person_1["amount_due"] + person_2["amount_due"] + person_3["amount_due"], totals.amount_due)
        self.assertEqual(split_cents_evenly(totals.amount_due_cents, 2), [2622, 2623])
        self.assertEqual(split_cents_evenly(totals.amount_due_cents, 3), [1748, 1748, 1749])

    def test_same_equal_part_cannot_be_paid_twice(self):
        order = self._order([self._shrimp_item(), self._shrimp_item()])

        first = self.client.post(
            "/api/payments/",
            self._payment_payload(order, "2.99", "card", self.card_method, split_part=1, payment_scope="split_part"),
            format="json",
        )
        self.assertEqual(first.status_code, 201, first.data)

        duplicate = self.client.post(
            "/api/payments/",
            self._payment_payload(order, "2.99", "card", self.card_method, split_part=1, payment_scope="split_part"),
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.data["detail"], "Esta parte ya fue pagada.")

    def test_table_pending_order_sets_mesa_service_and_preserves_auto_snapshot_after_kitchen(self):
        auto_discount = Discount.objects.create(
            name="DESCUENTO ESTUDIANTE AUTO",
            type="percent",
            value=Decimal("25.00"),
            applies_to="products",
            is_active=True,
            auto_apply=True,
            service_types=["MESA"],
            days_of_week=[1, 2, 3, 4, 5, 6],
            start_time=time(11, 0),
            end_time=time(14, 0),
            min_amount=Decimal("0.00"),
        )
        DiscountRuleTarget.objects.create(discount=auto_discount, product=self.shrimp)
        area = DiningArea.objects.create(name="Salón snapshot")
        table = RestaurantTable.objects.create(area=area, name="Mesa 2", number=2, capacity=2)
        order = Order.objects.create(order_number=701, branch=self.branch, status="new", is_pending=True, pending_state="pending_payment")
        session = TableSession.objects.create(
            guests_count=2,
            order_mode=TableSession.ORDER_MODE_TABLE,
            opened_by=self.user,
            primary_order=order,
        )
        TableSessionTable.objects.create(session=session, table=table)

        valid_time = timezone.make_aware(datetime(2026, 7, 27, 13, 16, 0))
        with patch("apps.orders.discount_engine.timezone.now", return_value=valid_time):
            response = self.client.post(
                f"/api/orders/{order.id}/pending/",
                {
                    "is_pending": True,
                    "pending_state": "in_kitchen",
                    "pending_reference": "Mesa 2",
                    "items": [self._shrimp_item()],
                },
                format="json",
            )
        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        self.assertEqual(order.service_type.key, "MESA")
        self.assertEqual(order.discount_total, Decimal("1.50"))
        self.assertEqual(order.total, Decimal("4.49"))
        self.assertEqual(order.discount_snapshot.get("mode"), "auto")
        first_item_id = order.items.first().id

        order.send_to_kitchen = True
        order.save(update_fields=["send_to_kitchen", "updated_at"])
        session.status = TableSession.STATUS_SENT_TO_KITCHEN
        session.save(update_fields=["status", "updated_at"])
        outside_time = timezone.make_aware(datetime(2026, 7, 27, 14, 30, 0))
        with patch("apps.orders.discount_engine.timezone.now", return_value=outside_time):
            response = self.client.post(
                f"/api/orders/{order.id}/pending/",
                {
                    "is_pending": True,
                    "pending_state": "in_kitchen",
                    "pending_reference": "Mesa 2",
                    "items": [{**self._shrimp_item(), "source_order_item_id": first_item_id}],
                },
                format="json",
            )
        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        self.assertEqual(order.discount_total, Decimal("1.50"))
        self.assertEqual(order.total, Decimal("4.49"))
        self.assertEqual(order.amount_due_cents, 449)
        self.assertEqual(order.items.first().discount_amount, Decimal("1.50"))
