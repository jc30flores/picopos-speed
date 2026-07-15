import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import CanAccessTablePos, IsAdminOrManager, IsCashierOrManagerOrAdmin
from apps.orders.models import Order
from apps.inventory.models import (
    CatalogProductInventoryLink,
    CategoryInventoryLink,
    InventoryCountLine,
    InventoryCountSession,
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
    InventoryCountCancelSerializer,
    InventoryCountCreateSerializer,
    InventoryCountLinesBulkUpdateSerializer,
    InventoryCountSessionDetailSerializer,
    InventoryCountSessionListSerializer,
    InventoryCountUpdateSerializer,
    ProductEffectiveInventoryLinkWriteSerializer,
)
from apps.inventory.services import check_cart_inventory_availability, check_order_inventory_availability, resolve_effective_inventory_links_for_product, reverse_inventory_for_order

logger = logging.getLogger(__name__)


class CartInventoryAvailabilityView(APIView):
    permission_classes = [CanAccessTablePos]

    def post(self, request):
        cart_items = request.data.get("cart_items") or []
        candidate_product_ids = request.data.get("candidate_product_ids") or []
        if not isinstance(cart_items, list) or not isinstance(candidate_product_ids, list):
            return Response({"detail": "Formato de carrito inválido."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(check_cart_inventory_availability(cart_items=cart_items, candidate_product_ids=candidate_product_ids))


class OrderInventoryAvailabilityCheckView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def post(self, request, order_id: int):
        order = Order.objects.prefetch_related("items__product").filter(pk=order_id).first()
        if not order:
            return Response({"detail": "Orden no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        return Response(check_order_inventory_availability(order))


class OrderInventoryReverseView(APIView):
    permission_classes = [IsAdminOrManager]

    def post(self, request, order_id: int):
        order = Order.objects.filter(pk=order_id).first()
        if not order:
            return Response({"detail": "Orden no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        reason = (request.data.get("reason") or f"Reversión manual de venta #{order.order_number}").strip()
        result = reverse_inventory_for_order(order, user=request.user, reason=reason)
        return Response(result, status=status.HTTP_200_OK)


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
                "entry": [InventoryMovement.TYPE_INVENTORY_ENTRY, InventoryMovement.TYPE_STOCK_ADD, InventoryMovement.TYPE_PURCHASE_RECEIPT],
                "loss": [InventoryMovement.TYPE_INVENTORY_LOSS],
                "damaged": [InventoryMovement.TYPE_INVENTORY_DAMAGED],
                "correction": [InventoryMovement.TYPE_INVENTORY_CORRECTION, InventoryMovement.TYPE_STOCK_ADJUST],
                "sales": [InventoryMovement.TYPE_SALE_DEDUCTION],
                "count": [InventoryMovement.TYPE_INVENTORY_COUNT_ADJUSTMENT],
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


def _filter_count_sessions(queryset, params):
    status_param = params.get("status")
    if status_param:
        queryset = queryset.filter(status=status_param)
    count_type = params.get("count_type")
    if count_type:
        queryset = queryset.filter(count_type=count_type)
    user_id = params.get("user")
    if user_id and str(user_id).isdigit():
        queryset = queryset.filter(created_by_id=int(user_id))
    date_from = params.get("date_from")
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    date_to = params.get("date_to")
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    item_id = params.get("inventory_item")
    if item_id and str(item_id).isdigit():
        queryset = queryset.filter(lines__inventory_item_id=int(item_id)).distinct()
    q = (params.get("q") or "").strip()
    if q:
        queryset = queryset.filter(Q(code__icontains=q) | Q(notes__icontains=q))
    return queryset


def _filter_inventory_movements(queryset, params):
    item_id = params.get("inventory_item")
    if item_id and str(item_id).isdigit():
        queryset = queryset.filter(inventory_item_id=int(item_id))
    movement_type = params.get("movement_type")
    if movement_type:
        queryset = queryset.filter(movement_type=movement_type)
    user_id = params.get("user")
    if user_id and str(user_id).isdigit():
        queryset = queryset.filter(created_by_id=int(user_id))
    date_from = params.get("date_from")
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    date_to = params.get("date_to")
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return queryset


def _pdf_response(filename: str, title: str, rows: list[list[str]]):
    from importlib.util import find_spec
    from io import BytesIO

    if find_spec("reportlab") is None:
        html_rows = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
        html = f"<html><head><title>{title}</title><style>body{{font-family:sans-serif;padding:24px}}table{{width:100%;border-collapse:collapse}}td{{border:1px solid #bbb;padding:6px;font-size:12px}}tr:first-child td{{background:#166534;color:white;font-weight:bold}}</style></head><body><h1>{title}</h1><p>Generado: {timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M')}</p><table>{html_rows}</table></body></html>"
        response = HttpResponse(html, content_type="text/html; charset=utf-8")
        response["Content-Disposition"] = f'inline; filename="{filename.replace(".pdf", ".html")}"'
        return response

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Paragraph(f"Generado: {timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M')}", styles["Normal"]), Spacer(1, 12)]
    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#166534")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)
    doc.build(story)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class InventoryCountListCreateView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request):
        queryset = _filter_count_sessions(InventoryCountSession.objects.select_related("created_by", "finalized_by", "applied_by", "cancelled_by"), request.query_params)
        return Response(InventoryCountSessionListSerializer(queryset[:500], many=True).data)

    @transaction.atomic
    def post(self, request):
        serializer = InventoryCountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        count_type = data["count_type"]
        session = InventoryCountSession.objects.create(count_type=count_type, notes=data.get("notes", ""), created_by=request.user)
        if count_type == InventoryCountSession.TYPE_COMPLETE:
            items = InventoryItem.objects.filter(is_active=True).order_by("name", "id")
        else:
            ids = list(dict.fromkeys(data.get("item_ids") or []))
            items = InventoryItem.objects.filter(id__in=ids).order_by("name", "id")
        InventoryCountLine.objects.bulk_create([
            InventoryCountLine(session=session, inventory_item=item, system_stock=item.current_stock)
            for item in items
        ])
        session.refresh_summary()
        return Response(InventoryCountSessionDetailSerializer(session).data, status=status.HTTP_201_CREATED)


class InventoryCountDetailView(APIView):
    permission_classes = [IsAdminOrManager]

    def get_object(self, pk):
        return InventoryCountSession.objects.select_related("created_by", "finalized_by", "applied_by", "cancelled_by").prefetch_related("lines__inventory_item").filter(pk=pk).first()

    def get(self, request, pk: int):
        session = self.get_object(pk)
        if not session:
            return Response({"detail": "Conteo no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(InventoryCountSessionDetailSerializer(session).data)

    def patch(self, request, pk: int):
        session = self.get_object(pk)
        if not session:
            return Response({"detail": "Conteo no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if session.status not in {InventoryCountSession.STATUS_DRAFT, InventoryCountSession.STATUS_IN_PROGRESS}:
            return Response({"detail": "Solo puedes editar conteos en borrador o en progreso."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = InventoryCountUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session.notes = serializer.validated_data.get("notes", session.notes)
        session.save(update_fields=["notes", "updated_at"])
        return Response(InventoryCountSessionDetailSerializer(session).data)

    @transaction.atomic
    def delete(self, request, pk: int):
        session = InventoryCountSession.objects.select_for_update().filter(pk=pk).first()
        if not session:
            return Response({"detail": "Conteo no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if session.status == InventoryCountSession.STATUS_APPLIED:
            return Response({"detail": "No puedes eliminar un conteo aplicado porque ya afectó el inventario."}, status=status.HTTP_400_BAD_REQUEST)
        if session.status == InventoryCountSession.STATUS_FINALIZED:
            return Response({"detail": "No puedes eliminar un conteo finalizado. Cancélalo primero si aún no fue aplicado."}, status=status.HTTP_400_BAD_REQUEST)
        has_movements = (
            session.lines.filter(movement__isnull=False).exists()
            or InventoryMovement.objects.filter(reference_type="inventory_count", reference_id=str(session.id)).exists()
        )
        if has_movements:
            return Response({"detail": "No puedes eliminar este conteo porque ya generó movimientos de inventario."}, status=status.HTTP_400_BAD_REQUEST)
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InventoryCountLinesUpdateView(APIView):
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def post(self, request, pk: int):
        session = InventoryCountSession.objects.select_for_update().filter(pk=pk).first()
        if not session:
            return Response({"detail": "Conteo no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if session.status not in {InventoryCountSession.STATUS_DRAFT, InventoryCountSession.STATUS_IN_PROGRESS}:
            return Response({"detail": "Solo puedes editar conteos en borrador o en progreso."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = InventoryCountLinesBulkUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        line_map = {line.id: line for line in InventoryCountLine.objects.filter(session=session)}
        for row in serializer.validated_data["lines"]:
            line = line_map.get(row["id"])
            if not line:
                continue
            if "counted_stock" in row:
                line.counted_stock = row.get("counted_stock")
            if "note" in row:
                line.note = row.get("note") or ""
            line.save(update_fields=["counted_stock", "difference", "note", "updated_at"])
        if session.status == InventoryCountSession.STATUS_DRAFT:
            session.status = InventoryCountSession.STATUS_IN_PROGRESS
            session.save(update_fields=["status", "updated_at"])
        session.refresh_summary()
        session = InventoryCountSession.objects.prefetch_related("lines__inventory_item").get(pk=session.pk)
        return Response(InventoryCountSessionDetailSerializer(session).data)


class InventoryCountFinalizeView(APIView):
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def post(self, request, pk: int):
        session = InventoryCountSession.objects.select_for_update().filter(pk=pk).first()
        if not session:
            return Response({"detail": "Conteo no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if session.status not in {InventoryCountSession.STATUS_DRAFT, InventoryCountSession.STATUS_IN_PROGRESS}:
            return Response({"detail": "Solo puedes finalizar conteos en borrador o en progreso."}, status=status.HTTP_400_BAD_REQUEST)
        if not InventoryCountLine.objects.filter(session=session, counted_stock__isnull=False).exists():
            return Response({"detail": "Debes contar al menos un artículo antes de finalizar."}, status=status.HTTP_400_BAD_REQUEST)
        session.status = InventoryCountSession.STATUS_FINALIZED
        session.finalized_by = request.user
        session.finalized_at = timezone.now()
        session.save(update_fields=["status", "finalized_by", "finalized_at", "updated_at"])
        session.refresh_summary()
        return Response(InventoryCountSessionDetailSerializer(session).data)


class InventoryCountApplyView(APIView):
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def post(self, request, pk: int):
        session = InventoryCountSession.objects.select_for_update().filter(pk=pk).first()
        if not session:
            return Response({"detail": "Conteo no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if session.status != InventoryCountSession.STATUS_FINALIZED:
            return Response({"detail": "Solo puedes aplicar conteos finalizados y no aplicados."}, status=status.HTTP_400_BAD_REQUEST)
        lines = list(InventoryCountLine.objects.select_for_update().filter(session=session, counted_stock__isnull=False).select_related("inventory_item"))
        if not lines:
            return Response({"detail": "Debes contar al menos un artículo antes de aplicar diferencias."}, status=status.HTTP_400_BAD_REQUEST)
        item_ids = [line.inventory_item_id for line in lines if line.difference != 0]
        items = {item.id: item for item in InventoryItem.objects.select_for_update().filter(id__in=item_ids)}
        movement_count = 0
        for line in lines:
            if line.difference == 0:
                continue
            item = items[line.inventory_item_id]
            before = item.current_stock
            after = before + line.difference
            item.current_stock = after
            item.save(update_fields=["current_stock", "updated_at"])
            note_suffix = f" — {line.note}" if line.note else ""
            movement = InventoryMovement.objects.create(
                inventory_item=item,
                movement_type=InventoryMovement.TYPE_INVENTORY_COUNT_ADJUSTMENT,
                quantity_change=line.difference,
                quantity_before=before,
                quantity_after=after,
                reference_type="inventory_count",
                reference_id=str(session.id),
                reason=f"Ajuste aplicado por conteo físico #{session.code or session.id}{note_suffix}",
                created_by=request.user,
            )
            line.stock_before_apply = before
            line.stock_after_apply = after
            line.movement = movement
            line.save(update_fields=["stock_before_apply", "stock_after_apply", "movement", "updated_at"])
            movement_count += 1
        session.status = InventoryCountSession.STATUS_APPLIED
        session.applied_by = request.user
        session.applied_at = timezone.now()
        session.save(update_fields=["status", "applied_by", "applied_at", "updated_at"])
        session.refresh_summary()
        return Response({"message": "Diferencias aplicadas correctamente.", "movements_created": movement_count, "session": InventoryCountSessionDetailSerializer(session).data})


class InventoryCountCancelView(APIView):
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def post(self, request, pk: int):
        session = InventoryCountSession.objects.select_for_update().filter(pk=pk).first()
        if not session:
            return Response({"detail": "Conteo no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if session.status == InventoryCountSession.STATUS_APPLIED:
            return Response({"detail": "No puedes cancelar un conteo aplicado."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = InventoryCountCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session.status = InventoryCountSession.STATUS_CANCELLED
        session.cancel_reason = serializer.validated_data.get("cancel_reason") or "Cancelado manualmente"
        session.cancelled_by = request.user
        session.cancelled_at = timezone.now()
        session.save(update_fields=["status", "cancel_reason", "cancelled_by", "cancelled_at", "updated_at"])
        return Response(InventoryCountSessionDetailSerializer(session).data)


class InventoryAdjustmentsReportView(generics.ListAPIView):
    serializer_class = InventoryMovementSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        return _filter_inventory_movements(InventoryMovement.objects.select_related("inventory_item", "created_by"), self.request.query_params).order_by("-created_at", "-id")[:1000]


class InventoryAdjustmentsReportPdfView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request):
        movements = _filter_inventory_movements(InventoryMovement.objects.select_related("inventory_item", "created_by"), request.query_params).order_by("-created_at", "-id")[:1000]
        rows = [["Fecha", "Artículo", "Código", "Unidad", "Tipo", "Cambio", "Antes", "Después", "Usuario", "Motivo", "Referencia"]]
        for m in movements:
            rows.append([timezone.localtime(m.created_at).strftime("%Y-%m-%d %H:%M"), m.inventory_item.name, m.inventory_item.sku or "—", m.inventory_item.unit, m.get_movement_type_display(), str(m.quantity_change), str(m.quantity_before), str(m.quantity_after), getattr(m.created_by, "username", "") or "—", m.reason or "—", f"{m.reference_type}:{m.reference_id}" if m.reference_type or m.reference_id else "—"])
        return _pdf_response(f"reporte-ajustes-inventario-{timezone.localdate().isoformat()}.pdf", "Reporte de Ajustes de Inventario", rows)


class InventoryCountsReportView(generics.ListAPIView):
    serializer_class = InventoryCountSessionListSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        return _filter_count_sessions(InventoryCountSession.objects.select_related("created_by", "applied_by"), self.request.query_params).order_by("-created_at", "-id")[:1000]


class InventoryCountReportDetailView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request, pk: int):
        session = InventoryCountSession.objects.select_related("created_by", "finalized_by", "applied_by", "cancelled_by").prefetch_related("lines__inventory_item").filter(pk=pk).first()
        if not session:
            return Response({"detail": "Conteo no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(InventoryCountSessionDetailSerializer(session).data)


class InventoryCountReportPdfView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request, pk: int):
        session = InventoryCountSession.objects.prefetch_related("lines__inventory_item").filter(pk=pk).first()
        if not session:
            return Response({"detail": "Conteo no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        rows = [["Artículo", "Código", "Unidad", "Stock sistema", "Conteo físico", "Diferencia", "Stock antes", "Stock después", "Nota"], ["Sesión", session.code or str(session.id), session.get_count_type_display(), session.get_status_display(), timezone.localtime(session.created_at).strftime("%Y-%m-%d %H:%M"), f"Diferencias: {session.total_differences}", f"Contados: {session.counted_items}", f"Total: {session.total_items}", session.notes or "—"]]
        for line in session.lines.all():
            rows.append([line.inventory_item.name, line.inventory_item.sku or "—", line.inventory_item.unit, str(line.system_stock), str(line.counted_stock) if line.counted_stock is not None else "Pendiente", str(line.difference), str(line.stock_before_apply or "—"), str(line.stock_after_apply or "—"), line.note or "—"])
        return _pdf_response(f"conteo-inventario-{session.code or session.id}.pdf", f"Reporte de Conteo de Inventario {session.code or session.id}", rows)


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

        effective = resolve_effective_inventory_links_for_product(product, include_disabled_components=True)
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
        seen_item_ids = set()
        for inventory_item_id, quantity in effective.items():
            seen_item_ids.add(inventory_item_id)
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
        for override in overrides.values():
            if not override.is_disabled or override.category_link.inventory_item_id in seen_item_ids:
                continue
            rows.append({
                "inventory_item": override.category_link.inventory_item_id,
                "inventory_item_name": override.category_link.inventory_item.name,
                "inventory_item_unit": override.category_link.inventory_item.unit,
                "quantity_required": override.category_link.quantity_required,
                "origin": "disabled",
                "category_link_id": override.category_link_id,
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

from apps.core.feature_flags import is_feature_enabled
from apps.inventory.models import InventorySupplier, PurchaseOrder, PurchaseOrderLine, PurchaseReceipt, PurchaseReceiptLine
from apps.inventory.serializers import (
    InventorySupplierSerializer,
    PurchaseOrderCancelSerializer,
    PurchaseOrderReceiveSerializer,
    PurchaseOrderSerializer,
)


def _advanced_inventory_enabled() -> bool:
    return is_feature_enabled("FF_INVENTORY", default=False)


class AdvancedInventoryRequiredMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not _advanced_inventory_enabled():
            self.permission_denied(request, message="Inventario avanzado no está activo.")


def _sync_purchase_order_lines(order: PurchaseOrder, lines_data: list[dict]):
    order.lines.all().delete()
    for raw in lines_data:
        item = InventoryItem.objects.get(pk=raw["inventory_item"].id if isinstance(raw.get("inventory_item"), InventoryItem) else raw.get("inventory_item"))
        PurchaseOrderLine.objects.create(
            purchase_order=order,
            inventory_item=item,
            description=(raw.get("description") or item.name)[:200],
            quantity_ordered=raw.get("quantity_ordered"),
            purchase_unit=raw.get("purchase_unit") or item.purchase_unit or item.unit,
            purchase_to_inventory_factor=raw.get("purchase_to_inventory_factor") or item.purchase_to_inventory_factor or Decimal("1"),
            unit_cost=raw.get("unit_cost") if raw.get("unit_cost") is not None else (item.unit_cost or Decimal("0")),
            notes=raw.get("notes") or "",
        )
    order.refresh_totals()


class InventorySupplierListCreateView(AdvancedInventoryRequiredMixin, generics.ListCreateAPIView):
    serializer_class = InventorySupplierSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        queryset = InventorySupplier.objects.all().order_by("name", "id")
        query = (self.request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(phone__icontains=query) | Q(email__icontains=query))
        is_active = self.request.query_params.get("is_active")
        if is_active in {"true", "false"}:
            queryset = queryset.filter(is_active=(is_active == "true"))
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class InventorySupplierDetailView(AdvancedInventoryRequiredMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = InventorySupplier.objects.all()
    serializer_class = InventorySupplierSerializer
    permission_classes = [IsAdminOrManager]

    def destroy(self, request, *args, **kwargs):
        supplier = self.get_object()
        if supplier.purchase_orders.exists() or supplier.inventory_items.exists():
            supplier.is_active = False
            supplier.save(update_fields=["is_active", "updated_at"])
            return Response({"detail": "No puedes eliminar este proveedor porque tiene registros relacionados. Puedes desactivarlo."}, status=status.HTTP_200_OK)
        supplier.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PurchaseOrderListCreateView(AdvancedInventoryRequiredMixin, generics.ListCreateAPIView):
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        queryset = PurchaseOrder.objects.select_related("supplier", "created_by", "approved_by").prefetch_related("lines__inventory_item").all()
        query = (self.request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(Q(code__icontains=query) | Q(supplier__name__icontains=query))
        supplier = self.request.query_params.get("supplier")
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lines_data = serializer.validated_data.pop("lines", [])
        order = serializer.save(created_by=request.user)
        _sync_purchase_order_lines(order, lines_data)
        return Response(self.get_serializer(order).data, status=status.HTTP_201_CREATED)


class PurchaseOrderDetailView(AdvancedInventoryRequiredMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAdminOrManager]
    queryset = PurchaseOrder.objects.select_related("supplier", "created_by", "approved_by").prefetch_related("lines__inventory_item")

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        order = self.get_object()
        if order.status != PurchaseOrder.STATUS_DRAFT:
            return Response({"detail": "Solo puedes editar órdenes en borrador."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(order, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        lines_data = serializer.validated_data.pop("lines", None)
        order = serializer.save()
        if lines_data is not None:
            _sync_purchase_order_lines(order, lines_data)
        return Response(self.get_serializer(order).data)

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        if order.status != PurchaseOrder.STATUS_DRAFT:
            return Response({"detail": "Solo puedes eliminar órdenes en borrador."}, status=status.HTTP_400_BAD_REQUEST)
        order.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PurchaseOrderApproveView(AdvancedInventoryRequiredMixin, APIView):
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def post(self, request, pk: int):
        order = PurchaseOrder.objects.select_for_update().prefetch_related("lines").filter(pk=pk).first()
        if not order:
            return Response({"detail": "Orden de compra no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        if order.status != PurchaseOrder.STATUS_DRAFT:
            return Response({"detail": "Solo puedes aprobar órdenes en borrador."}, status=status.HTTP_400_BAD_REQUEST)
        if not order.lines.exists():
            return Response({"detail": "No puedes aprobar una orden sin líneas."}, status=status.HTTP_400_BAD_REQUEST)
        order.status = PurchaseOrder.STATUS_APPROVED
        order.approved_by = request.user
        order.approved_at = timezone.now()
        order.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return Response(PurchaseOrderSerializer(order).data)


class PurchaseOrderCancelView(AdvancedInventoryRequiredMixin, APIView):
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def post(self, request, pk: int):
        order = PurchaseOrder.objects.select_for_update().prefetch_related("lines").filter(pk=pk).first()
        if not order:
            return Response({"detail": "Orden de compra no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        if order.status in {PurchaseOrder.STATUS_RECEIVED, PurchaseOrder.STATUS_CANCELLED}:
            return Response({"detail": "No puedes cancelar esta orden."}, status=status.HTTP_400_BAD_REQUEST)
        if order.lines.filter(quantity_received__gt=0).exists():
            return Response({"detail": "No puedes cancelar una orden con productos ya recibidos desde este flujo."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = PurchaseOrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order.status = PurchaseOrder.STATUS_CANCELLED
        order.cancelled_by = request.user
        order.cancelled_at = timezone.now()
        order.cancel_reason = serializer.validated_data.get("reason") or "Cancelación manual"
        order.save(update_fields=["status", "cancelled_by", "cancelled_at", "cancel_reason", "updated_at"])
        return Response(PurchaseOrderSerializer(order).data)


class PurchaseOrderReceiveView(AdvancedInventoryRequiredMixin, APIView):
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def post(self, request, pk: int):
        order = PurchaseOrder.objects.select_for_update().prefetch_related("lines__inventory_item").filter(pk=pk).first()
        if not order:
            return Response({"detail": "Orden de compra no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        if order.status not in {PurchaseOrder.STATUS_APPROVED, PurchaseOrder.STATUS_PARTIALLY_RECEIVED}:
            return Response({"detail": "Solo puedes recibir órdenes aprobadas o parcialmente recibidas."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = PurchaseOrderReceiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lines_payload = serializer.validated_data["lines"]
        update_unit_cost = serializer.validated_data["update_unit_cost"]
        line_map = {line.id: line for line in order.lines.all()}
        receipt = PurchaseReceipt.objects.create(purchase_order=order, received_by=request.user, notes=serializer.validated_data.get("notes") or "")
        received_any = False
        for raw in lines_payload:
            line = line_map.get(raw["line_id"])
            if not line:
                raise serializers.ValidationError({"lines": "Línea de orden inválida."})
            qty_purchase = raw["quantity_received"]
            if qty_purchase > line.pending_quantity:
                raise serializers.ValidationError({"lines": f"No puedes recibir más de lo pendiente para {line.inventory_item.name}."})
            item = InventoryItem.objects.select_for_update().get(pk=line.inventory_item_id)
            qty_inventory = qty_purchase * line.purchase_to_inventory_factor
            before = Decimal(item.current_stock)
            after = before + qty_inventory
            item.current_stock = after
            update_fields = ["current_stock", "updated_at"]
            if update_unit_cost:
                item.unit_cost = line.unit_cost
                update_fields.append("unit_cost")
            item.save(update_fields=update_fields)
            movement = InventoryMovement.objects.create(
                inventory_item=item,
                movement_type=InventoryMovement.TYPE_PURCHASE_RECEIPT,
                quantity_change=qty_inventory,
                quantity_before=before,
                quantity_after=after,
                reference_type="purchase_receipt",
                reference_id=str(receipt.id),
                reason=f"Entrada por orden de compra #{order.code}",
                created_by=request.user,
            )
            line.quantity_received = line.quantity_received + qty_purchase
            line.save(update_fields=["quantity_received", "updated_at"])
            PurchaseReceiptLine.objects.create(
                receipt=receipt,
                purchase_order_line=line,
                inventory_item=item,
                quantity_received_purchase_unit=qty_purchase,
                purchase_to_inventory_factor=line.purchase_to_inventory_factor,
                quantity_added_inventory_unit=qty_inventory,
                unit_cost=line.unit_cost,
                movement=movement,
                notes=raw.get("notes") or "",
            )
            received_any = True
        if not received_any:
            raise serializers.ValidationError({"lines": "Debes recibir al menos una línea."})
        all_received = all(line.pending_quantity <= 0 for line in order.lines.all())
        order.status = PurchaseOrder.STATUS_RECEIVED if all_received else PurchaseOrder.STATUS_PARTIALLY_RECEIVED
        order.save(update_fields=["status", "updated_at"])
        return Response({"message": "Productos recibidos correctamente.", "order": PurchaseOrderSerializer(order).data, "receipt": receipt.code})


class PurchaseOrderPDFView(AdvancedInventoryRequiredMixin, APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request, pk: int):
        order = PurchaseOrder.objects.select_related("supplier").prefetch_related("lines__inventory_item").filter(pk=pk).first()
        if not order:
            return Response({"detail": "Orden de compra no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        if order.status == PurchaseOrder.STATUS_DRAFT:
            return Response({"detail": "No puedes generar PDF de una orden en borrador."}, status=status.HTTP_400_BAD_REQUEST)
        rows = "".join(
            f"<tr><td>{line.inventory_item.name}</td><td>{line.quantity_ordered}</td><td>{line.quantity_received}</td><td>{line.purchase_unit or line.inventory_item.unit}</td><td>{line.unit_cost}</td><td>{line.subtotal}</td></tr>"
            for line in order.lines.all()
        )
        html = f"""
        <html><head><title>{order.code}</title><style>body{{font-family:sans-serif;padding:24px}}table{{width:100%;border-collapse:collapse}}td,th{{border:1px solid #999;padding:6px;font-size:12px}}th{{background:#166534;color:white}}</style></head>
        <body><h1>Orden de compra {order.code}</h1><p><strong>Proveedor:</strong> {order.supplier.name}</p><p><strong>Estado:</strong> {order.get_status_display()}</p><p><strong>Total:</strong> {order.total}</p><p><strong>Notas:</strong> {order.notes or '—'}</p><table><thead><tr><th>Artículo</th><th>Ordenado</th><th>Recibido</th><th>Unidad compra</th><th>Costo</th><th>Subtotal</th></tr></thead><tbody>{rows}</tbody></table></body></html>
        """
        response = HttpResponse(html, content_type="text/html; charset=utf-8")
        response["Content-Disposition"] = f'inline; filename="orden-compra-{order.code}.html"'
        return response
