from rest_framework import serializers
import re

from apps.core.models import ActivityCatalog, Customer, FeatureFlag, GeoDepartment, GeoMunicipality, ServiceType, TaxConfig


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ["id", "key", "label", "is_active", "sort_order"]

    def validate_key(self, value: str) -> str:
        normalized = re.sub(r"[^A-Z0-9_]+", "_", (value or "").upper()).strip("_")
        if not normalized:
            raise serializers.ValidationError("Código inválido.")
        return normalized

    def validate_label(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Nombre requerido.")
        return cleaned


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


class ClientSerializer(serializers.ModelSerializer):
    is_deleted = serializers.BooleanField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id",
            "full_name",
            "company_name",
            "client_type",
            "dui",
            "nit",
            "nrc",
            "phone",
            "email",
            "direccion",
            "department_code",
            "municipality_code",
            "activity_code",
            "activity_description",
            "is_deleted",
            "is_consumer_final",
            "created_at",
            "updated_at",
        ]

    phone = serializers.CharField(source="telefono", required=False, allow_blank=True)
    email = serializers.EmailField(source="correo", required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        data = {**{k: getattr(self.instance, k, None) for k in ["client_type", "dui", "nit", "nrc", "full_name", "direccion", "department_code", "municipality_code", "activity_code", "activity_description", "is_consumer_final"] if self.instance}, **attrs}
        ctype = (data.get("client_type") or "CF").upper()

        dui = re.sub(r"[^0-9]", "", data.get("dui") or "")
        if data.get("dui"):
            if len(dui) != 9:
                raise serializers.ValidationError({"dui": "DUI inválido (formato 00000000-0)."})
            data["dui"] = f"{dui[:8]}-{dui[8]}"

        nit_digits = re.sub(r"[^0-9]", "", data.get("nit") or "")
        if ctype == "CCF":
            required = {
                "full_name": data.get("full_name"),
                "nit": nit_digits,
                "nrc": re.sub(r"[^0-9]", "", data.get("nrc") or ""),
                "department_code": data.get("department_code"),
                "municipality_code": data.get("municipality_code"),
                "direccion": data.get("direccion"),
            }
            missing = {k: "Este campo es requerido para CCF." for k, v in required.items() if not v}
            if not (data.get("activity_code") or data.get("activity_description")):
                missing["activity_code"] = "activity_code o activity_description es requerido para CCF."
            if missing:
                raise serializers.ValidationError(missing)
            if len(nit_digits) != 14:
                raise serializers.ValidationError({"nit": "NIT debe tener 14 dígitos."})
            data["nit"] = nit_digits
            data["nrc"] = re.sub(r"[^0-9]", "", data.get("nrc") or "")

        if ctype == "SX":
            required = {
                "dui": data.get("dui"),
                "direccion": data.get("direccion"),
                "department_code": data.get("department_code"),
                "municipality_code": data.get("municipality_code"),
            }
            missing = {k: "Este campo es requerido para SX." for k, v in required.items() if not v}
            if missing:
                raise serializers.ValidationError(missing)

        if ctype == "CF" and not data.get("full_name"):
            data["full_name"] = "CONSUMIDOR FINAL"

        attrs.update(data)
        return attrs


class GeoDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoDepartment
        fields = ["code", "name"]


class GeoMunicipalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoMunicipality
        fields = ["code", "department_code", "name"]


class ActivityCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityCatalog
        fields = ["code", "description"]
