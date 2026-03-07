from django.db import migrations


def seed_and_map(apps, schema_editor):
    ServiceType = apps.get_model('core', 'ServiceType')
    Order = apps.get_model('orders', 'Order')
    KitchenOrderView = apps.get_model('kitchen', 'KitchenOrderView')
    SaleSnapshot = apps.get_model('reports', 'SaleSnapshot')

    defaults = [
        ('MESA', 'Mesa', 0),
        ('PEDIDOS_YA', 'Pedidos Ya', 1),
        ('PARA_LLEVAR', 'Para Llevar', 2),
        ('KIOSK', 'Kiosk', 3),
    ]
    by_key = {}
    for key, label, sort_order in defaults:
        obj, _ = ServiceType.objects.update_or_create(
            key=key,
            defaults={
                'label': label,
                'sort_order': sort_order,
                'is_active': True,
            },
        )
        by_key[key] = obj

    mapping = {
        'DINE-IN': 'MESA',
        'DINE_IN': 'MESA',
        'EN_LOCAL': 'MESA',
        'MESA': 'MESA',
        'TAKEOUT': 'PARA_LLEVAR',
        'PARA_LLEVAR': 'PARA_LLEVAR',
        'DELIVERY': 'PEDIDOS_YA',
        'PEDIDOS_YA': 'PEDIDOS_YA',
        'KIOSK': 'KIOSK',
    }

    for legacy, target in mapping.items():
        legacy_ids = list(ServiceType.objects.filter(key__iexact=legacy).values_list('id', flat=True))
        if not legacy_ids:
            continue
        target_obj = by_key[target]
        Order.objects.filter(service_type_id__in=legacy_ids).update(service_type_id=target_obj.id)
        KitchenOrderView.objects.filter(service_type_id__in=legacy_ids).update(service_type_id=target_obj.id)
        SaleSnapshot.objects.filter(service_type_id__in=legacy_ids).update(service_type_id=target_obj.id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_alter_servicetype_options_servicetype_sort_order'),
        ('orders', '0014_alter_order_service_type'),
        ('kitchen', '0002_alter_kitchenorderview_service_type'),
        ('reports', '0002_alter_salesnapshot_service_type'),
    ]

    operations = [
        migrations.RunPython(seed_and_map, noop),
    ]
