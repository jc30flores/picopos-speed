from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.cashier.models import Register, CashSession, CloseoutCount
from apps.cashier.serializers import (
    RegisterSerializer,
    CashSessionSerializer,
    CloseoutCountSerializer,
    CashSessionSummarySerializer,
    calculate_shift_summary,
)
from apps.core.audit import log_audit
from apps.core.permissions import IsAdminOrManager, IsCashierOrManagerOrAdmin, IsAuthenticatedAndActive
from apps.printing.services.renderers import render_closeout_ticket
from apps.printing.models import PrintJob


def _get_user_shift(user):
    return CashSession.objects.filter(opened_by=user, status="open").select_related("register").first()


def _ensure_can_view(session: CashSession, user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if session.opened_by_id == user.id or session.closed_by_id == user.id:
        return True
    return False


class RegisterListCreateView(generics.ListCreateAPIView):
    queryset = Register.objects.select_related("branch").all()
    serializer_class = RegisterSerializer
    permission_classes = [IsAdminOrManager]


class ShiftOpenView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    @transaction.atomic
    def post(self, request):
        register_id = request.data.get("register_id")
        opening_cash = Decimal(str(request.data.get("opening_cash", "0")))
        if not register_id:
            return Response({"detail": "register_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        register = Register.objects.filter(id=register_id, is_active=True).first()
        if not register:
            return Response({"detail": "Register not found"}, status=status.HTTP_404_NOT_FOUND)

        existing = CashSession.objects.filter(register=register, status="open").first()
        if existing:
            return Response({"detail": "Register already has an open shift"}, status=status.HTTP_400_BAD_REQUEST)

        session = CashSession.objects.create(
            register=register,
            opened_by=request.user,
            opening_cash=opening_cash,
            status="open",
        )
        log_audit(
            request,
            "shift.open",
            "CashSession",
            session.id,
            {"register_id": register.id, "opening_cash": str(opening_cash)},
        )
        serializer = CashSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ShiftCurrentView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        session = _get_user_shift(request.user)
        if not session:
            return Response({"detail": "No open shift"}, status=status.HTTP_200_OK)
        serializer = CashSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ShiftCloseView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    @transaction.atomic
    def post(self, request, pk):
        session = CashSession.objects.select_related("register").filter(pk=pk).first()
        if not session:
            return Response({"detail": "Shift not found"}, status=status.HTTP_404_NOT_FOUND)
        if session.status != "open":
            return Response({"detail": "Shift already closed"}, status=status.HTTP_400_BAD_REQUEST)
        if not _ensure_can_view(session, request.user):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        closeout_data = {
            "counted_cash": request.data.get("counted_cash", "0"),
            "counted_card": request.data.get("counted_card", "0"),
            "counted_transfer": request.data.get("counted_transfer", "0"),
            "counted_tips": request.data.get("counted_tips", "0"),
            "notes": request.data.get("notes", ""),
        }
        serializer = CloseoutCountSerializer(data={"cash_session": session.id, **closeout_data})
        serializer.is_valid(raise_exception=True)
        closeout = serializer.save()

        session.status = "closed"
        session.closed_by = request.user
        session.closed_at = timezone.now()
        session.save(update_fields=["status", "closed_by", "closed_at"])

        summary = calculate_shift_summary(session)
        log_audit(
            request,
            "shift.close",
            "CashSession",
            session.id,
            {
                "register_id": session.register_id,
                "counted_cash": str(closeout.counted_cash),
                "counted_card": str(closeout.counted_card),
                "counted_transfer": str(closeout.counted_transfer),
                "counted_tips": str(closeout.counted_tips),
                "over_short_total": str(summary["over_short_total"]),
            },
        )

        closeout_ticket = render_closeout_ticket(session, summary)
        PrintJob.objects.create(
            type="closeout",
            status="rendered",
            content_text=closeout_ticket["text"],
            content_html=closeout_ticket.get("html", ""),
            meta=closeout_ticket.get("meta", {}),
            requested_by=request.user,
        )

        summary_serializer = CashSessionSummarySerializer(summary)
        return Response(
            {
                "session": CashSessionSerializer(session).data,
                "closeout": CloseoutCountSerializer(closeout).data,
                "summary": summary_serializer.data,
            }
        )


class ShiftSummaryView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, pk):
        session = CashSession.objects.select_related("register").filter(pk=pk).first()
        if not session:
            return Response({"detail": "Shift not found"}, status=status.HTTP_404_NOT_FOUND)
        if not _ensure_can_view(session, request.user):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        summary = calculate_shift_summary(session)
        serializer = CashSessionSummarySerializer(summary)
        return Response(serializer.data)


class ShiftCloseoutPrintJobView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, pk):
        session = CashSession.objects.filter(pk=pk).first()
        if not session:
            return Response({"detail": "Shift not found"}, status=status.HTTP_404_NOT_FOUND)
        if not _ensure_can_view(session, request.user):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        job = PrintJob.objects.filter(type="closeout", meta__cash_session_id=session.id).order_by("-created_at").first()
        if not job:
            return Response({"detail": "Print job not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "id": job.id,
                "status": job.status,
                "content_text": job.content_text,
                "content_html": job.content_html,
                "created_at": job.created_at,
                "printed_at": job.printed_at,
            }
        )
