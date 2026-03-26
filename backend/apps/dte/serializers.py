from rest_framework import serializers

from apps.dte.models import DTERecord, DTEInvalidation, CreditNote


class DTERecordListSerializer(serializers.ModelSerializer):
    attempts = serializers.IntegerField(read_only=True)
    sale_id = serializers.IntegerField(source="order_id", read_only=True)
    cliente = serializers.CharField(source="receiver_name", read_only=True)
    ultimo_envio = serializers.DateTimeField(source="last_sent_at", read_only=True)

    class Meta:
        model = DTERecord
        fields = [
            "id",
            "sale_id",
            "dte_type",
            "status",
            "control_number",
            "codigo_generacion",
            "generation_code",
            "receiver_name",
            "cliente",
            "total_amount",
            "hacienda_uuid",
            "sello_recepcion",
            "sello_recibido",
            "estado_mh",
            "hacienda_state",
            "recibido_at",
            "attempts",
            "error_message",
            "last_sent_at",
            "ultimo_envio",
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
