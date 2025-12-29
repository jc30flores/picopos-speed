from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from apps.core.models import Branch, ServiceType, TaxConfig
from apps.menu.models import Category, Product
from apps.orders.models import Order


class Command(BaseCommand):
    help = "Run basic ORM and API checks for tax, discounts, reports, and order creation."

    def handle(self, *args, **options):
        branch, _ = Branch.objects.get_or_create(code="CENTRO", defaults={"name": "Sucursal Centro"})
        ServiceType.objects.get_or_create(key="dine-in", defaults={"label": "En local"})
        TaxConfig.objects.get_or_create(name="IVA", defaults={"rate": Decimal("0.13"), "is_active": True})

        category, _ = Category.objects.get_or_create(name="Test")
        product, _ = Product.objects.get_or_create(
            name="Producto Test",
            defaults={"description": "Test", "price": Decimal("11.30"), "category": category, "available": True},
        )

        client = Client()

        tax_response = client.get("/api/core/tax-config/active/")
        if tax_response.status_code != 200:
            raise CommandError("Tax config endpoint failed")
        tax_rate = Decimal(str(tax_response.json().get("rate")))
        if tax_rate != Decimal("0.13"):
            raise CommandError(f"Unexpected tax rate: {tax_rate}")

        discounts_response = client.get("/api/menu/discounts/")
        if discounts_response.status_code != 200:
            raise CommandError("Discounts endpoint failed")

        report_response = client.get("/api/reports/sales/")
        if report_response.status_code != 200:
            raise CommandError("Sales report endpoint failed")

        order_payload = {
            "service_type_key": "dine-in",
            "customer_name": "Test",
            "items": [
                {
                    "product_id": product.id,
                    "product_name_snapshot": product.name,
                    "price_snapshot": str(product.price),
                    "quantity": 1,
                    "modifiers": [],
                }
            ],
        }
        order_response = client.post("/api/orders/", data=order_payload, content_type="application/json")
        if order_response.status_code != 201:
            raise CommandError("Order creation failed")
        order_data = order_response.json()
        total = Decimal(str(order_data.get("total")))
        expected_subtotal = (total / Decimal("1.13")).quantize(Decimal("0.01"))
        expected_tax = (total - expected_subtotal).quantize(Decimal("0.01"))
        if Decimal(str(order_data.get("tax"))) != expected_tax:
            raise CommandError("Tax calculation mismatch")

        self.stdout.write(f"Categories: {Category.objects.count()}")
        self.stdout.write(f"Products: {Product.objects.count()}")
        self.stdout.write(f"Orders: {Order.objects.count()}")
