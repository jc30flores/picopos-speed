Hook point para DTE (auditoría interna):
- Venta final: `Order` + `OrderInvoice` (`backend/apps/orders/models.py`).
- Punto de pago/completada: `PaymentListCreateView.create` cuando `remaining <= 0` (`backend/apps/payments/views.py`).
- Trigger aplicado: `transmit_sale_dte(payment.order_id, source="normal_send")`.
- Métodos de pago actuales: `cash`, `card`, `transfer` (`backend/apps/payments/models.py`).
- Config tributaria existente: endpoint activo `/api/core/tax-config/active/`.
