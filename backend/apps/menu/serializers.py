from rest_framework import serializers
from django.db import transaction
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
    id = serializers.IntegerField(required=False)
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

    def _coerce_modifier_id(self, value):
        if value in (None, "", 0, "0"):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError({"modifiers": "ID de opción inválido."})

    def _validate_modifier_payload(self, group: ModifierGroup, modifiers_data: list[dict]):
        normalized_names: set[str] = set()
        for item in modifiers_data:
            name = (item.get("name") or "").strip()
            if not name:
                raise serializers.ValidationError({"modifiers": "Todas las opciones deben tener nombre."})
            lower = name.lower()
            if lower in normalized_names:
                raise serializers.ValidationError({"modifiers": f"La opción '{name}' está duplicada en el grupo."})
            normalized_names.add(lower)

    def _sync_modifiers(self, group: ModifierGroup, modifiers_data: list[dict]):
        self._validate_modifier_payload(group, modifiers_data)
        existing = {modifier.id: modifier for modifier in group.modifiers.all()}
        seen_ids: set[int] = set()

        for index, modifier_data in enumerate(modifiers_data):
            modifier_id = self._coerce_modifier_id(modifier_data.get("id"))
            option_name = (modifier_data.get("name") or "").strip()
            payload = {
                "name": option_name,
                "price": modifier_data.get("price", 0),
                "is_active": modifier_data.get("is_active", True),
                "sort_order": index,
            }

            if modifier_id is not None:
                modifier = existing.get(modifier_id)
                if not modifier:
                    raise serializers.ValidationError({"modifiers": f"La opción con id {modifier_id} no pertenece a este grupo."})
                conflict_qs = group.modifiers.filter(name__iexact=option_name).exclude(id=modifier_id)
                if conflict_qs.exists():
                    raise serializers.ValidationError({"modifiers": f"Ya existe una opción con el nombre '{option_name}' en este grupo."})
                for key, value in payload.items():
                    setattr(modifier, key, value)
                modifier.save(update_fields=["name", "price", "is_active", "sort_order"])
                seen_ids.add(modifier_id)
                continue

            if group.modifiers.filter(name__iexact=option_name).exists():
                raise serializers.ValidationError(
                    {
                        "modifiers": (
                            f"La opción '{option_name}' ya existe en este grupo. "
                            "Incluye el campo 'id' para actualizar opciones existentes."
                        )
                    }
                )
            created = Modifier.objects.create(group=group, **payload)
            seen_ids.add(created.id)

        stale_ids = set(existing.keys()) - seen_ids
        if stale_ids:
            group.modifiers.filter(id__in=stale_ids).delete()

    def create(self, validated_data):
        modifiers_data = validated_data.pop("modifiers", [])
        request = self.context.get("request")
        group_image_file = request.FILES.get("group_image") if request else None

        with transaction.atomic():
            group = ModifierGroup.objects.create(**validated_data)
            self._sync_modifiers(group, modifiers_data)

            if group_image_file:
                saved_group = save_menu_image(group_image_file, "MODIFIER_GROUPS")
                group.image = saved_group["image"]
                group.image_path = saved_group["image_path"]
                group.save(update_fields=["image", "image_path"])

            for index, modifier in enumerate(group.modifiers.order_by("sort_order", "id")):
                option_image_file = request.FILES.get(f"option_image_{index}") if request else None
                if option_image_file:
                    saved_option = save_menu_image(option_image_file, "MODIFIERS")
                    modifier.image = saved_option["image"]
                    modifier.image_path = saved_option["image_path"]
                    modifier.save(update_fields=["image", "image_path"])
            return group

    def update(self, instance, validated_data):
        modifiers_data = validated_data.pop("modifiers", None)
        request = self.context.get("request")
        if modifiers_data is None and request is not None and "modifiers" in request.data:
            raw_modifiers = request.data.get("modifiers")
            if isinstance(raw_modifiers, str):
                try:
                    modifiers_data = json.loads(raw_modifiers)
                except Exception:
                    raise serializers.ValidationError({"modifiers": "Formato de opciones inválido."})
            elif isinstance(raw_modifiers, list):
                modifiers_data = raw_modifiers
        group_image_file = request.FILES.get("image") if request else None

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            if modifiers_data is not None:
                self._sync_modifiers(instance, modifiers_data)

            if group_image_file:
                saved_group = save_menu_image(group_image_file, "MODIFIER_GROUPS")
                instance.image = saved_group["image"]
                instance.image_path = saved_group["image_path"]
                instance.save(update_fields=["image", "image_path"])

            return instance


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
