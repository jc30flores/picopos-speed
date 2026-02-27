from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from apps.orders.models import Order, OrderItem, OrderItemModifier, AppliedDiscount, OrderInvoice, OrderFee
from apps.menu.models import Product, Discount, Modifier
from apps.core.models import Branch, ServiceType, Table, TaxConfig
from apps.payments.models import Payment


class OrderItemModifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItemModifier
        fields = ["id", "modifier_name_snapshot", "modifier_price_snapshot"]


class OrderItemSerializer(serializers.ModelSerializer):
    applied_modifiers = OrderItemModifierSerializer(many=True, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_id",
            "product_name_snapshot",
            "price_snapshot",
            "quantity",
            "applied_modifiers",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    service_type = serializers.CharField(source="service_type.key", read_only=True)
    discounts_applied = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    financial_status = serializers.CharField(read_only=True)
    refund_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    net_paid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    fees = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "customer_name",
            "subtotal",
            "tax",
            "total",
            "discount_total",
            "disposable_total",
            "payment_status",
            "financial_status",
            "total_paid",
            "remaining",
            "refund_total",
            "net_paid",
            "service_type",
            "branch_id",
            "table_id",
            "created_at",
            "items",
            "discounts_applied",
            "channel",
            "requires_kitchen",
            "fees",
        ]

    def get_fees(self, obj: Order):
        return [
            {
                "type": fee.fee_type,
                "name": fee.fee_name,
                "unit_amount": fee.unit_amount,
                "quantity": fee.quantity,
                "total_amount": fee.total_amount,
            }
            for fee in obj.fees.all()
        ]

    def get_discounts_applied(self, obj: Order):
        return [
            {
                "name": discount.discount_name_snapshot,
                "type": discount.discount_type_snapshot,
                "value": discount.discount_value_snapshot,
                "amount": discount.amount_discounted,
            }
            for discount in obj.applied_discounts.all()
        ]

    def get_total_paid(self, obj: Order):
        total = Payment.objects.filter(order=obj).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_amount"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
        )["total"] or Decimal("0")
        return total

    def get_remaining(self, obj: Order):
        total_paid = self.get_total_paid(obj)
        remaining = (obj.total - total_paid).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return remaining


class AppliedModifierInputSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    name = serializers.CharField(required=False, allow_blank=True)
    price = serializers.DecimalField(max_digits=8, decimal_places=2, required=False)



class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    product_name_snapshot = serializers.CharField()
    price_snapshot = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField(min_value=1)
    modifiers = AppliedModifierInputSerializer(many=True, required=False)


class OrderCreateSerializer(serializers.Serializer):
    branch_id = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False)
    service_type_id = serializers.IntegerField(required=False)
    service_type_key = serializers.CharField(required=False, allow_blank=True)
    table_id = serializers.PrimaryKeyRelatedField(queryset=Table.objects.all(), required=False, allow_null=True)
    customer_name = serializers.CharField(required=False, allow_blank=True)
    source = serializers.CharField(required=False, allow_blank=True)
    channel = serializers.CharField(required=False, allow_blank=True)
    fast_pos_mode = serializers.BooleanField(required=False, default=False)
    items = OrderItemInputSerializer(many=True)

    def _next_order_number(self, branch: Branch) -> int:
        latest = Order.objects.filter(branch=branch).order_by("-order_number").first()
        return (latest.order_number + 1) if latest else 100

    def _resolve_modifier_payload(self, product: Product, modifiers, fast_pos_mode: bool, channel: str):
        selected = []
        by_group = {}
        for raw in modifiers or []:
            mod_id = raw.get("id") if isinstance(raw, dict) else None
            name = raw.get("name") if isinstance(raw, dict) else None
            price = raw.get("price") if isinstance(raw, dict) else None
            modifier = None
            if mod_id:
                modifier = Modifier.objects.filter(id=mod_id, group__products=product).select_related("group").first()
            if modifier is None and name:
                modifier = Modifier.objects.filter(name=name, group__products=product).select_related("group").first()
            if modifier is None:
                continue
            by_group.setdefault(modifier.group_id, []).append(modifier)
            selected.append({"name": modifier.name, "price": modifier.price})

        if channel == "pos" and fast_pos_mode:
            for group in product.modifier_groups.filter(required=True).prefetch_related("modifiers"):
                if by_group.get(group.id):
                    continue
                default_modifier = group.modifiers.filter(is_active=True).order_by("id").first()
                if not default_modifier:
                    continue
                selected.append({"name": default_modifier.name, "price": default_modifier.price})

        return selected

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        service_type_id = validated_data.pop("service_type_id", None)
        service_type_key = (validated_data.pop("service_type_key", None) or "").strip() or None
        source = (validated_data.pop("source", "") or "").strip().lower()
        channel = ((validated_data.pop("channel", "") or source or "pos").strip().lower())
        fast_pos_mode = bool(validated_data.pop("fast_pos_mode", False))
        branch = validated_data.pop("branch_id", None)
        if branch is None:
            branch = Branch.objects.first()
            if branch is None:
                raise serializers.ValidationError("Branch is required")

        service_type = None
        if service_type_id is not None:
            service_type = ServiceType.objects.filter(id=service_type_id).first()
        if service_type is None and service_type_key:
            service_type = ServiceType.objects.filter(key=service_type_key).first()
        if service_type is None:
            raise serializers.ValidationError("Service type is required")
        service_type_key = service_type.key

        order_number = self._next_order_number(branch)
        status = "preparing" if source == "kiosk" or service_type_key == "kiosk" else "waiting_payment"
        order = Order.objects.create(
            branch=branch,
            order_number=order_number,
            service_type=service_type,
            status=status,
            channel=channel if channel in {"pos", "kiosk", "online"} else "pos",
            **validated_data,
        )

        discounts = Discount.objects.filter(is_active=True, auto_apply=True)
        now = timezone.localtime(timezone.now())
        day_of_week = now.weekday()
        time_of_day = now.time()

        filtered_discounts = []
        for discount in discounts:
            if discount.service_types and service_type_key not in discount.service_types:
                continue
            if discount.days_of_week and day_of_week not in discount.days_of_week:
                continue
            if discount.start_time and discount.end_time:
                if not (discount.start_time <= time_of_day <= discount.end_time):
                    continue
            filtered_discounts.append(discount)

        subtotal = Decimal("0")
        disposable_total = Decimal("0")
        discount_totals = {}

        for item_data in items_data:
            modifiers = item_data.pop("modifiers", [])
            product = item_data.pop("product_id")
            modifiers = self._resolve_modifier_payload(product, modifiers, fast_pos_mode, channel)
            price_snapshot = item_data["price_snapshot"]
            quantity = item_data["quantity"]
            modifiers_total = sum((modifier["price"] for modifier in modifiers), Decimal("0"))
            item_total = (price_snapshot + modifiers_total) * quantity

            line_discount_total = Decimal("0")
            for discount in filtered_discounts:
                if discount.applies_to == "products":
                    if not discount.targets.filter(product_id=product.id).exists():
                        continue
                elif discount.applies_to == "categories":
                    if not discount.targets.filter(category_id=product.category_id).exists():
                        continue
                else:
                    continue
                if discount.min_amount and item_total < discount.min_amount:
                    continue

                if discount.type == "percent":
                    discount_amount = (item_total * (discount.value / Decimal("100"))).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                else:
                    discount_amount = min(discount.value, item_total)

                line_discount_total += discount_amount
                discount_totals[discount.id] = discount_totals.get(discount.id, Decimal("0")) + discount_amount

            item_total_after_discount = max(item_total - line_discount_total, Decimal("0"))
            subtotal += item_total_after_discount

            order_item = OrderItem.objects.create(order=order, product=product, **item_data)
            for modifier_data in modifiers:
                OrderItemModifier.objects.create(
                    order_item=order_item,
                    modifier_name_snapshot=modifier_data["name"],
                    modifier_price_snapshot=modifier_data["price"],
                )

            if channel == "pos" and Decimal(product.disposable_fee or 0) > 0 and service_type_key in (product.disposable_apply_to or []):
                fee_total = (Decimal(product.disposable_fee) * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                disposable_total += fee_total
                OrderFee.objects.create(
                    order=order,
                    order_item=order_item,
                    fee_type="disposable",
                    fee_name="Desechables",
                    unit_amount=Decimal(product.disposable_fee),
                    quantity=quantity,
                    total_amount=fee_total,
                )

        if subtotal > 0:
            for discount in filtered_discounts:
                if discount.applies_to != "order":
                    continue
                if discount.min_amount and subtotal < discount.min_amount:
                    continue

                if discount.type == "percent":
                    discount_amount = (subtotal * (discount.value / Decimal("100"))).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                else:
                    discount_amount = min(discount.value, subtotal)

                if discount_amount > 0:
                    discount_totals[discount.id] = discount_totals.get(discount.id, Decimal("0")) + discount_amount
                    subtotal = max(subtotal - discount_amount, Decimal("0"))

        subtotal += disposable_total
        discount_total = sum(discount_totals.values(), Decimal("0"))
        total = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        tax_config = TaxConfig.objects.filter(is_active=True).order_by("-id").first()
        tax_rate = tax_config.rate if tax_config else Decimal("0.13")
        divisor = Decimal("1.00") + tax_rate
        subtotal_exclusive = (total / divisor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax = (total - subtotal_exclusive).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        order.subtotal = subtotal_exclusive
        order.tax = tax
        order.total = total
        order.discount_total = discount_total
        order.disposable_total = disposable_total
        order.requires_kitchen = order.items.filter(product__requires_kitchen=True).exists()
        if order.requires_kitchen and order.status == "preparing":
            from apps.kitchen.models import KitchenOrderView
            KitchenOrderView.objects.get_or_create(
                order=order,
                defaults={"service_type": service_type, "status": "preparing"},
            )
        order.save(update_fields=["subtotal", "tax", "total", "discount_total", "disposable_total", "requires_kitchen", "updated_at"])


        for discount in filtered_discounts:
            amount = discount_totals.get(discount.id)
            if amount and amount > 0:
                AppliedDiscount.objects.create(
                    order=order,
                    discount_name_snapshot=discount.name,
                    discount_type_snapshot=discount.type,
                    discount_value_snapshot=discount.value,
                    amount_discounted=amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                )

        return order
