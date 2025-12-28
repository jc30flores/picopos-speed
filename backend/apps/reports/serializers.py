from rest_framework import serializers
from apps.reports.models import SaleSnapshot


class SaleSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleSnapshot
        fields = [
            "id",
            "order_number",
            "service_type_id",
            "channel",
            "payment_method",
            "items",
            "subtotal",
            "tax",
            "total",
            "cashier_name",
            "status",
            "created_at",
        ]
