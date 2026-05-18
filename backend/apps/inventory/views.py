import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdminOrManager
from apps.inventory.models import (
    CatalogProductInventoryLink,
    CategoryInventoryLink,
    InventoryItem,
    InventoryMovement,
    ProductInventoryOverride,
)
from apps.inventory.serializers import (
    CatalogInventoryLinkSerializer,
    CatalogInventoryLinkWriteSerializer,
    CategoryInventoryLinkSerializer,
    InventoryAddStockSerializer,
    InventoryAdjustStockSerializer,
    InventoryItemSerializer,
    InventoryMovementSerializer,
    InventoryFormalAdjustmentSerializer,
    ProductEffectiveInventoryLinkWriteSerializer,
)
from apps.inventory.services import resolve_effective_inventory_links_for_product

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
        movement_type = self.request.query_params.get("movement_type") or self.request.query_params.get("adjustment_type")
        if movement_type:
            aliases = {
                "entry": [InventoryMovement.TYPE_INVENTORY_ENTRY, InventoryMovement.TYPE_STOCK_ADD],
                "loss": [InventoryMovement.TYPE_INVENTORY_LOSS],
                "damaged": [InventoryMovement.TYPE_INVENTORY_DAMAGED],
                "correction": [InventoryMovement.TYPE_INVENTORY_CORRECTION, InventoryMovement.TYPE_STOCK_ADJUST],
                "sales": [InventoryMovement.TYPE_SALE_DEDUCTION],
            }
            queryset = queryset.filter(movement_type__in=aliases.get(movement_type, [movement_type]))
        user_id = self.request.query_params.get("user")
        if user_id and user_id.isdigit():
            queryset = queryset.filter(created_by_id=int(user_id))
        date_from = self.request.query_params.get("date_from")
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        date_to = self.request.query_params.get("date_to")
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        return queryset.order_by("-created_at", "-id")[:500]


class InventoryAdjustmentCreateView(APIView):
    permission_classes = [IsAdminOrManager]

    MOVEMENT_TYPE_BY_ADJUSTMENT = {
        "entry": InventoryMovement.TYPE_INVENTORY_ENTRY,
        "loss": InventoryMovement.TYPE_INVENTORY_LOSS,
        "damaged": InventoryMovement.TYPE_INVENTORY_DAMAGED,
        "correction": InventoryMovement.TYPE_INVENTORY_CORRECTION,
    }

    DEFAULT_REASON_BY_ADJUSTMENT = {
        "entry": "Entrada de producto",
        "loss": "Pérdida",
        "damaged": "Producto dañado",
        "correction": "Corrección de stock",
    }

    @transaction.atomic
    def post(self, request):
        serializer = InventoryFormalAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        item = InventoryItem.objects.select_for_update().filter(pk=data["inventory_item"]).first()
        if not item:
            return Response({"detail": "Artículo de inventario no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        adjustment_type = data["adjustment_type"]
        before = Decimal(item.current_stock)
        if adjustment_type == "entry":
            change = Decimal(data["quantity"])
            after = before + change
        elif adjustment_type in {"loss", "damaged"}:
            quantity = Decimal(data["quantity"])
            if quantity > before:
                return Response({"quantity": ["La cantidad no puede ser mayor al stock disponible."]}, status=status.HTTP_400_BAD_REQUEST)
            change = -quantity
            after = before + change
        else:
            after = Decimal(data["set_stock"])
            change = after - before

        item.current_stock = after
        item.save(update_fields=["current_stock", "updated_at"])
        movement = InventoryMovement.objects.create(
            inventory_item=item,
            movement_type=self.MOVEMENT_TYPE_BY_ADJUSTMENT[adjustment_type],
            quantity_change=change,
            quantity_before=before,
            quantity_after=after,
            reference_type="inventory_adjustment",
            reason=data.get("reason") or self.DEFAULT_REASON_BY_ADJUSTMENT[adjustment_type],
            created_by=request.user,
        )
        return Response({
            "message": "Ajuste registrado correctamente.",
            "item": InventoryItemSerializer(item).data,
            "movement": InventoryMovementSerializer(movement).data,
            "stock_before": before,
            "stock_after": after,
            "adjustment_type": adjustment_type,
        }, status=status.HTTP_201_CREATED)


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


class CategoryInventoryLinksView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request, category_id: int):
        rows = CategoryInventoryLink.objects.filter(category_id=category_id).select_related("inventory_item")
        return Response(CategoryInventoryLinkSerializer(rows, many=True).data)

    @transaction.atomic
    def put(self, request, category_id: int):
        serializer = CatalogInventoryLinkWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        CategoryInventoryLink.objects.filter(category_id=category_id).delete()
        to_create = [
            CategoryInventoryLink(
                category_id=category_id,
                inventory_item_id=row["inventory_item"],
                quantity_required=row["quantity_required"],
            )
            for row in serializer.validated_data["links"]
        ]
        CategoryInventoryLink.objects.bulk_create(to_create)
        rows = CategoryInventoryLink.objects.filter(category_id=category_id).select_related("inventory_item")
        return Response(CategoryInventoryLinkSerializer(rows, many=True).data)


class ProductEffectiveInventoryLinksView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request, product_id: int):
        from apps.menu.models import Product

        product = Product.objects.select_related("category").filter(id=product_id).first()
        if not product:
            return Response({"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        effective = resolve_effective_inventory_links_for_product(product)
        category_links = {
            row.inventory_item_id: row
            for row in CategoryInventoryLink.objects.filter(category_id=product.category_id).select_related("inventory_item")
        }
        overrides = {
            row.category_link_id: row
            for row in ProductInventoryOverride.objects.filter(product_id=product.id).select_related("category_link", "category_link__inventory_item")
        }
        direct_links = {
            row.inventory_item_id: row
            for row in CatalogProductInventoryLink.objects.filter(catalog_product_id=product.id).select_related("inventory_item")
        }

        rows = []
        for inventory_item_id, quantity in effective.items():
            if inventory_item_id in direct_links:
                direct = direct_links[inventory_item_id]
                rows.append({
                    "inventory_item": inventory_item_id,
                    "inventory_item_name": direct.inventory_item.name,
                    "inventory_item_unit": direct.inventory_item.unit,
                    "quantity_required": quantity,
                    "origin": "direct",
                })
                continue
            category_link = category_links.get(inventory_item_id)
            if not category_link:
                continue
            override = overrides.get(category_link.id)
            rows.append({
                "inventory_item": inventory_item_id,
                "inventory_item_name": category_link.inventory_item.name,
                "inventory_item_unit": category_link.inventory_item.unit,
                "quantity_required": quantity,
                "origin": "override" if override and not override.is_disabled and override.quantity_required is not None else "inherited",
                "category_link_id": category_link.id,
            })
        return Response(rows)

    @transaction.atomic
    def put(self, request, product_id: int):
        from apps.menu.models import Product

        serializer = ProductEffectiveInventoryLinkWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = Product.objects.select_related("category").filter(id=product_id).first()
        if not product:
            return Response({"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        payload_links = serializer.validated_data["links"]
        category_links = {
            row.inventory_item_id: row
            for row in CategoryInventoryLink.objects.filter(category_id=product.category_id)
        }
        payload_by_item = {int(row.get("inventory_item")): row for row in payload_links if row.get("inventory_item")}

        # Sync direct links
        direct_to_create = []
        CatalogProductInventoryLink.objects.filter(catalog_product_id=product.id).delete()
        ProductInventoryOverride.objects.filter(product_id=product.id).delete()

        for item_id, row in payload_by_item.items():
            qty = Decimal(str(row.get("quantity_required")))
            if qty <= 0:
                continue
            category_link = category_links.get(item_id)
            if category_link:
                if Decimal(category_link.quantity_required) != qty:
                    ProductInventoryOverride.objects.create(product_id=product.id, category_link=category_link, quantity_required=qty, is_disabled=False)
            else:
                direct_to_create.append(CatalogProductInventoryLink(catalog_product_id=product.id, inventory_item_id=item_id, quantity_required=qty))

        # Disabled inherited links
        for item_id, category_link in category_links.items():
            if item_id not in payload_by_item:
                ProductInventoryOverride.objects.create(product_id=product.id, category_link=category_link, is_disabled=True)

        CatalogProductInventoryLink.objects.bulk_create(direct_to_create)
        return self.get(request, product_id)
