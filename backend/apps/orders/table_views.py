from decimal import Decimal
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import Branch, FeatureFlag
from apps.core.audit import log_audit
from apps.core.money import to_cents
from apps.core.permissions import CanAccessTablePos, CanManageKitchenItems, CanServeKitchenItems, CanViewKitchen, IsAdminOrManager, IsCashierOrManagerOrAdmin
from apps.orders.models import DiningArea, RestaurantTable, TableSession, TableSessionTable, TableGuest, Order, OrderItem
from apps.orders.serializers import DiningAreaSerializer, OrderSerializer, RestaurantTableSerializer, TableSessionSerializer
from apps.payments.models import Payment
from apps.users.models import UserProfile
from apps.users.pin_utils import is_valid_pin_format, user_matches_pin


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


def _next_group_number() -> int:
    current = (
        TableSession.objects.select_for_update()
        .filter(group_number__isnull=False)
        .aggregate(max_group_number=Max("group_number"))
        .get("max_group_number")
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


def _is_admin_or_superadmin(user) -> bool:
    profile = UserProfile.objects.filter(user=user, is_active=True).first()
    return bool(getattr(user, "is_superuser", False) or (profile and profile.role in {"superadmin", "admin"}))


def _authorize_admin_or_superadmin_pin(pin: str):
    if not is_valid_pin_format(pin):
        return None
    profiles = UserProfile.objects.select_related("user").filter(
        is_active=True,
        role__in=["superadmin", "admin"],
        user__is_active=True,
    )
    for profile in profiles:
        if profile.user and user_matches_pin(profile.user, pin):
            return profile.user
    return None


def _serialize_kitchen_item(item: OrderItem):
    guest_label = (item.table_guest.label if item.table_guest_id and item.table_guest else "") or item.assigned_name
    status_label = {
        OrderItem.KITCHEN_STATUS_PENDING: "Pendiente de enviar",
        OrderItem.KITCHEN_STATUS_SENT: "En cocina",
        OrderItem.KITCHEN_STATUS_READY: "Terminado",
        OrderItem.KITCHEN_STATUS_DELIVERED: "Servido",
    }.get(item.kitchen_status, "Pendiente de enviar")
    return {
        "id": item.id,
        "product_name": item.product_name_snapshot,
        "quantity": item.quantity,
        "assigned_name": item.assigned_name,
        "guest_number": item.table_guest.seat_number if item.table_guest_id and item.table_guest else None,
        "guest_label": guest_label,
        "table_guest_id": item.table_guest_id,
        "table_guest_label": guest_label,
        "table_guest_seat_number": item.table_guest.seat_number if item.table_guest_id and item.table_guest else None,
        "kitchen_status": item.kitchen_status,
        "kitchen_status_label": status_label,
        "kitchen_sent_at": item.kitchen_sent_at,
        "kitchen_ready_at": item.kitchen_ready_at,
        "kitchen_delivered_at": item.kitchen_delivered_at,
        "kitchen_completed_at": item.kitchen_ready_at,
        "kitchen_served_at": item.kitchen_delivered_at,
        "is_pending_kitchen": item.kitchen_status == OrderItem.KITCHEN_STATUS_PENDING,
        "is_in_kitchen": item.kitchen_status == OrderItem.KITCHEN_STATUS_SENT,
        "is_completed": item.kitchen_status == OrderItem.KITCHEN_STATUS_READY,
        "is_served": item.kitchen_status == OrderItem.KITCHEN_STATUS_DELIVERED,
        "modifiers": [mod.modifier_name_snapshot for mod in item.applied_modifiers.all()],
        "line_total": str((item.effective_unit_price * Decimal(item.quantity or 0)).quantize(Decimal("0.01"))),
    }


def _serialize_kitchen_session(session: TableSession):
    order = session.primary_order
    table_names = list(session.session_tables.select_related("table").order_by("created_at", "id").values_list("table__name", flat=True))
    items = list(order.items.select_related("table_guest").prefetch_related("applied_modifiers").order_by("id")) if order else []
    by_person: dict[str, dict] = {}
    for item in items:
        label = item.assigned_name or (item.table_guest.label if item.table_guest_id and item.table_guest else "Cuenta general")
        bucket = by_person.setdefault(label, {"label": label, "items": [], "total": Decimal("0.00")})
        line_total = (item.effective_unit_price * Decimal(item.quantity or 0)).quantize(Decimal("0.01"))
        bucket["items"].append(_serialize_kitchen_item(item))
        bucket["total"] += line_total
    return {
        "session_id": session.id,
        "order_id": session.primary_order_id,
        "status": session.status,
        "tables": table_names,
        "table_label": " + ".join(table_names),
        "guests_count": session.guests_count,
        "order_mode": session.order_mode,
        "total": str(order.total if order else session.total_cached),
        "remaining": str(max((Decimal(order.amount_due_cents or to_cents(order.total)) / Decimal("100")) - (Payment.objects.filter(order=order).aggregate(total=Sum("amount_applied"))["total"] or Decimal("0")), Decimal("0.00")) if order else Decimal("0.00")),
        "items": [_serialize_kitchen_item(item) for item in items],
        "people": [{**value, "total": str(value["total"].quantize(Decimal("0.01")))} for value in by_person.values()],
    }


def _serialize_ready_session(session: TableSession):
    order = session.primary_order
    table_links = list(session.session_tables.select_related("table").order_by("created_at", "id"))
    table_names = [link.table.name for link in table_links]
    ready_items = list(
        order.items.select_related("table_guest").prefetch_related("applied_modifiers").filter(kitchen_status=OrderItem.KITCHEN_STATUS_READY).order_by("kitchen_ready_at", "id")
    ) if order else []
    group_label = f"Grupo {session.group_number}" if session.group_number else None
    return {
        "table_id": table_links[0].table_id if table_links else None,
        "table_ids": [link.table_id for link in table_links],
        "table_name": " + ".join(table_names),
        "session_id": session.id,
        "order_id": session.primary_order_id,
        "ready_count": sum(int(item.quantity or 0) for item in ready_items),
        "group_label": group_label,
        "items": [_serialize_kitchen_item(item) for item in ready_items],
    }


class TableMapFeatureGuardMixin:
    def initial(self, request, *args, **kwargs):
        if not _table_map_enabled():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Mapa de mesas no está activo.")
        return super().initial(request, *args, **kwargs)


class DiningAreaListCreateView(TableMapFeatureGuardMixin, generics.ListCreateAPIView):
    queryset = DiningArea.objects.all().order_by("sort_order", "id")
    serializer_class = DiningAreaSerializer
    permission_classes = [CanAccessTablePos]

    def get_permissions(self):
        if self.request.method in {"POST"}:
            return [IsAdminOrManager()]
        return [CanAccessTablePos()]


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
    permission_classes = [CanAccessTablePos]

    def get_permissions(self):
        if self.request.method in {"POST"}:
            return [IsAdminOrManager()]
        return [CanAccessTablePos()]


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
            TableSession.objects.select_related("primary_order").filter(status__in=ACTIVE_TABLE_SESSION_STATUSES).order_by("-opened_at"),
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
    permission_classes = [CanAccessTablePos]

    def get(self, request):
        qs = TableSession.objects.select_related("primary_order").filter(status__in=ACTIVE_TABLE_SESSION_STATUSES).order_by("-opened_at")
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
        busy_link = (
            TableSessionTable.objects.select_for_update()
            .filter(table_id__in=table_ids, session__status__in=ACTIVE_TABLE_SESSION_STATUSES)
            .select_related("session")
            .order_by("-session__opened_at", "-session_id")
            .first()
        )
        if busy_link:
            session = busy_link.session
            data = TableSessionSerializer(session).data
            return Response(
                {
                    "code": "table_already_has_active_session",
                    "message": "La mesa ya tiene una orden activa.",
                    "detail": "La mesa ya tiene una orden activa.",
                    "session": data,
                    "order_id": session.primary_order_id,
                    "table_id": busy_link.table_id,
                },
                status=status.HTTP_409_CONFLICT,
            )
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
        session = TableSession.objects.create(
            status="open",
            guests_count=guests_count,
            order_mode=order_mode,
            primary_order=order,
            opened_by=request.user,
            notes=notes,
            group_number=_next_group_number() if len(tables) > 1 else None,
        )
        TableSessionTable.objects.bulk_create([TableSessionTable(session=session, table=tb) for tb in tables])
        if order_mode == "per_person":
            TableGuest.objects.bulk_create([TableGuest(session=session, label=f"Persona {i+1}", seat_number=i+1) for i in range(guests_count)])
        return _session_response(session, status_code=status.HTTP_201_CREATED)


class TableSessionDetailView(TableMapFeatureGuardMixin, generics.RetrieveUpdateAPIView):
    queryset = TableSession.objects.all()
    serializer_class = TableSessionSerializer
    permission_classes = [CanAccessTablePos]


class TableSessionSendToKitchenView(TableMapFeatureGuardMixin, APIView):
    permission_classes = [CanAccessTablePos]

    @transaction.atomic
    def post(self, request, pk: int):
        session = TableSession.objects.select_for_update().filter(id=pk).first()
        if not session or not session.primary_order_id:
            return Response({"detail": "Sesión no encontrada."}, status=404)
        order = session.primary_order
        if not order.items.exists():
            return Response({"detail": "No se puede enviar una orden vacía."}, status=400)
        scope = str(request.data.get("scope") or "table").strip().lower()
        if scope not in {"guest", "table"}:
            return Response({"scope": "Usa guest o table."}, status=400)
        pending_qs = order.items.select_for_update().filter(kitchen_status=OrderItem.KITCHEN_STATUS_PENDING)
        guest = None
        if scope == "guest":
            if session.order_mode != TableSession.ORDER_MODE_PER_PERSON:
                return Response({"scope": "El envío individual solo aplica a orden por persona."}, status=400)
            raw_guest_id = request.data.get("guest_id") or request.data.get("table_guest_id")
            raw_guest_number = request.data.get("guest_number") or request.data.get("seat_number")
            try:
                guest_id = int(raw_guest_id) if raw_guest_id not in (None, "") else None
            except (TypeError, ValueError):
                guest_id = None
            try:
                guest_number = int(raw_guest_number) if raw_guest_number not in (None, "") else None
            except (TypeError, ValueError):
                guest_number = None
            guests = session.guests.select_for_update().all()
            if guest_id:
                guest = guests.filter(id=guest_id).first()
            if guest is None and guest_number:
                guest = guests.filter(seat_number=guest_number).first()
            if guest is None:
                return Response({"guest_number": "Selecciona una persona válida de la mesa."}, status=400)
            pending_qs = pending_qs.filter(table_guest=guest)
        pending_items = list(pending_qs)
        if not pending_items:
            detail = "No hay productos pendientes para enviar."
            if guest:
                detail = f"No hay productos pendientes para {guest.label}."
            return Response(
                {
                    "detail": detail,
                    "sent_count": 0,
                    "session": TableSessionSerializer(session).data,
                    "order": OrderSerializer(order).data,
                    "summary": _serialize_kitchen_session(session),
                },
                status=status.HTTP_200_OK,
            )
        now = timezone.now()
        for item in pending_items:
            item.kitchen_status = OrderItem.KITCHEN_STATUS_SENT
            item.kitchen_sent_at = now
            item.save(update_fields=["kitchen_status", "kitchen_sent_at"])
        order.send_to_kitchen = True
        order.pending_state = "in_kitchen"
        order.save(update_fields=["send_to_kitchen", "pending_state", "updated_at"])
        session.status = "sent_to_kitchen"
        session.save(update_fields=["status", "updated_at"])
        detail = f"{len(pending_items)} productos enviados a cocina."
        if guest:
            detail = f"Productos de {guest.label} enviados a cocina."
        return Response({
            "detail": detail,
            "sent_count": len(pending_items),
            "session": TableSessionSerializer(session).data,
            "order": OrderSerializer(order).data,
            "summary": _serialize_kitchen_session(session),
        })


class TableKitchenSummaryView(TableMapFeatureGuardMixin, APIView):
    permission_classes = [CanViewKitchen]

    def get(self, request):
        sessions = (
            TableSession.objects.select_related("primary_order")
            .prefetch_related("session_tables__table", "primary_order__items__table_guest", "primary_order__items__applied_modifiers")
            .filter(status__in=ACTIVE_TABLE_SESSION_STATUSES)
            .order_by("-updated_at", "-id")
        )
        return Response({"sessions": [_serialize_kitchen_session(session) for session in sessions]})


class TableReadySummaryView(TableMapFeatureGuardMixin, APIView):
    permission_classes = [CanViewKitchen]

    def get(self, request):
        sessions = (
            TableSession.objects.select_related("primary_order")
            .prefetch_related("session_tables__table", "primary_order__items__table_guest", "primary_order__items__applied_modifiers")
            .filter(status__in=ACTIVE_TABLE_SESSION_STATUSES, primary_order__items__kitchen_status=OrderItem.KITCHEN_STATUS_READY)
            .distinct()
            .order_by("-updated_at", "-id")
        )
        rows = [_serialize_ready_session(session) for session in sessions]
        return Response({"tables": rows, "total_ready": sum(row["ready_count"] for row in rows)})


class TableOrderItemKitchenStatusView(APIView):
    permission_classes = [CanManageKitchenItems]

    def get_permissions(self):
        if self.kwargs.get("target_status") == OrderItem.KITCHEN_STATUS_DELIVERED:
            return [CanServeKitchenItems()]
        return [CanManageKitchenItems()]

    @transaction.atomic
    def post(self, request, pk: int, target_status: str):
        item = OrderItem.objects.select_for_update().select_related("order").filter(id=pk).first()
        if not item:
            return Response({"detail": "Producto no encontrado."}, status=404)
        now = timezone.now()
        if target_status == OrderItem.KITCHEN_STATUS_READY:
            if item.kitchen_status == OrderItem.KITCHEN_STATUS_DELIVERED:
                return Response({"detail": "El producto ya fue servido.", "code": "ALREADY_SERVED"}, status=400)
            if item.kitchen_status not in {OrderItem.KITCHEN_STATUS_SENT, OrderItem.KITCHEN_STATUS_READY}:
                return Response({"detail": "El producto aún no fue enviado a cocina.", "code": "NOT_IN_KITCHEN"}, status=400)
            item.kitchen_status = OrderItem.KITCHEN_STATUS_READY
            item.kitchen_ready_at = item.kitchen_ready_at or now
            fields = ["kitchen_status", "kitchen_ready_at"]
        elif target_status == OrderItem.KITCHEN_STATUS_DELIVERED:
            if item.kitchen_status == OrderItem.KITCHEN_STATUS_DELIVERED:
                return Response({"detail": "El producto ya estaba servido.", "code": "ALREADY_SERVED", "item": _serialize_kitchen_item(item)}, status=200)
            if item.kitchen_status != OrderItem.KITCHEN_STATUS_READY:
                return Response({"detail": "Solo puedes servir productos terminados.", "code": "NOT_READY_TO_SERVE"}, status=400)
            item.kitchen_status = OrderItem.KITCHEN_STATUS_DELIVERED
            item.kitchen_delivered_at = item.kitchen_delivered_at or now
            fields = ["kitchen_status", "kitchen_delivered_at"]
        else:
            return Response({"detail": "Estado inválido."}, status=400)
        item.save(update_fields=fields)
        if target_status == OrderItem.KITCHEN_STATUS_DELIVERED:
            active_session = (
                TableSession.objects.select_for_update()
                .filter(primary_order=item.order, status=TableSession.STATUS_SENT_TO_KITCHEN)
                .first()
            )
            has_open_kitchen_items = item.order.items.filter(
                kitchen_status__in=[
                    OrderItem.KITCHEN_STATUS_PENDING,
                    OrderItem.KITCHEN_STATUS_SENT,
                    OrderItem.KITCHEN_STATUS_READY,
                ]
            ).exists()
            if active_session and not has_open_kitchen_items:
                active_session.status = TableSession.STATUS_OPEN
                active_session.save(update_fields=["status", "updated_at"])
        return Response({"detail": "Estado actualizado.", "item": _serialize_kitchen_item(item)})


class TableSessionServeReadyView(TableMapFeatureGuardMixin, APIView):
    permission_classes = [CanServeKitchenItems]

    @transaction.atomic
    def post(self, request, pk: int):
        session = TableSession.objects.select_for_update().filter(id=pk, status__in=ACTIVE_TABLE_SESSION_STATUSES).first()
        if not session or not session.primary_order_id:
            return Response({"detail": "Sesión no encontrada."}, status=404)
        raw_item_ids = request.data.get("item_ids")
        item_ids = []
        if isinstance(raw_item_ids, list):
            for value in raw_item_ids:
                try:
                    item_ids.append(int(value))
                except (TypeError, ValueError):
                    return Response({"item_ids": "Lista de productos inválida."}, status=400)
        items_qs = session.primary_order.items.select_for_update().filter(kitchen_status=OrderItem.KITCHEN_STATUS_READY)
        if item_ids:
            items_qs = items_qs.filter(id__in=item_ids)
        items = list(items_qs)
        if not items:
            return Response({"detail": "No hay productos listos para servir.", "served_count": 0, "summary": _serialize_ready_session(session)}, status=200)
        now = timezone.now()
        for item in items:
            item.kitchen_status = OrderItem.KITCHEN_STATUS_DELIVERED
            item.kitchen_delivered_at = item.kitchen_delivered_at or now
            item.save(update_fields=["kitchen_status", "kitchen_delivered_at"])
        has_open_kitchen_items = session.primary_order.items.filter(
            kitchen_status__in=[
                OrderItem.KITCHEN_STATUS_PENDING,
                OrderItem.KITCHEN_STATUS_SENT,
                OrderItem.KITCHEN_STATUS_READY,
            ]
        ).exists()
        if session.status == TableSession.STATUS_SENT_TO_KITCHEN and not has_open_kitchen_items:
            session.status = TableSession.STATUS_OPEN
            session.save(update_fields=["status", "updated_at"])
        refreshed = TableSession.objects.select_related("primary_order").prefetch_related(
            "session_tables__table", "primary_order__items__table_guest", "primary_order__items__applied_modifiers"
        ).get(id=session.id)
        return Response({
            "detail": f"{len(items)} productos servidos.",
            "served_count": len(items),
            "summary": _serialize_ready_session(refreshed),
            "session": TableSessionSerializer(refreshed).data,
        })


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
        if session.session_tables.count() > 1 and not session.group_number:
            session.group_number = _next_group_number()
            session.save(update_fields=["group_number", "updated_at"])
        if session.primary_order_id:
            names = list(session.session_tables.select_related("table").order_by("created_at", "id").values_list("table__name", flat=True))
            session.primary_order.pending_reference = " + ".join(names)
            session.primary_order.save(update_fields=["pending_reference", "updated_at"])
        return _session_response(session)


class TableSessionSplitTableView(TableMapFeatureGuardMixin, APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    @transaction.atomic
    def post(self, request, pk: int):
        session = TableSession.objects.select_for_update().filter(id=pk, status__in=ACTIVE_TABLE_SESSION_STATUSES).first()
        if not session:
            return Response({"detail": "Sesión no encontrada o cerrada."}, status=404)
        table_id = _parse_int(request.data.get("table_id"))
        if not table_id:
            return Response({"table_id": "Mesa inválida."}, status=400)
        links = TableSessionTable.objects.select_for_update().filter(session=session)
        if links.count() <= 1:
            return Response({"detail": "La mesa no pertenece a un grupo unido."}, status=400)
        removed, _ = links.filter(table_id=table_id).delete()
        if removed == 0:
            return Response({"table_id": "La mesa no pertenece a esta sesión."}, status=400)
        remaining_names = list(
            TableSessionTable.objects.filter(session=session)
            .select_related("table")
            .order_by("created_at", "id")
            .values_list("table__name", flat=True)
        )
        if session.primary_order_id:
            session.primary_order.pending_reference = " + ".join(remaining_names) if len(remaining_names) > 1 else f"Mesa {remaining_names[0]}"
            session.primary_order.save(update_fields=["pending_reference", "updated_at"])
        if len(remaining_names) <= 1 and session.group_number:
            session.group_number = None
            session.save(update_fields=["group_number", "updated_at"])
        return Response({"detail": "Mesa separada correctamente.", "session": TableSessionSerializer(session).data})


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
            closed_session = TableSession.objects.filter(id=pk, status__in=[TableSession.STATUS_CLOSED, TableSession.STATUS_CANCELLED]).first()
            if closed_session:
                return Response(
                    {"detail": "La mesa ya estaba liberada.", "session": TableSessionSerializer(closed_session).data},
                    status=status.HTTP_200_OK,
                )
            return Response({"detail": "Sesión no encontrada."}, status=404)
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


class TableSessionForceReleaseView(TableMapFeatureGuardMixin, APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    @transaction.atomic
    def post(self, request, pk: int):
        session = TableSession.objects.select_for_update().filter(id=pk, status__in=ACTIVE_TABLE_SESSION_STATUSES).first()
        if not session:
            return Response({"detail": "Sesión no encontrada o ya cerrada."}, status=404)
        reason = str(request.data.get("reason") or "").strip()
        if not reason:
            return Response({"reason": "Motivo obligatorio."}, status=400)
        order = session.primary_order
        order_total_paid = Decimal("0.00")
        order_remaining = Decimal("0.00")
        if order:
            order.recalculate_financials()
            order_total_paid = Payment.objects.filter(order=order).aggregate(total=Sum("amount_applied"))["total"] or Decimal("0.00")
            due = Decimal(order.amount_due_cents or to_cents(order.total)) / Decimal("100")
            order_remaining = max(due - order_total_paid, Decimal("0.00")).quantize(Decimal("0.01"))
        authorized_by = request.user if _is_admin_or_superadmin(request.user) else None
        if order_remaining > 0 and not authorized_by:
            authorized_by = _authorize_admin_or_superadmin_pin(str(request.data.get("authorization_pin") or "").strip())
            if not authorized_by:
                return Response({"detail": "Autorización de admin/superadmin requerida."}, status=status.HTTP_403_FORBIDDEN)
        if order:
            order.status = "canceled"
            order.financial_status = "voided"
            order.payment_status = "partial" if order_total_paid > 0 else "unpaid"
            order.net_paid = order_total_paid
            order.amount_due_cents = to_cents(order_total_paid)
            order.is_pending = False
            order.pending_state = "none"
            order.pending_completed_at = timezone.localtime(timezone.now())
            order.pending_completion_type = "canceled"
            order.pending_completion_note = reason[:160]
            order.save(update_fields=[
                "status", "financial_status", "payment_status", "net_paid", "amount_due_cents",
                "is_pending", "pending_state", "pending_completed_at", "pending_completion_type",
                "pending_completion_note", "updated_at",
            ])
        session.status = TableSession.STATUS_CANCELLED
        session.closed_by = request.user
        session.closed_at = timezone.now()
        session.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])
        log_audit(
            request,
            "table_session.force_release",
            "TableSession",
            session.id,
            {
                "order_id": order.id if order else None,
                "requested_by": getattr(request.user, "id", None),
                "authorized_by": getattr(authorized_by, "id", None) if authorized_by else None,
                "reason": reason,
                "cancelled_balance": str(order_remaining),
                "paid_kept": str(order_total_paid),
            },
        )
        return Response({
            "ok": True,
            "session": TableSessionSerializer(session).data,
            "voided_order_id": order.id if order else None,
            "authorized_by": getattr(authorized_by, "id", None) if authorized_by else None,
        })


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
