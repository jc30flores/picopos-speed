from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from apps.orders.models import Order, OrderItem, OrderItemModifier, AppliedDiscount, OrderInvoice, OrderFee
from apps.menu.models import Product, Discount, Modifier
from apps.core.models import Branch, Customer, ServiceType, Table, TaxConfig
from apps.payments.models import Payment
from apps.orders.discount_engine import apply_discounts, discount_conditions_met, discount_has_conditions
from apps.menu.utils.pricing import resolve_effective_price
from django.conf import settings
from apps.core.audit import log_audit


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
            "unit_price_override",
            "discount_amount",
            "snapshot_sku_or_code",
            "is_custom",
            "quantity",
            "assigned_name",
            "applied_special_price_rule_id",
            "applied_modifiers",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    service_type = serializers.SerializerMethodField()
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
            "customer_id",
            "dte_document_type",
            "iva_exempt",
            "iva_exempt_discount",
            "subtotal",
            "tax",
            "total",
            "discount_total",
            "discount_snapshot",
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

    def get_service_type(self, obj: Order):
        return obj.service_type.key if obj.service_type else None

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
                "breakdown": discount.breakdown,
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
    type = serializers.CharField(required=False, allow_blank=True)
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), required=False, allow_null=True)
    product_name_snapshot = serializers.CharField(required=False, allow_blank=True)
    price_snapshot = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    is_custom = serializers.BooleanField(required=False, default=False)
    custom_name = serializers.CharField(required=False, allow_blank=False)
    name = serializers.CharField(required=False, allow_blank=False)
    manual_name = serializers.CharField(required=False, allow_blank=False)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    manual_unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    custom_code = serializers.CharField(required=False, allow_blank=True, max_length=80)
    unit_price_override = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1)
    assigned_name = serializers.CharField(required=False, allow_blank=True, max_length=80)
    modifiers = AppliedModifierInputSerializer(many=True, required=False)

    def validate(self, attrs):
        item_type = (attrs.get("type") or "").strip().lower()
        if item_type in {"manual", "man", "custom"}:
            item_type = "manual"
        elif item_type in {"menu", "product", "catalog"}:
            item_type = "menu"
        else:
            item_type = "manual" if bool(attrs.get("is_custom", False)) else "menu"
        attrs["type"] = item_type
        is_custom = item_type == "manual" or bool(attrs.get("is_custom", False))
        attrs["is_custom"] = is_custom
        if attrs.get("name") and not attrs.get("custom_name"):
            attrs["custom_name"] = attrs.get("name")
        if attrs.get("manual_name") and not attrs.get("custom_name"):
            attrs["custom_name"] = attrs.get("manual_name")
        if attrs.get("manual_unit_price") is not None and attrs.get("unit_price") is None:
            attrs["unit_price"] = attrs.get("manual_unit_price")
        product = attrs.get("product_id")
        if is_custom:
            if product is not None:
                raise serializers.ValidationError({"product_id": "Los ítems manuales no deben incluir product_id."})
            custom_name = (attrs.get("custom_name") or "").strip()
            if not custom_name:
                raise serializers.ValidationError({"custom_name": "custom_name es requerido para ítems manuales."})
            if len(custom_name) < 2:
                raise serializers.ValidationError({"custom_name": "custom_name debe tener al menos 2 caracteres."})
            unit_price = attrs.get("unit_price")
            if unit_price is None or unit_price <= 0:
                raise serializers.ValidationError({"unit_price": "unit_price debe ser mayor que 0."})
            attrs["custom_name"] = custom_name
        else:
            if product is None:
                raise serializers.ValidationError({"product_id": "product_id es requerido para ítems de menú."})
        unit_price_override = attrs.get("unit_price_override")
        if unit_price_override is not None and unit_price_override <= 0:
            raise serializers.ValidationError({"unit_price_override": "unit_price_override debe ser mayor que 0."})
        return attrs


class OrderCreateSerializer(serializers.Serializer):
    branch_id = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False)
    service_type_id = serializers.IntegerField(required=False)
    service_type_key = serializers.CharField(required=False, allow_blank=True)
    table_id = serializers.PrimaryKeyRelatedField(queryset=Table.objects.all(), required=False, allow_null=True)
    customer_name = serializers.CharField(required=False, allow_blank=True)
    customer_id = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=False, allow_null=True)
    dte_document_type = serializers.ChoiceField(choices=["CF", "CCF", "SX"], required=False, default="CF")
    iva_exempt = serializers.BooleanField(required=False, default=False)
    source = serializers.CharField(required=False, allow_blank=True)
    channel = serializers.CharField(required=False, allow_blank=True)
    fast_pos_mode = serializers.BooleanField(required=False, default=False)
    price_change_pin = serializers.CharField(required=False, allow_blank=True, max_length=12)
    discount_id = serializers.IntegerField(required=False, allow_null=True)
    discount_mode = serializers.ChoiceField(choices=["manual", "auto"], required=False, allow_null=True)
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
        price_change_pin = (validated_data.pop("price_change_pin", "") or "").strip()
        manual_discount_id = validated_data.pop("discount_id", None)
        discount_mode = (validated_data.pop("discount_mode", "") or "").strip().lower()
        customer_name = (validated_data.pop("customer_name", "") or "").strip()
        branch = validated_data.pop("branch_id", None)
        customer = validated_data.pop("customer_id", None)
        dte_document_type = validated_data.pop("dte_document_type", "CF")
        iva_exempt = bool(validated_data.pop("iva_exempt", False))
        if branch is None:
            branch = Branch.objects.first()
            if branch is None:
                raise serializers.ValidationError("Branch is required")

        if customer is None:
            customer = Customer.objects.filter(is_deleted=False, is_consumer_final=True).first() or Customer.objects.filter(is_default_consumer_final=True).first()
            if customer is None:
                customer = Customer.objects.create(name="CONSUMIDOR FINAL", full_name="CONSUMIDOR FINAL", client_type="CF", dui="00000000-0", telefono="00000000", is_consumer_final=True)

        if dte_document_type == "CCF" and customer.client_type != "CCF":
            raise serializers.ValidationError({"dte_document_type": "Cliente debe ser CCF para emitir CCF."})
        if dte_document_type == "SX" and customer.client_type != "SX":
            raise serializers.ValidationError({"dte_document_type": "Cliente debe ser SX para emitir SX."})

        service_type = None
        if service_type_id is not None:
            service_type = ServiceType.objects.filter(id=service_type_id).first()
        if service_type is None and service_type_key:
            normalized_key = service_type_key.strip().upper().replace("-", "_")
            service_type = ServiceType.objects.filter(key__iexact=normalized_key).first()
            if service_type is None:
                service_type = ServiceType.objects.filter(key__iexact=service_type_key.strip()).first()
        if service_type is None:
            raise serializers.ValidationError("Service type is required")
        service_type_key = service_type.key

        order_number = self._next_order_number(branch)
        status = "preparing" if source == "kiosk" or service_type_key == "KIOSK" else "waiting_payment"
        order = Order.objects.create(
            branch=branch,
            order_number=order_number,
            service_type=service_type,
            status=status,
            channel=channel if channel in {"pos", "kiosk", "online"} else "pos",
            customer=customer,
            customer_name=customer_name or customer.name,
            dte_document_type=dte_document_type,
            iva_exempt=iva_exempt,
            **validated_data,
        )

        discounts = list(Discount.objects.filter(is_active=True).prefetch_related("targets").order_by("priority", "id"))

        order_lines = []
        subtotal = Decimal("0")
        disposable_total = Decimal("0")
        product_totals: dict[int, Decimal] = {}
        category_totals: dict[int, Decimal] = {}

        override_requested = any(item.get("unit_price_override") is not None for item in items_data)
        if override_requested:
            configured_pin = (getattr(settings, "CODE_CHANGE_PRICE", "") or "").strip()
            if not configured_pin:
                raise serializers.ValidationError({"price_change_pin": "Configuración CODE_CHANGE_PRICE no disponible."})
            if not price_change_pin or price_change_pin != configured_pin:
                raise PermissionDenied("Código incorrecto")

        for item_data in items_data:
            item_data = dict(item_data)
            raw_type = str(item_data.pop("type", "") or "").strip().lower()
            incoming_is_custom = bool(item_data.pop("is_custom", False))
            is_custom = raw_type == "manual" or incoming_is_custom
            item_data.pop("manual_name", None)
            item_data.pop("manual_unit_price", None)
            item_data.pop("name", None)
            modifiers = item_data.pop("modifiers", [])
            product = item_data.pop("product_id", None)
            quantity = item_data["quantity"]
            unit_price_override = item_data.pop("unit_price_override", None)
            pricing_result = None
            if is_custom:
                custom_name = item_data.pop("custom_name")
                price_snapshot = item_data.pop("unit_price")
                item_data["product_name_snapshot"] = custom_name
                item_data["price_snapshot"] = price_snapshot
                item_data["snapshot_sku_or_code"] = (item_data.pop("custom_code", "") or "").strip()
            else:
                modifiers = self._resolve_modifier_payload(product, modifiers, fast_pos_mode, channel)
                pricing_result = resolve_effective_price(product, order_type=service_type, at=timezone.now())
                price_snapshot = pricing_result.effective_price
                item_data["price_snapshot"] = price_snapshot
                item_data["product_name_snapshot"] = product.name
                item_data["snapshot_sku_or_code"] = f"PROD-{product.id}"
            effective_unit_price = unit_price_override if unit_price_override is not None else price_snapshot
            modifiers_total = sum((modifier["price"] for modifier in modifiers), Decimal("0"))
            line_total = (effective_unit_price + modifiers_total) * quantity
            line_key = f"line-{len(order_lines)}"
            if is_custom and not item_data["snapshot_sku_or_code"]:
                item_data["snapshot_sku_or_code"] = f"MANUAL-{order.id}-{len(order_lines) + 1}"

            item_data.pop("is_custom", None)
            order_item = OrderItem.objects.create(
                order=order,
                product=product,
                applied_special_price_rule=pricing_result.applied_rule if pricing_result else None,
                is_custom=is_custom,
                unit_price_override=unit_price_override,
                **item_data,
            )
            for modifier_data in modifiers:
                OrderItemModifier.objects.create(
                    order_item=order_item,
                    modifier_name_snapshot=modifier_data["name"],
                    modifier_price_snapshot=modifier_data["price"],
                )

            if product and channel == "pos" and Decimal(product.disposable_fee or 0) > 0 and service_type_key in (product.disposable_apply_to or []):
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

            order_lines.append(
                {
                    "line_key": line_key,
                    "order_item_id": order_item.id,
                    "product_id": product.id if product else None,
                    "category_id": product.category_id if product else None,
                    "quantity": quantity,
                    "price_snapshot": effective_unit_price,
                    "modifier_total": modifiers_total,
                    "line_total": line_total,
                }
            )
            subtotal += line_total
            if product:
                product_totals[product.id] = product_totals.get(product.id, Decimal("0")) + line_total
                category_totals[product.category_id] = category_totals.get(product.category_id, Decimal("0")) + line_total

        discount_by_id = {}
        for discount in discounts:
            discount.target_product_ids = set(discount.targets.filter(product__isnull=False).values_list("product_id", flat=True))
            discount.target_category_ids = set(discount.targets.filter(category__isnull=False).values_list("category_id", flat=True))
            discount_by_id[discount.id] = discount

        selected_discount = None
        force_apply_discount = False
        if manual_discount_id:
            selected_discount = discount_by_id.get(int(manual_discount_id))
            if selected_discount is None:
                raise serializers.ValidationError({"discount_id": "Descuento no encontrado o inactivo."})
            force_apply_discount = True
            discount_mode = "manual"
        elif discount_mode == "manual":
            raise serializers.ValidationError({"discount_id": "discount_id es requerido para modo manual."})

        discount_result = apply_discounts(
            order_lines,
            discounts,
            service_type_key=service_type_key,
            disposable_total=disposable_total,
            selected_discount=selected_discount,
            force_apply=force_apply_discount,
        )

        discount_totals = discount_result["discount_totals"]
        discount_total = sum(discount_totals.values(), Decimal("0"))
        subtotal_after_discounts = discount_result["subtotal_after_discounts"]
        total = discount_result["final_subtotal"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        tax_config = TaxConfig.objects.filter(is_active=True).order_by("-id").first()
        tax_rate = tax_config.rate if tax_config else Decimal("0.13")
        divisor = Decimal("1.00") + tax_rate
        tax_included = (total - (total / divisor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        order.subtotal = total
        order.tax = tax_included
        order.total = total
        order.discount_total = discount_total
        order.discount_snapshot = {}
        order.disposable_total = disposable_total
        if order.iva_exempt:
            exempt_discount = (total - (total / Decimal("1.13"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            order.iva_exempt_discount = exempt_discount
            order.discount_total = (discount_total + exempt_discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            order.tax = Decimal("0.00")
            order.total = (total - exempt_discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            order.iva_exempt_discount = Decimal("0.00")
        order.requires_kitchen = order.items.filter(product__requires_kitchen=True).exists()
        if order.requires_kitchen and order.status == "preparing":
            from apps.kitchen.models import KitchenOrderView
            KitchenOrderView.objects.get_or_create(
                order=order,
                defaults={"service_type": service_type, "status": "preparing"},
            )
        order.save(update_fields=["subtotal", "tax", "total", "discount_total", "discount_snapshot", "disposable_total", "iva_exempt_discount", "requires_kitchen", "updated_at"])

        breakdown_by_discount = {}
        for entry in discount_result["applied_breakdown"]:
            did = entry.get("discount_id")
            breakdown_by_discount.setdefault(did, []).append(entry)

        order_discount_snapshot = {}
        line_discount_map = discount_result["line_discounts"]
        for line in order_lines:
            OrderItem.objects.filter(id=line["order_item_id"]).update(
                discount_amount=(line_discount_map.get(line["line_key"]) or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            )

        for discount in discounts:
            amount = discount_totals.get(discount.id)
            if amount and amount > 0:
                applied = AppliedDiscount.objects.create(
                    order=order,
                    discount_name_snapshot=discount.name,
                    discount_type_snapshot=discount.type,
                    discount_value_snapshot=discount.value,
                    amount_discounted=amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    breakdown={"entries": breakdown_by_discount.get(discount.id, [])},
                )
                order_discount_snapshot = {
                    "discount_id": discount.id,
                    "name": discount.name,
                    "type": discount.type,
                    "value": str(discount.value),
                    "amount": str(applied.amount_discounted),
                    "mode": discount_mode or ("manual" if force_apply_discount else "auto"),
                    "conditions_met": discount_conditions_met(
                        discount,
                        service_type_key=service_type_key,
                        subtotal_before_discounts=subtotal,
                    ),
                    "has_conditions": discount_has_conditions(discount),
                    "applies_to": discount.applies_to,
                    "line_breakdown": breakdown_by_discount.get(discount.id, []),
                }

        if order_discount_snapshot:
            order.discount_snapshot = order_discount_snapshot
            order.save(update_fields=["discount_snapshot", "updated_at"])
            if force_apply_discount:
                log_audit(
                    self.context.get("request"),
                    "orders.discount.manual_apply",
                    "Order",
                    order.id,
                    {"discount_id": order_discount_snapshot.get("discount_id"), "name": order_discount_snapshot.get("name")},
                )

        return order
