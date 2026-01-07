import os
from rest_framework import generics, status
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from apps.core.audit import log_audit
from apps.core.permissions import IsAuthenticatedAndActive, IsAdminOrManager
from rest_framework.parsers import MultiPartParser, FormParser
from apps.menu.models import Category, Product, ModifierGroup, Discount
from apps.menu.serializers import (
    CategorySerializer,
    ProductSerializer,
    ModifierGroupSerializer,
    DiscountSerializer,
)


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
            return [IsAuthenticatedAndActive()]
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
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Product.objects.select_related("category").prefetch_related("modifier_groups")

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticatedAndActive()]
        return [IsAdminOrManager()]

    def perform_create(self, serializer):
        product = serializer.save()
        log_audit(self.request, "menu.product.create", "Product", product.id, {"name": product.name})


class ProductDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ProductSerializer
    parser_classes = [MultiPartParser, FormParser]
    queryset = Product.objects.select_related("category").prefetch_related("modifier_groups")

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticatedAndActive()]
        return [IsAdminOrManager()]


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

    def get_queryset(self):
        return ModifierGroup.objects.prefetch_related("modifiers").order_by("name")

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticatedAndActive()]
        return [IsAdminOrManager()]

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
