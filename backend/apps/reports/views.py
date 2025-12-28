from django.utils.dateparse import parse_date
from rest_framework import generics
from rest_framework.response import Response
from apps.orders.models import Order
from apps.reports.serializers import SalesReportSerializer


class SalesReportListView(generics.ListAPIView):
    serializer_class = SalesReportSerializer

    def get_queryset(self):
        queryset = Order.objects.select_related("service_type").all()
        date_from = parse_date(self.request.query_params.get("date_from") or "")
        date_to = parse_date(self.request.query_params.get("date_to") or "")
        service_type = self.request.query_params.get("service_type")
        status = self.request.query_params.get("status")

        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        if service_type:
            queryset = queryset.filter(service_type__key=service_type)
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = [
            {
                "order_id": order.id,
                "order_number": order.order_number,
                "service_type": order.service_type.key,
                "date": order.created_at,
                "subtotal": order.subtotal,
                "tax": order.tax,
                "total": order.total,
                "status": order.status,
            }
            for order in queryset
        ]
        serializer = self.get_serializer(data, many=True)
        return Response(serializer.data)
