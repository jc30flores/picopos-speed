from rest_framework import serializers
from apps.core.models import Customer, FeatureFlag, ServiceType, TaxConfig


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


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id", "name", "tipo_documento", "num_documento", "nrc", "cod_actividad",
            "desc_actividad", "direccion_departamento", "direccion_municipio",
            "direccion_complemento", "telefono", "correo", "is_default_consumer_final",
            "created_at", "updated_at",
        ]
