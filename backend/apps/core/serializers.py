from rest_framework import serializers
from apps.core.models import ServiceType, TaxConfig


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ["id", "key", "label", "is_active"]


class TaxConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxConfig
        fields = ["id", "name", "rate", "is_active"]
