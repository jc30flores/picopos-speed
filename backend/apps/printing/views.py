from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.core.permissions import IsAuthenticatedAndActive, IsAdminOrManager
from apps.orders.models import Order
from apps.payments.models import Refund
from apps.printing.models import PrintJob
from apps.printing.serializers import PrintJobSerializer
from apps.printing.services.jobs import create_print_job, create_refund_print_job
from apps.users.models import UserProfile


def _has_role(user, roles):
    if not user.is_authenticated:
        return False
    profile = UserProfile.objects.filter(user=user).first()
    if not profile or not profile.is_active:
        return False
    return profile.role in roles


class PrintJobListCreateView(generics.ListCreateAPIView):
    serializer_class = PrintJobSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        queryset = PrintJob.objects.select_related("order", "requested_by")
        order_id = self.request.query_params.get("order_id")
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset

    def create(self, request, *args, **kwargs):
        order_id = request.data.get("order_id")
        job_type = request.data.get("type")
        if not order_id or not job_type:
            return Response({"detail": "order_id and type are required"}, status=status.HTTP_400_BAD_REQUEST)

        if job_type == "customer":
            allowed = _has_role(request.user, {"cashier", "admin", "manager"})
        elif job_type == "kitchen":
            allowed = _has_role(request.user, {"kitchen", "admin", "manager", "cashier"})
        else:
            allowed = _has_role(request.user, {"admin", "manager"})

        if not allowed:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        order = Order.objects.prefetch_related("items__applied_modifiers").select_related("branch", "service_type").filter(id=order_id).first()
        if not order:
            return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        job = create_print_job(order, job_type, requested_by=request.user)
        serializer = self.get_serializer(job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PrintJobDetailView(generics.RetrieveAPIView):
    queryset = PrintJob.objects.select_related("order", "requested_by")
    serializer_class = PrintJobSerializer
    permission_classes = [IsAuthenticatedAndActive]


class PrintJobMarkPrintedView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request, pk):
        job = PrintJob.objects.filter(pk=pk).first()
        if not job:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        job.status = "printed"
        job.printed_at = timezone.now()
        job.save(update_fields=["status", "printed_at"])
        serializer = PrintJobSerializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RefundPrintJobCreateView(APIView):
    permission_classes = [IsAdminOrManager]

    def post(self, request):
        refund_id = request.data.get("refund_id")
        if not refund_id:
            return Response({"detail": "refund_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        refund = Refund.objects.select_related("order").prefetch_related("order__items__applied_modifiers").filter(id=refund_id).first()
        if not refund:
            return Response({"detail": "Refund not found"}, status=status.HTTP_404_NOT_FOUND)

        job = create_refund_print_job(refund, requested_by=request.user)
        serializer = PrintJobSerializer(job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
