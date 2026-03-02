from django.conf import settings
from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import generics, status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.audit import log_audit
from apps.core.permissions import _get_profile
from apps.dte.models import CreditNote, DTEInvalidation, DTERecord
from apps.dte.serializers import (
    CreditNoteSerializer,
    DTEInvalidationSerializer,
    DTERecordDetailSerializer,
    DTERecordListSerializer,
)
from apps.dte.services import transmit_sale_dte
from apps.dte.services.dte_retry import resend_record
from apps.dte.services.dte_security import redact_payload


class IsDTECashierOrAbove(BasePermission):
    def has_permission(self, request, view):
        profile = _get_profile(request.user)
        return bool(profile and profile.is_active and profile.role in {"cashier", "manager", "admin", "accountant"})


class IsDTEAccountantOrAdmin(BasePermission):
    def has_permission(self, request, view):
        profile = _get_profile(request.user)
        return bool(profile and profile.is_active and profile.role in {"manager", "admin", "accountant"})


class DTEIssuedListView(generics.ListAPIView):
    serializer_class = DTERecordListSerializer
    permission_classes = [IsDTECashierOrAbove]

    def get_queryset(self):
        qs = DTERecord.objects.select_related("order", "branch")
        status_filter = self.request.query_params.get("status")
        dte_type = self.request.query_params.get("dte_type")
        date_from = parse_date(self.request.query_params.get("date_from", ""))
        date_to = parse_date(self.request.query_params.get("date_to", ""))
        query = self.request.query_params.get("q")

        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        if dte_type:
            qs = qs.filter(dte_type=dte_type.upper())
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        if query:
            qs = qs.filter(
                Q(receiver_name__icontains=query)
                | Q(control_number__icontains=query)
                | Q(codigo_generacion__icontains=query)
                | Q(hacienda_uuid__icontains=query)
            )
        return qs


class DTEIssuedDetailView(generics.RetrieveAPIView):
    queryset = DTERecord.objects.select_related("order", "branch")
    serializer_class = DTERecordDetailSerializer
    permission_classes = [IsDTECashierOrAbove]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        data = self.get_serializer(instance).data
        profile = _get_profile(request.user)
        can_view_json = bool(profile and profile.role in {"manager", "admin", "accountant"})
        if not can_view_json:
            data.pop("request_payload", None)
            data.pop("response_payload", None)
        elif not settings.DEBUG:
            data["request_payload"] = redact_payload(data.get("request_payload") or {})
            data["response_payload"] = redact_payload(data.get("response_payload") or {})
        return Response(data)


class DTEResendView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, pk: int):
        record = generics.get_object_or_404(DTERecord, pk=pk)
        if record.status not in {DTERecord.STATUS_PENDING, DTERecord.STATUS_REJECTED}:
            return Response({"detail": "Solo se puede reenviar pendiente/rechazado"}, status=status.HTTP_400_BAD_REQUEST)
        # re-orchestrate safely (same control/code via invoice)
        updated = transmit_sale_dte(record.order_id, source="manual_resend", force=True)
        log_audit(request, "dte.resend", "DTERecord", updated.id, {"sale_id": updated.order_id, "status": updated.status})
        return Response(DTERecordDetailSerializer(updated).data)


class DTESendEmailView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, pk: int):
        _record = generics.get_object_or_404(DTERecord, pk=pk)
        return Response({"detail": "Integración de correo no implementada"}, status=status.HTTP_501_NOT_IMPLEMENTED)


class DTESendWhatsAppView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, pk: int):
        _record = generics.get_object_or_404(DTERecord, pk=pk)
        return Response({"detail": "Integración de WhatsApp no implementada"}, status=status.HTTP_501_NOT_IMPLEMENTED)


class DTEInvalidateView(APIView):
    permission_classes = [IsDTEAccountantOrAdmin]

    def post(self, request, pk: int):
        record = generics.get_object_or_404(DTERecord, pk=pk)
        if record.status != DTERecord.STATUS_ACCEPTED:
            return Response({"detail": "Solo DTE aceptado puede invalidarse"}, status=status.HTTP_400_BAD_REQUEST)
        invalidation = DTEInvalidation.objects.create(
            order=record.order,
            dte_record=record,
            motivo=request.data.get("motivo", ""),
            tipo_anulacion=request.data.get("tipo_anulacion", "total"),
            status=DTERecord.STATUS_PENDING,
        )
        record.status = DTERecord.STATUS_INVALIDATED
        record.save(update_fields=["status", "updated_at"])
        log_audit(request, "dte.invalidate", "DTEInvalidation", invalidation.id, {"dte_record_id": record.id})
        return Response(DTEInvalidationSerializer(invalidation).data, status=status.HTTP_201_CREATED)


class DTECreditNoteView(APIView):
    permission_classes = [IsDTEAccountantOrAdmin]

    def post(self, request, pk: int):
        record = generics.get_object_or_404(DTERecord, pk=pk)
        if record.status != DTERecord.STATUS_ACCEPTED:
            return Response({"detail": "Solo DTE aceptado puede generar NC"}, status=status.HTTP_400_BAD_REQUEST)
        note = CreditNote.objects.create(
            order=record.order,
            motivo=request.data.get("motivo", ""),
            total=record.total_amount,
            dte_numero_control=record.control_number,
            dte_codigo_generacion=record.codigo_generacion,
            status=DTERecord.STATUS_PENDING,
        )
        log_audit(request, "dte.credit_note", "CreditNote", note.id, {"dte_record_id": record.id})
        return Response(CreditNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class DTEInvalidatePreviewView(APIView):
    permission_classes = [IsDTEAccountantOrAdmin]

    def post(self, request):
        sale_id = request.query_params.get("sale_id") or request.data.get("sale_id")
        record = DTERecord.objects.filter(order_id=sale_id, status=DTERecord.STATUS_ACCEPTED).order_by("-id").first()
        if not record:
            return Response({"detail": "No existe DTE aceptado"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"sale_id": record.order_id, "control_number": record.control_number, "codigo_generacion": record.codigo_generacion})


class DTECreditNotePreviewView(APIView):
    permission_classes = [IsDTEAccountantOrAdmin]

    def get(self, request):
        sale_id = request.query_params.get("sale_id")
        record = DTERecord.objects.filter(order_id=sale_id, status=DTERecord.STATUS_ACCEPTED).order_by("-id").first()
        if not record:
            return Response({"detail": "No existe DTE aceptado"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"sale_id": record.order_id, "total": record.total_amount, "related_control_number": record.control_number})
