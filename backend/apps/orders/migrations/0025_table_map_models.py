from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0024_order_whatsapp_num_cliente_default"),
            ]

    operations = [
        migrations.CreateModel(
            name="DiningArea",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("sort_order", models.IntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="RestaurantTable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("number", models.PositiveIntegerField(default=1)),
                ("capacity", models.PositiveIntegerField(default=1)),
                ("shape", models.CharField(choices=[("round", "Redonda"), ("square", "Cuadrada"), ("rectangle", "Rectangular"), ("booth", "Booth"), ("bar", "Barra")], default="square", max_length=16)),
                ("x", models.FloatField(default=0)), ("y", models.FloatField(default=0)), ("width", models.FloatField(default=120)), ("height", models.FloatField(default=80)),
                ("rotation", models.FloatField(default=0)), ("color", models.CharField(blank=True, default="", max_length=20)),
                ("is_active", models.BooleanField(default=True)), ("sort_order", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("area", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tables", to="orders.diningarea")),
            ],
        ),
        migrations.CreateModel(
            name="TableSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("open", "Abierta"), ("sent_to_kitchen", "En cocina"), ("partially_paid", "Parcialmente pagada"), ("paid", "Pagada"), ("closed", "Cerrada"), ("cancelled", "Cancelada")], default="open", max_length=24)),
                ("guests_count", models.PositiveIntegerField(default=1)),
                ("order_mode", models.CharField(choices=[("table", "Orden completa"), ("per_person", "Por persona")], default="table", max_length=24)),
                ("opened_at", models.DateTimeField(auto_now_add=True)), ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.CharField(blank=True, default="", max_length=255)),
                ("total_cached", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("closed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="closed_table_sessions", to="auth.user")),
                ("opened_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="opened_table_sessions", to="auth.user")),
                ("primary_order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="table_sessions", to="orders.order")),
            ],
        ),
        migrations.CreateModel(
            name="TableGuest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(max_length=64)), ("seat_number", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)), ("is_paid", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="guests", to="orders.tablesession")),
            ],
            options={"ordering": ["seat_number", "id"], "unique_together": {("session", "seat_number")}},
        ),
        migrations.CreateModel(
            name="TableSessionTable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="session_tables", to="orders.tablesession")),
                ("table", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="table_sessions", to="orders.restauranttable")),
            ],
            options={"unique_together": {("session", "table")}},
        ),
        migrations.AddField(
            model_name="orderitem",
            name="table_guest",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_items", to="orders.tableguest"),
        ),
    ]
