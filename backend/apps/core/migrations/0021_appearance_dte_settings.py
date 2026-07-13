from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_gastroposv_flags(apps, schema_editor):
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    defaults = [
        ("module_pos_enabled", "POS", "Mostrar u ocultar venta rápida/POS.", True, {"category": "Venta rápida / POS"}),
        ("module_open_orders_enabled", "Pedidos clientes", "Mostrar u ocultar pedidos abiertos y pendientes.", True, {"category": "Venta rápida / POS"}),
        ("module_menu_discounts_enabled", "Menú & descuentos", "Mostrar u ocultar gestión de menú y descuentos.", True, {"category": "Operación / Pantallas"}),
        ("module_reports_enabled", "Reportes", "Mostrar u ocultar reportes y registros.", True, {"category": "Reportes"}),
        ("module_clients_enabled", "Clientes", "Mostrar u ocultar la gestión de clientes.", True, {"category": "Clientes"}),
        ("module_settings_enabled", "Configuración para administradores", "Oculta Configuración a administradores; superadmin siempre mantiene acceso.", True, {"category": "Seguridad / Caja"}),
        ("module_dte_enabled", "DTE / Hacienda", "Mostrar u ocultar funciones fiscales DTE.", False, {"category": "Fiscal / DTE"}),
        ("module_whatsapp_enabled", "WhatsApp fiscal", "Permitir acciones de entrega fiscal por WhatsApp.", True, {"category": "Comunicación"}),
        ("module_email_enabled", "Correo fiscal", "Permitir acciones de entrega fiscal por correo.", True, {"category": "Comunicación"}),
    ]
    for key, label, description, enabled, metadata in defaults:
        FeatureFlag.objects.get_or_create(
            key=key,
            defaults={"label": label, "description": description, "is_enabled": enabled, "metadata": metadata},
        )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0020_ticket_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="DTEGlobalSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("hacienda_enabled", models.BooleanField(default=False)),
                ("ambiente", models.CharField(choices=[("00", "Pruebas"), ("01", "Producción")], default="00", max_length=2)),
                ("base_url", models.URLField(blank=True, default="")),
                ("api_token", models.CharField(blank=True, default="", max_length=255)),
                ("timeout_seconds", models.PositiveIntegerField(default=15)),
                ("retry_count", models.PositiveIntegerField(default=3)),
                ("status", models.CharField(choices=[("pending", "Pendiente"), ("configured", "Configurado"), ("invalid", "Inválido"), ("disabled", "Desactivado")], default="disabled", max_length=20)),
                ("last_connection_test_at", models.DateTimeField(blank=True, null=True)),
                ("last_error_sanitized", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="dte_global_settings_updates", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "DTE global settings",
                "verbose_name_plural": "DTE global settings",
            },
        ),
        migrations.CreateModel(
            name="SystemAppearanceSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("primary_color", models.CharField(default="#1F7A4D", max_length=7)),
                ("color_primary", models.CharField(default="#1F7A4D", max_length=7)),
                ("color_primary_hover", models.CharField(default="#17623E", max_length=7)),
                ("color_primary_soft", models.CharField(default="#DDF3E8", max_length=7)),
                ("color_primary_border", models.CharField(default="#7EC8A3", max_length=7)),
                ("color_primary_text", models.CharField(default="#0D3B26", max_length=7)),
                ("color_primary_contrast", models.CharField(default="#FFFFFF", max_length=7)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="appearance_updates", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "System appearance settings",
                "verbose_name_plural": "System appearance settings",
            },
        ),
        migrations.RunPython(seed_gastroposv_flags, migrations.RunPython.noop),
    ]
