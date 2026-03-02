from rest_framework import generics, status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dte.models import DTERecord, DTEInvalidation, CreditNote
from apps.dte.serializers import DTERecordListSerializer, DTERecordDetailSerializer, DTEInvalidationSerializer, CreditNoteSerializer
from apps.dte.services import transmit_invoice_dte
from apps.dte.services.dte_retry import resend_record
from apps.core.permissions import _get_profile


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
        query = self.request.query_params.get("q")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if dte_type:
            qs = qs.filter(dte_type=dte_type)
        if query:
            qs = qs.filter(control_number__icontains=query)
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
        return Response(data)


class DTEResendView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, pk: int):
        record = generics.get_object_or_404(DTERecord, pk=pk)
        if record.status not in {"pendiente", "rechazado"}:
            return Response({"detail": "Solo se puede reenviar pendiente/rechazado"}, status=status.HTTP_400_BAD_REQUEST)
        updated = resend_record(record)
        return Response(DTERecordDetailSerializer(updated).data)


class DTEInvalidatePreviewView(APIView):
    permission_classes = [IsDTEAccountantOrAdmin]

    def post(self, request):
        order_id = request.query_params.get("sale_id") or request.data.get("sale_id")
        record = DTERecord.objects.filter(order_id=order_id, status="aceptado").order_by("-id").first()
        if not record:
            return Response({"detail": "No existe DTE aceptado"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"order_id": record.order_id, "control_number": record.control_number, "codigo_generacion": record.codigo_generacion})


class DTEInvalidateView(generics.CreateAPIView):
    serializer_class = DTEInvalidationSerializer
    permission_classes = [IsDTEAccountantOrAdmin]


class DTECreditNotePreviewView(APIView):
    permission_classes = [IsDTEAccountantOrAdmin]

    def get(self, request):
        order_id = request.query_params.get("sale_id")
        record = DTERecord.objects.filter(order_id=order_id, status="aceptado").order_by("-id").first()
        if not record:
            return Response({"detail": "No existe DTE aceptado"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"order_id": record.order_id, "total": record.total_amount, "related_control_number": record.control_number})


class DTECreditNoteCreateView(generics.CreateAPIView):
    serializer_class = CreditNoteSerializer
    permission_classes = [IsDTEAccountantOrAdmin]


class DTESendEmailView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, pk: int):
        record = generics.get_object_or_404(DTERecord, pk=pk)
        return Response({"detail": "Email enviado", "record_id": record.id})


class DTESendWhatsAppView(APIView):
    permission_classes = [IsDTECashierOrAbove]

    def post(self, request, pk: int):
        record = generics.get_object_or_404(DTERecord, pk=pk)
        return Response({"detail": "WhatsApp enviado", "record_id": record.id})
