import logging
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from apps.orders.models import Order, OrderItem, OrderItemModifier, AppliedDiscount, OrderInvoice, OrderFee
from apps.menu.models import Product, Discount, Modifier
from apps.core.models import Branch, Customer, ServiceType, Table, TaxConfig
from apps.core.service_types import normalize_service_type
from apps.payments.models import Payment
from apps.orders.discount_engine import apply_discounts, discount_conditions_met, discount_has_conditions
from apps.orders.schema import ensure_whatsapp_order_columns, has_whatsapp_order_columns
from apps.orders.whatsapp_phone import normalize_whatsapp_num_cliente
from apps.menu.utils.pricing import resolve_effective_price
from apps.core.audit import log_audit
from apps.core.money import to_cents
from apps.users.models import UserProfile
from apps.users.pin_utils import is_valid_pin_format, user_matches_pin

logger = logging.getLogger(__name__)


class OrderItemModifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItemModifier
        fields = ["id", "modifier_name_snapshot", "modifier_price_snapshot"]


class OrderItemSerializer(serializers.ModelSerializer):
    applied_modifiers = OrderItemModifierSerializer(many=True, read_only=True)
    unit_price_list = serializers.SerializerMethodField()
    unit_price_special = serializers.SerializerMethodField()
    unit_price_before_discount = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()
    unit_price_final = serializers.SerializerMethodField()
    line_total_before_discount = serializers.SerializerMethodField()
    line_total_discount = serializers.SerializerMethodField()
    line_total_final = serializers.SerializerMethodField()
    pricing_metadata = serializers.SerializerMethodField()

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
            "unit_price_list",
            "unit_price_special",
            "unit_price_before_discount",
            "discount_percent",
            "unit_price_final",
            "line_total_before_discount",
            "line_total_discount",
            "line_total_final",
            "pricing_metadata",
        ]

    def _modifier_total(self, obj: OrderItem) -> Decimal:
        return sum((Decimal(mod.modifier_price_snapshot or 0) for mod in obj.applied_modifiers.all()), Decimal("0.00"))

    def _unit_before_discount(self, obj: OrderItem) -> Decimal:
        return (Decimal(obj.price_snapshot or 0) + self._modifier_total(obj)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def get_unit_price_list(self, obj: OrderItem):
        if obj.product_id and obj.product:
            return Decimal(obj.product.price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return Decimal(obj.price_snapshot or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def get_unit_price_special(self, obj: OrderItem):
        if obj.applied_special_price_rule_id:
            return Decimal(obj.price_snapshot or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return None

    def get_unit_price_before_discount(self, obj: OrderItem):
        return self._unit_before_discount(obj)

    def get_discount_percent(self, obj: OrderItem):
        unit_before = self._unit_before_discount(obj)
        if unit_before <= 0:
            return Decimal("0.00")
        unit_discount = (Decimal(obj.discount_amount or 0) / Decimal(obj.quantity or 1)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return ((unit_discount / unit_before) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def get_unit_price_final(self, obj: OrderItem):
        unit_before = self._unit_before_discount(obj)
        unit_discount = (Decimal(obj.discount_amount or 0) / Decimal(obj.quantity or 1)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return max(unit_before - unit_discount, Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def get_line_total_before_discount(self, obj: OrderItem):
        return (self._unit_before_discount(obj) * Decimal(obj.quantity or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def get_line_total_discount(self, obj: OrderItem):
        return Decimal(obj.discount_amount or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def get_line_total_final(self, obj: OrderItem):
        return max(self.get_line_total_before_discount(obj) - self.get_line_total_discount(obj), Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def get_pricing_metadata(self, obj: OrderItem):
        return {
            "special_price_rule_id": obj.applied_special_price_rule_id,
            "special_price_rule_name": getattr(obj.applied_special_price_rule, "name", None) if obj.applied_special_price_rule_id else None,
        }


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    service_type = serializers.SerializerMethodField()
    discounts_applied = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    amount_due_cents = serializers.IntegerField(read_only=True)
    remaining_cents = serializers.SerializerMethodField()
    financial_status = serializers.CharField(read_only=True)
    refund_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    net_paid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    fees = serializers.SerializerMethodField()
    subtotal_before_discounts = serializers.SerializerMethodField()
    subtotal_after_discounts = serializers.SerializerMethodField()
    tax_total = serializers.SerializerMethodField()
    total_payable = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "customer_name",
            "customer_id",
            "whatsapp_num_cliente",
            "whatsapp_num_cliente_country",
            "dte_document_type",
            "iva_exempt",
            "iva_exempt_discount",
            "subtotal",
            "tax",
            "total",
            "discount_total",
            "discount_snapshot",
            "disposable_total",
            "send_to_kitchen",
            "payment_status",
            "financial_status",
            "is_pending",
            "pending_state",
            "pending_reference",
            "pending_marked_at",
            "pending_completed_at",
            "pending_completion_type",
            "pending_completion_note",
            "total_paid",
            "remaining",
            "amount_due_cents",
            "remaining_cents",
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
            "subtotal_before_discounts",
            "subtotal_after_discounts",
            "tax_total",
            "total_payable",
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
        total = Payment.objects.filter(order=obj).aggregate(total=Sum("amount_applied"))["total"] or Decimal("0")
        return total

    def get_remaining(self, obj: Order):
        total_paid = self.get_total_paid(obj)
        due = Decimal(obj.amount_due_cents or to_cents(obj.total)) / Decimal("100")
        remaining = (due - total_paid).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return remaining

    def get_remaining_cents(self, obj: Order):
        return max(to_cents(self.get_remaining(obj)), 0)

    def get_subtotal_before_discounts(self, obj: Order):
        total = Decimal("0.00")
        for item in obj.items.all():
            modifiers_total = sum((Decimal(mod.modifier_price_snapshot or 0) for mod in item.applied_modifiers.all()), Decimal("0.00"))
            unit_before = Decimal(item.price_snapshot or 0) + modifiers_total
            total += unit_before * Decimal(item.quantity or 0)
        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def get_subtotal_after_discounts(self, obj: Order):
        return Decimal(obj.total or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def get_tax_total(self, obj: Order):
        return Decimal(obj.tax or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def get_total_payable(self, obj: Order):
        return Decimal(obj.total or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not has_whatsapp_order_columns():
            self.fields.pop("whatsapp_num_cliente", None)
            self.fields.pop("whatsapp_num_cliente_country", None)


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
    whatsapp_num_cliente = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=32)
    whatsapp_num_cliente_country = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=8)
    dte_document_type = serializers.ChoiceField(choices=["CF", "CCF", "SX"], required=False, default="CF")
    iva_exempt = serializers.BooleanField(required=False, default=False)
    source = serializers.CharField(required=False, allow_blank=True)
    channel = serializers.CharField(required=False, allow_blank=True)
    fast_pos_mode = serializers.BooleanField(required=False, default=False)
    price_change_pin = serializers.CharField(required=False, allow_blank=True, max_length=12)
    send_to_kitchen = serializers.BooleanField(required=False, default=False)
    discount_id = serializers.IntegerField(required=False, allow_null=True)
    manual_discount_id = serializers.IntegerField(required=False, allow_null=True)
    discount_mode = serializers.ChoiceField(choices=["manual", "auto"], required=False, allow_null=True)
    manual_discount_snapshot = serializers.JSONField(required=False)
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
        ensure_whatsapp_order_columns()
        items_data = validated_data.pop("items")
        service_type_id = validated_data.pop("service_type_id", None)
        service_type_key = (validated_data.pop("service_type_key", None) or "").strip() or None
        source = (validated_data.pop("source", "") or "").strip().lower()
        channel = ((validated_data.pop("channel", "") or source or "pos").strip().lower())
        fast_pos_mode = bool(validated_data.pop("fast_pos_mode", False))
        price_change_pin = (validated_data.pop("price_change_pin", "") or "").strip()
        requested_send_to_kitchen = bool(validated_data.pop("send_to_kitchen", False))
        manual_discount_id = validated_data.pop("manual_discount_id", None)
        if manual_discount_id is None:
            manual_discount_id = validated_data.pop("discount_id", None)
        else:
            validated_data.pop("discount_id", None)
        discount_mode = (validated_data.pop("discount_mode", "") or "").strip().lower()
        manual_discount_snapshot = validated_data.pop("manual_discount_snapshot", None)
        customer_name = (validated_data.pop("customer_name", "") or "").strip()
        branch = validated_data.pop("branch_id", None)
        customer = validated_data.pop("customer_id", None)
        raw_whatsapp_num_cliente = (validated_data.pop("whatsapp_num_cliente", "") or "").strip()
        raw_whatsapp_num_cliente_country = (validated_data.pop("whatsapp_num_cliente_country", "") or "").strip().upper()
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
            normalized_key = normalize_service_type(service_type_key, default="")
            for candidate in ServiceType.objects.filter(is_active=True):
                if normalize_service_type(candidate.key, default="") == normalized_key:
                    service_type = candidate
                    break
        if service_type is None:
            raise serializers.ValidationError("Service type is required")
        service_type_key = service_type.key
        is_kiosk_service = service_type_key.strip().upper() == "KIOSK" or source == "kiosk" or channel == "kiosk"

        order_number = self._next_order_number(branch)
        status = "preparing" if source == "kiosk" or service_type_key == "KIOSK" else "waiting_payment"
        normalized_whatsapp = normalize_whatsapp_num_cliente(
            raw_number=raw_whatsapp_num_cliente,
            raw_country=raw_whatsapp_num_cliente_country,
        )
        normalized_whatsapp_num_cliente = normalized_whatsapp.e164 if normalized_whatsapp else ""
        normalized_whatsapp_num_cliente_country = normalized_whatsapp.country if normalized_whatsapp else ""
        logger.info(
            "orders.create.normalized_contact source=%s channel=%s customer_id=%s consumer_final=%s dte_document_type=%s whatsapp_in_payload=%s whatsapp_final=%s whatsapp_country_in_payload=%s whatsapp_country_final=%s",
            source,
            channel,
            getattr(customer, "id", None),
            bool(getattr(customer, "is_consumer_final", False)),
            dte_document_type,
            raw_whatsapp_num_cliente,
            normalized_whatsapp_num_cliente,
            raw_whatsapp_num_cliente_country,
            normalized_whatsapp_num_cliente_country,
        )
        order = Order.objects.create(
            branch=branch,
            order_number=order_number,
            service_type=service_type,
            status=status,
            channel=channel if channel in {"pos", "kiosk", "online"} else "pos",
            customer=customer,
            customer_name=customer_name or customer.name,
            whatsapp_num_cliente=normalized_whatsapp_num_cliente,
            whatsapp_num_cliente_country=normalized_whatsapp_num_cliente_country,
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
            request_user = getattr(self.context.get("request"), "user", None)
            request_profile = (
                UserProfile.objects.filter(user=request_user).first()
                if request_user and getattr(request_user, "is_authenticated", False)
                else None
            )
            is_requester_privileged = bool(
                request_user
                and getattr(request_user, "is_authenticated", False)
                and (
                    getattr(request_user, "is_superuser", False)
                    or (request_profile and request_profile.role in {"admin", "manager"})
                )
            )
            if not is_requester_privileged:
                if not is_valid_pin_format(price_change_pin):
                    raise PermissionDenied("Código inválido")
                privileged_profiles = UserProfile.objects.select_related("user").filter(
                    is_active=True,
                    role__in=["admin", "manager"],
                    user__is_active=True,
                )
                if not any(user_matches_pin(profile.user, price_change_pin) for profile in privileged_profiles):
                    raise PermissionDenied("Código inválido")

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

            if product and channel == "pos" and Decimal(product.disposable_fee or 0) > 0 and bool(getattr(service_type, "disposables_enabled", False)):
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
                raise serializers.ValidationError({"manual_discount_id": "Descuento no encontrado o inactivo."})
            force_apply_discount = True
            discount_mode = "manual"
        elif discount_mode == "manual":
            raise serializers.ValidationError({"manual_discount_id": "manual_discount_id es requerido para modo manual."})

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
        order.amount_due_cents = to_cents(order.total)
        order.requires_kitchen = order.items.filter(product__requires_kitchen=True).exists()
        order.send_to_kitchen = order.requires_kitchen and (is_kiosk_service or requested_send_to_kitchen)
        if order.send_to_kitchen and order.status == "preparing":
            from apps.kitchen.models import KitchenOrderView
            KitchenOrderView.objects.get_or_create(
                order=order,
                defaults={"service_type": service_type, "status": "preparing"},
            )
        order.save(update_fields=["subtotal", "tax", "total", "amount_due_cents", "discount_total", "discount_snapshot", "disposable_total", "iva_exempt_discount", "requires_kitchen", "send_to_kitchen", "updated_at"])

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
                if isinstance(manual_discount_snapshot, dict) and discount_mode == "manual":
                    order_discount_snapshot["manual_input"] = manual_discount_snapshot

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


class OrderCustomerUpdateSerializer(serializers.ModelSerializer):
    customer_id = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.filter(is_deleted=False), required=False, allow_null=True)
    whatsapp_num_cliente = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=32)
    whatsapp_num_cliente_country = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=8)

    class Meta:
        model = Order
        fields = ["customer_id", "dte_document_type", "iva_exempt", "whatsapp_num_cliente", "whatsapp_num_cliente_country"]

    def validate(self, attrs):
        customer = attrs.get("customer_id", self.instance.customer)
        dte_document_type = attrs.get("dte_document_type", self.instance.dte_document_type)
        if customer is None:
            raise serializers.ValidationError({"customer_id": "Cliente requerido"})
        if dte_document_type == "CCF" and customer.client_type != "CCF":
            raise serializers.ValidationError({"dte_document_type": "Cliente debe ser CCF para emitir CCF."})
        if dte_document_type == "SX" and customer.client_type != "SX":
            raise serializers.ValidationError({"dte_document_type": "Cliente debe ser SX para emitir SX."})
        return attrs

    def update(self, instance: Order, validated_data):
        ensure_whatsapp_order_columns()
        customer = validated_data.get("customer_id")
        if customer is not None:
            instance.customer = customer
            instance.customer_name = customer.name
        if "dte_document_type" in validated_data:
            instance.dte_document_type = validated_data["dte_document_type"]
        if "iva_exempt" in validated_data:
            instance.iva_exempt = bool(validated_data["iva_exempt"])
        if has_whatsapp_order_columns() and ("whatsapp_num_cliente" in validated_data or "whatsapp_num_cliente_country" in validated_data):
            normalized_whatsapp = normalize_whatsapp_num_cliente(
                raw_number=validated_data.get("whatsapp_num_cliente", instance.whatsapp_num_cliente),
                raw_country=validated_data.get("whatsapp_num_cliente_country", instance.whatsapp_num_cliente_country),
            )
            instance.whatsapp_num_cliente = normalized_whatsapp.e164 if normalized_whatsapp else ""
            instance.whatsapp_num_cliente_country = normalized_whatsapp.country if normalized_whatsapp else ""
        update_fields = [
            "customer",
            "customer_name",
            "dte_document_type",
            "iva_exempt",
            "updated_at",
        ]
        if has_whatsapp_order_columns():
            update_fields.extend(["whatsapp_num_cliente", "whatsapp_num_cliente_country"])
        instance.save(update_fields=update_fields)
        return instance
