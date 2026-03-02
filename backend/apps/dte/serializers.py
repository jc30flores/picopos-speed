from rest_framework import serializers

from apps.dte.models import DTERecord, DTEInvalidation, CreditNote


class DTERecordListSerializer(serializers.ModelSerializer):
    attempts = serializers.IntegerField(source="send_attempts", read_only=True)
    sale_id = serializers.IntegerField(source="order_id", read_only=True)

    class Meta:
        model = DTERecord
        fields = [
            "id",
            "sale_id",
            "dte_type",
            "status",
            "control_number",
            "codigo_generacion",
            "receiver_name",
            "total_amount",
            "hacienda_uuid",
            "sello_recepcion",
            "attempts",
            "error_message",
            "last_sent_at",
            "created_at",
        ]


class DTERecordDetailSerializer(serializers.ModelSerializer):
    sale_id = serializers.IntegerField(source="order_id", read_only=True)

    class Meta:
        model = DTERecord
        fields = "__all__"


class DTEInvalidationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DTEInvalidation
        fields = "__all__"


class CreditNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditNote
        fields = "__all__"
