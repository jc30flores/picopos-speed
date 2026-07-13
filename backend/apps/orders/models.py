from django.db import models
from django.conf import settings
from apps.core.models import Branch, Customer, ServiceType, Table
from apps.core.money import to_cents
from apps.menu.models import Product, ProductSpecialPriceRule




class DiningArea(models.Model):
    name = models.CharField(max_length=120)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    x = models.FloatField(default=0)
    y = models.FloatField(default=0)
    width = models.FloatField(default=320)
    height = models.FloatField(default=220)
    color = models.CharField(max_length=20, blank=True, default="")
    operational_zoom = models.FloatField(default=1)
    operational_offset_x = models.FloatField(default=0)
    operational_offset_y = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return self.name


class RestaurantTable(models.Model):
    SHAPE_ROUND = "round"
    SHAPE_SQUARE = "square"
    SHAPE_RECTANGLE = "rectangle"
    SHAPE_BOOTH = "booth"
    SHAPE_BAR = "bar"
    SHAPE_CHOICES = [
        (SHAPE_ROUND, "Redonda"),
        (SHAPE_SQUARE, "Cuadrada"),
        (SHAPE_RECTANGLE, "Rectangular"),
        (SHAPE_BOOTH, "Booth"),
        (SHAPE_BAR, "Barra"),
    ]

    area = models.ForeignKey(DiningArea, on_delete=models.PROTECT, related_name="tables")
    name = models.CharField(max_length=120)
    number = models.PositiveIntegerField(default=1)
    capacity = models.PositiveIntegerField(default=1)
    shape = models.CharField(max_length=16, choices=SHAPE_CHOICES, default=SHAPE_SQUARE)
    x = models.FloatField(default=0)
    y = models.FloatField(default=0)
    width = models.FloatField(default=120)
    height = models.FloatField(default=80)
    rotation = models.FloatField(default=0)
    color = models.CharField(max_length=20, blank=True, default="")
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class TableSession(models.Model):
    STATUS_OPEN = "open"
    STATUS_SENT_TO_KITCHEN = "sent_to_kitchen"
    STATUS_PARTIALLY_PAID = "partially_paid"
    STATUS_PAID = "paid"
    STATUS_CLOSED = "closed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Abierta"),
        (STATUS_SENT_TO_KITCHEN, "En cocina"),
        (STATUS_PARTIALLY_PAID, "Parcialmente pagada"),
        (STATUS_PAID, "Pagada"),
        (STATUS_CLOSED, "Cerrada"),
        (STATUS_CANCELLED, "Cancelada"),
    ]

    ORDER_MODE_TABLE = "table"
    ORDER_MODE_PER_PERSON = "per_person"
    ORDER_MODE_CHOICES = [
        (ORDER_MODE_TABLE, "Orden completa"),
        (ORDER_MODE_PER_PERSON, "Por persona"),
    ]

    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_OPEN)
    guests_count = models.PositiveIntegerField(default=1)
    order_mode = models.CharField(max_length=24, choices=ORDER_MODE_CHOICES, default=ORDER_MODE_TABLE)
    primary_order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='table_sessions')
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='opened_table_sessions')
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='closed_table_sessions')
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, default="")
    total_cached = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    group_number = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class TableSessionTable(models.Model):
    session = models.ForeignKey(TableSession, on_delete=models.CASCADE, related_name='session_tables')
    table = models.ForeignKey(RestaurantTable, on_delete=models.PROTECT, related_name='table_sessions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("session", "table")


class TableGuest(models.Model):
    session = models.ForeignKey(TableSession, on_delete=models.CASCADE, related_name='guests')
    label = models.CharField(max_length=64)
    seat_number = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("session", "seat_number")
        ordering = ["seat_number", "id"]


class Order(models.Model):
    STATUS_CHOICES = [
        ("waiting_payment", "Waiting Payment"),
        ("new", "New"),
        ("preparing", "Preparing"),
        ("ready", "Ready"),
        ("delivered", "Delivered"),
        ("canceled", "Canceled"),
    ]
    PAYMENT_STATUS_CHOICES = [
        ("unpaid", "Unpaid"),
        ("partial", "Partial"),
        ("paid", "Paid"),
    ]
    CHANNEL_CHOICES = [("pos", "POS"), ("kiosk", "Kiosk"), ("online", "Online")]
    DTE_DOCUMENT_TYPE_CHOICES = [("CF", "Consumidor Final"), ("CCF", "Credito Fiscal"), ("SX", "Sujeto Excluido")]
    FINANCIAL_STATUS_CHOICES = [
        ("open", "Open"),
        ("paid", "Paid"),
        ("refunded_partial", "Refunded (Partial)"),
        ("refunded_full", "Refunded (Full)"),
        ("voided", "Voided"),
    ]
    PENDING_STATE_CHOICES = [
        ("none", "No pendiente"),
        ("pending_payment", "Pendiente de pago"),
        ("paid_pending_delivery", "Pagada pendiente de entrega"),
        ("in_kitchen", "En cocina"),
        ("ready", "Lista"),
    ]
    PENDING_COMPLETION_CHOICES = [
        ("none", "Sin finalizar"),
        ("paid", "Pagada"),
        ("removed", "Removida"),
        ("canceled", "Cancelada"),
    ]

    order_number = models.PositiveIntegerField()
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="orders")
    service_type = models.ForeignKey(ServiceType, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    table = models.ForeignKey(Table, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="waiting_payment")
    customer_name = models.CharField(max_length=120, blank=True)
    whatsapp_num_cliente = models.CharField(max_length=32, blank=True, default="")
    whatsapp_num_cliente_country = models.CharField(max_length=8, blank=True, default="")

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, null=True, blank=True, related_name="orders")
    dte_document_type = models.CharField(max_length=4, choices=DTE_DOCUMENT_TYPE_CHOICES, default="CF")
    iva_exempt = models.BooleanField(default=False)
    iva_exempt_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="pos")
    requires_kitchen = models.BooleanField(default=False)
    send_to_kitchen = models.BooleanField(default=False)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_snapshot = models.JSONField(default=dict, blank=True)
    disposable_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="unpaid")
    financial_status = models.CharField(
        max_length=20,
        choices=FINANCIAL_STATUS_CHOICES,
        default="open",
    )
    refund_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_pending = models.BooleanField(default=False)
    pending_state = models.CharField(max_length=30, choices=PENDING_STATE_CHOICES, default="none")
    pending_reference = models.CharField(max_length=120, blank=True, default="")
    pending_marked_at = models.DateTimeField(null=True, blank=True)
    pending_completed_at = models.DateTimeField(null=True, blank=True)
    pending_completion_type = models.CharField(max_length=20, choices=PENDING_COMPLETION_CHOICES, default="none")
    pending_completion_note = models.CharField(max_length=160, blank=True, default="")
    amount_due_cents = models.IntegerField(default=0)
    financial_locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["service_type"]),
            models.Index(fields=["branch", "order_number"]),
            models.Index(fields=["channel", "requires_kitchen", "status"]),
        ]
        unique_together = ("branch", "order_number")

    def __str__(self) -> str:
        return f"Order {self.order_number}"

    def recalculate_financials(self) -> None:
        from decimal import Decimal
        from django.db.models import DecimalField, ExpressionWrapper, F, Sum
        from apps.payments.models import Payment, Refund

        totals = Payment.objects.filter(order=self).aggregate(total_paid=Sum("amount_applied"))
        refunded = Refund.objects.filter(order=self).aggregate(
            total_refunded=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_refunded"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
        )
        total_paid = (totals["total_paid"] or Decimal("0")).quantize(Decimal("0.01"))
        total_refunded = refunded["total_refunded"] or Decimal("0")
        net_paid = max(total_paid - total_refunded, Decimal("0")).quantize(Decimal("0.01"))

        if self.financial_status != "voided":
            if total_paid <= 0:
                self.payment_status = "unpaid"
                self.financial_status = "open"
            amount_due = Decimal(self.amount_due_cents or to_cents(self.total)) / Decimal("100")
            if self.amount_due_cents <= 0:
                self.amount_due_cents = to_cents(self.total)
            elif total_paid < amount_due:
                self.payment_status = "partial"
                self.financial_status = "open"
            else:
                self.payment_status = "paid"
                if total_refunded <= 0:
                    self.financial_status = "paid"
                elif total_refunded < total_paid:
                    self.financial_status = "refunded_partial"
                else:
                    self.financial_status = "refunded_full"

        self.refund_total = total_refunded
        self.net_paid = net_paid
        self.save(
            update_fields=[
                "payment_status",
                "financial_status",
                "refund_total",
                "net_paid",
                "amount_due_cents",
                "updated_at",
            ]
        )


class OrderItem(models.Model):
    KITCHEN_STATUS_PENDING = "pending"
    KITCHEN_STATUS_SENT = "sent"
    KITCHEN_STATUS_READY = "ready"
    KITCHEN_STATUS_DELIVERED = "delivered"
    KITCHEN_STATUS_CHOICES = [
        (KITCHEN_STATUS_PENDING, "Pendiente"),
        (KITCHEN_STATUS_SENT, "En cocina"),
        (KITCHEN_STATUS_READY, "Listo"),
        (KITCHEN_STATUS_DELIVERED, "Entregado"),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items", null=True, blank=True)
    product_name_snapshot = models.CharField(max_length=160)
    price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    snapshot_sku_or_code = models.CharField(max_length=80, blank=True, default="")
    is_custom = models.BooleanField(default=False)
    quantity = models.PositiveIntegerField(default=1)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    assigned_name = models.CharField(max_length=80, blank=True, default="")
    table_guest = models.ForeignKey(TableGuest, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items")
    applied_special_price_rule = models.ForeignKey(ProductSpecialPriceRule, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items")
    kitchen_status = models.CharField(max_length=16, choices=KITCHEN_STATUS_CHOICES, default=KITCHEN_STATUS_PENDING)
    kitchen_sent_at = models.DateTimeField(null=True, blank=True)
    kitchen_ready_at = models.DateTimeField(null=True, blank=True)
    kitchen_delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["order"]), models.Index(fields=["order", "kitchen_status"]) ]

    def __str__(self) -> str:
        return f"{self.product_name_snapshot} x{self.quantity}"

    @property
    def name(self):
        return self.product_name_snapshot or (self.product.name if self.product_id and self.product else "")

    @property
    def unit_price(self):
        return self.effective_unit_price

    @property
    def is_manual(self):
        return bool(self.is_custom)

    @property
    def effective_unit_price(self):
        return self.unit_price_override if self.unit_price_override is not None else self.price_snapshot


class OrderItemModifier(models.Model):
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="applied_modifiers")
    modifier_name_snapshot = models.CharField(max_length=120)
    modifier_price_snapshot = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    class Meta:
        indexes = [models.Index(fields=["order_item"]) ]

    def __str__(self) -> str:
        return self.modifier_name_snapshot


class AppliedDiscount(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="applied_discounts")
    discount_name_snapshot = models.CharField(max_length=160)
    discount_type_snapshot = models.CharField(max_length=20)
    discount_value_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    amount_discounted = models.DecimalField(max_digits=10, decimal_places=2)
    breakdown = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["order"]) ]

    def __str__(self) -> str:
        return self.discount_name_snapshot


class OrderFee(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="fees")
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="fees", null=True, blank=True)
    fee_type = models.CharField(max_length=40, default="disposable")
    fee_name = models.CharField(max_length=120)
    unit_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    quantity = models.PositiveIntegerField(default=1)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        indexes = [models.Index(fields=["order", "fee_type"]) ]

    def __str__(self) -> str:
        return f"{self.fee_name} ({self.total_amount})"


class OrderInvoice(models.Model):
    HACIENDA_STATUS_CHOICES = [("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="invoice")
    status = models.CharField(max_length=20, choices=HACIENDA_STATUS_CHOICES, default="pending")
    dte_number = models.CharField(max_length=80, blank=True)
    generation_code = models.CharField(max_length=120, blank=True)
    dte_status = models.CharField(max_length=20, blank=True, default="pending")
    dte_send_attempts = models.PositiveIntegerField(default=0)
    last_dte_sent_at = models.DateTimeField(null=True, blank=True)
    last_dte_error = models.TextField(blank=True)
    last_dte_error_code = models.CharField(max_length=80, blank=True)
    numero_control = models.CharField(max_length=80, blank=True)
    codigo_generacion = models.CharField(max_length=40, blank=True)
    hacienda_payload = models.JSONField(default=dict, blank=True)
    hacienda_response = models.JSONField(default=dict, blank=True)
    sale_snapshot = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status", "updated_at"])]

    def __str__(self) -> str:
        return f"Invoice {self.order_id} ({self.status})"
