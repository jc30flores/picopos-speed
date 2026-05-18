from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("items/", views.InventoryItemListCreateView.as_view(), name="inventory-items"),
    path("items/<int:pk>/", views.InventoryItemDetailView.as_view(), name="inventory-item-detail"),
    path("items/<int:pk>/add-stock/", views.InventoryItemAddStockView.as_view(), name="inventory-item-add-stock"),
    path("items/<int:pk>/adjust-stock/", views.InventoryItemAdjustStockView.as_view(), name="inventory-item-adjust-stock"),
    path("movements/", views.InventoryMovementListView.as_view(), name="inventory-movements"),
    path("adjustments/", views.InventoryAdjustmentCreateView.as_view(), name="inventory-adjustments"),
    path("counts/", views.InventoryCountListCreateView.as_view(), name="inventory-counts"),
    path("counts/<int:pk>/", views.InventoryCountDetailView.as_view(), name="inventory-count-detail"),
    path("counts/<int:pk>/lines/", views.InventoryCountLinesUpdateView.as_view(), name="inventory-count-lines"),
    path("counts/<int:pk>/lines/bulk-update/", views.InventoryCountLinesUpdateView.as_view(), name="inventory-count-lines-bulk-update"),
    path("counts/<int:pk>/finalize/", views.InventoryCountFinalizeView.as_view(), name="inventory-count-finalize"),
    path("counts/<int:pk>/apply/", views.InventoryCountApplyView.as_view(), name="inventory-count-apply"),
    path("counts/<int:pk>/cancel/", views.InventoryCountCancelView.as_view(), name="inventory-count-cancel"),
    path("reports/adjustments/", views.InventoryAdjustmentsReportView.as_view(), name="inventory-report-adjustments"),
    path("reports/adjustments/pdf/", views.InventoryAdjustmentsReportPdfView.as_view(), name="inventory-report-adjustments-pdf"),
    path("reports/counts/", views.InventoryCountsReportView.as_view(), name="inventory-report-counts"),
    path("reports/counts/<int:pk>/", views.InventoryCountReportDetailView.as_view(), name="inventory-report-count-detail"),
    path("reports/counts/<int:pk>/pdf/", views.InventoryCountReportPdfView.as_view(), name="inventory-report-count-pdf"),
    path("orders/<int:order_id>/availability-check/", views.OrderInventoryAvailabilityCheckView.as_view(), name="inventory-order-availability-check"),
    path("orders/<int:order_id>/reverse/", views.OrderInventoryReverseView.as_view(), name="inventory-order-reverse"),
    path("catalog-links/<int:product_id>/", views.CatalogProductInventoryLinksView.as_view(), name="inventory-catalog-links"),
    path("category-links/<int:category_id>/", views.CategoryInventoryLinksView.as_view(), name="inventory-category-links"),
    path("product-effective-links/<int:product_id>/", views.ProductEffectiveInventoryLinksView.as_view(), name="inventory-product-effective-links"),
]
