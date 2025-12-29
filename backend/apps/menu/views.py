from rest_framework import generics
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


class ProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Product.objects.select_related("category").prefetch_related("modifier_groups")


class ModifierGroupListCreateView(generics.ListCreateAPIView):
    serializer_class = ModifierGroupSerializer

    def get_queryset(self):
        return ModifierGroup.objects.prefetch_related("modifiers").order_by("name")


class DiscountListCreateView(generics.ListCreateAPIView):
    serializer_class = DiscountSerializer

    def get_queryset(self):
        return Discount.objects.prefetch_related("targets").order_by("name")


class DiscountDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = DiscountSerializer
    queryset = Discount.objects.prefetch_related("targets").all()
