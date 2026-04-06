import logging
from django.db.models import Sum

from django.conf import settings
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
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
from apps.dte.services.availability import evaluate_record_actions

logger = logging.getLogger("apps.dte")


class IsDTECashierOrAbove(BasePermission):
    def has_permission(self, request, view):
        profile = _get_profile(request.user)
        return bool(profile and profile.is_active and profile.role in {"admin"})


class IsDTEAccountantOrAdmin(BasePermission):
    def has_permission(self, request, view):
        profile = _get_profile(request.user)
        return bool(profile and profile.is_active and profile.role in {"admin"})


class DTEIssuedListView(generics.ListAPIView):
    serializer_class = DTERecordListSerializer
    permission_classes = [IsDTECashierOrAbove]
    pagination_class = None

    def get_queryset(self):
        qs = DTERecord.objects.select_related("order", "branch", "order__customer").prefetch_related("credit_notes")
        status_filter = self.request.query_params.get("status")
        dte_type = self.request.query_params.get("dte_type") or self.request.query_params.get("type")
        start_at, end_at = parse_business_date_range(
            self.request.query_params.get("date_from"),
            self.request.query_params.get("date_to"),
        )
        query = self.request.query_params.get("q") or self.request.query_params.get("search")

        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        if dte_type:
            normalized = dte_type.upper()
            if normalized in {"CF", "CCF", "SX", "SE"}:
                prefix = {"CF": "CF", "CCF": "CCF", "SX": "SE", "SE": "SE"}[normalized]
                qs = qs.filter(dte_type__startswith=prefix)
            else:
                qs = qs.filter(dte_type=normalized)
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
        return qs.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        count = queryset.count()
        total_amount_sum = queryset.aggregate(total=Sum("total_amount")).get("total") or 0
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = max(1, min(100, int(request.query_params.get("page_size", 20))))
        except (TypeError, ValueError):
            page_size = 20
        start = (page - 1) * page_size
        end = start + page_size
        page_qs = queryset[start:end]
        serializer = self.get_serializer(page_qs, many=True)
        return Response(
            {
                "count": count,
                "page": page,
                "page_size": page_size,
                "results": serializer.data,
                "total_amount_sum": str(total_amount_sum),
            }
        )


class DTEIssuedDetailView(generics.RetrieveAPIView):
    queryset = DTERecord.objects.select_related("order", "branch", "order__customer").prefetch_related("credit_notes")
    serializer_class = DTERecordDetailSerializer
    permission_classes = [IsDTECashierOrAbove]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        data = self.get_serializer(instance).data
        if not settings.DEBUG:
            data["request_payload"] = redact_payload(data.get("request_payload") or {})
            data["response_payload"] = redact_payload(data.get("response_payload") or {})
        return Response(data)


class DTEResendView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, pk: int):
        logger.info(
            "[DTE RESEND] user=%s auth=%s perms=%s is_authenticated=%s",
            getattr(request.user, "username", "anonymous"),
            [a.__name__ for a in self.authentication_classes],
            [p.__name__ for p in self.permission_classes],
            bool(getattr(request.user, "is_authenticated", False)),
        )
        record = generics.get_object_or_404(DTERecord, pk=pk)
        if record.status != DTERecord.STATUS_PENDING:
            return Response({"detail": "Solo se puede reenviar pendiente"}, status=status.HTTP_400_BAD_REQUEST)
        if record.status == DTERecord.STATUS_SENDING:
            return Response({"detail": "El DTE está en proceso de envío"}, status=status.HTTP_409_CONFLICT)
        try:
            updated = resend_record(record)
        except PermissionDenied as exc:
            return Response({"success": False, "message": str(exc), "detail": "permission_denied"}, status=status.HTTP_403_FORBIDDEN)
        log_audit(request, "dte.resend", "DTERecord", updated.id, {"sale_id": updated.order_id, "status": updated.status})
        payload = DTERecordDetailSerializer(updated).data
        response_payload = {
            "success": True,
            "issued_id": updated.id,
            "dte_record_id": updated.id,
            "status": updated.status,
            "http_status": payload.get("response_payload", {}).get("http_status") or 0,
            "message": "Reenvío procesado",
            "body_preview": (updated.response_text or "")[:400],
            "sello_recibido": updated.sello_recibido or updated.sello_recepcion or "",
            "firma": updated.firma or "",
            "recibido_at": updated.recibido_at,
            "record": payload,
        }
        return Response(response_payload, status=status.HTTP_200_OK)


class DTESendEmailView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, pk: int):
        record = generics.get_object_or_404(DTERecord.objects.select_related("order", "order__customer"), pk=pk)
        flags = evaluate_record_actions(record)
        if not flags["can_send_email"]:
            return Response({"success": False, "message": flags["missing_email_reason"], "detail": "missing_email"}, status=status.HTTP_400_BAD_REQUEST)
        to_email = request.data.get("email") or flags["customer_email"]
        attempt = send_dte_email(record, to_email=to_email)
        log_audit(request, "dte.send_email", "DTERecord", record.id, {"status": attempt.status, "provider_status": attempt.provider_status})
        logger.info("[DTE EMAIL] dte_id=%s status=%s provider_status=%s", record.id, attempt.status, attempt.provider_status)
        return Response(
            {
                "success": attempt.status == "SENT",
                "message": "Correo enviado" if attempt.status == "SENT" else "No se pudo enviar correo",
                "status": attempt.status,
                "provider_status": attempt.provider_status,
                "retries": attempt.retries,
                "body_preview": str(attempt.provider_body)[:400],
                "record": DTERecordDetailSerializer(record).data,
            }
        )


def _normalize_channels(raw_channels) -> list[str]:
    if not isinstance(raw_channels, list):
        return []
    out: list[str] = []
    for channel in raw_channels:
        normalized = str(channel or "").strip().lower()
        if normalized in {"whatsapp", "email"} and normalized not in out:
            out.append(normalized)
    return out


def _deliver_record(record: DTERecord, *, request, channels: list[str], to_email: str | None, to_phone: str | None) -> dict:
    results: dict[str, dict] = {}
    for channel in channels:
        if channel == "email":
            flags = evaluate_record_actions(record)
            if not flags["can_send_email"]:
                results["email"] = {"success": False, "status": "FAILED", "message": flags["missing_email_reason"], "detail": "missing_email"}
                continue
            attempt = send_dte_email(record, to_email=to_email or flags["customer_email"])
            log_audit(request, "dte.send_email", "DTERecord", record.id, {"status": attempt.status, "provider_status": attempt.provider_status})
            results["email"] = {
                "success": attempt.status == "SENT",
                "status": attempt.status,
                "provider_status": attempt.provider_status,
                "retries": attempt.retries,
                "message": "Correo enviado" if attempt.status == "SENT" else "No se pudo enviar correo",
            }
        if channel == "whatsapp":
            flags = evaluate_record_actions(record)
            if not flags["can_send_whatsapp"]:
                results["whatsapp"] = {"success": False, "status": "FAILED", "message": flags["missing_phone_reason"], "detail": "missing_phone"}
                continue
            attempt = send_dte_whatsapp(record, to_phone=to_phone or flags["customer_phone"])
            log_audit(request, "dte.send_whatsapp", "DTERecord", record.id, {"status": attempt.status, "provider_status": attempt.provider_status})
            results["whatsapp"] = {
                "success": attempt.status == "SENT",
                "status": attempt.status,
                "provider_status": attempt.provider_status,
                "retries": attempt.retries,
                "message": "WhatsApp enviado" if attempt.status == "SENT" else "No se pudo enviar WhatsApp",
            }
    return results


class DTEBulkDeliveryView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, pk: int):
        record = generics.get_object_or_404(DTERecord.objects.select_related("order", "order__customer"), pk=pk)
        channels = _normalize_channels(request.data.get("channels"))
        if not channels:
            return Response({"detail": "Debe enviar channels con al menos uno: whatsapp, email"}, status=status.HTTP_400_BAD_REQUEST)
        results = _deliver_record(
            record,
            request=request,
            channels=channels,
            to_email=request.data.get("email"),
            to_phone=request.data.get("phone"),
        )
        success = all(bool(result.get("success")) for result in results.values()) if results else False
        return Response(
            {
                "success": success,
                "message": "Envío completado" if success else "Uno o más envíos fallaron",
                "channels": results,
                "record": DTERecordDetailSerializer(record).data,
            }
        )


class DTEOrderBulkDeliveryView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, order_id: int):
        record = DTERecord.objects.select_related("order", "order__customer").filter(order_id=order_id).order_by("-id").first()
        if not record:
            return Response({"detail": "No existe DTE para esta venta"}, status=status.HTTP_404_NOT_FOUND)
        channels = _normalize_channels(request.data.get("channels"))
        if not channels:
            return Response({"detail": "Debe enviar channels con al menos uno: whatsapp, email"}, status=status.HTTP_400_BAD_REQUEST)
        results = _deliver_record(
            record,
            request=request,
            channels=channels,
            to_email=request.data.get("email"),
            to_phone=request.data.get("phone"),
        )
        success = all(bool(result.get("success")) for result in results.values()) if results else False
        return Response(
            {
                "success": success,
                "message": "Envío completado" if success else "Uno o más envíos fallaron",
                "channels": results,
                "record": DTERecordDetailSerializer(record).data,
            }
        )


class DTESendWhatsAppView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, pk: int):
        record = generics.get_object_or_404(DTERecord.objects.select_related("order", "order__customer"), pk=pk)
        flags = evaluate_record_actions(record)
        if not flags["can_send_whatsapp"]:
            return Response({"success": False, "message": flags["missing_phone_reason"], "detail": "missing_phone"}, status=status.HTTP_400_BAD_REQUEST)
        to_phone = request.data.get("phone") or flags["customer_phone"]
        attempt = send_dte_whatsapp(record, to_phone=to_phone)
        log_audit(request, "dte.send_whatsapp", "DTERecord", record.id, {"status": attempt.status, "provider_status": attempt.provider_status})
        logger.info("[DTE WA] dte_id=%s status=%s provider_status=%s", record.id, attempt.status, attempt.provider_status)
        return Response(
            {
                "success": attempt.status == "SENT",
                "message": "WhatsApp enviado" if attempt.status == "SENT" else "No se pudo enviar WhatsApp",
                "status": attempt.status,
                "provider_status": attempt.provider_status,
                "retries": attempt.retries,
                "body_preview": str(attempt.provider_body)[:400],
                "record": DTERecordDetailSerializer(record).data,
            }
        )


class DTEInvalidateView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, pk: int):
        record = generics.get_object_or_404(DTERecord, pk=pk)
        flags = evaluate_record_actions(record)
        if not flags["can_invalidate"]:
            return Response({"detail": flags["invalidate_reason"] or "No se puede invalidar"}, status=status.HTTP_400_BAD_REQUEST)
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
        data["success"] = bool(result.get("success"))
        data["message"] = "DTE invalidado" if result.get("success") else (result.get("error") or "No se pudo invalidar")
        data["record"] = DTERecordDetailSerializer(record).data
        return Response(data, status=status.HTTP_201_CREATED)


class DTECreditNoteView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, pk: int):
        record = generics.get_object_or_404(DTERecord.objects.prefetch_related("credit_notes"), pk=pk)
        flags = evaluate_record_actions(record)
        if not flags["can_credit_note"]:
            return Response({"detail": flags["credit_note_reason"] or "No se puede emitir NC"}, status=status.HTTP_400_BAD_REQUEST)
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
        payload = CreditNoteSerializer(note).data
        payload["success"] = True
        payload["message"] = "Nota de crédito creada"
        payload["record"] = DTERecordDetailSerializer(record).data
        return Response(payload, status=status.HTTP_201_CREATED)


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
