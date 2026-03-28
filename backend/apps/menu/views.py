import os
import logging
from decimal import Decimal, InvalidOperation
from secrets import compare_digest
from functools import lru_cache
from rest_framework import generics, status
from django.db import transaction, connection
from django.db import models
from django.db.models.deletion import ProtectedError
from rest_framework.permissions import SAFE_METHODS, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from django.conf import settings
from apps.core.audit import log_audit
from apps.core.permissions import IsAuthenticatedAndActive, IsAdminOrManager, IsCashierOrManagerOrAdmin
from apps.core.models import ServiceType
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from apps.menu.models import Category, Product, ModifierGroup, Modifier, Discount, ProductSpecialPriceRule, PriceChangeAudit
from apps.core.models import Branch
from apps.menu.serializers import (
    CategorySerializer,
    ProductSerializer,
    ModifierGroupSerializer,
    ModifierSerializer,
    DiscountSerializer,
    ProductSpecialPriceRuleSerializer,
)

logger = logging.getLogger(__name__)


def _parse_effective_context(request):
    order_type = None
    order_type_id = request.query_params.get("order_type_id")
    if order_type_id:
        try:
            order_type = ServiceType.objects.filter(id=int(order_type_id)).first()
        except (TypeError, ValueError):
            order_type = None
    at = None
    at_raw = request.query_params.get("at")
    if at_raw:
        from django.utils.dateparse import parse_datetime
        at = parse_datetime(at_raw)
    return {"order_type": order_type, "at": at}


@lru_cache(maxsize=1)
def _product_sort_order_column_exists() -> bool:
    table_name = Product._meta.db_table
    with connection.cursor() as cursor:
        columns = connection.introspection.get_table_description(cursor, table_name)
    return any(column.name == "sort_order" for column in columns)

class CategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = CategorySerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        queryset = Category.objects.filter(is_active=True)
        include_hidden = self.request.query_params.get("include_hidden") in {"1", "true", "True"}
        user = getattr(self.request, "user", None)
        can_view_hidden = bool(
            include_hidden
            and user
            and user.is_authenticated
            and getattr(user, "role", None) in {"admin", "manager"}
        )
        if not can_view_hidden:
            queryset = queryset.filter(is_hidden=False)

        query = self.request.query_params.get("q")
        if query:
            normalized = query.strip().upper()
            if normalized:
                queryset = queryset.filter(name__icontains=normalized)
        return queryset.order_by("position", "id")

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAdminOrManager()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"]
        next_position = (Category.objects.aggregate(max_position=models.Max("position")).get("max_position") or -1) + 1
        category, created = Category.objects.get_or_create(name=name, defaults={"is_active": True, "position": next_position})

        update_fields = []
        if not category.is_active:
            category.is_active = True
            update_fields.append("is_active")
        if category.position != next_position:
            category.position = next_position
            update_fields.append("position")
        if update_fields:
            category.save(update_fields=update_fields)

        image_file = request.FILES.get("image")
        if image_file:
            category.image = image_file
            category.save(update_fields=["image", "image_path"])

        if created:
            log_audit(self.request, "menu.category.create", "Category", category.id, {"name": category.name})
        response_serializer = self.get_serializer(category)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CategoryReorderView(APIView):
    permission_classes = [IsAdminOrManager]

    def patch(self, request):
        ordered_ids = request.data.get("ordered_ids") or []
        if not isinstance(ordered_ids, list) or not all(isinstance(item, int) for item in ordered_ids):
            return Response({"detail": "ordered_ids debe ser una lista de IDs."}, status=status.HTTP_400_BAD_REQUEST)
        if len(set(ordered_ids)) != len(ordered_ids):
            return Response({"detail": "ordered_ids contiene IDs duplicados."}, status=status.HTTP_400_BAD_REQUEST)

        expected_ids = list(
            Category.objects.filter(is_active=True, is_hidden=False)
            .order_by("position", "id")
            .values_list("id", flat=True)
        )
        if sorted(expected_ids) != sorted(ordered_ids):
            return Response({"detail": "ordered_ids debe incluir todas las categorías activas visibles."}, status=status.HTTP_400_BAD_REQUEST)

        categories = {category.id: category for category in Category.objects.filter(id__in=ordered_ids)}
        with transaction.atomic():
            for index, category_id in enumerate(ordered_ids):
                categories[category_id].position = index
            Category.objects.bulk_update(categories.values(), ["position"])

        serialized = CategorySerializer(
            Category.objects.filter(id__in=ordered_ids).order_by("position", "id"),
            many=True,
        )
        return Response(serialized.data, status=status.HTTP_200_OK)


class ProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update(_parse_effective_context(self.request))
        return context

    def get_queryset(self):
        queryset = Product.objects.select_related("category").prefetch_related("modifier_groups", "special_price_rules__order_types")
        query = self.request.query_params.get("search") or self.request.query_params.get("q")
        if query:
            queryset = queryset.filter(name__icontains=query.strip())
        category_id = self.request.query_params.get("category_id") or self.request.query_params.get("categoryId")
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        ids_param = self.request.query_params.get("ids")
        if ids_param:
            ids = [int(item) for item in ids_param.split(",") if item.strip().isdigit()]
            if ids:
                queryset = queryset.filter(id__in=ids)
        include_archived = self.request.query_params.get("include_archived") in {"1", "true", "True"}
        if not include_archived:
            queryset = queryset.filter(is_archived=False)
        if _product_sort_order_column_exists():
            return queryset.order_by("category__position", "category_id", "sort_order", "name", "id")
        return queryset.order_by("category__position", "category_id", "name", "id")

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = request.query_params.get("page")
        limit = request.query_params.get("limit")
        if limit and limit.isdigit():
            limit_value = int(limit)
            if limit_value > 0:
                page_value = int(page) if page and page.isdigit() else 1
                offset = max(page_value - 1, 0) * limit_value
                queryset = queryset[offset : offset + limit_value]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAdminOrManager()]

    def perform_create(self, serializer):
        category = serializer.validated_data.get("category")
        next_sort_order = (
            Product.objects.filter(category=category)
            .aggregate(max_sort=models.Max("sort_order"))
            .get("max_sort")
            or -1
        ) + 1
        product = serializer.save(sort_order=next_sort_order)
        log_audit(self.request, "menu.product.create", "Product", product.id, {"name": product.name})


class ProductReorderView(APIView):
    permission_classes = [IsAdminOrManager]

    def post(self, request):
        ordered_ids = request.data.get("ordered_ids") or []
        category_id = request.data.get("category_id")

        if not isinstance(ordered_ids, list) or not all(isinstance(item, int) for item in ordered_ids):
            return Response({"detail": "ordered_ids debe ser una lista de IDs."}, status=status.HTTP_400_BAD_REQUEST)
        if len(set(ordered_ids)) != len(ordered_ids):
            return Response({"detail": "ordered_ids contiene IDs duplicados."}, status=status.HTTP_400_BAD_REQUEST)

        base_qs = Product.objects.filter(is_archived=False)
        if category_id is not None:
            base_qs = base_qs.filter(category_id=category_id)

        expected_ids = list(base_qs.order_by("sort_order", "id").values_list("id", flat=True))
        if sorted(expected_ids) != sorted(ordered_ids):
            return Response({"detail": "ordered_ids debe incluir todos los productos del filtro actual."}, status=status.HTTP_400_BAD_REQUEST)

        products_by_id = {product.id: product for product in Product.objects.filter(id__in=ordered_ids)}
        with transaction.atomic():
            for index, product_id in enumerate(ordered_ids):
                products_by_id[product_id].sort_order = index
            Product.objects.bulk_update(products_by_id.values(), ["sort_order"])

        return Response({"ok": True}, status=status.HTTP_200_OK)


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = Product.objects.select_related("category").prefetch_related("modifier_groups", "special_price_rules__order_types")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update(_parse_effective_context(self.request))
        return context

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAdminOrManager()]

    def perform_update(self, serializer):
        product = serializer.save()
        modifier_group_ids = []
        if hasattr(self.request.data, "getlist"):
            modifier_group_ids = self.request.data.getlist("modifier_group_ids")
        elif "modifier_group_ids" in self.request.data:
            modifier_group_ids = self.request.data.get("modifier_group_ids") or []
        logger.info(
            "Product updated",
            extra={
                "product_id": product.id,
                "modifier_group_ids": modifier_group_ids,
                "user_id": getattr(self.request.user, "id", None),
            },
        )
        log_audit(
            self.request,
            "menu.product.update",
            "Product",
            product.id,
            {"name": product.name, "modifier_group_ids": modifier_group_ids},
        )

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        referenced = product.order_items.exists()
        if referenced:
            product.is_archived = True
            product.available = False
            product.save(update_fields=["is_archived", "available", "updated_at"] if hasattr(product, "updated_at") else ["is_archived", "available"])
            return Response({"detail": "Producto archivado porque tiene historial de ventas."}, status=status.HTTP_200_OK)
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductDuplicateView(APIView):
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def post(self, request, pk: int):
        product = Product.objects.select_related("category").prefetch_related("productmodifiergroup_set").filter(pk=pk).first()
        if not product:
            return Response({"detail": "Producto no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        base_name = product.name

        def _next_name() -> str:
            existing = Product.objects.filter(name__startswith=f"{base_name} #").values_list("name", flat=True)
            max_n = 0
            for name in existing:
                suffix = name.replace(f"{base_name} #", "", 1).strip()
                if suffix.isdigit():
                    max_n = max(max_n, int(suffix))
            return f"{base_name} #{max_n + 1}"

        cloned = None
        for attempt in range(10):
            candidate = _next_name()
            try:
                cloned = Product.objects.create(
                    name=candidate,
                    description=product.description,
                    price=product.price,
                    category=product.category,
                    sort_order=product.sort_order + attempt + 1,
                    image=product.image,
                    image_path=product.image_path,
                    available=product.available,
                    is_archived=product.is_archived,
                    disposable_fee=product.disposable_fee,
                    disposable_apply_to=product.disposable_apply_to,
                    requires_kitchen=product.requires_kitchen,
                    modifier_group_order=product.modifier_group_order,
                )
                break
            except Exception:
                cloned = None

        if cloned is None:
            return Response({"detail": "No se pudo duplicar el producto"}, status=status.HTTP_400_BAD_REQUEST)

        for link in product.productmodifiergroup_set.all():
            cloned.productmodifiergroup_set.create(modifier_group_id=link.modifier_group_id, show_in_pos=link.show_in_pos)

        logger.info("menu.product.duplicate source=%s duplicate=%s", product.id, cloned.id)
        log_audit(request, "menu.product.duplicate", "Product", cloned.id, {"source_product_id": product.id, "name": cloned.name})
        return Response(ProductSerializer(cloned, context={"request": request}).data, status=status.HTTP_201_CREATED)


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    permission_classes = [IsAdminOrManager]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()

        active_products = list(
            Product.objects.filter(category=category, is_archived=False)
            .order_by("name")
            .values_list("name", flat=True)
        )
        if active_products:
            return Response(
                {
                    "detail": "No se puede eliminar la categoría porque tiene productos activos asociados.",
                    "active_products": active_products,
                },
                status=status.HTTP_409_CONFLICT,
            )

        inactive_products_qs = Product.objects.filter(category=category, is_archived=True)
        try:
            with transaction.atomic():
                if inactive_products_qs.exists():
                    fallback_name = "SIN CATEGORÍA"
                    if category.name == fallback_name:
                        fallback_name = "SIN CATEGORÍA (ARCHIVADOS)"
                    fallback_category, _ = Category.objects.get_or_create(name=fallback_name, defaults={"is_hidden": True})
                    if not fallback_category.is_hidden:
                        fallback_category.is_hidden = True
                        fallback_category.save(update_fields=["is_hidden"])
                    inactive_products_qs.update(category=fallback_category)
                category.delete()
        except ProtectedError:
            blocking_active_products = list(
                Product.objects.filter(category=category, is_archived=False)
                .order_by("name")
                .values_list("name", flat=True)
            )
            return Response(
                {
                    "detail": "No se puede eliminar la categoría porque tiene productos activos asociados.",
                    "active_products": blocking_active_products,
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class MenuImageHealthView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        return Response(
            {
                "ok": True,
                "menu_image_dir": str(settings.MEDIA_ROOT),
                "exists": os.path.isdir(settings.MEDIA_ROOT),
            }
        )


class ModifierGroupListCreateView(generics.ListCreateAPIView):
    serializer_class = ModifierGroupSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return ModifierGroup.objects.prefetch_related("modifiers").order_by("name")

    def create(self, request, *args, **kwargs):
        modifiers_raw = request.data.get("modifiers")
        modifiers = []
        if isinstance(modifiers_raw, str):
            import json
            try:
                modifiers = json.loads(modifiers_raw)
            except Exception:
                modifiers = []
        elif isinstance(modifiers_raw, list):
            modifiers = modifiers_raw

        payload = {
            "name": request.data.get("name"),
            "required": request.data.get("required"),
            "min_selection": request.data.get("min_selection"),
            "max_selection": request.data.get("max_selection"),
            "modifiers": modifiers,
        }
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        group = serializer.save()
        headers = self.get_success_headers(serializer.data)
        return Response(self.get_serializer(group).data, status=status.HTTP_201_CREATED, headers=headers)

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticatedAndActive()]
        return [IsAdminOrManager()]




class ModifierGroupDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ModifierGroupSerializer
    parser_classes = [JSONParser]
    queryset = ModifierGroup.objects.prefetch_related("modifiers")

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticatedAndActive()]
        return [IsAdminOrManager()]

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        group.products.clear()
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ModifierGroupImageUploadView(generics.UpdateAPIView):
    serializer_class = ModifierGroupSerializer
    parser_classes = [MultiPartParser, FormParser]
    queryset = ModifierGroup.objects.prefetch_related("modifiers")

    def get_permissions(self):
        return [IsAdminOrManager()]

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        image_file = request.FILES.get("image")
        if not image_file:
            return Response({"image": "Debes enviar un archivo en el campo 'image'."}, status=status.HTTP_400_BAD_REQUEST)

        from apps.menu.utils.images import save_menu_image

        saved = save_menu_image(image_file, "MODIFIER_GROUPS")
        instance.image = saved["image"]
        instance.image_path = saved["image_path"]
        instance.save(update_fields=["image", "image_path"])
        return Response(self.get_serializer(instance).data)


class ModifierOptionDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ModifierSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = Modifier.objects.select_related("group")

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticatedAndActive()]
        return [IsAdminOrManager()]

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        image_file = request.FILES.get("image")
        if image_file:
            from apps.menu.utils.images import save_menu_image
            saved = save_menu_image(image_file, "MODIFIERS")
            instance.image = saved["image"]
            instance.image_path = saved["image_path"]
            instance.save(update_fields=["image", "image_path"])
            return Response(self.get_serializer(instance).data)
        return super().patch(request, *args, **kwargs)


class ModifierImageUploadView(generics.UpdateAPIView):
    serializer_class = ModifierSerializer
    parser_classes = [MultiPartParser, FormParser]
    queryset = Modifier.objects.select_related("group")

    def get_permissions(self):
        return [IsAdminOrManager()]

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        image_file = request.FILES.get("image")
        if not image_file:
            return Response({"image": "Debes enviar un archivo en el campo 'image'."}, status=status.HTTP_400_BAD_REQUEST)

        from apps.menu.utils.images import save_menu_image

        saved = save_menu_image(image_file, "MODIFIERS")
        instance.image = saved["image"]
        instance.image_path = saved["image_path"]
        instance.save(update_fields=["image", "image_path"])
        return Response(self.get_serializer(instance).data)

class ProductModifierGroupsReorderView(APIView):
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def patch(self, request, product_id: int):
        ordered_ids = request.data.get("ordered_ids") or []
        product = Product.objects.prefetch_related("modifier_groups").filter(id=product_id).first()
        if not product:
            return Response({"detail": "Producto no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        existing_ids = list(product.modifier_groups.values_list("id", flat=True))
        if sorted(existing_ids) != sorted(ordered_ids):
            return Response({"detail": "ordered_ids inválido para este producto"}, status=status.HTTP_400_BAD_REQUEST)
        product.modifier_group_order = ordered_ids
        product.save(update_fields=["modifier_group_order"])
        return Response({"ordered_ids": ordered_ids}, status=status.HTTP_200_OK)


class ModifierGroupOptionsReorderView(APIView):
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def patch(self, request, group_id: int):
        ordered_ids = request.data.get("ordered_ids") or []
        group = ModifierGroup.objects.prefetch_related("modifiers").filter(id=group_id).first()
        if not group:
            return Response({"detail": "Grupo no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        existing_ids = list(group.modifiers.values_list("id", flat=True))
        if sorted(existing_ids) != sorted(ordered_ids):
            return Response({"detail": "ordered_ids inválido para este grupo"}, status=status.HTTP_400_BAD_REQUEST)
        for idx, modifier_id in enumerate(ordered_ids):
            Modifier.objects.filter(id=modifier_id, group=group).update(sort_order=idx)
        return Response({"ordered_ids": ordered_ids}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        group = serializer.save()
        log_audit(self.request, "menu.modifier_group.create", "ModifierGroup", group.id, {"name": group.name})


class ProductSpecialPriceListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSpecialPriceRuleSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        return ProductSpecialPriceRule.objects.filter(product_id=self.kwargs["product_id"]).prefetch_related("order_types").order_by("-priority", "id")

    def perform_create(self, serializer):
        product = Product.objects.filter(id=self.kwargs["product_id"]).first()
        if not product:
            raise ValidationError({"product": "Producto no encontrado."})
        serializer.save(product=product)


class ProductSpecialPriceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSpecialPriceRuleSerializer
    permission_classes = [IsAdminOrManager]
    queryset = ProductSpecialPriceRule.objects.prefetch_related("order_types")

class DiscountListCreateView(generics.ListCreateAPIView):
    serializer_class = DiscountSerializer

    def get_queryset(self):
        return Discount.objects.prefetch_related("targets").order_by("name")

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticatedAndActive()]
        return [IsAdminOrManager()]

    def perform_create(self, serializer):
        discount = serializer.save()
        log_audit(self.request, "menu.discount.create", "Discount", discount.id, {"name": discount.name})


class DiscountDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = DiscountSerializer
    queryset = Discount.objects.prefetch_related("targets").all()

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticatedAndActive()]
        return [IsAdminOrManager()]

    def perform_update(self, serializer):
        discount = serializer.save()
        log_audit(self.request, "menu.discount.update", "Discount", discount.id, {"name": discount.name})


class ProductChangePriceView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    @transaction.atomic
    def post(self, request, pk: int):
        configured_code = (getattr(settings, "CODE_CHANGE_PRICE", "") or "").strip()
        if not configured_code:
            return Response({"detail": "Cambio de precio deshabilitado por configuración."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        code = str(request.data.get("code") or "").strip()
        if not compare_digest(code, configured_code):
            return Response({"detail": "Código incorrecto"}, status=status.HTTP_403_FORBIDDEN)

        validate_only = bool(request.data.get("validate_only"))
        if validate_only:
            return Response({"success": True, "validated": True}, status=status.HTTP_200_OK)

        product = Product.objects.filter(pk=pk).first()
        if not product:
            return Response({"detail": "Producto no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        raw_new_price = request.data.get("new_price")
        try:
            new_price = Decimal(str(raw_new_price)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"new_price": "Precio inválido"}, status=status.HTTP_400_BAD_REQUEST)
        if new_price <= 0:
            return Response({"new_price": "Debe ser mayor que 0"}, status=status.HTTP_400_BAD_REQUEST)

        old_price = Decimal(product.price).quantize(Decimal("0.01"))
        product.price = new_price
        product.save(update_fields=["price"])

        branch_id = request.query_params.get("branch_id")
        branch = None
        if str(branch_id).isdigit():
            branch = Branch.objects.filter(id=int(branch_id)).first()
        if branch is None:
            branch = Branch.objects.filter(is_active=True).order_by("id").first()
        ip_address = (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0] or request.META.get("REMOTE_ADDR") or "").strip() or None

        PriceChangeAudit.objects.create(
            product=product,
            old_price=old_price,
            new_price=new_price,
            branch=branch,
            user=request.user if getattr(request.user, "is_authenticated", False) else None,
            reason="emergency",
            ip_address=ip_address,
        )

        from django.utils import timezone

        return Response(
            {
                "success": True,
                "product_id": product.id,
                "old_price": f"{old_price:.2f}",
                "new_price": f"{new_price:.2f}",
                "updated_at": timezone.now().isoformat(),
            },
            status=status.HTTP_200_OK,
        )
