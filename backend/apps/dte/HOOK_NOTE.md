Hook point para DTE:
- Archivo: `backend/apps/payments/views.py`
- Función: `PaymentListCreateView.create`
- Evento: cuando `remaining <= 0` (pago confirmado / venta cerrada) se ejecuta `transmit_invoice_dte(payment.order_id, source="normal_send")`.
