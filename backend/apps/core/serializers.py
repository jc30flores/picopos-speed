from rest_framework import serializers
from apps.core.models import FeatureFlag, ServiceType, TaxConfig


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ["id", "key", "label", "is_active"]


class TaxConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxConfig
        fields = ["id", "name", "rate", "tax_included", "is_active"]


class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = ["id", "key", "label", "description", "is_enabled"]


from apps.core.models import Branch


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "code", "is_active"]
