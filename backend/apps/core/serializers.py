from django.db import transaction
from django.db.models.expressions import RawSQL
from rest_framework import serializers
import re

from apps.core.models import ActivityCatalog, Customer, FeatureFlag, GeoDepartment, GeoMunicipality, ServiceType, TaxConfig
from apps.menu.models import Product


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ["id", "key", "label", "is_active", "sort_order", "disposables_enabled"]

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

    @transaction.atomic
    def update(self, instance: ServiceType, validated_data):
        previous_disposables_enabled = bool(instance.disposables_enabled)
        updated = super().update(instance, validated_data)
        current_disposables_enabled = bool(updated.disposables_enabled)
        service_type_key = (updated.key or "").strip()

        if not service_type_key or previous_disposables_enabled == current_disposables_enabled:
            return updated

        if current_disposables_enabled:
            Product.objects.exclude(disposable_apply_to__contains=[service_type_key]).update(
                disposable_apply_to=RawSQL(
                    "COALESCE(disposable_apply_to, '[]'::jsonb) || to_jsonb(ARRAY[%s]::text[])",
                    [service_type_key],
                )
            )
        else:
            Product.objects.filter(disposable_apply_to__contains=[service_type_key]).update(
                disposable_apply_to=RawSQL(
                    """
                    COALESCE(
                        (
                            SELECT jsonb_agg(entry)
                            FROM jsonb_array_elements_text(COALESCE(disposable_apply_to, '[]'::jsonb)) AS entry
                            WHERE entry <> %s
                        ),
                        '[]'::jsonb
                    )
                    """,
                    [service_type_key],
                )
            )

        return updated


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
    DEFAULT_EMAIL = "facturasPDG23@gmail.com"
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

    def _default_email_if_empty(self, value: str | None) -> str:
        email = (value or "").strip()
        return email or self.DEFAULT_EMAIL

    def _digits(self, value: str | None) -> str:
        return re.sub(r"[^0-9]", "", value or "")

    def _format_dui(self, digits: str) -> str:
        return f"{digits[:8]}-{digits[8]}" if len(digits) == 9 else "00000000-0"

    def _format_phone(self, value: str | None) -> str:
        digits = self._digits(value)[:8]
        if not digits:
            return "0000-0000"
        if len(digits) < 8:
            digits = digits.ljust(8, "0")
        return f"{digits[:4]}-{digits[4:8]}"

    def _resolve_geo_defaults(self) -> tuple[str, str, str]:
        from apps.core.models import GeoDepartment, GeoMunicipality

        dept = GeoDepartment.objects.filter(name__iexact="SAN MIGUEL").first() or GeoDepartment.objects.filter(code="12").first()
        dept_code = getattr(dept, "code", "12")
        dept_name = getattr(dept, "name", "SAN MIGUEL")
        muni = (
            GeoMunicipality.objects.filter(department_code=dept_code, name__iexact="SAN MIGUEL CENTRO").first()
            or GeoMunicipality.objects.filter(department_code=dept_code).order_by("name").first()
        )
        muni_code = getattr(muni, "municipality_code", "22")
        return dept_code, muni_code, dept_name

    def validate(self, attrs):
        base_keys = [
            "client_type",
            "dui",
            "nit",
            "nrc",
            "full_name",
            "company_name",
            "direccion",
            "department_code",
            "municipality_code",
            "activity_code",
            "activity_description",
            "telefono",
            "correo",
            "is_consumer_final",
        ]
        data = {**{k: getattr(self.instance, k, None) for k in base_keys if self.instance}, **attrs}
        ctype = (data.get("client_type") or "CF").upper()
        data["client_type"] = ctype

        full_name = (data.get("full_name") or "").strip()
        if not full_name:
            raise serializers.ValidationError({"full_name": "Este campo es requerido."})
        data["full_name"] = full_name.upper()

        dept_code = (data.get("department_code") or "").strip()
        muni_code = (data.get("municipality_code") or "").strip()
        dept_default, muni_default, dept_name_default = self._resolve_geo_defaults()

        if ctype in {"CF", "SX"}:
            document_digits = self._digits(data.get("dui") or data.get("nit"))
            if not document_digits:
                data["dui"] = "00000000-0"
                data["nit"] = ""
            elif len(document_digits) <= 9:
                data["dui"] = self._format_dui(document_digits if len(document_digits) == 9 else "000000000")
                data["nit"] = ""
            else:
                data["nit"] = document_digits[:14]
                data["dui"] = ""

            data["telefono"] = self._format_phone(data.get("telefono"))
            data["correo"] = self._default_email_if_empty(data.get("correo"))
            data["company_name"] = (data.get("company_name") or "").strip().upper()
            data["nrc"] = (data.get("nrc") or "").strip()

            if not dept_code and not muni_code:
                dept_code, muni_code = dept_default, muni_default
            elif dept_code and not muni_code:
                from apps.core.models import GeoMunicipality

                first_muni = GeoMunicipality.objects.filter(department_code=dept_code).order_by("name").first()
                muni_code = getattr(first_muni, "municipality_code", muni_default if dept_code == dept_default else "")
            data["department_code"] = dept_code or dept_default
            data["municipality_code"] = muni_code or muni_default

            if not (data.get("direccion") or "").strip():
                data["direccion"] = dept_name_default if data["department_code"] == dept_default else "SAN MIGUEL"
            else:
                data["direccion"] = (data.get("direccion") or "").strip()

        if ctype == "CCF":
            errors = {}
            nit_digits = self._digits(data.get("nit"))
            required = {
                "full_name": data.get("full_name"),
                "company_name": data.get("company_name"),
                "nit": nit_digits,
                "nrc": (data.get("nrc") or "").strip(),
                "telefono": self._digits(data.get("telefono")),
                "correo": self._default_email_if_empty(data.get("correo")),
                "direccion": (data.get("direccion") or "").strip(),
                "department_code": dept_code,
                "municipality_code": muni_code,
            }
            for field, value in required.items():
                if not value:
                    errors[field] = "Este campo es requerido para CCF."
            if len(nit_digits) != 14:
                errors["nit"] = "NIT debe tener 14 dígitos."
            phone_digits = self._digits(data.get("telefono"))
            if len(phone_digits) != 8:
                errors["phone"] = "Teléfono debe tener 8 dígitos."
            email = self._default_email_if_empty(data.get("correo"))
            if "@" not in email or "." not in email:
                errors["email"] = "Email inválido."
            if not ((data.get("activity_code") or "").strip() or (data.get("activity_description") or "").strip()):
                errors["activity_code"] = "Actividad económica requerida."
            if errors:
                raise serializers.ValidationError(errors)
            data["nit"] = nit_digits
            data["dui"] = ""
            data["telefono"] = self._format_phone(data.get("telefono"))
            data["correo"] = email
            data["company_name"] = (data.get("company_name") or "").strip().upper()
            data["direccion"] = (data.get("direccion") or "").strip()
            data["department_code"] = dept_code
            data["municipality_code"] = muni_code

        attrs.update(data)
        return attrs

    def create(self, validated_data):
        validated_data["correo"] = self._default_email_if_empty(validated_data.get("correo"))
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "correo" in validated_data:
            validated_data["correo"] = self._default_email_if_empty(validated_data.get("correo"))
        elif not instance.correo:
            validated_data["correo"] = self.DEFAULT_EMAIL
        return super().update(instance, validated_data)


class GeoDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoDepartment
        fields = ["code", "name"]


class GeoMunicipalitySerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="municipality_code", read_only=True)

    class Meta:
        model = GeoMunicipality
        fields = ["code", "department_code", "name"]


class ActivityCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityCatalog
        fields = ["code", "description"]
