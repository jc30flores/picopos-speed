from rest_framework import serializers


class SalesReportSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    order_id = serializers.IntegerField()
    order_number = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    customer_name = serializers.CharField(required=False, allow_blank=True)
    service_type_code = serializers.CharField()
    service_type_label = serializers.CharField()
    payment_method_code = serializers.CharField()
    payment_method_label = serializers.CharField()
    total_amount = serializers.CharField()
    status = serializers.CharField()
    financial_status = serializers.CharField()
    control_number = serializers.CharField(required=False, allow_blank=True)
