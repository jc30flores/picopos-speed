from decimal import Decimal

from rest_framework import serializers

from apps.inventory.models import (
    CatalogProductInventoryLink,
    CategoryInventoryLink,
    InventoryItem,
    InventoryMovement,
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


class InventoryItemSerializer(serializers.ModelSerializer):
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
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]


class InventoryMovementSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = InventoryMovement
        fields = [
            "id",
            "inventory_item",
            "inventory_item_name",
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
