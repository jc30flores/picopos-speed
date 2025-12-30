from rest_framework import serializers
from apps.printing.models import PrintJob


class PrintJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrintJob
        fields = [
            "id",
            "order",
            "type",
            "status",
            "content_text",
            "content_html",
            "content_pdf_path",
            "requested_by",
            "printed_at",
            "created_at",
            "error_message",
            "meta",
        ]
        read_only_fields = [
            "status",
            "content_text",
            "content_html",
            "content_pdf_path",
            "requested_by",
            "printed_at",
            "created_at",
            "error_message",
            "meta",
        ]
