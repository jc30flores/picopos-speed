from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("items/", views.InventoryItemListCreateView.as_view(), name="inventory-items"),
    path("items/<int:pk>/", views.InventoryItemDetailView.as_view(), name="inventory-item-detail"),
    path("items/<int:pk>/add-stock/", views.InventoryItemAddStockView.as_view(), name="inventory-item-add-stock"),
    path("items/<int:pk>/adjust-stock/", views.InventoryItemAdjustStockView.as_view(), name="inventory-item-adjust-stock"),
    path("movements/", views.InventoryMovementListView.as_view(), name="inventory-movements"),
    path("adjustments/", views.InventoryAdjustmentCreateView.as_view(), name="inventory-adjustments"),
    path("catalog-links/<int:product_id>/", views.CatalogProductInventoryLinksView.as_view(), name="inventory-catalog-links"),
    path("category-links/<int:category_id>/", views.CategoryInventoryLinksView.as_view(), name="inventory-category-links"),
    path("product-effective-links/<int:product_id>/", views.ProductEffectiveInventoryLinksView.as_view(), name="inventory-product-effective-links"),
]
