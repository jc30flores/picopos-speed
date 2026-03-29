from rest_framework import serializers

from apps.dte.models import DTERecord, DTEInvalidation, CreditNote
from apps.dte.services.availability import evaluate_record_actions, resolve_issued_at


class DTERecordListSerializer(serializers.ModelSerializer):
    attempts = serializers.IntegerField(read_only=True)
    sale_id = serializers.IntegerField(source="order_id", read_only=True)
    cliente = serializers.CharField(source="receiver_name", read_only=True)
    ultimo_envio = serializers.DateTimeField(source="last_sent_at", read_only=True)
    issued_at = serializers.SerializerMethodField()
    can_resend = serializers.SerializerMethodField()
    can_send_email = serializers.SerializerMethodField()
    missing_email_reason = serializers.SerializerMethodField()
    can_send_whatsapp = serializers.SerializerMethodField()
    missing_phone_reason = serializers.SerializerMethodField()
    can_credit_note = serializers.SerializerMethodField()
    credit_note_reason = serializers.SerializerMethodField()
    has_credit_note = serializers.SerializerMethodField()
    can_invalidate = serializers.SerializerMethodField()
    invalidate_reason = serializers.SerializerMethodField()
    invalidate_deadline = serializers.SerializerMethodField()
    invalidate_remaining = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()

    def _flags(self, obj: DTERecord) -> dict:
        cache = getattr(self, "_flags_cache", None)
        if cache is None:
            cache = {}
            self._flags_cache = cache
        if obj.id not in cache:
            cache[obj.id] = evaluate_record_actions(obj)
        return cache[obj.id]

    def get_issued_at(self, obj: DTERecord):
        return resolve_issued_at(obj)

    def get_can_resend(self, obj: DTERecord):
        return self._flags(obj)["can_resend"]

    def get_can_send_email(self, obj: DTERecord):
        return self._flags(obj)["can_send_email"]

    def get_missing_email_reason(self, obj: DTERecord):
        return self._flags(obj)["missing_email_reason"]

    def get_can_send_whatsapp(self, obj: DTERecord):
        return self._flags(obj)["can_send_whatsapp"]

    def get_missing_phone_reason(self, obj: DTERecord):
        return self._flags(obj)["missing_phone_reason"]

    def get_can_credit_note(self, obj: DTERecord):
        return self._flags(obj)["can_credit_note"]

    def get_credit_note_reason(self, obj: DTERecord):
        return self._flags(obj)["credit_note_reason"]

    def get_has_credit_note(self, obj: DTERecord):
        return self._flags(obj)["has_credit_note"]

    def get_can_invalidate(self, obj: DTERecord):
        return self._flags(obj)["can_invalidate"]

    def get_invalidate_reason(self, obj: DTERecord):
        return self._flags(obj)["invalidate_reason"]

    def get_invalidate_deadline(self, obj: DTERecord):
        return self._flags(obj)["invalidate_deadline"]

    def get_invalidate_remaining(self, obj: DTERecord):
        return self._flags(obj)["invalidate_remaining"]

    def get_customer_email(self, obj: DTERecord):
        return self._flags(obj)["customer_email"]

    def get_customer_phone(self, obj: DTERecord):
        return self._flags(obj)["customer_phone"]

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
            "issued_at",
            "can_resend",
            "can_send_email",
            "missing_email_reason",
            "can_send_whatsapp",
            "missing_phone_reason",
            "can_credit_note",
            "credit_note_reason",
            "has_credit_note",
            "can_invalidate",
            "invalidate_reason",
            "invalidate_deadline",
            "invalidate_remaining",
            "customer_email",
            "customer_phone",
        ]


class DTERecordDetailSerializer(serializers.ModelSerializer):
    sale_id = serializers.IntegerField(source="order_id", read_only=True)
    issued_at = serializers.SerializerMethodField()
    can_resend = serializers.SerializerMethodField()
    can_send_email = serializers.SerializerMethodField()
    missing_email_reason = serializers.SerializerMethodField()
    can_send_whatsapp = serializers.SerializerMethodField()
    missing_phone_reason = serializers.SerializerMethodField()
    can_credit_note = serializers.SerializerMethodField()
    credit_note_reason = serializers.SerializerMethodField()
    can_invalidate = serializers.SerializerMethodField()
    invalidate_reason = serializers.SerializerMethodField()
    invalidate_deadline = serializers.SerializerMethodField()
    invalidate_remaining = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()

    def _flags(self, obj: DTERecord):
        cache = getattr(self, "_flags_cache", None)
        if cache is None:
            cache = {}
            self._flags_cache = cache
        if obj.id not in cache:
            cache[obj.id] = evaluate_record_actions(obj)
        return cache[obj.id]

    def get_issued_at(self, obj: DTERecord):
        return resolve_issued_at(obj)

    def get_can_resend(self, obj: DTERecord):
        return self._flags(obj)["can_resend"]

    def get_can_send_email(self, obj: DTERecord):
        return self._flags(obj)["can_send_email"]

    def get_missing_email_reason(self, obj: DTERecord):
        return self._flags(obj)["missing_email_reason"]

    def get_can_send_whatsapp(self, obj: DTERecord):
        return self._flags(obj)["can_send_whatsapp"]

    def get_missing_phone_reason(self, obj: DTERecord):
        return self._flags(obj)["missing_phone_reason"]

    def get_can_credit_note(self, obj: DTERecord):
        return self._flags(obj)["can_credit_note"]

    def get_credit_note_reason(self, obj: DTERecord):
        return self._flags(obj)["credit_note_reason"]

    def get_can_invalidate(self, obj: DTERecord):
        return self._flags(obj)["can_invalidate"]

    def get_invalidate_reason(self, obj: DTERecord):
        return self._flags(obj)["invalidate_reason"]

    def get_invalidate_deadline(self, obj: DTERecord):
        return self._flags(obj)["invalidate_deadline"]

    def get_invalidate_remaining(self, obj: DTERecord):
        return self._flags(obj)["invalidate_remaining"]

    def get_customer_email(self, obj: DTERecord):
        return self._flags(obj)["customer_email"]

    def get_customer_phone(self, obj: DTERecord):
        return self._flags(obj)["customer_phone"]

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
