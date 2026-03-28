from django.urls import path
from apps.menu import views

urlpatterns = [
    path("categories/", views.CategoryListCreateView.as_view(), name="menu-categories"),
    path("categories/reorder/", views.CategoryReorderView.as_view(), name="menu-categories-reorder"),
    path("categories/<int:pk>/", views.CategoryDetailView.as_view(), name="menu-categories-detail"),
    path("products/", views.ProductListCreateView.as_view(), name="menu-products"),
    path("products/reorder/", views.ProductReorderView.as_view(), name="menu-products-reorder"),
    path("products/<int:pk>/", views.ProductDetailView.as_view(), name="menu-products-detail"),
    path("products/<int:pk>/change-price/", views.ProductChangePriceView.as_view(), name="menu-products-change-price"),
    path("products/<int:pk>/duplicate/", views.ProductDuplicateView.as_view(), name="menu-products-duplicate"),
    path("products/<int:product_id>/modifier-groups/reorder/", views.ProductModifierGroupsReorderView.as_view(), name="menu-product-modifier-groups-reorder"),
    path("products/<int:product_id>/special-prices/", views.ProductSpecialPriceListCreateView.as_view(), name="menu-product-special-prices"),
    path("special-prices/<int:pk>/", views.ProductSpecialPriceDetailView.as_view(), name="menu-special-prices-detail"),
    path("image-health/", views.MenuImageHealthView.as_view(), name="menu-image-health"),
    path("modifier-groups/", views.ModifierGroupListCreateView.as_view(), name="menu-modifier-groups"),
    path("modifier-groups/<int:pk>/", views.ModifierGroupDetailView.as_view(), name="menu-modifier-groups-detail"),
    path("modifier-groups/<int:pk>/image/", views.ModifierGroupImageUploadView.as_view(), name="menu-modifier-groups-image"),
    path("modifier-options/<int:pk>/", views.ModifierOptionDetailView.as_view(), name="menu-modifier-options-detail"),
    path("modifiers/<int:pk>/image/", views.ModifierImageUploadView.as_view(), name="menu-modifiers-image"),
    path("modifier-groups/<int:group_id>/options/reorder/", views.ModifierGroupOptionsReorderView.as_view(), name="menu-modifier-group-options-reorder"),
    path("discounts/", views.DiscountListCreateView.as_view(), name="menu-discounts"),
    path("discounts/<int:pk>/", views.DiscountDetailView.as_view(), name="menu-discounts-detail"),
]
