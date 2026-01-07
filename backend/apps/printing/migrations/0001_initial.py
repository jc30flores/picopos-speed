from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("orders", "0003_order_payment_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PrintJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "type",
                    models.CharField(
                        choices=[("kitchen", "Kitchen"), ("customer", "Customer"), ("closeout", "Closeout")],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("queued", "Queued"), ("rendered", "Rendered"), ("printed", "Printed"), ("failed", "Failed")],
                        default="queued",
                        max_length=20,
                    ),
                ),
                ("content_text", models.TextField()),
                ("content_html", models.TextField(blank=True)),
                ("content_pdf_path", models.CharField(blank=True, max_length=255)),
                ("printed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("error_message", models.TextField(blank=True)),
                ("meta", models.JSONField(blank=True, default=dict)),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="print_jobs",
                        to="orders.order",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="print_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="printjob",
            index=models.Index(fields=["type", "status"], name="printing_pr_type_4f9d5c_idx"),
        ),
        migrations.AddIndex(
            model_name="printjob",
            index=models.Index(fields=["created_at"], name="printing_pr_created_18a3a2_idx"),
        ),
    ]
