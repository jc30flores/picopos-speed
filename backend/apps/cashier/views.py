from datetime import timedelta
from decimal import Decimal, InvalidOperation
import json
import logging

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cashier.models import Register, CashSession, CashTransaction
from apps.cashier.printing import build_end_of_day_ticket, build_end_of_day_ticket_pdf, print_ticket_text
from apps.cashier.serializers import (
    RegisterSerializer,
    CashSessionSerializer,
    CashSessionCloseSerializer,
    CashSessionSummarySerializer,
    CashTransactionSerializer,
    calculate_shift_summary,
)
from apps.core.audit import log_audit
from apps.core.models import Branch
from apps.core.feature_flags import can_view_cash_expected_totals, get_pos_quick_sales_settings, is_feature_enabled
from apps.core.permissions import IsAdminOrManager, IsManagerOrAdmin, IsCashierOrManagerOrAdmin, IsAuthenticatedAndActive, _get_profile
from apps.core.timezone_utils import parse_business_date_range
from apps.printing.models import PrintJob
from apps.cashier.services import CashDrawerService, get_open_cash_session_for_branch, resolve_branch_id, resolve_open_cash_session
from apps.cashier.services.auto_close import count_open_orders_for_cash_close, maybe_auto_close_expired_cash_sessions
from apps.payments.models import Payment

logger = logging.getLogger(__name__)


class PdfRenderer(BaseRenderer):
    media_type = "application/pdf"
    format = "pdf"
    charset = None
    render_style = "binary"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


def _get_open_session_for_register(register):
    return (
        CashSession.objects.filter(register=register, status="open", closed_at__isnull=True)
        .select_related("register", "register__branch")
        .first()
    )


def _get_open_session_for_request(request, register_id=None):
    requested_register_id = register_id or request.query_params.get("register_id") or request.data.get("register_id")
    if requested_register_id:
        register = _ensure_register(requested_register_id)
        return register, _get_open_session_for_register(register)

    raw_branch_id = (
        request.query_params.get("branch_id")
        or request.headers.get("X-Branch-Id")
        or request.headers.get("x-branch-id")
        or request.data.get("branch_id")
    )
    branch_id = resolve_branch_id(raw_branch_id)
    session = get_open_cash_session_for_branch(branch_id)
    return None, session


def _ensure_register(register_id=None):
    register = None
    if register_id:
        register = Register.objects.filter(id=register_id, is_active=True).first()
    if register:
        return register
    register = Register.objects.filter(is_active=True).order_by("id").first()
    if register:
        return register
    branch = Branch.objects.filter(is_active=True).order_by("id").first() or Branch.objects.order_by("id").first()
    if not branch:
        raise ValueError("No hay sucursales configuradas")
    return Register.objects.create(name="CAJA 1", station_name="POS 1", branch=branch, is_active=True)


def _parse_decimal(value, *, field_label: str) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{field_label} inválido")


def _to_json_compatible(value):
    return json.loads(json.dumps(value, default=str))


def _build_close_payload(data) -> dict:
    return {
        "branch_id": data.get("branch_id"),
        "session_id": data.get("session_id"),
        "total_billetes": data.get("total_billetes", data.get("total_bills")),
        "total_monedas": data.get("total_monedas", data.get("total_coins")),
        "total_pos_tarjetas": data.get("total_pos_tarjetas", data.get("total_pos_cards")),
        "total_pedidos_ya": data.get("total_pedidos_ya", data.get("total_pedidosya")),
        "total_contado": data.get("total_contado", data.get("counted_cash_amount", data.get("closing_cash_counted"))),
        "notes": data.get("notes", ""),
    }


def _first_serializer_error(errors) -> str:
    if isinstance(errors, list) and errors:
        return str(errors[0])
    if isinstance(errors, dict):
        for value in errors.values():
            msg = _first_serializer_error(value)
            if msg:
                return msg
    return "Datos inválidos."


def _session_contract_payload(session: CashSession, *, include_sensitive: bool = True) -> dict:
    raw = CashSessionSerializer(session).data
    payload = {
        **raw,
        "opening_amount": raw.get("opening_cash") if include_sensitive else None,
        "user": {
            "id": raw.get("opened_by"),
            "username": raw.get("opened_by_username"),
        },
        "branch": raw.get("branch_id"),
        "terminal": {
            "register_id": raw.get("register"),
            "register_name": raw.get("register_name"),
            "station_name": raw.get("station_name"),
        },
    }
    if not include_sensitive:
        payload["opening_cash"] = None
    return payload


def _can_view_sensitive_cash_data(request) -> bool:
    if getattr(request.user, "is_superuser", False):
        return True
    profile = _get_profile(request.user)
    return bool(profile and profile.is_active and profile.role == "admin")


def _filter_expected_totals_for_user(summary: dict, user) -> dict:
    if not isinstance(summary, dict):
        return summary
    allowed, visible_fields = can_view_cash_expected_totals(user)
    if allowed and not visible_fields:
        return summary

    filtered = dict(summary)
    methods = dict(filtered.get("totals_by_method") or {})
    if not allowed:
        filtered["expected_cash_in_drawer"] = Decimal("0")
        filtered["difference"] = Decimal("0")
        methods.update({"cash": Decimal("0"), "card": Decimal("0"), "card_credit": Decimal("0"), "card_debit": Decimal("0"), "transfer": Decimal("0"), "pedidos_ya": Decimal("0"), "paypal": Decimal("0")})
    else:
        if "expected_cash_in_drawer" not in visible_fields:
            filtered["expected_cash_in_drawer"] = Decimal("0")
        if "difference" not in visible_fields:
            filtered["difference"] = Decimal("0")
        code_by_method = {
            "cash": "card_expected",  # override below
            "card": "card_expected",
            "card_credit": "card_expected",
            "card_debit": "card_expected",
            "transfer": "transfer_expected",
            "pedidos_ya": "pedidos_ya_expected",
            "paypal": "paypal_expected",
        }
        code_by_method["cash"] = "expected_cash_in_drawer"
        for method_key, field_code in code_by_method.items():
            if field_code not in visible_fields:
                methods[method_key] = Decimal("0")
    filtered["totals_by_method"] = methods
    return filtered


class RegisterListCreateView(generics.ListCreateAPIView):
    queryset = Register.objects.select_related("branch").all()
    serializer_class = RegisterSerializer
    permission_classes = [IsAdminOrManager]


class CashSessionCurrentView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        profile = _get_profile(request.user)
        if profile and profile.role in {"waiter", "mesero"}:
            return Response(
                {
                    "has_open_session": False,
                    "has_open_cash_session": False,
                    "session": None,
                    "current_cash_session": None,
                    "summary": None,
                    "business_date": str(timezone.localdate()),
                    "last_opened_at": None,
                    "last_closed_at": None,
                    "total_sessions_today": 0,
                    "can_open_cash": False,
                    "can_close_cash": False,
                    "detail": "El rol Mesero no necesita caja abierta para tomar órdenes en mesas.",
                },
                status=status.HTTP_200_OK,
            )
        if not IsCashierOrManagerOrAdmin().has_permission(request, self):
            raise PermissionDenied("No tienes permiso para consultar caja.")
        auto_close_result = maybe_auto_close_expired_cash_sessions()
        raw_branch_id = (
            request.query_params.get("branch_id")
            or request.headers.get("X-Branch-Id")
            or request.headers.get("x-branch-id")
        )
        branch_id = resolve_branch_id(raw_branch_id)
        session = get_open_cash_session_for_branch(branch_id)
        today_sv = timezone.localdate()
        scoped_sessions = CashSession.objects.filter(register__branch_id=branch_id) if branch_id else CashSession.objects.all()
        latest_session = scoped_sessions.order_by("-opened_at").first()
        total_sessions_today = scoped_sessions.filter(opened_at__date=today_sv).count()
        pending_orders_count = count_open_orders_for_cash_close(branch_id)
        include_sensitive = _can_view_sensitive_cash_data(request)
        logger.info("cash_session.current branch_id=%s has_open_session=%s filter_scope=%s", branch_id, bool(session), "branch" if branch_id else "global")
        if not session:
            return Response(
                {
                    "has_open_session": False,
                    "has_open_cash_session": False,
                    "session": None,
                    "current_cash_session": None,
                    "summary": None,
                    "business_date": str(timezone.localdate()),
                    "last_opened_at": latest_session.opened_at if latest_session else None,
                    "last_closed_at": latest_session.closed_at if latest_session else None,
                    "total_sessions_today": total_sessions_today,
                    "can_open_cash": True,
                    "can_close_cash": False,
                    "pending_orders_count": pending_orders_count,
                    "cash_auto_close": auto_close_result,
                },
                status=status.HTTP_200_OK,
            )
        summary = _filter_expected_totals_for_user(calculate_shift_summary(session), request.user) if include_sensitive else None
        return Response(
            {
                "has_open_session": True,
                "has_open_cash_session": True,
                "session": _session_contract_payload(session, include_sensitive=include_sensitive),
                "current_cash_session": _session_contract_payload(session, include_sensitive=include_sensitive),
                "summary": CashSessionSummarySerializer(summary).data if summary else None,
                "business_date": str(timezone.localdate()),
                "last_opened_at": session.opened_at,
                "last_closed_at": session.closed_at,
                "total_sessions_today": total_sessions_today,
                "can_open_cash": False,
                "can_close_cash": True,
                "pending_orders_count": pending_orders_count,
                "cash_auto_close": auto_close_result,
            },
            status=status.HTTP_200_OK,
        )


class CashSessionOpenView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        profile = _get_profile(request.user)
        if profile and profile.role in {"waiter", "mesero"}:
            raise PermissionDenied("El rol Mesero no puede abrir caja.")
        if not IsCashierOrManagerOrAdmin().has_permission(request, self):
            raise PermissionDenied("No tienes permiso para abrir caja.")

    @transaction.atomic
    def post(self, request):
        maybe_auto_close_expired_cash_sessions()
        try:
            opening_cash = _parse_decimal(
                request.data.get("opening_cash_amount", request.data.get("opening_cash", "0")) or "0",
                field_label="Monto inicial",
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if opening_cash < 0:
            return Response({"detail": "Monto inicial inválido"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            branch_id = resolve_branch_id(request.data.get("branch_id"))
            register = Register.objects.filter(branch_id=branch_id, is_active=True).order_by("id").first() if branch_id else None
            if not register and branch_id:
                branch = Branch.objects.filter(id=branch_id, is_active=True).first()
                if branch:
                    register = Register.objects.create(name="CAJA 1", station_name="POS 1", branch=branch, is_active=True)
            if not register:
                register = _ensure_register(request.data.get("cash_register_id") or request.data.get("register_id"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        register = Register.objects.select_for_update().get(pk=register.pk)
        scope_branch_id = branch_id or register.branch_id
        existing_session = (
            CashSession.objects.select_for_update()
            .select_related("register", "register__branch")
            .filter(register__branch_id=scope_branch_id, status="open", closed_at__isnull=True)
            .first()
        )
        if existing_session:
            logger.info("cash_session.open branch_id=%s already_open_session_id=%s", scope_branch_id, existing_session.id)
            logger.info(
                "cash_session.open.response status=409 branch_id=%s session_id=%s has_open_session=%s",
                scope_branch_id,
                existing_session.id,
                True,
            )
            return Response(
                {
                    "code": "CASH_SESSION_ALREADY_OPEN",
                    "detail": "Ya existe una caja abierta para esta sucursal.",
                    "has_open_session": True,
                    "has_open_cash_session": True,
                    "can_open_cash": False,
                    "can_close_cash": True,
                    "session": _session_contract_payload(existing_session, include_sensitive=_can_view_sensitive_cash_data(request)),
                },
                status=status.HTTP_409_CONFLICT,
            )

        session = CashSession.objects.create(register=register, opened_by=request.user, opening_cash=opening_cash, status="open")
        logger.info("cash_session.open branch_id=%s opened_session_id=%s", register.branch_id, session.id)
        logger.info(
            "cash_session.open.response status=201 branch_id=%s session_id=%s has_open_session=%s",
            register.branch_id,
            session.id,
            True,
        )
        log_audit(request, "cash_session.open", "CashSession", session.id, {"register_id": register.id, "opening_cash": str(opening_cash)})
        return Response(
            {
                "has_open_session": True,
                "has_open_cash_session": True,
                "can_open_cash": False,
                "can_close_cash": True,
                "already_open": False,
                "session": _session_contract_payload(session, include_sensitive=_can_view_sensitive_cash_data(request)),
            },
            status=status.HTTP_201_CREATED,
        )


class CashSessionCloseView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        profile = _get_profile(request.user)
        if profile and profile.role in {"waiter", "mesero"}:
            raise PermissionDenied("El rol Mesero no puede cerrar caja.")
        if not IsCashierOrManagerOrAdmin().has_permission(request, self):
            raise PermissionDenied("No tienes permiso para cerrar caja.")

    @transaction.atomic
    def post(self, request):
        maybe_auto_close_expired_cash_sessions()
        raw_payload = _build_close_payload(request.data)
        branch_id = resolve_branch_id(
            raw_payload.get("branch_id")
            or request.query_params.get("branch_id")
            or request.headers.get("X-Branch-Id")
            or request.headers.get("x-branch-id")
        )
        raw_session_id = raw_payload.get("session_id")
        session_id = int(raw_session_id) if str(raw_session_id).isdigit() else None
        logger.info(
            "cash_session.close.payload user_id=%s username=%s branch_id=%s session_id=%s payload=%s",
            getattr(request.user, "id", None),
            getattr(request.user, "username", ""),
            branch_id,
            session_id,
            _to_json_compatible(raw_payload),
        )
        current_scope_session = get_open_cash_session_for_branch(branch_id)
        session, resolution_error = resolve_open_cash_session(branch_id=branch_id, session_id=session_id)
        logger.info(
            "cash_session.close.resolution branch_id=%s requested_session_id=%s current_scope_session_id=%s resolved_session_id=%s resolution_error=%s",
            branch_id,
            session_id,
            getattr(current_scope_session, "id", None),
            getattr(session, "id", None),
            resolution_error,
        )
        if not session:
            if resolution_error == "SESSION_BRANCH_MISMATCH":
                return Response({"detail": "La sesión indicada no pertenece a la sucursal seleccionada."}, status=status.HTTP_400_BAD_REQUEST)
            if resolution_error == "SESSION_NOT_OPEN":
                return Response({"detail": "La sesión indicada no está abierta."}, status=status.HTTP_400_BAD_REQUEST)
            logger.warning(
                "cash_session.close.no_open_session user_id=%s branch_header=%s branch_query=%s",
                getattr(request.user, "id", None),
                request.headers.get("X-Branch-Id") or request.headers.get("x-branch-id"),
                request.query_params.get("branch_id"),
            )
            return Response({"detail": "No hay caja abierta."}, status=status.HTTP_400_BAD_REQUEST)
        pending_count = count_open_orders_for_cash_close(session.register.branch_id)
        allow_close_with_pending = is_feature_enabled("FF_CASH_CLOSE_ALLOW_PENDING_ORDERS")
        if pending_count > 0 and not allow_close_with_pending:
            account_label = "cuenta abierta" if pending_count == 1 else "cuentas abiertas"
            return Response(
                {
                    "code": "PENDING_ORDERS_BLOCK_CASH_CLOSE",
                    "detail": f"No puedes cerrar la caja porque hay {pending_count} {account_label}. Resuelve o cobra esas cuentas antes de cerrar.",
                    "pending_orders": pending_count,
                },
                status=status.HTTP_409_CONFLICT,
            )
        serializer = CashSessionCloseSerializer(data=raw_payload)
        if not serializer.is_valid():
            logger.warning(
                "cash_session.close.validation_error session_id=%s errors=%s",
                session.id,
                _to_json_compatible(serializer.errors),
            )
            return Response(
                {
                    "detail": "No se pudo cerrar la caja porque uno de los montos no es válido. Revisa los montos ingresados. Usa valores con máximo 2 decimales.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        counted_cash = serializer.validated_data["total_contado"]
        counted_bills = serializer.validated_data["total_billetes"]
        counted_coins = serializer.validated_data["total_monedas"]
        counted_pos_cards = serializer.validated_data["total_pos_tarjetas"]
        counted_pedidos_ya = serializer.validated_data["total_pedidos_ya"]
        notes = serializer.validated_data["notes"]

        session.status = "closed"
        session.closed_by = request.user
        session.closed_at = timezone.now()
        session.closing_counted_cash = counted_cash
        session.closing_total_bills = counted_bills
        session.closing_total_coins = counted_coins
        session.closing_total_pos_cards = counted_pos_cards
        session.closing_total_pedidos_ya = counted_pedidos_ya
        session.close_type = CashSession.CLOSE_TYPE_MANUAL
        session.notes = notes
        # snapshot after close-time set
        snapshot = calculate_shift_summary(session)
        session.summary_snapshot = _to_json_compatible(snapshot)
        session.save(
            update_fields=[
                "status",
                "closed_by",
                "closed_at",
                "closing_counted_cash",
                "closing_total_bills",
                "closing_total_coins",
                "closing_total_pos_cards",
                "closing_total_pedidos_ya",
                "close_type",
                "notes",
                "summary_snapshot",
            ]
        )

        ticket_text = ""
        printed = False
        print_error = None
        try:
            ticket_text = build_end_of_day_ticket(session.id)
            printed, print_error = print_ticket_text(ticket_text)
            PrintJob.objects.create(
                type="closeout",
                status="rendered",
                content_text=ticket_text,
                meta={"cash_session_id": session.id, "event": "cash_session.closed", "printed": printed, "print_error": print_error},
                requested_by=request.user,
            )
            logger.info(
                "cash_session.close.print_attempted",
                extra={"cash_session_id": session.id, "user_id": getattr(request.user, "id", None), "printed": printed},
            )
            if not printed:
                logger.warning(
                    "cash_session.close.print_unavailable",
                    extra={
                        "cash_session_id": session.id,
                        "user_id": getattr(request.user, "id", None),
                        "print_error": print_error,
                    },
                )
        except Exception as exc:
            print_error = str(exc)
            logger.exception(
                "cash_session.close.print_failed",
                extra={"cash_session_id": session.id, "user_id": getattr(request.user, "id", None)},
            )
        logger.info(
            "cash_session.close.response status=200 branch_id=%s session_id=%s printed=%s print_error=%s",
            session.register.branch_id,
            session.id,
            printed,
            print_error,
        )
        log_audit(request, "cash_session.close", "CashSession", session.id, {"counted_cash": str(counted_cash)})
        return Response(
            {
                "ok": True,
                "session": CashSessionSerializer(session).data,
                "summary": snapshot,
                "ticket_text": ticket_text,
                "printed": printed,
                "print_error": print_error,
                "total_billetes": f"{counted_bills:.2f}",
                "total_monedas": f"{counted_coins:.2f}",
                "total_pos_tarjetas": f"{counted_pos_cards:.2f}",
                "total_pedidos_ya": f"{counted_pedidos_ya:.2f}",
                "total_contado": f"{counted_cash:.2f}",
            }
        )


class CashTransactionListCreateView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request):
        if not _can_view_sensitive_cash_data(request):
            logger.info(
                "CASHIER_TRANSACTIONS_LIST include=%s count=%s has_session=%s user_id=%s",
                request.query_params.get("include") or "",
                0,
                False,
                getattr(request.user, "id", None),
            )
            return Response([], status=status.HTTP_200_OK)
        session_id = request.query_params.get("session_id")
        start_at, end_at = parse_business_date_range(
            request.query_params.get("date_from"),
            request.query_params.get("date_to"),
        )
        if session_id:
            session = CashSession.objects.filter(pk=session_id).first()
        else:
            _, session = _get_open_session_for_request(request)
        if not session:
            logger.info(
                "CASHIER_TRANSACTIONS_LIST include=%s count=%s has_session=%s user_id=%s",
                request.query_params.get("include") or "",
                0,
                False,
                getattr(request.user, "id", None),
            )
            return Response([], status=status.HTTP_200_OK)
        include_all = str(request.query_params.get("include", "")).strip().lower() == "all"
        items = CashTransaction.objects.filter(session=session).select_related("payment", "refund").order_by("-created_at")
        if not include_all:
            items = items.filter(
                type__in=["cash_out", "expense", "payout"],
                payment__isnull=True,
                refund__isnull=True,
            )
        if start_at:
            items = items.filter(created_at__gte=start_at)
        if end_at:
            items = items.filter(created_at__lte=end_at)
        logger.info(
            "CASHIER_TRANSACTIONS_LIST include=%s count=%s has_session=%s user_id=%s",
            request.query_params.get("include") or "",
            items.count(),
            True,
            getattr(request.user, "id", None),
        )
        return Response(CashTransactionSerializer(items, many=True).data)

    @transaction.atomic
    def post(self, request):
        _, session = _get_open_session_for_request(request)
        if not session:
            return Response({"detail": "No hay caja abierta"}, status=status.HTTP_409_CONFLICT)

        try:
            amount = _parse_decimal(request.data.get("amount", "0"), field_label="Monto")
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        description = str(request.data.get("description", "")).strip()
        transaction_type = str(request.data.get("type", "cash_out")).strip().lower()

        if transaction_type not in {"cash_out", "cash_in", "expense", "payout"}:
            return Response({"detail": "Tipo de transacción inválido."}, status=status.HTTP_400_BAD_REQUEST)
        if amount <= 0:
            return Response({"detail": "El monto debe ser mayor que cero."}, status=status.HTTP_400_BAD_REQUEST)
        if not description:
            return Response({"detail": "La descripción es obligatoria."}, status=status.HTTP_400_BAD_REQUEST)

        tx = CashTransaction.objects.create(session=session, type=transaction_type, amount=amount, description=description, created_by=request.user)
        log_audit(request, "cash_transaction.create", "CashTransaction", tx.id, {"type": tx.type, "amount": str(tx.amount)})
        return Response(CashTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class CashSessionListView(generics.ListAPIView):
    permission_classes = [IsAuthenticatedAndActive]
    serializer_class = CashSessionSerializer

    def get_queryset(self):
        qs = CashSession.objects.select_related("register", "register__branch", "opened_by", "closed_by").all()
        start_at, end_at = parse_business_date_range(
            self.request.query_params.get("date_from"),
            self.request.query_params.get("date_to"),
        )
        register_id = self.request.query_params.get("register_id")
        if start_at:
            qs = qs.filter(opened_at__gte=start_at)
        if end_at:
            qs = qs.filter(opened_at__lte=end_at)
        if register_id:
            qs = qs.filter(register_id=register_id)
        return qs

    def list(self, request, *args, **kwargs):
        payload = []
        for session in self.get_queryset():
            summary = _filter_expected_totals_for_user(calculate_shift_summary(session), request.user)
            payload.append({**CashSessionSerializer(session).data, "summary": summary})
        return Response(payload)


class CashSessionHistoryView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        start_at, end_at = parse_business_date_range(
            request.query_params.get("date_from"),
            request.query_params.get("date_to"),
        )
        register_id = request.query_params.get("register_id")

        queryset = CashSession.objects.select_related("register", "opened_by", "closed_by").all()
        if start_at:
            queryset = queryset.filter(opened_at__gte=start_at)
        if end_at:
            queryset = queryset.filter(opened_at__lte=end_at)
        if register_id:
            queryset = queryset.filter(register_id=register_id)

        payload = []
        for session in queryset:
            summary = _filter_expected_totals_for_user(calculate_shift_summary(session), request.user)
            payload.append(
                {
                    "id": session.id,
                    "opened_at": session.opened_at,
                    "closed_at": session.closed_at,
                    "opened_by": getattr(session.opened_by, "username", ""),
                    "closed_by": getattr(session.closed_by, "username", ""),
                    "expected_cash": summary.get("expected_cash_in_drawer", Decimal("0")),
                    "counted_cash": summary.get("counted_cash", Decimal("0")),
                    "difference": summary.get("difference", Decimal("0")),
                    "summary_snapshot": _to_json_compatible(summary),
                    "status": session.status,
                    "notes": session.notes,
                    "register_name": getattr(session.register, "name", ""),
                }
            )
        return Response(payload)


class CashSessionDetailView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, pk: int):
        session = CashSession.objects.select_related("register", "register__branch", "opened_by", "closed_by").filter(pk=pk).first()
        if not session:
            return Response({"detail": "Sesión no encontrada"}, status=status.HTTP_404_NOT_FOUND)
        txs = CashTransaction.objects.filter(session=session).order_by("-created_at")
        return Response({"session": CashSessionSerializer(session).data, "summary": _filter_expected_totals_for_user(calculate_shift_summary(session), request.user), "transactions": CashTransactionSerializer(txs, many=True).data})


class CashSessionTicketPDFView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]
    renderer_classes = [PdfRenderer]

    def perform_content_negotiation(self, request, force=False):
        renderer = PdfRenderer()
        return renderer, renderer.media_type

    def get(self, request, pk: int):
        session = CashSession.objects.select_related("register", "register__branch").filter(pk=pk).first()
        if not session:
            return Response({"detail": "Sesión no encontrada"}, status=status.HTTP_404_NOT_FOUND)
        try:
            pdf_bytes = build_end_of_day_ticket_pdf(pk)
        except Exception:
            logger.exception("cashier.ticket_pdf.failed session_id=%s", pk)
            return Response({"detail": "No se pudo generar el PDF de cierre de caja."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        ts = timezone.localtime(session.closed_at or timezone.now()).strftime("%Y-%m-%d_%H-%M-%S")
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="end_of_day_{ts}.pdf"'
        return response


def _quick_sales_disabled_response(expected_mode: str):
    settings = get_pos_quick_sales_settings()
    if settings["mode"] != expected_mode:
        return Response(
            {"detail": "La función rápida de ventas no está habilitada para este modo.", "mode": settings["mode"]},
            status=status.HTTP_409_CONFLICT,
        )
    return None


def _valid_sales_payments_queryset():
    return (
        Payment.objects.select_related("order", "order__customer", "order__invoice", "payment_method", "reporting_payment_method")
        .filter(order__isnull=False, order__payment_status="paid")
        .exclude(order__status="canceled")
        .exclude(order__financial_status__in=["voided", "refunded_full"])
    )


def _scope_payments_to_session_or_today(payments_qs, *, branch_id=None, session=None):
    if session:
        return payments_qs.filter(Q(cash_session=session) | Q(cash_session__isnull=True, created_at__gte=session.opened_at, created_at__lte=session.closed_at or timezone.now()))
    start_at, end_at = parse_business_date_range(str(timezone.localdate()), str(timezone.localdate()))
    if start_at:
        payments_qs = payments_qs.filter(created_at__gte=start_at)
    if end_at:
        payments_qs = payments_qs.filter(created_at__lte=end_at)
    if branch_id:
        payments_qs = payments_qs.filter(order__branch_id=branch_id)
    return payments_qs


def _latest_session_for_branch(branch_id=None):
    qs = CashSession.objects.select_related("register", "register__branch").all()
    if branch_id:
        qs = qs.filter(register__branch_id=branch_id)
    return qs.order_by("-opened_at").first()


def _sale_action_payload(payment: Payment) -> dict:
    order = payment.order
    invoice = getattr(order, "invoice", None)
    method = payment.reporting_payment_method or payment.payment_method
    customer_name = getattr(order.customer, "full_name", "") or getattr(order.customer, "name", "") or order.customer_name or "CONSUMIDOR FINAL"
    control_number = getattr(invoice, "numero_control", "") or getattr(invoice, "dte_number", "") or ""
    return {
        "id": order.id,
        "order_id": order.id,
        "payment_id": payment.id,
        "order_number": f"ORD-{order.order_number}",
        "control_number": control_number,
        "customer_name": customer_name,
        "payment_method": getattr(method, "name", "") or payment.get_method_display(),
        "total": f"{((payment.amount or Decimal('0')) + (payment.tip_amount or Decimal('0'))):.2f}",
        "status": order.get_payment_status_display() if order.payment_status else order.get_status_display(),
        "created_at": timezone.localtime(payment.created_at).isoformat(),
        "can_print_ticket": True,
        "can_send_dte": bool(control_number),
    }


class LastSaleActionView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request):
        disabled = _quick_sales_disabled_response("last_sale")
        if disabled:
            return disabled
        branch_id = resolve_branch_id(
            request.query_params.get("branch_id")
            or request.headers.get("X-Branch-Id")
            or request.headers.get("x-branch-id")
        )
        session = get_open_cash_session_for_branch(branch_id)
        payments_qs = _scope_payments_to_session_or_today(_valid_sales_payments_queryset(), branch_id=branch_id, session=session)
        payment = payments_qs.order_by("-created_at", "-id").first()
        if not payment:
            return Response({"detail": "No hay una venta reciente para reimprimir."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_sale_action_payload(payment), status=status.HTTP_200_OK)

class RecentSalesActionsView(APIView):
    permission_classes = [IsManagerOrAdmin]

    def get(self, request):
        disabled = _quick_sales_disabled_response("history")
        if disabled:
            return disabled
        settings = get_pos_quick_sales_settings()
        branch_id = resolve_branch_id(
            request.query_params.get("branch_id")
            or request.headers.get("X-Branch-Id")
            or request.headers.get("x-branch-id")
        )
        payments_qs = _valid_sales_payments_queryset()
        if settings["history_scope"] == "current_shift":
            session = get_open_cash_session_for_branch(branch_id) or _latest_session_for_branch(branch_id)
            if not session:
                return Response([], status=status.HTTP_200_OK)
            payments_qs = _scope_payments_to_session_or_today(payments_qs, branch_id=branch_id, session=session)
        else:
            window_minutes = settings["history_window_minutes"]
            if window_minutes == 1440:
                start_at, end_at = parse_business_date_range(str(timezone.localdate()), str(timezone.localdate()))
                if start_at:
                    payments_qs = payments_qs.filter(created_at__gte=start_at)
                if end_at:
                    payments_qs = payments_qs.filter(created_at__lte=end_at)
            else:
                payments_qs = payments_qs.filter(created_at__gte=timezone.now() - timedelta(minutes=window_minutes))
            if branch_id:
                payments_qs = payments_qs.filter(order__branch_id=branch_id)
        rows = [_sale_action_payload(payment) for payment in payments_qs.order_by("-created_at", "-id")[:50]]
        return Response(rows, status=status.HTTP_200_OK)


class CashDrawerOpenView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def post(self, request):
        _, session = _get_open_session_for_request(request)
        branch_name = getattr(getattr(session, "register", None), "branch", None)
        branch_name = getattr(branch_name, "name", None)
        log_extra = {
            "event": "cash_drawer.open",
            "user": getattr(request.user, "username", "unknown"),
            "branch": branch_name or "N/A",
            "session_id": getattr(session, "id", None),
        }
        result = CashDrawerService().open_drawer()
        if not result.success:
            logger.warning("cash_drawer.open.failed", extra={**log_extra, "error": result.message, "error_code": result.error})
            return Response(
                {
                    "ok": False,
                    "success": False,
                    "variant": result.variant,
                    "on": result.on,
                    "off": result.off,
                    "error": result.error,
                    "message": result.message,
                },
                status=status.HTTP_200_OK,
            )

        logger.info("cash_drawer.open.success", extra={**log_extra, "vendor_id": result.vendor_id, "product_id": result.product_id, "interface": result.interface, "out_endpoint": result.out_endpoint})
        log_audit(request, "cash_drawer.open", "CashSession", getattr(session, "id", None), {"branch": branch_name or ""})
        return Response(
            {
                "ok": True,
                "success": True,
                "variant": result.variant,
                "on": result.on,
                "off": result.off,
                "error": None,
                "message": result.message or "Gaveta abierta",
            },
            status=status.HTTP_200_OK,
        )


class CashDrawerTestView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def post(self, request):
        variant = request.data.get("variant")
        on = request.data.get("on")
        off = request.data.get("off")
        try:
            parsed_variant = None if variant is None else int(variant)
            parsed_on = None if on is None else int(on)
            parsed_off = None if off is None else int(off)
        except (TypeError, ValueError):
            return Response({"success": False, "error": "PARAMS", "message": "Parámetros inválidos"}, status=status.HTTP_200_OK)

        result = CashDrawerService().open_drawer(variant=parsed_variant, on=parsed_on, off=parsed_off)
        return Response(
            {
                "success": bool(result.success),
                "variant": result.variant,
                "on": result.on,
                "off": result.off,
                "command_hex": result.command_hex,
                "error": result.error or None,
                "message": result.message,
            },
            status=status.HTTP_200_OK,
        )


class CashDrawerStatusView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request):
        payload = CashDrawerService().status()
        payload["ok"] = True
        return Response(payload)


ShiftOpenView = CashSessionOpenView
ShiftCurrentView = CashSessionCurrentView


class ShiftCloseView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def post(self, request, pk: int):
        return CashSessionCloseView().post(request)


class ShiftSummaryView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, pk: int):
        return CashSessionDetailView().get(request, pk)


class ShiftCloseoutPrintJobView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request, pk: int):
        job = PrintJob.objects.filter(type="closeout", meta__cash_session_id=pk).order_by("-created_at").first()
        if not job:
            return Response({"detail": "Print job not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"id": job.id, "status": job.status, "content_text": job.content_text, "created_at": job.created_at, "printed_at": job.printed_at})
