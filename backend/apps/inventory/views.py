import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdminOrManager
from apps.inventory.models import CatalogProductInventoryLink, InventoryItem, InventoryMovement
from apps.inventory.serializers import (
    CatalogInventoryLinkSerializer,
    CatalogInventoryLinkWriteSerializer,
    InventoryAddStockSerializer,
    InventoryAdjustStockSerializer,
    InventoryItemSerializer,
    InventoryMovementSerializer,
)

logger = logging.getLogger(__name__)


class InventoryItemListCreateView(generics.ListCreateAPIView):
    serializer_class = InventoryItemSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        queryset = InventoryItem.objects.all().order_by("name", "id")
        query = (self.request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(sku__icontains=query))
        is_active = self.request.query_params.get("is_active")
        if is_active in {"true", "false"}:
            queryset = queryset.filter(is_active=(is_active == "true"))
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        initial_stock = Decimal(str(self.request.data.get("initial_stock") or self.request.data.get("current_stock") or "0"))
        item = serializer.save(current_stock=initial_stock)
        if initial_stock != 0:
            InventoryMovement.objects.create(
                inventory_item=item,
                movement_type=InventoryMovement.TYPE_INITIAL_STOCK,
                quantity_change=initial_stock,
                quantity_before=Decimal("0"),
                quantity_after=initial_stock,
                reason="Stock inicial",
                created_by=self.request.user,
            )
        logger.info("inventory.item.create item_id=%s stock=%s user_id=%s", item.id, initial_stock, self.request.user.id)


class InventoryItemDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = InventoryItemSerializer
    queryset = InventoryItem.objects.all()
    permission_classes = [IsAdminOrManager]

    def perform_update(self, serializer):
        item = serializer.save()
        logger.info("inventory.item.update item_id=%s user_id=%s", item.id, self.request.user.id)


class InventoryItemAddStockView(APIView):
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def post(self, request, pk: int):
        item = InventoryItem.objects.select_for_update().filter(pk=pk).first()
        if not item:
            return Response({"detail": "Producto de inventario no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = InventoryAddStockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        qty = serializer.validated_data["quantity"]
        reason = serializer.validated_data.get("reason") or "Entrada manual"
        before = Decimal(item.current_stock)
        after = before + qty
        item.current_stock = after
        item.save(update_fields=["current_stock", "updated_at"])
        InventoryMovement.objects.create(
            inventory_item=item,
            movement_type=InventoryMovement.TYPE_STOCK_ADD,
            quantity_change=qty,
            quantity_before=before,
            quantity_after=after,
            reason=reason,
            created_by=request.user,
        )
        return Response(InventoryItemSerializer(item).data)


class InventoryItemAdjustStockView(APIView):
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def post(self, request, pk: int):
        item = InventoryItem.objects.select_for_update().filter(pk=pk).first()
        if not item:
            return Response({"detail": "Producto de inventario no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = InventoryAdjustStockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        set_stock = serializer.validated_data.get("set_stock")
        delta = serializer.validated_data.get("delta")
        before = Decimal(item.current_stock)
        after = Decimal(set_stock) if set_stock is not None else before + Decimal(delta)
        item.current_stock = after
        item.save(update_fields=["current_stock", "updated_at"])
        InventoryMovement.objects.create(
            inventory_item=item,
            movement_type=InventoryMovement.TYPE_STOCK_ADJUST,
            quantity_change=(after - before),
            quantity_before=before,
            quantity_after=after,
            reason=serializer.validated_data.get("reason") or "Ajuste manual",
            created_by=request.user,
        )
        return Response(InventoryItemSerializer(item).data)


class InventoryMovementListView(generics.ListAPIView):
    serializer_class = InventoryMovementSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        queryset = InventoryMovement.objects.select_related("inventory_item", "created_by")
        item_id = self.request.query_params.get("inventory_item")
        if item_id and item_id.isdigit():
            queryset = queryset.filter(inventory_item_id=int(item_id))
        movement_type = self.request.query_params.get("movement_type")
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)
        return queryset.order_by("-created_at", "-id")[:500]


class CatalogProductInventoryLinksView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request, product_id: int):
        rows = CatalogProductInventoryLink.objects.filter(catalog_product_id=product_id).select_related("inventory_item")
        return Response(CatalogInventoryLinkSerializer(rows, many=True).data)

    @transaction.atomic
    def put(self, request, product_id: int):
        serializer = CatalogInventoryLinkWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        CatalogProductInventoryLink.objects.filter(catalog_product_id=product_id).delete()
        to_create = [
            CatalogProductInventoryLink(
                catalog_product_id=product_id,
                inventory_item_id=row["inventory_item"],
                quantity_required=row["quantity_required"],
            )
            for row in serializer.validated_data["links"]
        ]
        CatalogProductInventoryLink.objects.bulk_create(to_create)
        rows = CatalogProductInventoryLink.objects.filter(catalog_product_id=product_id).select_related("inventory_item")
        logger.info("inventory.catalog_links.save product_id=%s links=%s user_id=%s", product_id, len(to_create), request.user.id)
        return Response(CatalogInventoryLinkSerializer(rows, many=True).data)
