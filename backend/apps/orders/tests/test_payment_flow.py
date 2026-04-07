import re
from decimal import Decimal

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.core.models import Branch, Customer, ServiceType
from apps.cashier.models import CashSession, Register
from apps.menu.models import Category, Product
from apps.orders.models import Order, OrderItem
from apps.users.models import UserProfile


class OrderPaymentFlowTests(TestCase):
    @staticmethod
    def _extract_media_box_width(pdf_bytes: bytes) -> float:
        match = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)\s*\]", pdf_bytes)
        if not match:
            raise AssertionError("No se encontró MediaBox en el PDF.")
        return float(match.group(1))

    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="cashier_order_payment", password="123456")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)
        self.client.force_authenticate(self.user)
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine-in", label="En local")
        self.category = Category.objects.create(name="ALMUERZO")
        self.customer = Customer.objects.create(
            name="CONSUMIDOR FINAL",
            full_name="CONSUMIDOR FINAL",
            client_type="CF",
            is_default_consumer_final=True,
            department_code="01",
            municipality_code="01",
        )
        self.product = Product.objects.create(
            name="Plato Test",
            description="",
            price=Decimal("10.00"),
            category=self.category,
            image=None,
            available=True,
        )

    def test_order_waiting_payment_then_preparing_on_payment(self):
        order = Order.objects.create(
            order_number=101,
            branch=self.branch,
            service_type=self.service_type,
            status="waiting_payment",
            customer=self.customer,
            customer_name=self.customer.name,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
            discount_total=Decimal("0.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name_snapshot=self.product.name,
            price_snapshot=self.product.price,
            quantity=1,
        )

        response = self.client.post(
            "/api/payments/",
            {
                "order": order.id,
                "method": "cash",
                "amount": "10.00",
                "tip_amount": "0.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        order.refresh_from_db()
        self.assertEqual(order.status, "preparing")

    def test_patch_order_customer_returns_full_totals_payload(self):
        alt_customer = Customer.objects.create(
            name="IGNACIO RAMIREZ",
            full_name="IGNACIO RAMIREZ",
            client_type="CF",
            department_code="01",
            municipality_code="01",
        )
        order = Order.objects.create(
            order_number=102,
            branch=self.branch,
            service_type=self.service_type,
            status="waiting_payment",
            customer=self.customer,
            customer_name=self.customer.name,
            subtotal=Decimal("20.00"),
            tax=Decimal("0.00"),
            total=Decimal("20.00"),
            discount_total=Decimal("0.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name_snapshot=self.product.name,
            price_snapshot=self.product.price,
            quantity=2,
        )

        response = self.client.patch(
            f"/api/orders/{order.id}/",
            {
                "customer_id": alt_customer.id,
                "dte_document_type": "CF",
                "iva_exempt": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("customer_id"), alt_customer.id)
        self.assertEqual(payload.get("total"), "20.00")
        self.assertIn("remaining", payload)
        self.assertIn("subtotal_before_discounts", payload)

    def test_payment_ticket_pdf_endpoint_returns_readable_pdf(self):
        order = Order.objects.create(
            order_number=103,
            branch=self.branch,
            service_type=self.service_type,
            status="waiting_payment",
            customer=self.customer,
            customer_name=self.customer.name,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
            discount_total=Decimal("0.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name_snapshot=self.product.name,
            price_snapshot=self.product.price,
            quantity=1,
        )
        payment_response = self.client.post(
            "/api/payments/",
            {
                "order": order.id,
                "method": "cash",
                "amount": "10.00",
                "tip_amount": "0.00",
            },
            format="json",
        )
        self.assertEqual(payment_response.status_code, 201)
        payment_id = payment_response.json()["id"]
        pdf_response = self.client.get(f"/api/payments/{payment_id}/ticket.pdf", HTTP_ACCEPT="text/html")
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        self.assertIn(b"%PDF", pdf_response.content[:10])
        self.assertIn(b"ORDEN", pdf_response.content.upper())

    @override_settings(PRINTER_SIZE=80)
    def test_payment_ticket_pdf_respects_printer_size_width_80mm(self):
        order = Order.objects.create(
            order_number=104,
            branch=self.branch,
            service_type=self.service_type,
            status="waiting_payment",
            customer=self.customer,
            customer_name=self.customer.name,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
            discount_total=Decimal("0.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name_snapshot=self.product.name,
            price_snapshot=self.product.price,
            quantity=1,
        )
        payment_response = self.client.post(
            "/api/payments/",
            {"order": order.id, "method": "cash", "amount": "10.00", "tip_amount": "0.00"},
            format="json",
        )
        self.assertEqual(payment_response.status_code, 201)
        payment_id = payment_response.json()["id"]
        pdf_response = self.client.get(f"/api/payments/{payment_id}/ticket.pdf", HTTP_ACCEPT="text/html")
        self.assertEqual(pdf_response.status_code, 200)
        self.assertRegex(
            pdf_response["Content-Disposition"],
            r'attachment; filename="venta_104_\\d{4}-\\d{2}-\\d{2}_\\d{2}-\\d{2}\\.pdf"',
        )
        width = self._extract_media_box_width(pdf_response.content)
        self.assertAlmostEqual(width, 80 * 72 / 25.4, delta=1.0)
        self.assertLess(width, 400.0)

    def test_create_order_requires_open_cash_session_when_register_exists(self):
        Register.objects.create(name="Caja 1", station_name="POS 1", branch=self.branch, is_active=True)
        response = self.client.post(
            "/api/orders/",
            {
                "branch_id": self.branch.id,
                "service_type_key": "dine-in",
                "items": [
                    {
                        "product_id": self.product.id,
                        "product_name_snapshot": self.product.name,
                        "price_snapshot": "10.00",
                        "quantity": 1,
                        "modifiers": [],
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json().get("code"), "CASH_SESSION_REQUIRED")

    def test_create_order_allows_when_open_session_exists_for_branch(self):
        register = Register.objects.create(name="Caja 1", station_name="POS 1", branch=self.branch, is_active=True)
        CashSession.objects.create(register=register, opened_by=self.user, opening_cash=Decimal("20.00"), status="open")
        response = self.client.post(
            "/api/orders/",
            {
                "branch_id": self.branch.id,
                "service_type_key": "dine-in",
                "items": [
                    {
                        "product_id": self.product.id,
                        "product_name_snapshot": self.product.name,
                        "price_snapshot": "10.00",
                        "quantity": 1,
                        "modifiers": [],
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())

    def test_create_payment_requires_open_cash_session_when_register_exists(self):
        Register.objects.create(name="Caja 1", station_name="POS 1", branch=self.branch, is_active=True)
        order = Order.objects.create(
            order_number=105,
            branch=self.branch,
            service_type=self.service_type,
            status="waiting_payment",
            customer=self.customer,
            customer_name=self.customer.name,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
            discount_total=Decimal("0.00"),
        )
        response = self.client.post(
            "/api/payments/",
            {"order": order.id, "method": "cash", "amount": "10.00", "tip_amount": "0.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json().get("code"), "CASH_SESSION_REQUIRED")
