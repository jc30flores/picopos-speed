from rest_framework import serializers
from apps.menu.models import Category, Product, ModifierGroup, Modifier, Discount
from apps.core.models import ServiceType


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "is_active"]


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
            "image_url",
            "available",
            "modifier_groups",
            "modifier_group_ids",
        ]

    def get_image_url(self, obj: Product) -> str | None:
        if obj.image and hasattr(obj.image, "url"):
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class DiscountSerializer(serializers.ModelSerializer):
    target_category_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        source="target_categories",
        queryset=Category.objects.all(),
        required=False,
    )
    target_product_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        source="target_products",
        queryset=Product.objects.all(),
        required=False,
    )
    service_type_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        source="service_types",
        queryset=ServiceType.objects.all(),
        required=False,
    )

    class Meta:
        model = Discount
        fields = [
            "id",
            "name",
            "description",
            "type",
            "value",
            "applies_to",
            "target_category_ids",
            "target_product_ids",
            "days",
            "start_time",
            "end_time",
            "service_type_ids",
            "min_amount",
            "requires_approval",
            "auto_apply",
            "active",
        ]
