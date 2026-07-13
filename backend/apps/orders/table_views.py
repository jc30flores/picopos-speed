from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import Branch, FeatureFlag
from apps.core.permissions import IsAdminOrManager, IsCashierOrManagerOrAdmin
from apps.orders.models import DiningArea, RestaurantTable, TableSession, TableSessionTable, TableGuest, Order, OrderItem
from apps.orders.serializers import DiningAreaSerializer, RestaurantTableSerializer, TableSessionSerializer


def _table_map_enabled() -> bool:
    return bool(FeatureFlag.objects.filter(key="table_map_enabled", is_enabled=True).exists())


ACTIVE_TABLE_SESSION_STATUSES = ["open", "sent_to_kitchen", "partially_paid"]


def _parse_table_ids(data) -> list[int]:
    raw_table_ids = data.get("table_ids")
    if raw_table_ids is None and data.get("table_id") is not None:
        raw_table_ids = [data.get("table_id")]
    if not isinstance(raw_table_ids, list):
        return []
    table_ids: list[int] = []
    for raw_id in raw_table_ids:
        try:
            table_id = int(raw_id)
        except (TypeError, ValueError):
            return []
        if table_id > 0 and table_id not in table_ids:
            table_ids.append(table_id)
    return table_ids


def _parse_int(value, *, default=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _parse_guests_count(data):
    raw_value = data.get("guests_count", data.get("guest_count", 1))
    try:
        guests_count = int(raw_value)
    except (TypeError, ValueError):
        return None
    if guests_count < 1 or guests_count > 99:
        return None
    return guests_count


def _normalize_order_mode(raw_mode: str) -> str | None:
    mode = str(raw_mode or "table").strip().lower()
    aliases = {
        "full": TableSession.ORDER_MODE_TABLE,
        "table": TableSession.ORDER_MODE_TABLE,
        "complete": TableSession.ORDER_MODE_TABLE,
        "by_guest": TableSession.ORDER_MODE_PER_PERSON,
        "per_person": TableSession.ORDER_MODE_PER_PERSON,
        "guest": TableSession.ORDER_MODE_PER_PERSON,
    }
    return aliases.get(mode)


def _resolve_branch(request):
    raw_branch_id = request.data.get("branch_id")
    if raw_branch_id not in (None, ""):
        try:
            branch_id = int(raw_branch_id)
        except (TypeError, ValueError):
            return None
        return Branch.objects.select_for_update().filter(id=branch_id, is_active=True).first()
    return (
        Branch.objects.select_for_update().filter(code="PRINCIPAL", is_active=True).first()
        or Branch.objects.select_for_update().filter(is_active=True).order_by("id").first()
    )


def _next_order_number(branch: Branch) -> int:
    current = (
        Order.objects.select_for_update()
        .filter(branch=branch)
        .aggregate(max_order_number=Max("order_number"))
        .get("max_order_number")
        or 0
    )
    return int(current) + 1


def _session_response(session: TableSession, *, status_code=status.HTTP_200_OK):
    data = TableSessionSerializer(session).data
    data["session_id"] = session.id
    data["order_id"] = session.primary_order_id
    data["table_id"] = data["table_ids"][0] if data.get("table_ids") else None
    data["guest_count"] = session.guests_count
    return Response(data, status=status_code)


class TableMapFeatureGuardMixin:
    def initial(self, request, *args, **kwargs):
        if not _table_map_enabled():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Mapa de mesas no está activo.")
        return super().initial(request, *args, **kwargs)


class DiningAreaListCreateView(TableMapFeatureGuardMixin, generics.ListCreateAPIView):
    queryset = DiningArea.objects.all().order_by("sort_order", "id")
    serializer_class = DiningAreaSerializer
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get_permissions(self):
        if self.request.method in {"POST"}:
            return [IsAdminOrManager()]
        return [IsCashierOrManagerOrAdmin()]


class DiningAreaDetailView(TableMapFeatureGuardMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = DiningArea.objects.all()
    serializer_class = DiningAreaSerializer
    permission_classes = [IsAdminOrManager]

    def destroy(self, request, *args, **kwargs):
        area = self.get_object()
        if area.tables.exists():
            area.is_active = False
            area.save(update_fields=["is_active", "updated_at"])
            return Response({"detail": "El área tiene mesas asociadas y fue desactivada."}, status=200)
        return super().destroy(request, *args, **kwargs)


class RestaurantTableListCreateView(TableMapFeatureGuardMixin, generics.ListCreateAPIView):
    queryset = RestaurantTable.objects.select_related("area").all().order_by("area__sort_order", "sort_order", "id")
    serializer_class = RestaurantTableSerializer
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get_permissions(self):
        if self.request.method in {"POST"}:
            return [IsAdminOrManager()]
        return [IsCashierOrManagerOrAdmin()]


class RestaurantTableDetailView(TableMapFeatureGuardMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = RestaurantTable.objects.select_related("area").all()
    serializer_class = RestaurantTableSerializer
    permission_classes = [IsAdminOrManager]

    def destroy(self, request, *args, **kwargs):
        table = self.get_object()
        has_active_session = TableSessionTable.objects.filter(
            table=table,
            session__status__in=ACTIVE_TABLE_SESSION_STATUSES,
        ).exists()
        if has_active_session:
            return Response({"detail": "No se puede eliminar una mesa con sesión activa."}, status=400)
        has_history = TableSessionTable.objects.filter(table=table).exists()
        if has_history:
            table.is_active = False
            table.save(update_fields=["is_active", "updated_at"])
            return Response({"detail": "La mesa tiene historial y fue desactivada."}, status=200)
        return super().destroy(request, *args, **kwargs)


class TableLayoutView(TableMapFeatureGuardMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        areas = DiningAreaSerializer(DiningArea.objects.all().order_by("sort_order","id"), many=True).data
        tables = RestaurantTableSerializer(RestaurantTable.objects.select_related("area").filter(is_active=True), many=True).data
        sessions = TableSessionSerializer(
            TableSession.objects.filter(status__in=ACTIVE_TABLE_SESSION_STATUSES).order_by("-opened_at"),
            many=True,
        ).data
        return Response({"areas": areas, "tables": tables, "sessions": sessions})

    def patch(self, request):
        if not IsAdminOrManager().has_permission(request, self):
            return Response({"detail": "No autorizado."}, status=status.HTTP_403_FORBIDDEN)
        items = request.data.get("tables") or []
        with transaction.atomic():
            for row in items:
                table_id = int(row.get("id"))
                RestaurantTable.objects.filter(id=table_id).update(
                    x=float(row.get("x", 0)), y=float(row.get("y", 0)), width=max(float(row.get("width", 80)), 20),
                    height=max(float(row.get("height", 80)), 20), rotation=float(row.get("rotation", 0)),
                )
        return Response({"detail": "Mapa guardado correctamente."})


class TableSessionListCreateView(TableMapFeatureGuardMixin, APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request):
        qs = TableSession.objects.filter(status__in=ACTIVE_TABLE_SESSION_STATUSES).order_by("-opened_at")
        return Response(TableSessionSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        table_ids = _parse_table_ids(request.data)
        guests_count = _parse_guests_count(request.data)
        order_mode = _normalize_order_mode(request.data.get("order_mode"))
        notes = str(request.data.get("notes") or "")[:255]
        if not table_ids:
            return Response({"detail": "Debes seleccionar al menos una mesa."}, status=400)
        if guests_count is None:
            return Response({"guest_count": "La cantidad de personas debe estar entre 1 y 99."}, status=400)
        if order_mode is None:
            return Response({"order_mode": "Modo de orden inválido."}, status=400)
        branch = _resolve_branch(request)
        if not branch:
            return Response({"branch_id": "Sucursal inválida o inactiva."}, status=400)
        tables = list(RestaurantTable.objects.select_for_update().filter(id__in=table_ids, is_active=True))
        if len(tables) != len(set(table_ids)):
            return Response({"detail": "Hay mesas inválidas o inactivas."}, status=400)
        busy = TableSessionTable.objects.select_for_update().filter(table_id__in=table_ids, session__status__in=ACTIVE_TABLE_SESSION_STATUSES).exists()
        if busy:
            return Response({"detail": "Una o más mesas ya tienen sesión activa."}, status=400)
        order = Order.objects.create(
            order_number=_next_order_number(branch),
            branch=branch,
            status="new",
            customer_name="",
            is_pending=True,
            pending_state="pending_payment",
            pending_reference=f"Mesa {tables[0].name}",
            pending_marked_at=timezone.localtime(timezone.now()),
        )
        session = TableSession.objects.create(status="open", guests_count=guests_count, order_mode=order_mode, primary_order=order, opened_by=request.user, notes=notes)
        TableSessionTable.objects.bulk_create([TableSessionTable(session=session, table=tb) for tb in tables])
        if order_mode == "per_person":
            TableGuest.objects.bulk_create([TableGuest(session=session, label=f"Persona {i+1}", seat_number=i+1) for i in range(guests_count)])
        return _session_response(session, status_code=status.HTTP_201_CREATED)


class TableSessionDetailView(TableMapFeatureGuardMixin, generics.RetrieveUpdateAPIView):
    queryset = TableSession.objects.all()
    serializer_class = TableSessionSerializer
    permission_classes = [IsCashierOrManagerOrAdmin]


class TableSessionSendToKitchenView(TableMapFeatureGuardMixin, APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def post(self, request, pk: int):
        session = TableSession.objects.filter(id=pk).first()
        if not session or not session.primary_order_id:
            return Response({"detail": "Sesión no encontrada."}, status=404)
        order = session.primary_order
        if not order.items.exists():
            return Response({"detail": "No se puede enviar una orden vacía."}, status=400)
        order.send_to_kitchen = True
        order.pending_state = "in_kitchen"
        order.save(update_fields=["send_to_kitchen", "pending_state", "updated_at"])
        session.status = "sent_to_kitchen"
        session.save(update_fields=["status", "updated_at"])
        return Response({"detail": "Orden enviada a cocina.", "session": TableSessionSerializer(session).data})


class TableSessionMergeView(TableMapFeatureGuardMixin, APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    @transaction.atomic
    def post(self, request, pk: int):
        session = TableSession.objects.select_for_update().filter(id=pk, status__in=ACTIVE_TABLE_SESSION_STATUSES).first()
        if not session:
            return Response({"detail": "Sesión no encontrada o cerrada."}, status=404)
        table_ids = _parse_table_ids(request.data)
        if not table_ids:
            return Response({"detail": "Selecciona mesas para unir."}, status=400)
        existing = set(session.session_tables.values_list("table_id", flat=True))
        to_add = [tid for tid in table_ids if tid not in existing]
        if not to_add:
            return _session_response(session)
        tables = list(RestaurantTable.objects.select_for_update().filter(id__in=to_add, is_active=True))
        if len(tables) != len(set(to_add)):
            return Response({"detail": "Hay mesas inválidas o inactivas."}, status=400)
        busy = TableSessionTable.objects.select_for_update().filter(
            table_id__in=to_add,
            session__status__in=ACTIVE_TABLE_SESSION_STATUSES,
        ).exclude(session=session).exists()
        if busy:
            return Response({"detail": "No se puede unir una mesa ocupada en esta versión."}, status=400)
        TableSessionTable.objects.bulk_create([TableSessionTable(session=session, table=t) for t in tables])
        if session.primary_order_id:
            names = list(session.session_tables.select_related("table").order_by("created_at", "id").values_list("table__name", flat=True))
            session.primary_order.pending_reference = " + ".join(names)
            session.primary_order.save(update_fields=["pending_reference", "updated_at"])
        return _session_response(session)


class TableSessionMoveTableView(TableMapFeatureGuardMixin, APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    @transaction.atomic
    def post(self, request, pk: int):
        session = TableSession.objects.select_for_update().filter(id=pk, status__in=ACTIVE_TABLE_SESSION_STATUSES).first()
        if not session:
            return Response({"detail": "Sesión no encontrada o cerrada."}, status=404)
        try:
            target_table_id = int(request.data.get("target_table_id"))
        except (TypeError, ValueError):
            return Response({"target_table_id": "Mesa destino inválida."}, status=400)
        target = RestaurantTable.objects.select_for_update().filter(id=target_table_id, is_active=True).first()
        if not target:
            return Response({"target_table_id": "Mesa destino inválida o inactiva."}, status=400)
        target_busy = TableSessionTable.objects.select_for_update().filter(
            table=target,
            session__status__in=ACTIVE_TABLE_SESSION_STATUSES,
        ).exclude(session=session).exists()
        if target_busy:
            return Response({"detail": "La mesa destino ya tiene una sesión activa."}, status=400)

        source_table_id = _parse_int(request.data.get("source_table_id"))
        if source_table_id not in (None, ""):
            removed, _ = TableSessionTable.objects.filter(session=session, table_id=source_table_id).delete()
            if removed == 0:
                return Response({"source_table_id": "La mesa origen no pertenece a esta sesión."}, status=400)
        else:
            TableSessionTable.objects.filter(session=session).delete()

        TableSessionTable.objects.get_or_create(session=session, table=target)
        if session.primary_order_id:
            session.primary_order.pending_reference = f"Mesa {target.name}"
            session.primary_order.save(update_fields=["pending_reference", "updated_at"])
        return Response({"detail": "Mesa movida correctamente.", "session": TableSessionSerializer(session).data})


class TableSessionReleaseView(TableMapFeatureGuardMixin, APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    @transaction.atomic
    def post(self, request, pk: int):
        session = TableSession.objects.select_for_update().filter(id=pk, status__in=ACTIVE_TABLE_SESSION_STATUSES).first()
        if not session:
            return Response({"detail": "Sesión no encontrada o ya cerrada."}, status=404)
        order = session.primary_order
        if order:
            order.recalculate_financials()
            has_balance = order.items.exists() and order.payment_status != "paid"
            if has_balance:
                return Response({"detail": "No puedes liberar una mesa con saldo pendiente."}, status=400)
        session.status = TableSession.STATUS_CLOSED
        session.closed_by = request.user
        session.closed_at = timezone.now()
        session.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])
        return Response({"detail": "Mesa liberada correctamente.", "session": TableSessionSerializer(session).data})


class TableSessionMoveItemsView(TableMapFeatureGuardMixin, APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    @transaction.atomic
    def post(self, request, pk: int):
        session = TableSession.objects.select_for_update().filter(id=pk).first()
        if not session or not session.primary_order_id:
            return Response({"detail": "Sesión no encontrada."}, status=404)
        item = OrderItem.objects.select_for_update().filter(id=request.data.get("order_item_id"), order_id=session.primary_order_id).first()
        if not item:
            return Response({"detail": "Producto no pertenece a la sesión."}, status=400)
        to_guest = TableGuest.objects.filter(id=request.data.get("to_guest_id"), session=session, is_active=True).first()
        if not to_guest:
            return Response({"detail": "Persona destino inválida."}, status=400)
        qty = int(request.data.get("quantity") or 1)
        if qty <= 0 or qty > item.quantity:
            return Response({"detail": "Cantidad inválida."}, status=400)
        if qty == item.quantity:
            item.table_guest = to_guest
            item.save(update_fields=["table_guest"])
        else:
            item.quantity -= qty
            item.save(update_fields=["quantity"])
            OrderItem.objects.create(
                order=item.order, product=item.product, product_name_snapshot=item.product_name_snapshot, price_snapshot=item.price_snapshot,
                unit_price_override=item.unit_price_override, snapshot_sku_or_code=item.snapshot_sku_or_code, is_custom=item.is_custom,
                quantity=qty, discount_amount=0, assigned_name=item.assigned_name, table_guest=to_guest,
            )
        return Response({"detail": "Producto movido correctamente."})
