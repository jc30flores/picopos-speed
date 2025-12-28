from rest_framework import generics
from rest_framework.parsers import MultiPartParser, FormParser
from apps.menu.models import Category, Product
from apps.menu.serializers import CategorySerializer, ProductSerializer


class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.filter(is_active=True).order_by("name")
    serializer_class = CategorySerializer


class ProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Product.objects.select_related("category").prefetch_related("modifier_groups")
