from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cashier.models import Register, CashSession, CashTransaction
from apps.cashier.printing import build_end_of_day_ticket
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
from apps.printing.models import PrintJob


def _get_open_session_for_user(user):
    return CashSession.objects.filter(opened_by=user, status="open").select_related("register", "register__branch").first()


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
    return Register.objects.create(
        name="CAJA 1",
        station_name="POS 1",
        branch=branch,
        is_active=True,
    )


class RegisterListCreateView(generics.ListCreateAPIView):
    queryset = Register.objects.select_related("branch").all()
    serializer_class = RegisterSerializer
    permission_classes = [IsAdminOrManager]


class CashSessionCurrentView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request):
        session = _get_open_session_for_user(request.user)
        if not session:
            return Response({"open": False}, status=status.HTTP_200_OK)

        summary = calculate_shift_summary(session)
        return Response({
            "open": True,
            "session": CashSessionSerializer(session).data,
            "summary": CashSessionSummarySerializer(summary).data,
        })


class CashSessionOpenView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    @transaction.atomic
    def post(self, request):
        if _get_open_session_for_user(request.user):
            return Response({"detail": "Ya hay una caja abierta."}, status=status.HTTP_400_BAD_REQUEST)

        opening_cash = Decimal(str(request.data.get("opening_cash", "0")))
        if opening_cash < 0:
            return Response({"detail": "Monto inicial inválido"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            register = _ensure_register(request.data.get("register_id"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if CashSession.objects.filter(register=register, status="open").exists():
            return Response({"detail": "La caja seleccionada ya está abierta."}, status=status.HTTP_400_BAD_REQUEST)

        session = CashSession.objects.create(
            register=register,
            opened_by=request.user,
            opening_cash=opening_cash,
            status="open",
        )
        log_audit(request, "cash_session.open", "CashSession", session.id, {"register_id": register.id, "opening_cash": str(opening_cash)})
        return Response(CashSessionSerializer(session).data, status=status.HTTP_201_CREATED)


class CashSessionCloseView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    @transaction.atomic
    def post(self, request):
        session = _get_open_session_for_user(request.user)
        if not session:
            return Response({"detail": "No hay caja abierta."}, status=status.HTTP_400_BAD_REQUEST)

        counted_cash = Decimal(str(request.data.get("closing_cash_counted", "0")))
        notes = str(request.data.get("notes", "")).strip()

        session.status = "closed"
        session.closed_by = request.user
        session.closed_at = timezone.now()
        session.closing_counted_cash = counted_cash
        session.notes = notes
        session.save(update_fields=["status", "closed_by", "closed_at", "closing_counted_cash", "notes"])

        summary = calculate_shift_summary(session)
        ticket_text = build_end_of_day_ticket(session.id)
        PrintJob.objects.create(
            type="closeout",
            status="rendered",
            content_text=ticket_text,
            meta={"cash_session_id": session.id, "event": "cash_session.closed"},
            requested_by=request.user,
        )
        log_audit(request, "cash_session.close", "CashSession", session.id, {"counted_cash": str(counted_cash)})
        return Response({
            "session": CashSessionSerializer(session).data,
            "summary": CashSessionSummarySerializer(summary).data,
            "ticket_text": ticket_text,
        })


class CashTransactionListCreateView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request):
        session_id = request.query_params.get("session_id")
        if session_id:
            session = CashSession.objects.filter(pk=session_id).first()
            if not session:
                return Response([], status=status.HTTP_200_OK)
        else:
            session = _get_open_session_for_user(request.user)
            if not session:
                return Response([], status=status.HTTP_200_OK)
        items = CashTransaction.objects.filter(session=session).order_by("-created_at")
        return Response(CashTransactionSerializer(items, many=True).data)

    @transaction.atomic
    def post(self, request):
        session = _get_open_session_for_user(request.user)
        if not session:
            return Response({"detail": "No hay caja abierta"}, status=status.HTTP_400_BAD_REQUEST)

        amount = Decimal(str(request.data.get("amount", "0")))
        description = str(request.data.get("description", "")).strip()
        transaction_type = str(request.data.get("type", "cash_out")).strip().lower()

        allowed = {"cash_out", "cash_in", "expense", "payout"}
        if transaction_type not in allowed:
            return Response({"detail": "Tipo de transacción inválido."}, status=status.HTTP_400_BAD_REQUEST)
        if amount <= 0:
            return Response({"detail": "El monto debe ser mayor que cero."}, status=status.HTTP_400_BAD_REQUEST)
        if not description:
            return Response({"detail": "La descripción es obligatoria."}, status=status.HTTP_400_BAD_REQUEST)

        tx = CashTransaction.objects.create(
            session=session,
            type=transaction_type,
            amount=amount,
            description=description,
            created_by=request.user,
        )
        log_audit(request, "cash_transaction.create", "CashTransaction", tx.id, {"type": tx.type, "amount": str(tx.amount)})
        return Response(CashTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class CashSessionListView(generics.ListAPIView):
    permission_classes = [IsAuthenticatedAndActive]
    serializer_class = CashSessionSerializer

    def get_queryset(self):
        qs = CashSession.objects.select_related("register", "register__branch", "opened_by", "closed_by").all()
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        register_id = self.request.query_params.get("register_id")
        if date_from:
            qs = qs.filter(opened_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(opened_at__date__lte=date_to)
        if register_id:
            qs = qs.filter(register_id=register_id)
        return qs

    def list(self, request, *args, **kwargs):
        sessions = self.get_queryset()
        payload = []
        for session in sessions:
            summary = calculate_shift_summary(session)
            payload.append({
                **CashSessionSerializer(session).data,
                "summary": CashSessionSummarySerializer(summary).data,
            })
        return Response(payload)


class CashSessionDetailView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, pk: int):
        session = CashSession.objects.select_related("register", "register__branch", "opened_by", "closed_by").filter(pk=pk).first()
        if not session:
            return Response({"detail": "Sesión no encontrada"}, status=status.HTTP_404_NOT_FOUND)
        summary = calculate_shift_summary(session)
        txs = CashTransaction.objects.filter(session=session).order_by("-created_at")
        return Response({
            "session": CashSessionSerializer(session).data,
            "summary": CashSessionSummarySerializer(summary).data,
            "transactions": CashTransactionSerializer(txs, many=True).data,
        })


# Legacy routes kept for compatibility
ShiftOpenView = CashSessionOpenView
ShiftCurrentView = CashSessionCurrentView
class ShiftCloseView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def post(self, request, pk: int):
        session = CashSession.objects.filter(pk=pk, status="open").first()
        if not session:
            return Response({"detail": "Shift not found or closed"}, status=status.HTTP_404_NOT_FOUND)
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
        return Response({
            "id": job.id,
            "status": job.status,
            "content_text": job.content_text,
            "created_at": job.created_at,
            "printed_at": job.printed_at,
        })
