from decimal import Decimal, InvalidOperation
import json
import logging

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cashier.models import Register, CashSession, CashTransaction
from apps.cashier.printing import build_end_of_day_ticket, build_end_of_day_ticket_pdf, print_ticket_text
from apps.cashier.serializers import (
    RegisterSerializer,
    CashSessionSerializer,
    CashSessionSummarySerializer,
    CashTransactionSerializer,
    calculate_shift_summary,
)
from apps.core.audit import log_audit
from apps.core.models import Branch
from apps.core.permissions import IsAdminOrManager, IsCashierOrManagerOrAdmin, IsAuthenticatedAndActive
from apps.core.timezone_utils import parse_business_date_range
from apps.printing.models import PrintJob
from apps.cashier.services import CashDrawerService

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
    register = _ensure_register(register_id or request.query_params.get("register_id") or request.data.get("register_id"))
    session = _get_open_session_for_register(register)
    return register, session


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


class RegisterListCreateView(generics.ListCreateAPIView):
    queryset = Register.objects.select_related("branch").all()
    serializer_class = RegisterSerializer
    permission_classes = [IsAdminOrManager]


class CashSessionCurrentView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request):
        session = (
            CashSession.objects.filter(closed_at__isnull=True)
            .select_related("register", "register__branch")
            .order_by("-opened_at")
            .first()
        )
        if not session:
            return Response({"session": None, "summary": None}, status=status.HTTP_200_OK)
        summary = calculate_shift_summary(session)
        return Response({"session": CashSessionSerializer(session).data, "summary": CashSessionSummarySerializer(summary).data}, status=status.HTTP_200_OK)


class CashSessionOpenView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    @transaction.atomic
    def post(self, request):
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
            register = _ensure_register(request.data.get("cash_register_id") or request.data.get("register_id"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        register = Register.objects.select_for_update().get(pk=register.pk)
        existing_session = (
            CashSession.objects.select_for_update()
            .select_related("register", "register__branch")
            .filter(register=register, status="open", closed_at__isnull=True)
            .first()
        )
        if existing_session:
            return Response(
                {
                    "already_open": True,
                    "session": CashSessionSerializer(existing_session).data,
                },
                status=status.HTTP_200_OK,
            )

        session = CashSession.objects.create(register=register, opened_by=request.user, opening_cash=opening_cash, status="open")
        log_audit(request, "cash_session.open", "CashSession", session.id, {"register_id": register.id, "opening_cash": str(opening_cash)})
        return Response(
            {
                "already_open": False,
                "session": CashSessionSerializer(session).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CashSessionCloseView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    @transaction.atomic
    def post(self, request):
        _, session = _get_open_session_for_request(request)
        if not session:
            return Response({"detail": "No hay caja abierta."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            counted_cash = _parse_decimal(
                request.data.get("counted_cash_amount", request.data.get("closing_cash_counted", "0")) or "0",
                field_label="Monto contado",
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        notes = str(request.data.get("notes", "")).strip()
        if counted_cash < 0:
            return Response({"detail": "Monto contado inválido"}, status=status.HTTP_400_BAD_REQUEST)

        session.status = "closed"
        session.closed_by = request.user
        session.closed_at = timezone.now()
        session.closing_counted_cash = counted_cash
        session.notes = notes
        # snapshot after close-time set
        snapshot = calculate_shift_summary(session)
        session.summary_snapshot = _to_json_compatible(snapshot)
        session.save(update_fields=["status", "closed_by", "closed_at", "closing_counted_cash", "notes", "summary_snapshot"])

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
        log_audit(request, "cash_session.close", "CashSession", session.id, {"counted_cash": str(counted_cash)})
        return Response(
            {
                "ok": True,
                "session": CashSessionSerializer(session).data,
                "summary": snapshot,
                "ticket_text": ticket_text,
                "printed": printed,
                "print_error": print_error,
            }
        )


class CashTransactionListCreateView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request):
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
            return Response([], status=status.HTTP_200_OK)
        items = CashTransaction.objects.filter(
            session=session,
            type__in=["cash_out", "expense", "payout"],
            payment__isnull=True,
            refund__isnull=True,
        ).order_by("-created_at")
        if start_at:
            items = items.filter(created_at__gte=start_at)
        if end_at:
            items = items.filter(created_at__lte=end_at)
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
            summary = calculate_shift_summary(session)
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
            summary = calculate_shift_summary(session)
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
        return Response({"session": CashSessionSerializer(session).data, "summary": calculate_shift_summary(session), "transactions": CashTransactionSerializer(txs, many=True).data})


class CashSessionTicketPDFView(APIView):
    permission_classes = [IsAuthenticatedAndActive]
    renderer_classes = [PdfRenderer]

    def perform_content_negotiation(self, request, force=False):
        renderer = PdfRenderer()
        return renderer, renderer.media_type

    def get(self, request, pk: int):
        session = CashSession.objects.filter(pk=pk).first()
        if not session:
            return Response({"detail": "Sesión no encontrada"}, status=status.HTTP_404_NOT_FOUND)
        pdf_bytes = build_end_of_day_ticket_pdf(pk)
        ts = timezone.localtime(session.closed_at or timezone.now()).strftime("%Y-%m-%d_%H-%M-%S")
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="end_of_day_{ts}.pdf"'
        return response


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
