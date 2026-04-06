from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Modifier, ModifierGroup, Product
from apps.orders.models import Order, OrderItem, OrderItemModifier
from apps.payments.models import Payment, PaymentMethod
from apps.users.models import UserProfile


class SalesAggregatesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="reports_agg", password="pw")
        UserProfile.objects.create(user=self.user, role="manager", is_active=True)
        self.client.force_authenticate(self.user)

        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_dine = ServiceType.objects.create(key="dine_in", label="DINE IN")
        self.service_takeout = ServiceType.objects.create(key="takeout", label="Takeout")

        self.pm_cash = PaymentMethod.objects.create(code="cash", name="Efectivo", is_cash=True)
        self.pm_card = PaymentMethod.objects.create(code="card_credit", name="Tarjeta Crédito", is_cash=False)

        self.cat_burritos = Category.objects.create(name="Burritos")
        self.cat_bebidas = Category.objects.create(name="Bebidas")
        self.product_burrito = Product.objects.create(name="Burrito", category=self.cat_burritos, price="9.00")
        self.product_soda = Product.objects.create(name="Soda", category=self.cat_bebidas, price="2.00")

        self.mod_group = ModifierGroup.objects.create(name="Extras", min_selection=0, max_selection=2)
        self.mod_guac = Modifier.objects.create(group=self.mod_group, name="Guacamole", price="1.00")

    def _create_sale(
        self,
        *,
        order_number: int,
        created_at: datetime,
        service_type: ServiceType,
        payment_method: PaymentMethod,
        method: str = "cash",
        product: Product | None = None,
        quantity: int = 1,
        amount: str = "10.00",
    ):
        order = Order.objects.create(
            order_number=order_number,
            branch=self.branch,
            service_type=service_type,
            status="delivered",
            customer_name=f"Cliente {order_number}",
            subtotal=amount,
            tax="0.00",
            total=amount,
            payment_status="paid",
            financial_status="paid",
            net_paid=amount,
        )
        item = OrderItem.objects.create(
            order=order,
            product=product or self.product_burrito,
            product_name_snapshot=(product or self.product_burrito).name,
            price_snapshot=amount,
            quantity=quantity,
        )
        if product == self.product_burrito:
            OrderItemModifier.objects.create(
                order_item=item,
                modifier_name_snapshot=self.mod_guac.name,
                modifier_price_snapshot=Decimal("1.00"),
            )
        payment = Payment.objects.create(
            order=order,
            method=method,
            payment_method=payment_method,
            amount=amount,
            tip_amount="0.00",
            received_by=self.user,
        )
        Payment.objects.filter(id=payment.id).update(created_at=created_at)
        return payment

    def test_sales_timeseries_grouping_by_all_granularities(self):
        now = timezone.now()
        self._create_sale(order_number=1, created_at=now.replace(hour=8, minute=0), service_type=self.service_dine, payment_method=self.pm_cash)
        self._create_sale(order_number=2, created_at=now.replace(hour=9, minute=0), service_type=self.service_dine, payment_method=self.pm_card, method="card")

        start = now.date().isoformat()
        end = now.date().isoformat()

        for group_by in ["hour", "day", "week", "month", "year"]:
            response = self.client.get(f"/api/reports/sales-timeseries/?start={start}&end={end}&group_by={group_by}")
            self.assertEqual(response.status_code, 200)
            self.assertIn("series", response.data)
            self.assertGreaterEqual(len(response.data["series"]), 1)

    def test_sales_timeseries_accepts_date_from_and_granularity_alias(self):
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        self._create_sale(order_number=90, created_at=now, service_type=self.service_dine, payment_method=self.pm_cash, amount="12.00")
        response = self.client.get(
            f"/api/reports/sales-timeseries/?date_from={now.date().isoformat()}&date_to={now.date().isoformat()}&granularity=hours&compare_with=none"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["kpis"]["total"], "12.00")

    def test_sales_timeseries_compare_previous_period_single_day_uses_minus_7_days(self):
        target_day = date(2026, 4, 5)
        target_dt = timezone.make_aware(datetime.combine(target_day, datetime.min.time()).replace(hour=12))
        previous_week_dt = target_dt - timedelta(days=7)

        self._create_sale(
            order_number=10,
            created_at=target_dt,
            service_type=self.service_dine,
            payment_method=self.pm_cash,
            amount="15.00",
        )
        self._create_sale(
            order_number=11,
            created_at=previous_week_dt,
            service_type=self.service_dine,
            payment_method=self.pm_cash,
            amount="7.00",
        )

        response = self.client.get(
            f"/api/reports/sales-timeseries/?start={target_day.isoformat()}&end={target_day.isoformat()}&group_by=hour&compare=previous_period"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["compare"]["range"]["start"], (target_day - timedelta(days=7)).isoformat())
        self.assertEqual(response.data["compare"]["range"]["end"], (target_day - timedelta(days=7)).isoformat())
        self.assertEqual(response.data["compare_kpis"]["total"], "7.00")

    def test_sales_timeseries_compare_previous_year(self):
        current_day = date(2026, 3, 2)
        current_dt = timezone.make_aware(datetime.combine(current_day, datetime.min.time()).replace(hour=10))
        prev_year_dt = timezone.make_aware(datetime.combine(date(2025, 3, 2), datetime.min.time()).replace(hour=10))

        self._create_sale(order_number=20, created_at=current_dt, service_type=self.service_dine, payment_method=self.pm_cash, amount="20.00")
        self._create_sale(order_number=21, created_at=prev_year_dt, service_type=self.service_dine, payment_method=self.pm_cash, amount="9.00")

        response = self.client.get(
            f"/api/reports/sales-timeseries/?start={current_day.isoformat()}&end={current_day.isoformat()}&group_by=day&compare=previous_year"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["compare"]["range"]["start"], "2025-03-02")
        self.assertEqual(response.data["compare_kpis"]["total"], "9.00")

    def test_sales_breakdown_applies_category_product_and_payment_filters(self):
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        self._create_sale(
            order_number=30,
            created_at=now,
            service_type=self.service_dine,
            payment_method=self.pm_cash,
            product=self.product_burrito,
            amount="10.00",
        )
        self._create_sale(
            order_number=31,
            created_at=now,
            service_type=self.service_takeout,
            payment_method=self.pm_card,
            method="card",
            product=self.product_soda,
            amount="5.00",
        )

        start = now.date().isoformat()
        end = now.date().isoformat()
        response = self.client.get(
            f"/api/reports/sales-breakdown/?start={start}&end={end}&dimension=category&category_ids={self.cat_burritos.id}&product_ids={self.product_burrito.id}&payment_method=cash"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["name"], self.cat_burritos.name)
