from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentMethod
from apps.users.models import UserProfile


class PaymentMethodsConfigTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = get_user_model().objects.create_user(username="admin_payment_methods", password="123456")
        UserProfile.objects.create(user=self.admin, role="admin", is_active=True)
        self.client.force_authenticate(self.admin)
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.order_type = ServiceType.objects.create(key="pedidos_ya", label="Pedidos Ya")
        self.order = Order.objects.create(
            order_number=9100,
            branch=self.branch,
            service_type=self.order_type,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
        )

    def test_create_and_update_payment_method_with_fiscal_color_default_and_order_type(self):
        response = self.client.post(
            "/api/payments/methods/",
            {
                "name": "Pedidos Ya",
                "code": "pedidos_ya",
                "is_active": True,
                "color_hex": "#F97316",
                "sort_order": 4,
                "is_default": True,
                "fiscal_payment_type": "CARD",
                "linked_order_type_id": self.order_type.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["fiscal_payment_type"], "CARD")
        self.assertEqual(response.data["color_hex"], "#F97316")
        self.assertEqual(response.data["linked_order_type_id"], self.order_type.id)

        response = self.client.patch(
            f"/api/payments/methods/{response.data['id']}/",
            {"color_hex": "#2563EB", "fiscal_payment_type": "TRANSFER", "is_default": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["color_hex"], "#2563EB")
        self.assertEqual(response.data["fiscal_payment_type"], "TRANSFER")

    def test_delete_without_history_removes_method(self):
        method = PaymentMethod.objects.create(code="apple_pay", name="Apple Pay", fiscal_payment_type="TRANSFER")
        response = self.client.delete(f"/api/payments/methods/{method.id}/")
        self.assertEqual(response.status_code, 204, response.data if hasattr(response, "data") else None)
        self.assertFalse(PaymentMethod.objects.filter(id=method.id).exists())

    def test_delete_with_history_hides_method_and_reassigns_default(self):
        fallback = PaymentMethod.objects.create(code="cash", name="Efectivo", is_cash=True, fiscal_payment_type="CASH", is_default=False, sort_order=1)
        method = PaymentMethod.objects.create(
            code="tarjeta_dup",
            name="Tarjeta duplicada",
            fiscal_payment_type="CARD",
            is_default=True,
            auto_select_order_type=self.order_type,
            sort_order=2,
        )
        Payment.objects.create(order=self.order, payment_method=method, method="card", amount=Decimal("10.00"))

        response = self.client.delete(f"/api/payments/methods/{method.id}/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["hidden"])
        method.refresh_from_db()
        fallback.refresh_from_db()
        self.assertFalse(method.is_active)
        self.assertFalse(method.is_default)
        self.assertIsNone(method.auto_select_order_type_id)
        self.assertTrue(fallback.is_default)
        self.assertIn("ventas históricas", response.data["detail"])
        active_response = self.client.get("/api/payments/methods/")
        self.assertNotIn(method.id, [item["id"] for item in active_response.data])

    def test_inactive_method_cannot_be_linked_or_default(self):
        method = PaymentMethod.objects.create(code="paypal", name="PayPal", fiscal_payment_type="TRANSFER", is_default=True)
        response = self.client.patch(
            f"/api/payments/methods/{method.id}/",
            {"is_active": False, "linked_order_type_id": self.order_type.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        method.refresh_from_db()
        self.assertFalse(method.is_active)
        self.assertFalse(method.is_default)
        self.assertIsNone(method.auto_select_order_type_id)
