from django.conf import settings
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.audit import log_audit
from apps.core.permissions import _get_profile
from apps.core.timezone_utils import parse_business_date_range
from apps.dte.models import CreditNote, DTEInvalidation, DTERecord
from apps.dte.serializers import (
    CreditNoteSerializer,
    DTEInvalidationSerializer,
    DTERecordDetailSerializer,
    DTERecordListSerializer,
)
from apps.dte.services.dte_retry import resend_record
from apps.dte.services.dte_service import invalidate_dte_for_order, send_dte_for_credit_note
from apps.dte.services.email_dte_service import send_dte_email
from apps.dte.services.whatsapp_dte_service import send_dte_whatsapp
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
        start_at, end_at = parse_business_date_range(
            self.request.query_params.get("date_from"),
            self.request.query_params.get("date_to"),
        )
        query = self.request.query_params.get("q")

        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        if dte_type:
            qs = qs.filter(dte_type=dte_type.upper())
        if start_at:
            qs = qs.filter(created_at__gte=start_at)
        if end_at:
            qs = qs.filter(created_at__lte=end_at)
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
        if record.status == DTERecord.STATUS_SENDING:
            return Response({"detail": "El DTE está en proceso de envío"}, status=status.HTTP_409_CONFLICT)
        updated = resend_record(record)
        log_audit(request, "dte.resend", "DTERecord", updated.id, {"sale_id": updated.order_id, "status": updated.status})
        return Response(DTERecordDetailSerializer(updated).data)


class DTESendEmailView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, pk: int):
        record = generics.get_object_or_404(DTERecord, pk=pk)
        attempt = send_dte_email(record, to_email=request.data.get("email"))
        return Response({"status": attempt.status, "provider_status": attempt.provider_status, "retries": attempt.retries})


class DTESendWhatsAppView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, pk: int):
        record = generics.get_object_or_404(DTERecord, pk=pk)
        attempt = send_dte_whatsapp(record, to_phone=request.data.get("phone"))
        return Response({"status": attempt.status, "provider_status": attempt.provider_status, "retries": attempt.retries})


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
        result = invalidate_dte_for_order(
            record.order,
            motivo=request.data.get("motivo", ""),
            responsable_dui=request.data.get("responsable_dui", ""),
            solicitante_dui=request.data.get("solicitante_dui", ""),
        )
        if result.get("success"):
            record.status = DTERecord.STATUS_INVALIDATED
            record.save(update_fields=["status", "updated_at"])
        log_audit(request, "dte.invalidate", "DTEInvalidation", invalidation.id, {"dte_record_id": record.id})
        data = DTEInvalidationSerializer(invalidation).data
        data["attempt"] = result
        return Response(data, status=status.HTTP_201_CREATED)


class DTECreditNoteView(APIView):
    permission_classes = [IsDTEAccountantOrAdmin]

    def post(self, request, pk: int):
        record = generics.get_object_or_404(DTERecord, pk=pk)
        if record.status != DTERecord.STATUS_ACCEPTED:
            return Response({"detail": "Solo DTE aceptado puede generar NC"}, status=status.HTTP_400_BAD_REQUEST)
        note = CreditNote.objects.create(
            order=record.order,
            original_dte_record=record,
            motivo=request.data.get("motivo", ""),
            total=record.total_amount,
            dte_numero_control=record.control_number,
            dte_codigo_generacion=record.codigo_generacion,
            items=request.data.get("items", []),
            status=DTERecord.STATUS_PENDING,
        )
        send_dte_for_credit_note(note)
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


class OrderCreditNoteView(APIView):
    permission_classes = [IsDTEAccountantOrAdmin]

    def post(self, request, pk: int):
        record = DTERecord.objects.filter(order_id=pk, status=DTERecord.STATUS_ACCEPTED).order_by("-id").first()
        if not record:
            return Response({"detail": "No existe DTE aceptado"}, status=status.HTTP_404_NOT_FOUND)
        note = CreditNote.objects.create(
            order=record.order,
            original_dte_record=record,
            motivo=request.data.get("motivo", ""),
            total=record.total_amount,
            dte_numero_control=record.control_number,
            dte_codigo_generacion=record.codigo_generacion,
            items=request.data.get("items", []),
            status=DTERecord.STATUS_PENDING,
        )
        send_dte_for_credit_note(note)
        return Response(CreditNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class OrderCreditNotePreviewView(APIView):
    permission_classes = [IsDTEAccountantOrAdmin]

    def get(self, request, pk: int):
        record = DTERecord.objects.filter(order_id=pk, status=DTERecord.STATUS_ACCEPTED).order_by("-id").first()
        if not record:
            return Response({"detail": "No existe DTE aceptado"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"order_id": pk, "total": record.total_amount, "related_control_number": record.control_number})
