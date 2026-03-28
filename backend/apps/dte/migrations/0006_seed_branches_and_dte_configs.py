from django.db import migrations


def seed_branches_and_configs(apps, schema_editor):
    Branch = apps.get_model("core", "Branch")
    DTEBranchConfig = apps.get_model("dte", "DTEBranchConfig")

    principal, _ = Branch.objects.update_or_create(
        code="PRINCIPAL", defaults={"name": "Sucursal Principal", "is_active": True}
    )
    plaza, _ = Branch.objects.update_or_create(
        code="PLAZA_MONACO", defaults={"name": "Plaza Monaco", "is_active": True}
    )

    emisor_defaults = {
        "emisor_nit": "12171409901063",
        "emisor_nrc": "2564720",
        "emisor_nombre": "Pico de Gallo",
        "emisor_nombre_comercial": "Pico de Gallo",
        "cod_actividad": "56101",
        "desc_actividad": "Restaurantes y puestos de comidas",
        "tipo_establecimiento": "02",
        "cod_estable_mh": "M001",
        "cod_estable": "M001",
        "cod_punto_venta_mh": "P001",
        "cod_punto_venta": "P001",
        "direccion_departamento": "12",
        "direccion_municipio": "22",
        "direccion_complemento": "9AV NORTE BO SAN FRANCISCO,#507, FRENTE COSTADO SUR DEL PENAL,SAN MIGUEL SAN MIGUEL",
        "telefono": "60038807",
        "correo": "facturasPDG23@GMAIL.COM",
        "is_active": True,
    }

    DTEBranchConfig.objects.update_or_create(branch=principal, defaults=emisor_defaults)
    DTEBranchConfig.objects.update_or_create(branch=plaza, defaults=emisor_defaults)


class Migration(migrations.Migration):

    dependencies = [
        ("dte", "0005_dtebranchconfig"),
        ("core", "0008_rename_core_auditlog_action_1f4a33_idx_core_auditl_action_d9fb24_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_branches_and_configs, migrations.RunPython.noop),
    ]
