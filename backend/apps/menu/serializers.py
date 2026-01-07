import os
from rest_framework import serializers
from apps.menu.models import (
    Category,
    Product,
    ModifierGroup,
    Modifier,
    Discount,
    DiscountRuleTarget,
    normalize_category_name,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "is_active"]

    def validate_name(self, value: str) -> str:
        normalized = normalize_category_name(value)
        if not normalized:
            raise serializers.ValidationError("La categoría no puede estar vacía.")
        return normalized


class ModifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Modifier
        fields = ["id", "name", "price", "is_active"]


class ModifierGroupSerializer(serializers.ModelSerializer):
    modifiers = ModifierSerializer(many=True)

    class Meta:
        model = ModifierGroup
        fields = ["id", "name", "required", "min_selection", "max_selection", "modifiers"]

    def create(self, validated_data):
        modifiers_data = validated_data.pop("modifiers", [])
        group = ModifierGroup.objects.create(**validated_data)
        for modifier_data in modifiers_data:
            Modifier.objects.create(group=group, **modifier_data)
        return group


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="category.name", read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all(), write_only=True
    )
    category_id_display = serializers.IntegerField(source="category.id", read_only=True)
    modifier_groups = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True
    )
    modifier_group_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        source="modifier_groups",
        queryset=ModifierGroup.objects.all(),
        write_only=True,
        required=False,
    )
    image_path = serializers.CharField(read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "price",
            "category",
            "category_id",
            "category_id_display",
            "image",
            "image_path",
            "image_url",
            "available",
            "modifier_groups",
            "modifier_group_ids",
        ]

    def get_image_url(self, obj: Product) -> str | None:
        if obj.image_path:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image_path)
            return obj.image_path
        if obj.image and hasattr(obj.image, "url"):
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

    def validate_image(self, value):
        if not value:
            return value
        max_size = 5 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError("La imagen excede el máximo de 5MB.")
        extension = os.path.splitext(value.name)[1].lower().lstrip(".")
        if extension not in {"jpg", "jpeg", "png", "webp"}:
            raise serializers.ValidationError("Formato de imagen no permitido.")
        return value

    def update(self, instance, validated_data):
        new_image = validated_data.get("image")
        old_image = instance.image
        instance = super().update(instance, validated_data)
        if new_image and old_image and old_image.name != instance.image.name:
            old_image.delete(save=False)
        return instance


class DiscountSerializer(serializers.ModelSerializer):
    target_category_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    target_product_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    target_category_ids_display = serializers.SerializerMethodField()
    target_product_ids_display = serializers.SerializerMethodField()

    class Meta:
        model = Discount
        fields = [
            "id",
            "name",
            "description",
            "type",
            "value",
            "applies_to",
            "is_active",
            "min_amount",
            "auto_apply",
            "service_types",
            "days_of_week",
            "start_time",
            "end_time",
            "target_category_ids",
            "target_product_ids",
            "target_category_ids_display",
            "target_product_ids_display",
        ]

    def get_target_category_ids_display(self, obj: Discount):
        return list(obj.targets.filter(category__isnull=False).values_list("category_id", flat=True))

    def get_target_product_ids_display(self, obj: Discount):
        return list(obj.targets.filter(product__isnull=False).values_list("product_id", flat=True))

    def create(self, validated_data):
        target_category_ids = validated_data.pop("target_category_ids", [])
        target_product_ids = validated_data.pop("target_product_ids", [])
        discount = Discount.objects.create(**validated_data)
        for category_id in target_category_ids:
            DiscountRuleTarget.objects.create(discount=discount, category_id=category_id)
        for product_id in target_product_ids:
            DiscountRuleTarget.objects.create(discount=discount, product_id=product_id)
        return discount

    def update(self, instance, validated_data):
        target_category_ids = validated_data.pop("target_category_ids", None)
        target_product_ids = validated_data.pop("target_product_ids", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if target_category_ids is not None or target_product_ids is not None:
            instance.targets.all().delete()
            for category_id in target_category_ids or []:
                DiscountRuleTarget.objects.create(discount=instance, category_id=category_id)
            for product_id in target_product_ids or []:
                DiscountRuleTarget.objects.create(discount=instance, product_id=product_id)
        return instance
