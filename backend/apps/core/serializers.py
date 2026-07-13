from django.db import transaction
from django.db.models.expressions import RawSQL
from rest_framework import serializers
import re

from apps.core.models import ActivityCatalog, Customer, DTEGlobalSettings, FeatureFlag, GeoDepartment, GeoMunicipality, ServiceType, SystemAppearanceSettings, TaxConfig
from apps.menu.models import Product


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ["id", "key", "label", "is_active", "sort_order", "disposables_enabled", "color_hex"]


    def validate_color_hex(self, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        cleaned = str(value).strip()
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", cleaned):
            raise serializers.ValidationError("Color HEX inválido. Usa formato #RRGGBB.")
        return cleaned.upper()

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
        fields = ["id", "key", "label", "description", "is_enabled", "metadata"]


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    cleaned = value.strip().lstrip("#")
    return int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, int(c))):02X}" for c in rgb)


def _mix(color: tuple[int, int, int], target: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(round(color[i] + (target[i] - color[i]) * amount) for i in range(3))


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(v: int) -> float:
        n = v / 255
        return n / 12.92 if n <= 0.03928 else ((n + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    high, low = sorted([_relative_luminance(a), _relative_luminance(b)], reverse=True)
    return (high + 0.05) / (low + 0.05)


def build_color_tokens(primary: str) -> dict[str, str]:
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", primary or ""):
        raise serializers.ValidationError(
            {
                "error": "invalid_color_format",
                "code": "invalid_color_format",
                "message": "Color HEX inválido. Usa formato #RRGGBB.",
                "suggestions": ["#2563EB", "#0F766E", "#DB2777", "#C026D3", "#374151"],
            }
        )
    rgb = _hex_to_rgb(primary)
    white = (255, 255, 255)
    black = (15, 23, 42)
    contrast = "#FFFFFF" if _contrast(rgb, white) >= _contrast(rgb, black) else "#0F172A"
    hover = _mix(rgb, black if _relative_luminance(rgb) > 0.45 else white, 0.18)
    soft = _mix(rgb, white, 0.82)
    border = _mix(rgb, white, 0.45)
    text = _mix(rgb, black, 0.5) if _relative_luminance(rgb) > 0.45 else _mix(rgb, white, 0.45)
    on_light = _mix(rgb, black, 0.35) if _contrast(rgb, white) < 3 else rgb
    on_dark = _mix(rgb, white, 0.28) if _contrast(rgb, (17, 24, 39)) < 3 else rgb
    return {
        "primary_color": primary.upper(),
        "color_primary": primary.upper(),
        "color_primary_hover": _rgb_to_hex(hover),
        "color_primary_soft": _rgb_to_hex(soft),
        "color_primary_border": _rgb_to_hex(border),
        "color_primary_text": _rgb_to_hex(text),
        "color_primary_contrast": contrast,
        "color_primary_on_light": _rgb_to_hex(on_light),
        "color_primary_on_dark": _rgb_to_hex(on_dark),
    }


class SystemAppearanceSettingsSerializer(serializers.ModelSerializer):
    css_variables = serializers.SerializerMethodField()
    theme_mode = serializers.SerializerMethodField()
    allow_custom_color = serializers.SerializerMethodField()
    palette = serializers.SerializerMethodField()

    class Meta:
        model = SystemAppearanceSettings
        fields = [
            "primary_color",
            "color_primary",
            "color_primary_hover",
            "color_primary_soft",
            "color_primary_border",
            "color_primary_text",
            "color_primary_contrast",
            "theme_mode",
            "allow_custom_color",
            "palette",
            "css_variables",
            "updated_at",
        ]
        read_only_fields = fields

    def get_css_variables(self, obj: SystemAppearanceSettings) -> dict[str, str]:
        return {
            "--color-primary": obj.color_primary,
            "--color-primary-hover": obj.color_primary_hover,
            "--color-primary-soft": obj.color_primary_soft,
            "--color-primary-border": obj.color_primary_border,
            "--color-primary-text": obj.color_primary_text,
            "--color-primary-contrast": obj.color_primary_contrast,
            "--color-primary-on-light": getattr(obj, "color_primary_on_light", obj.color_primary),
            "--color-primary-on-dark": getattr(obj, "color_primary_on_dark", obj.color_primary),
            "--color-primary-muted": obj.color_primary_soft,
            "--color-primary-surface": obj.color_primary_soft,
        }

    def get_theme_mode(self, obj: SystemAppearanceSettings) -> str:
        return "system"

    def get_allow_custom_color(self, obj: SystemAppearanceSettings) -> bool:
        return True

    def get_palette(self, obj: SystemAppearanceSettings) -> list[str]:
        return [
            "#1F7A4D",
            "#2563EB",
            "#0F766E",
            "#0284C7",
            "#0891B2",
            "#6D28D9",
            "#A21CAF",
            "#C026D3",
            "#DB2777",
            "#BE185D",
            "#EC4899",
            "#E11D48",
            "#BE123C",
            "#B45309",
            "#B7791F",
            "#374151",
            "#111827",
            "#0D9488",
        ]


class DTEGlobalSettingsSerializer(serializers.ModelSerializer):
    api_token_masked = serializers.SerializerMethodField()
    enabled = serializers.BooleanField(source="hacienda_enabled", read_only=True)
    environment = serializers.SerializerMethodField()
    config_status = serializers.CharField(source="status", read_only=True)
    fiscal_email_enabled = serializers.SerializerMethodField()
    fiscal_whatsapp_enabled = serializers.SerializerMethodField()
    fiscal_pdf_enabled = serializers.SerializerMethodField()
    fiscal_json_enabled = serializers.SerializerMethodField()
    single_branch = serializers.SerializerMethodField()
    correlatives = serializers.SerializerMethodField()
    api = serializers.SerializerMethodField()
    issuer = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    pending_fields = serializers.SerializerMethodField()

    class Meta:
        model = DTEGlobalSettings
        fields = [
            "hacienda_enabled",
            "enabled",
            "ambiente",
            "environment",
            "base_url",
            "api_token_masked",
            "timeout_seconds",
            "retry_count",
            "fiscal_email_enabled",
            "fiscal_whatsapp_enabled",
            "fiscal_pdf_enabled",
            "fiscal_json_enabled",
            "status",
            "config_status",
            "single_branch",
            "correlatives",
            "api",
            "issuer",
            "branch",
            "permissions",
            "pending_fields",
            "last_connection_test_at",
            "last_error_sanitized",
            "updated_at",
        ]

    def get_api_token_masked(self, obj: DTEGlobalSettings) -> str:
        if not obj.api_token:
            return ""
        return f"{obj.api_token[:4]}...{obj.api_token[-4:]}" if len(obj.api_token) > 8 else "********"

    def get_environment(self, obj: DTEGlobalSettings) -> str:
        return "production" if obj.ambiente == DTEGlobalSettings.AMBIENTE_PROD else "test"

    def get_fiscal_email_enabled(self, obj: DTEGlobalSettings) -> bool:
        return bool(obj.hacienda_enabled and obj.fiscal_email_enabled)

    def get_fiscal_whatsapp_enabled(self, obj: DTEGlobalSettings) -> bool:
        return bool(obj.hacienda_enabled and obj.fiscal_whatsapp_enabled)

    def get_fiscal_pdf_enabled(self, obj: DTEGlobalSettings) -> bool:
        return bool(obj.hacienda_enabled and obj.fiscal_pdf_enabled)

    def get_fiscal_json_enabled(self, obj: DTEGlobalSettings) -> bool:
        return bool(obj.hacienda_enabled and obj.fiscal_json_enabled)

    def get_single_branch(self, obj: DTEGlobalSettings) -> dict:
        from apps.core.models import Branch
        from apps.dte.models import DTEBranchConfig

        branch = Branch.objects.filter(is_active=True).order_by("id").first()
        config = DTEBranchConfig.objects.filter(branch=branch).first() if branch else None
        return {
            "branch_name": branch.name if branch else "",
            "establishment_code": getattr(config, "cod_estable_mh", "") or "",
            "pos_code": getattr(config, "cod_punto_venta_mh", "") or "",
            "establishment_type": getattr(config, "tipo_establecimiento", "") or "",
            "address": getattr(config, "direccion_complemento", "") or getattr(branch, "address", "") or "",
        }

    def _branch_and_config(self):
        from apps.core.models import Branch
        from apps.dte.models import DTEBranchConfig

        branch = Branch.objects.filter(is_active=True).order_by("id").first()
        config = DTEBranchConfig.objects.filter(branch=branch).first() if branch else None
        return branch, config

    def get_api(self, obj: DTEGlobalSettings) -> dict:
        return {
            "enabled": obj.hacienda_enabled,
            "environment": self.get_environment(obj),
            "ambiente": obj.ambiente,
            "base_url": obj.base_url,
            "api_token_masked": self.get_api_token_masked(obj),
            "api_token_configured": bool(obj.api_token),
            "timeout_seconds": obj.timeout_seconds,
            "retry_count": obj.retry_count,
            "last_connection_test_at": obj.last_connection_test_at,
            "last_error_sanitized": obj.last_error_sanitized,
            "fiscal_email_enabled": bool(obj.hacienda_enabled and obj.fiscal_email_enabled),
            "fiscal_whatsapp_enabled": bool(obj.hacienda_enabled and obj.fiscal_whatsapp_enabled),
            "fiscal_pdf_enabled": bool(obj.hacienda_enabled and obj.fiscal_pdf_enabled),
            "fiscal_json_enabled": bool(obj.hacienda_enabled and obj.fiscal_json_enabled),
        }

    def get_issuer(self, obj: DTEGlobalSettings) -> dict:
        _branch, config = self._branch_and_config()
        return {
            "legal_name": getattr(config, "emisor_nombre", "") or "",
            "commercial_name": getattr(config, "emisor_nombre_comercial", "") or "",
            "document_type": "NIT",
            "nit": getattr(config, "emisor_nit", "") or "",
            "dui": "",
            "nrc": getattr(config, "emisor_nrc", "") or "",
            "activity_code": getattr(config, "cod_actividad", "") or "",
            "activity_description": getattr(config, "desc_actividad", "") or "",
            "establishment_type": getattr(config, "tipo_establecimiento", "") or "",
            "department": getattr(config, "direccion_departamento", "") or "",
            "municipality": getattr(config, "direccion_municipio", "") or "",
            "address": getattr(config, "direccion_complemento", "") or "",
            "phone": getattr(config, "telefono", "") or "",
            "email": getattr(config, "correo", "") or "",
            "updated_at": getattr(config, "updated_at", None),
            "validation_status": "configured" if config else "pending",
        }

    def get_branch(self, obj: DTEGlobalSettings) -> dict:
        branch, config = self._branch_and_config()
        return {
            "id": branch.id if branch else None,
            "name": branch.name if branch else "",
            "code": branch.code if branch else "",
            "address": getattr(branch, "address", "") or "",
            "establishment_code_mh": getattr(config, "cod_estable_mh", "") or "",
            "establishment_code": getattr(config, "cod_estable", "") or "",
            "pos_code_mh": getattr(config, "cod_punto_venta_mh", "") or "",
            "pos_code": getattr(config, "cod_punto_venta", "") or "",
            "establishment_type": getattr(config, "tipo_establecimiento", "") or "",
            "branch_address": getattr(config, "direccion_complemento", "") or getattr(branch, "address", "") or "",
            "phone": getattr(config, "telefono", "") or "",
            "email": getattr(config, "correo", "") or "",
            "active": bool(branch and branch.is_active and (getattr(config, "is_active", True))),
        }

    def get_permissions(self, obj: DTEGlobalSettings) -> dict:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        from apps.core.permissions import can_manage_correlatives, can_manage_dte_settings, is_admin, is_superadmin

        return {
            "can_view_basic": bool(user and user.is_authenticated and is_admin(user)),
            "can_edit_technical": bool(user and user.is_authenticated and can_manage_dte_settings(user)),
            "can_edit_correlatives": bool(user and user.is_authenticated and can_manage_correlatives(user)),
            "is_superadmin": bool(user and user.is_authenticated and is_superadmin(user)),
        }

    def get_pending_fields(self, obj: DTEGlobalSettings) -> list[str]:
        if not obj.hacienda_enabled:
            return []
        issuer = self.get_issuer(obj)
        branch = self.get_branch(obj)
        required = {
            "URL API": obj.base_url,
            "API token": obj.api_token,
            "razón social": issuer["legal_name"],
            "NIT": issuer["nit"],
            "NRC": issuer["nrc"],
            "código de actividad": issuer["activity_code"],
            "actividad económica": issuer["activity_description"],
            "departamento": issuer["department"],
            "municipio": issuer["municipality"],
            "dirección": issuer["address"],
            "teléfono": issuer["phone"],
            "correo": issuer["email"],
            "código establecimiento": branch["establishment_code"],
            "código punto de venta": branch["pos_code"],
        }
        pending = [label for label, value in required.items() if not str(value or "").strip()]
        if not self.get_correlatives(obj):
            pending.append("correlativos")
        return pending

    def get_correlatives(self, obj: DTEGlobalSettings) -> list[dict]:
        from apps.dte.models import DTEControlCounter

        rows = DTEControlCounter.objects.select_related("branch").order_by("branch__name", "dte_type", "year")[:50]
        return [
            {
                "id": row.id,
                "tipo_dte": row.dte_type,
                "label": {
                    "CF_01": "Consumidor Final / 01",
                    "CCF_03": "Crédito Fiscal / 03",
                    "NC_05": "Nota de Crédito / 05",
                    "ND_06": "Nota de Débito / 06",
                    "SE_14": "Sujeto Excluido / 14",
                }.get(row.dte_type, row.dte_type),
                "ambiente": row.ambiente,
                "environment": "production" if row.ambiente == "01" else "test",
                "branch_name": row.branch.name,
                "year": row.year,
                "establishment_code": row.establishment_code,
                "pos_code": row.pos_code,
                "last_number": row.last_number,
                "next_number": row.last_number + 1,
                "active": True,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]


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
            "is_iva_exempt", "created_at", "updated_at",
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
            "is_iva_exempt",
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
            "is_iva_exempt",
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

        if ctype != "CF":
            data["is_iva_exempt"] = False

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
