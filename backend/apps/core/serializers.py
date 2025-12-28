from rest_framework import serializers
from apps.core.models import ServiceType


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ["id", "key", "label", "is_active"]
