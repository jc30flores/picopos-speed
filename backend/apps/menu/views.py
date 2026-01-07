from rest_framework import generics
from rest_framework.permissions import SAFE_METHODS
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
    queryset = Category.objects.filter(is_active=True).order_by("name")
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticatedAndActive()]
        return [IsAdminOrManager()]

    def perform_create(self, serializer):
        category = serializer.save()
        log_audit(self.request, "menu.category.create", "Category", category.id, {"name": category.name})


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
