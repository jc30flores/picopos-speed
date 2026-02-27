import os
import logging
from rest_framework import generics, status
from django.db import transaction
from rest_framework.permissions import SAFE_METHODS, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from apps.core.audit import log_audit
from apps.core.permissions import IsAuthenticatedAndActive, IsAdminOrManager
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from apps.menu.models import Category, Product, ModifierGroup, Modifier, Discount
from apps.menu.serializers import (
    CategorySerializer,
    ProductSerializer,
    ModifierGroupSerializer,
    ModifierSerializer,
    DiscountSerializer,
)

logger = logging.getLogger(__name__)


class CategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = CategorySerializer

    def get_queryset(self):
        queryset = Category.objects.filter(is_active=True)
        query = self.request.query_params.get("q")
        if query:
            normalized = query.strip().upper()
            if normalized:
                queryset = queryset.filter(name__icontains=normalized)
        return queryset.order_by("name")

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAdminOrManager()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"]
        category, created = Category.objects.get_or_create(name=name, defaults={"is_active": True})
        if not category.is_active:
            category.is_active = True
            category.save(update_fields=["is_active"])
        if created:
            log_audit(self.request, "menu.category.create", "Category", category.id, {"name": category.name})
        response_serializer = self.get_serializer(category)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        queryset = Product.objects.select_related("category").prefetch_related("modifier_groups")
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
        return queryset

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
        product = serializer.save()
        log_audit(self.request, "menu.product.create", "Product", product.id, {"name": product.name})


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = Product.objects.select_related("category").prefetch_related("modifier_groups")

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


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    permission_classes = [IsAdminOrManager]

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        if category.products.filter(is_archived=False).exists():
            return Response(
                {"detail": "No se puede eliminar; primero mueve o elimina los productos."},
                status=status.HTTP_409_CONFLICT,
            )
        category.delete()
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




class ModifierGroupDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ModifierGroupSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = ModifierGroup.objects.prefetch_related("modifiers")

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticatedAndActive()]
        return [IsAdminOrManager()]


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
