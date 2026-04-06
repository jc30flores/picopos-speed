from decimal import Decimal
import logging
import threading
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.core.audit import log_audit
from apps.core.permissions import IsCashierOrManagerOrAdmin, IsAdminOrManager
from apps.cashier.models import CashSession, CashTransaction
from apps.payments.models import Payment, Refund, PaymentMethod, PaymentMethodChangeLog
from apps.printing.models import PrintJob
from apps.printing.serializers import PrintJobSerializer
from apps.printing.services.jobs import create_print_job, create_refund_print_job
from apps.printing.services.renderers import render_customer_ticket
from apps.printing.receipt_pdf import build_receipt_pdf_from_text
from apps.printing.services.system_printer import SystemPrinterService
from apps.payments.serializers import (
    PaymentSerializer,
    RefundSerializer,
    PaymentMethodSerializer,
    InternalPaymentMethodChangeSerializer,
)
from apps.orders.serializers import OrderSerializer
from apps.orders.services.snapshots import persist_sale_snapshot
from apps.dte.services.dte_service import send_dte_for_order, invalidate_dte_for_order, send_dte_for_credit_note
from apps.dte.services.availability import resolve_issued_at
from apps.dte.models import DTERecord, DTEInvalidation, CreditNote
from apps.core.money import to_cents, from_cents


logger = logging.getLogger(__name__)


def _get_open_session(user):
    return CashSession.objects.filter(opened_by=user, status="open").select_related("register").first()


def _is_cash_payment_method(payment_method: PaymentMethod | None) -> bool:
    if not payment_method:
        return False
    code = str(payment_method.code or "").strip().upper()
    return bool(payment_method.is_cash or code in {"01", "CASH", "EFECTIVO"})


def _refund_is_cash(*, method: str, payment_method: PaymentMethod | None, original_payment: Payment | None) -> bool:
    if _is_cash_payment_method(payment_method):
        return True
    if str(method or "").strip().lower() == "cash":
        return True
    if not original_payment:
        return False
    if _is_cash_payment_method(original_payment.payment_method):
        return True
    return str(original_payment.method or "").strip().lower() == "cash"


def _venta_pdf_filename(order, *, include_seconds: bool = False) -> str:
    ts = timezone.localtime(timezone.now())
    pattern = "%Y-%m-%d_%H-%M-%S" if include_seconds else "%Y-%m-%d_%H-%M"
    return f'venta_{order.order_number}_{ts.strftime(pattern)}.pdf'


def _get_open_session_for_branch(branch_id: int) -> CashSession | None:
    return (
        CashSession.objects.filter(register__branch_id=branch_id, status="open", closed_at__isnull=True)
        .select_related("register", "register__branch")
        .order_by("-opened_at")
        .first()
    )


def _create_cash_out_for_refund(refund: Refund, user) -> tuple[CashTransaction, bool]:
    amount = (refund.amount + (refund.tip_refunded or Decimal("0"))).quantize(Decimal("0.01"))
    return CashTransaction.objects.get_or_create(
        refund=refund,
        defaults={
            "session": refund.cash_session,
            "type": "cash_out",
            "amount": amount,
            "description": f"Reembolso orden #{refund.order_id} (refund_id={refund.id})",
            "created_by": user,
        },
    )


def _create_non_cash_transaction_for_refund(refund: Refund, user) -> tuple[CashTransaction | None, bool]:
    return None, False


def _non_cash_tx_type_from_code(code: str) -> str:
    return "transfer"


def _create_transaction_for_payment(payment: Payment, user) -> tuple[CashTransaction | None, bool]:
    session = payment.cash_session
    if not session:
        return None, False
    total_amount = (payment.amount + (payment.tip_amount or Decimal("0"))).quantize(Decimal("0.01"))
    if _refund_is_cash(method=payment.method, payment_method=payment.payment_method, original_payment=None):
        tx, created = CashTransaction.objects.get_or_create(
            payment=payment,
            defaults={
                "session": session,
                "type": "cash_in",
                "amount": total_amount,
                "description": f"Pago efectivo orden #{payment.order_id} (payment_id={payment.id})",
                "created_by": user,
            },
        )
        logger.info(
            "cashier.payment.cash_in payment_id=%s session_id=%s amount=%s branch_id=%s created=%s",
            payment.id,
            tx.session_id,
            tx.amount,
            payment.order.branch_id,
            created,
        )
        return tx, created

    return None, False




class PaymentMethodListView(generics.ListAPIView):
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get_queryset(self):
        return PaymentMethod.objects.filter(is_active=True).order_by("sort_order", "name")

class PaymentListCreateView(generics.ListCreateAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get_queryset(self):
        queryset = Payment.objects.select_related("order", "received_by", "payment_method", "reporting_payment_method")
        order_id = self.request.query_params.get("order_id")
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset


    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.validated_data["order"]
        order = order.__class__.objects.select_for_update().get(pk=order.pk)
        existing_applied_cents = sum(
            to_cents(p.amount_applied if p.amount_applied is not None else p.amount)
            for p in Payment.objects.select_for_update().filter(order=order)
        )
        due_cents = to_cents(order.total)
        order.amount_due_cents = due_cents
        remaining_cents = max(due_cents - existing_applied_cents, 0)
        requested_applied_cents = to_cents(serializer.validated_data.get("amount"))
        tip_cents = to_cents(serializer.validated_data.get("tip_amount"))
        if remaining_cents <= 0:
            return Response({"detail": "Order is already paid"}, status=status.HTTP_400_BAD_REQUEST)
        if requested_applied_cents > remaining_cents + 1:
            return Response({"detail": "Payment exceeds remaining balance"}, status=status.HTTP_400_BAD_REQUEST)
        applied_cents = remaining_cents if requested_applied_cents > remaining_cents else requested_applied_cents
        method = str(serializer.validated_data.get("method") or "").strip().lower()
        cash_received = serializer.validated_data.get("cash_received")
        received_cents = to_cents(cash_received) if method == "cash" and cash_received is not None else applied_cents + tip_cents
        if method == "cash" and received_cents < applied_cents + tip_cents:
            return Response({"detail": "Cash received must cover amount + tip"}, status=status.HTTP_400_BAD_REQUEST)
        change_cents = max(received_cents - (applied_cents + tip_cents), 0)
        if order.financial_locked_at is None:
            order.financial_locked_at = timezone.now()
            order.save(update_fields=["amount_due_cents", "financial_locked_at", "updated_at"])
        payment = serializer.save(
            cash_session=_get_open_session(request.user),
            amount=from_cents(applied_cents),
            amount_applied=from_cents(applied_cents),
            amount_received=from_cents(received_cents),
            change_amount=from_cents(change_cents),
            amount_applied_cents=applied_cents,
            amount_received_cents=received_cents,
            change_cents=change_cents,
            tip_cents=tip_cents,
            cash_received=from_cents(received_cents) if method == "cash" else None,
        )
        _create_transaction_for_payment(payment, request.user)
        logger.info(
            "payment.created order_id=%s payment_id=%s amount=%s method=%s",
            payment.order_id,
            payment.id,
            payment.amount,
            payment.method,
        )
        payment.order.recalculate_financials()
        total_paid_cents = sum(
            to_cents(p.amount_applied if p.amount_applied is not None else p.amount)
            for p in Payment.objects.filter(order=payment.order)
        )
        remaining_cents = max((payment.order.amount_due_cents or to_cents(payment.order.total)) - total_paid_cents, 0)
        remaining = from_cents(remaining_cents)
        log_audit(
            request,
            "payment.create",
            "Payment",
            payment.id,
            {
                "order_id": payment.order_id,
                "method": payment.method,
                "amount": str(payment.amount),
                "tip_amount": str(payment.tip_amount),
            },
        )
        print_result = {"printed": False, "print_error": None, "drawer_opened": False, "drawer_error": None}
        dte_meta = {"dte_status": None, "dte_record_id": None, "dte_outbox_id": None, "dte_last_error": None}

        if remaining <= 0:
            persist_sale_snapshot(payment.order)
            log_audit(
                request,
                "payment.completed",
                "Order",
                payment.order_id,
                {"order_id": payment.order_id},
            )
            should_send_to_kitchen = bool(payment.order.requires_kitchen and payment.order.send_to_kitchen)
            if should_send_to_kitchen:
                if payment.order.status != "preparing":
                    payment.order.status = "preparing"
                    payment.order.save(update_fields=["status", "updated_at"])
                from apps.kitchen.models import KitchenOrderView
                KitchenOrderView.objects.get_or_create(
                    order=payment.order,
                    defaults={"service_type": payment.order.service_type, "status": "preparing"},
                )
            else:
                if payment.order.status != "delivered":
                    payment.order.status = "delivered"
                    payment.order.save(update_fields=["status", "updated_at"])
            def _after_commit_dte():
                def _enqueue_dte_async():
                    try:
                        logger.info("payment.dte.trigger order_id=%s payment_id=%s", payment.order_id, payment.id)
                        dte_record = send_dte_for_order(payment.order, payment=payment, queue_only=True)
                        persist_sale_snapshot(payment.order)
                        outbox = dte_record.outbox_entries.order_by("-created_at").first()
                        status_map = {
                            "PENDING": "QUEUED",
                            "ACCEPTED": "SENT",
                            "REJECTED": "FAILED",
                            "FAILED": "FAILED",
                        }
                        dte_meta["dte_status"] = status_map.get(dte_record.status, "QUEUED")
                        dte_meta["dte_record_id"] = dte_record.id
                        dte_meta["dte_outbox_id"] = outbox.id if outbox else None
                        dte_meta["dte_last_error"] = (outbox.error_message if outbox else "") or (dte_record.error_message or "")
                        logger.info(
                            "payment.dte.queued order_id=%s payment_id=%s dte_status=%s outbox_id=%s",
                            payment.order_id,
                            payment.id,
                            dte_record.status,
                            dte_meta["dte_outbox_id"],
                        )
                    except Exception as exc:  # noqa: BLE001 - fiscal send must not break payment completion
                        logger.exception("payment.dte.failed order_id=%s payment_id=%s", payment.order_id, payment.id)
                        dte_meta["dte_status"] = "FAILED"
                        dte_meta["dte_last_error"] = str(exc)
                try:
                    threading.Thread(target=_enqueue_dte_async, daemon=True, name=f"dte-enqueue-{payment.id}").start()
                except Exception:
                    _enqueue_dte_async()
            transaction.on_commit(_after_commit_dte)
        else:
            log_audit(
                request,
                "payment.partial",
                "Order",
                payment.order_id,
                {"order_id": payment.order_id, "remaining": str(remaining)},
            )

        data = dict(serializer.data)
        data["printed"] = bool(print_result["printed"])
        data["print_error"] = print_result["print_error"]
        data["drawer_opened"] = bool(print_result["drawer_opened"])
        data["drawer_error"] = print_result["drawer_error"]
        if remaining <= 0 and hasattr(payment.order, "invoice"):
            data["invoice_status"] = payment.order.invoice.status
            data["invoice_id"] = payment.order.invoice.id
            data["dte_status"] = dte_meta["dte_status"] or "QUEUED"
            data["dte_record_id"] = dte_meta["dte_record_id"]
            data["dte_outbox_id"] = dte_meta["dte_outbox_id"]
            data["dte_last_error"] = dte_meta["dte_last_error"]
        return Response(data, status=status.HTTP_201_CREATED)


class PaymentInternalMethodUpdateView(APIView):
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def patch(self, request, pk: int):
        payment = (
            Payment.objects.select_related("order", "payment_method", "reporting_payment_method")
            .filter(pk=pk)
            .first()
        )
        if not payment:
            return Response({"detail": "Pago no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        order = payment.order
        if order.financial_status in {"voided", "refunded_partial", "refunded_full"} or order.refunds.exists():
            return Response(
                {"detail": "No se puede corregir método en órdenes anuladas o con reembolso."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = InternalPaymentMethodChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_method: PaymentMethod = serializer.context["new_method"]
        reason = (serializer.validated_data.get("reason") or "").strip()
        previous_method = payment.reporting_payment_method or payment.payment_method
        if previous_method and previous_method.id == new_method.id:
            return Response({"detail": "El método seleccionado ya está aplicado."}, status=status.HTTP_400_BAD_REQUEST)

        payment.reporting_payment_method = new_method
        payment.save(update_fields=["reporting_payment_method"])

        PaymentMethodChangeLog.objects.create(
            payment=payment,
            old_payment_method=previous_method,
            new_payment_method=new_method,
            changed_by=request.user,
            reason=reason,
        )

        log_audit(
            request,
            "payment.internal_method.change",
            "Payment",
            payment.id,
            {
                "order_id": payment.order_id,
                "old_method": previous_method.code if previous_method else None,
                "new_method": new_method.code,
                "reason": reason,
            },
        )

        return Response(
            {
                "id": payment.id,
                "order_id": payment.order_id,
                "payment_method_code": new_method.code,
                "payment_method_name": new_method.name,
                "detail": "Método de pago interno actualizado.",
            },
            status=status.HTTP_200_OK,
        )


class PaymentRecordRefundView(APIView):
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def post(self, request, pk: int):
        payment = Payment.objects.select_related("order", "payment_method", "reporting_payment_method").filter(pk=pk).first()
        if not payment:
            return Response({"detail": "Pago no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        order = payment.order
        if order.financial_status in {"voided", "refunded_partial", "refunded_full"}:
            return Response({"detail": "La venta ya fue anulada o reembolsada."}, status=status.HTTP_400_BAD_REQUEST)

        reason = (request.data.get("reason") or "").strip() or "Reembolso desde registros"
        record = DTERecord.objects.filter(order=order, status=DTERecord.STATUS_ACCEPTED).order_by("-created_at").first()
        if not record:
            return Response({"detail": "No existe DTE aceptado para esta venta."}, status=status.HTTP_400_BAD_REQUEST)

        dte_type = (record.dte_type or "").upper()
        issued_at = resolve_issued_at(record)
        should_credit_note = dte_type.startswith("CCF") and (timezone.now() - issued_at).total_seconds() > 24 * 3600

        if should_credit_note:
            note = CreditNote.objects.create(
                order=order,
                original_dte_record=record,
                motivo=reason,
                total=record.total_amount,
                dte_numero_control=record.control_number,
                dte_codigo_generacion=record.codigo_generacion,
                items=[],
                status=DTERecord.STATUS_PENDING,
            )
            send_dte_for_credit_note(note)
            dte_action = {"action": "credit_note", "credit_note_id": note.id}
        else:
            invalidation = DTEInvalidation.objects.create(
                order=order,
                dte_record=record,
                motivo=reason,
                tipo_anulacion="total",
                status=DTERecord.STATUS_PENDING,
            )
            result = invalidate_dte_for_order(order, motivo=reason, responsable_dui="", solicitante_dui="")
            if not result.get("success"):
                return Response({"detail": result.get("error") or "No se pudo invalidar DTE."}, status=status.HTTP_400_BAD_REQUEST)
            record.status = DTERecord.STATUS_INVALIDATED
            record.save(update_fields=["status", "updated_at"])
            invalidation.status = DTERecord.STATUS_INVALIDATED
            invalidation.save(update_fields=["status", "updated_at"])
            dte_action = {"action": "invalidate", "invalidation_id": invalidation.id}

        effective_method = payment.reporting_payment_method or payment.payment_method
        refund = Refund.objects.create(
            order=order,
            payment_method=effective_method,
            original_payment=payment,
            cash_session=_get_open_session_for_branch(order.branch_id),
            method=payment.method if payment.method in {"cash", "card", "transfer"} else "transfer",
            amount=payment.amount,
            tip_refunded=payment.tip_amount or Decimal("0"),
            reason=reason,
            approved_by=request.user,
            created_by=request.user,
        )
        order.recalculate_financials()
        if _refund_is_cash(method=refund.method, payment_method=refund.payment_method, original_payment=payment) and refund.cash_session:
            _create_cash_out_for_refund(refund, request.user)

        log_audit(
            request,
            "payment.record_refund",
            "Refund",
            refund.id,
            {"payment_id": payment.id, "order_id": order.id, "reason": reason, **dte_action},
        )
        return Response(
            {
                "detail": "Venta reembolsada correctamente.",
                "refund_id": refund.id,
                "order": OrderSerializer(order, context={"request": request}).data,
                **dte_action,
            },
            status=status.HTTP_201_CREATED,
        )


class RefundListCreateView(generics.ListCreateAPIView):
    serializer_class = RefundSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        queryset = Refund.objects.select_related(
            "order",
            "original_payment",
            "cash_session",
            "approved_by",
            "created_by",
        )
        order_id = self.request.query_params.get("order_id")
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("refund.create.bad_request errors=%s payload=%s", serializer.errors, request.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        order = validated["order"]
        original_payment = validated.get("original_payment")
        payment_method = validated.get("payment_method")
        method = validated.get("method")
        is_cash_refund = _refund_is_cash(method=method, payment_method=payment_method, original_payment=original_payment)
        cash_session = _get_open_session_for_branch(order.branch_id)
        if is_cash_refund and not cash_session:
            return Response({"detail": "No hay caja abierta para registrar el reembolso."}, status=status.HTTP_400_BAD_REQUEST)

        refund = serializer.save(
            cash_session=cash_session,
            approved_by=request.user,
            created_by=request.user,
        )
        refund.order.recalculate_financials()
        cash_tx = None
        if is_cash_refund:
            cash_tx, created = _create_cash_out_for_refund(refund, request.user)
            logger.info(
                "cashier.refund.cash_out.created refund_id=%s session_id=%s amount=%s branch_id=%s created=%s",
                refund.id,
                cash_tx.session_id,
                cash_tx.amount,
                refund.order.branch_id,
                created,
            )
        else:
            cash_tx, _ = _create_non_cash_transaction_for_refund(refund, request.user)

        log_audit(
            request,
            "refund.create",
            "Refund",
            refund.id,
            {
                "order_id": refund.order_id,
                "amount": str(refund.amount),
                "tip_refunded": str(refund.tip_refunded),
                "method": refund.method,
                "reason": refund.reason,
                "shift_id": cash_session.id if cash_session else None,
                "approved_by": request.user.id,
                "cash_transaction_id": cash_tx.id if cash_tx else None,
            },
        )

        job = create_refund_print_job(refund, requested_by=request.user)
        return Response(
            {
                "refund": RefundSerializer(refund).data,
                "order": OrderSerializer(refund.order).data,
                "print_job": PrintJobSerializer(job).data,
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentPrintTicketView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def post(self, request, pk: int):
        payment = Payment.objects.select_related("order").filter(pk=pk).first()
        if not payment:
            return Response({"detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)
        context = {
            "order_id": payment.order_id,
            "payment_id": payment.id,
            "user_id": getattr(request.user, "id", None),
            "endpoint": "payments.print-ticket",
        }
        try:
            exists = PrintJob.objects.filter(order=payment.order, type="customer", meta__event="payment.paid").exists()
            if not exists:
                create_print_job(payment.order, "customer", requested_by=request.user, event="payment.paid")
            payload = render_customer_ticket(payment.order)
            printer = SystemPrinterService()
            print_result = printer.print_with_pdf_fallback(
                payload.get("text", ""),
                order_id=payment.order_id,
                payment_id=payment.id,
                pdf_kwargs={
                    "logo_path": payload.get("meta", {}).get("logo_path"),
                    "qr_value": payload.get("meta", {}).get("public_url"),
                    "receipt_context": payload.get("meta", {}).get("receipt_context"),
                    "suppress_qr_url_lines": True,
                },
                context=context,
                endpoint="payments.print-ticket",
            )

            drawer_opened = False
            drawer_error = None
            should_open_drawer = payment.method == "cash" and bool(print_result["printed"])
            if should_open_drawer:
                drawer_opened, drawer_error = printer.open_cash_drawer(context=context, endpoint="payments.print-ticket.drawer")
            elif payment.method == "cash" and not print_result["printed"]:
                drawer_error = "No se pudo abrir la gaveta: impresora no detectada."
            job = PrintJob.objects.filter(order=payment.order, type="customer").order_by("-created_at").first()
            if job:
                if print_result["receipt_pdf_path"]:
                    job.content_pdf_path = str(print_result["receipt_pdf_path"])
                if print_result["printed"]:
                    job.status = "printed"
                else:
                    job.status = "failed"
                    job.error_message = print_result["print_error"] or ""
                job.save(update_fields=["status", "content_pdf_path", "error_message"])

            if print_result["receipt_pdf_path"]:
                with open(print_result["receipt_pdf_path"], "rb") as fh:
                    pdf_bytes = fh.read()
                response = HttpResponse(pdf_bytes, content_type="application/pdf")
                response["Content-Disposition"] = f'attachment; filename="{_venta_pdf_filename(payment.order)}"'
                response["X-Printed"] = "0"
                response["X-Print-Error"] = str(print_result["print_error"] or "")
                response["X-Drawer-Opened"] = "1" if drawer_opened else "0"
                response["X-Drawer-Error"] = str(drawer_error or "")
                response["X-Ticket-Fallback"] = "1"
                return response

            return Response(
                {
                    "printed": bool(print_result["printed"]),
                    "print_error": print_result["print_error"],
                    "receipt_pdf_url": print_result["receipt_pdf_url"],
                    "drawer_opened": bool(drawer_opened),
                    "drawer_error": drawer_error,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("payment.print.exception", extra={"payment_id": payment.id, "order_id": payment.order_id})
            return Response({"printed": False, "print_error": str(exc), "drawer_opened": False, "drawer_error": None}, status=status.HTTP_200_OK)


class PaymentTicketPDFView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return renderer, renderer.media_type

    def get(self, request, pk: int):
        payment = Payment.objects.select_related("order").filter(pk=pk).first()
        if not payment:
            return Response({"detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)
        payload = render_customer_ticket(payment.order)
        filename = _venta_pdf_filename(payment.order)
        result = build_receipt_pdf_from_text(
            text=payload.get("text", ""),
            filename=filename,
            logo_path=payload.get("meta", {}).get("logo_path"),
            qr_value=payload.get("meta", {}).get("public_url"),
            receipt_context=payload.get("meta", {}).get("receipt_context"),
            suppress_qr_url_lines=True,
        )
        response = HttpResponse(result.pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{result.filename}"'
        return response
