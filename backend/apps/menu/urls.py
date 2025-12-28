from django.urls import path
from apps.menu import views

urlpatterns = [
    path("categories/", views.CategoryListCreateView.as_view(), name="menu-categories"),
    path("products/", views.ProductListCreateView.as_view(), name="menu-products"),
    path("modifier-groups/", views.ModifierGroupListCreateView.as_view(), name="menu-modifier-groups"),
    path("discounts/", views.DiscountListCreateView.as_view(), name="menu-discounts"),
]
