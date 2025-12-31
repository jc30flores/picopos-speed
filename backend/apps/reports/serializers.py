from rest_framework import serializers


class SalesReportSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    order_number = serializers.IntegerField()
    service_type = serializers.CharField()
    date = serializers.DateTimeField()
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax = serializers.DecimalField(max_digits=10, decimal_places=2)
    total = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.CharField()
    financial_status = serializers.CharField()
    refund_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    net_paid = serializers.DecimalField(max_digits=10, decimal_places=2)
