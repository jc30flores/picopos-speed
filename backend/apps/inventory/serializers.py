from decimal import Decimal

from rest_framework import serializers

from apps.inventory.models import (
    CatalogProductInventoryLink,
    CategoryInventoryLink,
    InventoryCountLine,
    InventoryCountSession,
    InventoryItem,
    InventoryMovement,
    InventorySupplier,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseReceipt,
    PurchaseReceiptLine,
    ProductInventoryOverride,
)

INVENTORY_UNITS = {
    "unidad",
    "docena",
    "media_docena",
    "caja_25",
    "caja_50",
    "caja_75",
    "caja_100",
    "libra",
    "media_libra",
    "onza",
    "kilogramo",
    "gramo",
    "litro",
    "mililitro",
    "bolsa",
    "paquete",
    "rollo",
    "bandeja",
    "botella",
    "lata",
}


class InventorySupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventorySupplier
        fields = [
            "id", "name", "code", "contact_name", "phone", "email", "address",
            "tax_id", "notes", "is_active", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def validate_name(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("El nombre del proveedor es obligatorio.")
        return cleaned

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if code:
            qs = InventorySupplier.objects.filter(code__iexact=code, is_active=True)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("Ya existe un proveedor activo con este código.")
        return code


class InventoryItemSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    def validate_unit(self, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in INVENTORY_UNITS:
            raise serializers.ValidationError("Unidad inválida.")
        return normalized

    class Meta:
        model = InventoryItem
        fields = [
            "id",
            "name",
            "sku",
            "unit",
            "current_stock",
            "min_stock",
            "max_stock",
            "supplier",
            "supplier_name",
            "unit_cost",
            "supplier_code",
            "purchase_unit",
            "purchase_to_inventory_factor",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate_unit_cost(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("El costo debe ser mayor o igual a 0.")
        return value

    def validate_purchase_to_inventory_factor(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("El factor de conversión debe ser mayor a 0.")
        return value


class InventoryMovementSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    inventory_item_sku = serializers.CharField(source="inventory_item.sku", read_only=True)
    inventory_item_unit = serializers.CharField(source="inventory_item.unit", read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = InventoryMovement
        fields = [
            "id",
            "inventory_item",
            "inventory_item_name",
            "inventory_item_sku",
            "inventory_item_unit",
            "movement_type",
            "quantity_change",
            "quantity_before",
            "quantity_after",
            "reference_type",
            "reference_id",
            "reason",
            "created_by",
            "created_by_username",
            "created_at",
        ]


class InventoryAddStockSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class InventoryAdjustStockSerializer(serializers.Serializer):
    set_stock = serializers.DecimalField(max_digits=12, decimal_places=3, required=False)
    delta = serializers.DecimalField(max_digits=12, decimal_places=3, required=False)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        has_set = attrs.get("set_stock") is not None
        has_delta = attrs.get("delta") is not None
        if has_set == has_delta:
            raise serializers.ValidationError("Debes enviar set_stock o delta (solo uno).")
        return attrs


class InventoryFormalAdjustmentSerializer(serializers.Serializer):
    ADJUSTMENT_TYPES = {"entry", "loss", "damaged", "correction"}

    inventory_item = serializers.IntegerField()
    adjustment_type = serializers.ChoiceField(choices=sorted(ADJUSTMENT_TYPES))
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, required=False, min_value=Decimal("0.001"))
    set_stock = serializers.DecimalField(max_digits=12, decimal_places=3, required=False, min_value=Decimal("0"))
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        adjustment_type = attrs.get("adjustment_type")
        quantity = attrs.get("quantity")
        set_stock = attrs.get("set_stock")
        reason = (attrs.get("reason") or "").strip()
        if adjustment_type in {"entry", "loss", "damaged"} and quantity is None:
            raise serializers.ValidationError({"quantity": "La cantidad es obligatoria y debe ser mayor a 0."})
        if adjustment_type == "correction" and set_stock is None:
            raise serializers.ValidationError({"set_stock": "El stock real es obligatorio y debe ser mayor o igual a 0."})
        if adjustment_type in {"loss", "damaged", "correction"} and not reason:
            raise serializers.ValidationError({"reason": "El motivo es obligatorio para este tipo de ajuste."})
        attrs["reason"] = reason
        return attrs


class CatalogInventoryLinkSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    inventory_item_unit = serializers.CharField(source="inventory_item.unit", read_only=True)

    class Meta:
        model = CatalogProductInventoryLink
        fields = [
            "id",
            "catalog_product",
            "inventory_item",
            "inventory_item_name",
            "inventory_item_unit",
            "quantity_required",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class CatalogInventoryLinkWriteSerializer(serializers.Serializer):
    links = serializers.ListField(child=serializers.DictField(), allow_empty=True)

    def validate_links(self, value):
        normalized: dict[int, Decimal] = {}
        for raw in value:
            item_id = raw.get("inventory_item") or raw.get("inventoryItemId")
            quantity = raw.get("quantity_required") or raw.get("quantityRequired")
            try:
                item_id_int = int(item_id)
                qty_dec = Decimal(str(quantity))
            except Exception as exc:
                raise serializers.ValidationError("Formato de vínculo inválido.") from exc
            if qty_dec <= 0:
                raise serializers.ValidationError("La cantidad requerida debe ser mayor que 0.")
            normalized[item_id_int] = qty_dec

        missing = set(normalized.keys()) - set(InventoryItem.objects.filter(id__in=normalized.keys()).values_list("id", flat=True))
        if missing:
            raise serializers.ValidationError(f"Items no encontrados: {sorted(missing)}")
        return [{"inventory_item": item_id, "quantity_required": qty} for item_id, qty in normalized.items()]


class CategoryInventoryLinkSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    inventory_item_unit = serializers.CharField(source="inventory_item.unit", read_only=True)

    class Meta:
        model = CategoryInventoryLink
        fields = [
            "id",
            "category",
            "inventory_item",
            "inventory_item_name",
            "inventory_item_unit",
            "quantity_required",
            "created_at",
            "updated_at",
        ]


class ProductEffectiveInventoryLinkWriteSerializer(serializers.Serializer):
    links = serializers.ListField(child=serializers.DictField(), allow_empty=True)


class InventoryCountLineSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    inventory_item_sku = serializers.CharField(source="inventory_item.sku", read_only=True)
    inventory_item_unit = serializers.CharField(source="inventory_item.unit", read_only=True)

    class Meta:
        model = InventoryCountLine
        fields = [
            "id",
            "session",
            "inventory_item",
            "inventory_item_name",
            "inventory_item_sku",
            "inventory_item_unit",
            "system_stock",
            "counted_stock",
            "difference",
            "note",
            "stock_before_apply",
            "stock_after_apply",
            "movement",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["session", "difference", "stock_before_apply", "stock_after_apply", "movement", "created_at", "updated_at"]


class InventoryCountSessionListSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    finalized_by_username = serializers.CharField(source="finalized_by.username", read_only=True)
    applied_by_username = serializers.CharField(source="applied_by.username", read_only=True)
    cancelled_by_username = serializers.CharField(source="cancelled_by.username", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    count_type_display = serializers.CharField(source="get_count_type_display", read_only=True)

    class Meta:
        model = InventoryCountSession
        fields = [
            "id", "code", "count_type", "count_type_display", "status", "status_display", "notes",
            "created_by", "created_by_username", "created_at", "updated_at",
            "finalized_by", "finalized_by_username", "finalized_at",
            "applied_by", "applied_by_username", "applied_at",
            "cancelled_by", "cancelled_by_username", "cancelled_at", "cancel_reason",
            "total_items", "counted_items", "total_differences", "total_positive_differences", "total_negative_differences",
        ]


class InventoryCountSessionDetailSerializer(InventoryCountSessionListSerializer):
    lines = InventoryCountLineSerializer(many=True, read_only=True)

    class Meta(InventoryCountSessionListSerializer.Meta):
        fields = InventoryCountSessionListSerializer.Meta.fields + ["lines"]


class InventoryCountCreateSerializer(serializers.Serializer):
    count_type = serializers.ChoiceField(choices=["complete", "manual", "category", "supplier", "provider"])
    notes = serializers.CharField(required=False, allow_blank=True)
    item_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)
    category_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        count_type = attrs.get("count_type")
        if count_type == "manual" and not attrs.get("item_ids"):
            raise serializers.ValidationError({"item_ids": "Selecciona al menos un artículo para crear un conteo manual."})
        if count_type == "category":
            raise serializers.ValidationError({"count_type": "El conteo por categoría aún no está disponible."})
        if count_type in {"supplier", "provider"}:
            raise serializers.ValidationError({"count_type": "El conteo por proveedor está disponible en Inventario Avanzado."})
        return attrs


class InventoryCountUpdateSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)


class InventoryCountLineUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    counted_stock = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0"), required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)


class InventoryCountLinesBulkUpdateSerializer(serializers.Serializer):
    lines = InventoryCountLineUpdateSerializer(many=True)


class InventoryCountCancelSerializer(serializers.Serializer):
    cancel_reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    inventory_item_sku = serializers.CharField(source="inventory_item.sku", read_only=True)
    inventory_item_unit = serializers.CharField(source="inventory_item.unit", read_only=True)
    pending_quantity = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrderLine
        fields = [
            "id", "purchase_order", "inventory_item", "inventory_item_name", "inventory_item_sku",
            "inventory_item_unit", "description", "quantity_ordered", "quantity_received",
            "pending_quantity", "purchase_unit", "purchase_to_inventory_factor",
            "inventory_quantity_ordered", "unit_cost", "subtotal", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["purchase_order", "quantity_received", "inventory_quantity_ordered", "subtotal", "created_at", "updated_at"]

    def get_pending_quantity(self, obj):
        return obj.pending_quantity

    def validate(self, attrs):
        quantity = attrs.get("quantity_ordered", getattr(self.instance, "quantity_ordered", None))
        factor = attrs.get("purchase_to_inventory_factor", getattr(self.instance, "purchase_to_inventory_factor", None))
        cost = attrs.get("unit_cost", getattr(self.instance, "unit_cost", None))
        if quantity is not None and quantity <= 0:
            raise serializers.ValidationError({"quantity_ordered": "La cantidad debe ser mayor a 0."})
        if factor is not None and factor <= 0:
            raise serializers.ValidationError({"purchase_to_inventory_factor": "El factor debe ser mayor a 0."})
        if cost is not None and cost < 0:
            raise serializers.ValidationError({"unit_cost": "El costo no puede ser negativo."})
        return attrs


class PurchaseOrderSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    payment_category_label = serializers.CharField(source="get_payment_category_display", read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True)
    lines = PurchaseOrderLineSerializer(many=True, required=False)
    received_percent = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = [
            "id", "code", "supplier", "supplier_name", "status", "status_label",
            "payment_category", "payment_category_label", "expected_date", "notes",
            "proof_reference", "proof_url", "subtotal", "total", "created_by",
            "created_by_username", "created_at", "updated_at", "approved_by_username",
            "approved_at", "cancelled_at", "cancel_reason", "lines", "received_percent",
        ]
        read_only_fields = ["code", "status", "subtotal", "total", "created_by", "created_at", "updated_at", "approved_at", "cancelled_at", "cancel_reason"]

    def get_received_percent(self, obj):
        ordered = sum((line.quantity_ordered for line in obj.lines.all()), start=Decimal("0"))
        if ordered <= 0:
            return 0
        received = sum((line.quantity_received for line in obj.lines.all()), start=Decimal("0"))
        return round(float((received / ordered) * 100), 2)

    def validate(self, attrs):
        if not attrs.get("supplier") and not getattr(self.instance, "supplier_id", None):
            raise serializers.ValidationError({"supplier": "Selecciona un proveedor."})
        return attrs


class PurchaseReceiptLineSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)

    class Meta:
        model = PurchaseReceiptLine
        fields = [
            "id", "receipt", "purchase_order_line", "inventory_item", "inventory_item_name",
            "quantity_received_purchase_unit", "purchase_to_inventory_factor",
            "quantity_added_inventory_unit", "unit_cost", "movement", "notes",
        ]


class PurchaseReceiptSerializer(serializers.ModelSerializer):
    received_by_username = serializers.CharField(source="received_by.username", read_only=True)
    lines = PurchaseReceiptLineSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseReceipt
        fields = ["id", "code", "purchase_order", "received_by", "received_by_username", "received_at", "notes", "created_at", "lines"]


class PurchaseOrderReceiveSerializer(serializers.Serializer):
    lines = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    update_unit_cost = serializers.BooleanField(required=False, default=True)

    def validate_lines(self, value):
        normalized = []
        for raw in value:
            line_id = raw.get("line_id") or raw.get("line")
            quantity = raw.get("quantity_received")
            try:
                line_id = int(line_id)
                quantity = Decimal(str(quantity))
            except Exception as exc:
                raise serializers.ValidationError("Formato de recepción inválido.") from exc
            if quantity <= 0:
                raise serializers.ValidationError("La cantidad recibida debe ser mayor a 0.")
            normalized.append({"line_id": line_id, "quantity_received": quantity, "notes": (raw.get("notes") or "").strip()})
        return normalized


class PurchaseOrderCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)
