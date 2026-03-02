from rest_framework import serializers

from apps.dte.models import DTERecord, DTEInvalidation, CreditNote


class DTERecordListSerializer(serializers.ModelSerializer):
    class Meta:
        model = DTERecord
        fields = [
            "id",
            "order_id",
            "dte_type",
            "status",
            "control_number",
            "codigo_generacion",
            "receiver_name",
            "total_amount",
            "hacienda_uuid",
            "sello_recepcion",
            "attempt_number",
            "updated_at",
            "created_at",
        ]


class DTERecordDetailSerializer(serializers.ModelSerializer):
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
