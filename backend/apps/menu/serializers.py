from rest_framework import serializers
from django.conf import settings
import json
from apps.menu.models import (
    Category,
    Product,
    ModifierGroup,
    Modifier,
    Discount,
    DiscountRuleTarget,
    normalize_category_name,
)
from apps.menu.utils.images import delete_menu_image_by_image_field, save_menu_image


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
    image_path = serializers.CharField(read_only=True)

    class Meta:
        model = Modifier
        fields = ["id", "name", "price", "is_active", "sort_order", "image", "image_path"]


class ModifierGroupSerializer(serializers.ModelSerializer):
    modifiers = ModifierSerializer(many=True)
    image_path = serializers.CharField(read_only=True)

    class Meta:
        model = ModifierGroup
        fields = ["id", "name", "required", "min_selection", "max_selection", "image", "image_path", "modifiers"]

    def create(self, validated_data):
        modifiers_data = validated_data.pop("modifiers", [])
        group = ModifierGroup.objects.create(**validated_data)
        for index, modifier_data in enumerate(modifiers_data):
            modifier_data.setdefault("sort_order", index)
            Modifier.objects.create(group=group, **modifier_data)
        return group


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="category.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    image = serializers.CharField(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all(), write_only=True
    )
    category_id_display = serializers.IntegerField(source="category.id", read_only=True)
    modifier_groups = serializers.SerializerMethodField()
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
            "category_name",
            "category_id",
            "category_id_display",
            "image",
            "image_path",
            "image_url",
            "available",
            "is_archived",
            "disposable_fee",
            "disposable_apply_to",
            "requires_kitchen",
            "modifier_groups",
            "modifier_group_ids",
        ]

    def get_modifier_groups(self, obj: Product):
        ids = list(obj.modifier_groups.values_list("id", flat=True))
        ordered = [group_id for group_id in obj.modifier_group_order if group_id in ids]
        remaining = [group_id for group_id in ids if group_id not in ordered]
        return ordered + remaining

    def get_image_url(self, obj: Product) -> str | None:
        url = None
        if obj.image_path:
            url = obj.image_path
        elif obj.image:
            image_value = obj.image
            if not image_value.startswith("menu_image/"):
                image_value = f"menu_image/{image_value}"
            url = f"{settings.MEDIA_URL.rstrip('/')}/{image_value}"
        if not url:
            return None
        if url.startswith("/menu_image/"):
            url = url.replace("/menu_image/", "/media/menu_image/", 1)
        return url

    def update(self, instance, validated_data):
        disposable_apply_to = validated_data.get("disposable_apply_to")
        if isinstance(disposable_apply_to, str):
            try:
                validated_data["disposable_apply_to"] = json.loads(disposable_apply_to)
            except Exception:
                validated_data["disposable_apply_to"] = []
        modifier_groups = validated_data.get("modifier_groups")
        image_file = self.context.get("request").FILES.get("image") if self.context.get("request") else None
        validated_data.pop("image", None)
        old_image = instance.image
        instance = super().update(instance, validated_data)
        if modifier_groups is not None:
            instance.modifier_group_order = [group.id for group in modifier_groups]
            instance.save(update_fields=["modifier_group_order"])

        if image_file:
            saved = save_menu_image(image_file, instance.category.name)
            instance.image = saved["image"]
            instance.image_path = saved["image_path"]
            instance.save(update_fields=["image", "image_path"])
            if old_image and old_image != instance.image:
                delete_menu_image_by_image_field(old_image)

        return instance

    def create(self, validated_data):
        disposable_apply_to = validated_data.get("disposable_apply_to")
        if isinstance(disposable_apply_to, str):
            try:
                validated_data["disposable_apply_to"] = json.loads(disposable_apply_to)
            except Exception:
                validated_data["disposable_apply_to"] = []
        modifier_groups = validated_data.get("modifier_groups")
        image_file = self.context.get("request").FILES.get("image") if self.context.get("request") else None
        validated_data.pop("image", None)
        product = super().create(validated_data)
        if modifier_groups is not None:
            product.modifier_group_order = [group.id for group in modifier_groups]
            product.save(update_fields=["modifier_group_order"])
        if image_file:
            saved = save_menu_image(image_file, product.category.name)
            product.image = saved["image"]
            product.image_path = saved["image_path"]
            product.save(update_fields=["image", "image_path"])
        return product


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

    def validate(self, attrs):
        applies_to = attrs.get("applies_to")
        if applies_to is None and self.instance:
            applies_to = self.instance.applies_to

        target_product_ids = attrs.get("target_product_ids")
        if applies_to == "products":
            if target_product_ids is None and self.instance:
                target_product_ids = list(
                    self.instance.targets.filter(product__isnull=False).values_list("product_id", flat=True)
                )
            if not target_product_ids:
                raise serializers.ValidationError(
                    {"target_product_ids": "Selecciona al menos un producto."}
                )
            existing_count = Product.objects.filter(id__in=target_product_ids).count()
            if existing_count != len(set(target_product_ids)):
                raise serializers.ValidationError(
                    {"target_product_ids": "Algunos productos seleccionados no existen."}
                )
        return attrs

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
