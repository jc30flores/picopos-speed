from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


class USBPrinterService:
    def _config(self) -> dict[str, int | str | bool | None]:
        mode = getattr(settings, "RECEIPT_PRINTER_MODE", getattr(settings, "PRINTER_MODE", "mock"))
        return {
            "mode": (mode or "mock").lower(),
            "vendor_id": getattr(settings, "RECEIPT_PRINTER_USB_VENDOR_ID", getattr(settings, "PRINTER_USB_VENDOR_ID", None)),
            "product_id": getattr(settings, "RECEIPT_PRINTER_USB_PRODUCT_ID", getattr(settings, "PRINTER_USB_PRODUCT_ID", None)),
            "interface": getattr(settings, "RECEIPT_PRINTER_USB_INTERFACE", getattr(settings, "PRINTER_USB_INTERFACE", None)),
            "out_endpoint": getattr(settings, "RECEIPT_PRINTER_USB_OUT_ENDPOINT", getattr(settings, "PRINTER_USB_OUT_ENDPOINT", None)),
            "cut_enabled": bool(getattr(settings, "RECEIPT_PRINTER_CUT_ENABLED", True)),
            "enabled": bool(getattr(settings, "PRINTER_ENABLED", getattr(settings, "CASH_DRAWER_ENABLED", False))),
        }

    def print_text(self, text: str) -> tuple[bool, str | None]:
        cfg = self._config()
        if not cfg["enabled"]:
            return False, "Printer integration is disabled"

        mode = cfg["mode"]
        if mode == "mock":
            logger.info("receipt_printer.mock_output\n%s", text)
            return True, None
        if mode != "usb":
            return False, f"Unsupported RECEIPT_PRINTER_MODE: {mode}"
        return self._print_text_usb(text, cfg)

    def _print_text_usb(self, text: str, cfg: dict[str, int | str | bool | None]) -> tuple[bool, str | None]:
        required = {
            "RECEIPT_PRINTER_USB_VENDOR_ID": cfg["vendor_id"],
            "RECEIPT_PRINTER_USB_PRODUCT_ID": cfg["product_id"],
            "RECEIPT_PRINTER_USB_INTERFACE": cfg["interface"],
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            return False, f"Printer not configured. Missing: {', '.join(missing)}"

        try:
            import usb.core
            import usb.util
        except Exception:
            return False, "pyusb is not available"

        vendor_id = int(cfg["vendor_id"])
        product_id = int(cfg["product_id"])
        interface_number = int(cfg["interface"])
        out_endpoint = int(cfg["out_endpoint"] or 0)

        device = usb.core.find(idVendor=vendor_id, idProduct=product_id)
        if device is None:
            return False, "Printer device not found"

        detached = False
        try:
            device.set_configuration()
            config = device.get_active_configuration()
            interface = usb.util.find_descriptor(config, bInterfaceNumber=interface_number)
            if interface is None:
                return False, f"Interface {interface_number} not found"

            try:
                if device.is_kernel_driver_active(interface_number):
                    device.detach_kernel_driver(interface_number)
                    detached = True
            except Exception:
                logger.debug("receipt_printer.kernel_driver_check_failed", exc_info=True)

            if out_endpoint == 0:
                bulk_out = usb.util.find_descriptor(
                    interface,
                    custom_match=lambda ep: usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT
                    and usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK,
                )
                if bulk_out is None:
                    return False, "No BULK OUT endpoint found"
                out_endpoint = int(bulk_out.bEndpointAddress)

            payload = bytearray()
            payload.extend(b"\x1b\x40")
            payload.extend(text.encode("utf-8", errors="replace"))
            payload.extend(b"\n\n\n")
            device.write(out_endpoint, bytes(payload))
            if cfg["cut_enabled"]:
                device.write(out_endpoint, b"\x1d\x56\x41\x00")
            return True, None
        except usb.core.USBError as exc:
            return False, f"USBError: {exc}"
        except Exception as exc:
            return False, str(exc)
        finally:
            try:
                usb.util.dispose_resources(device)
            except Exception:
                logger.debug("receipt_printer.dispose_failed", exc_info=True)
            if detached:
                try:
                    device.attach_kernel_driver(interface_number)
                except Exception:
                    logger.debug("receipt_printer.attach_driver_failed", exc_info=True)

    def _logo_image(self, logo_path: str | None):
        if not logo_path:
            return None
        try:
            from PIL import Image

            path = Path(logo_path)
            if not path.exists():
                return None
            max_width = int(getattr(settings, "RECEIPT_LOGO_MAX_WIDTH_PX", 560))
            with Image.open(path) as original:
                image = original.convert("L")
                if image.width > max_width:
                    ratio = max_width / float(image.width)
                    target_h = max(1, int(image.height * ratio))
                    image = image.resize((max_width, target_h))
                return image.convert("1")
        except Exception:
            logger.warning("receipt_printer.logo_unavailable", exc_info=True)
            return None

    def _qr_image(self, public_url: str):
        try:
            import qrcode
            from PIL import Image

            qr = qrcode.QRCode(version=None, box_size=8, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
            qr.add_data(public_url)
            qr.make(fit=True)
            image = qr.make_image(fill_color="black", back_color="white").convert("L")
            max_w = int(getattr(settings, "RECEIPT_QR_MAX_WIDTH_PX", 280))
            if image.width > max_w:
                image = image.resize((max_w, max_w))
            return image.convert("1")
        except Exception:
            logger.warning("receipt_printer.qr_image_failed", exc_info=True)
            return None

    def print_receipt(self, payload: dict) -> tuple[bool, str | None]:
        text = str(payload.get("text") or "")
        cfg = self._config()
        if not cfg["enabled"]:
            return False, "Printer integration is disabled"
        if cfg["mode"] == "mock":
            logger.info("receipt_printer.mock_output\n%s", text)
            return True, None
        if cfg["mode"] != "usb":
            return False, f"Unsupported RECEIPT_PRINTER_MODE: {cfg['mode']}"

        meta = payload.get("meta") or {}
        ctx = meta.get("receipt_context") or {}
        if meta.get("type") != "customer" or not ctx:
            return self._print_text_usb(text, cfg)

        try:
            from escpos.printer import Usb
        except Exception:
            return self._print_text_usb(text, cfg)

        try:
            printer = Usb(
                idVendor=int(cfg["vendor_id"]),
                idProduct=int(cfg["product_id"]),
                interface=int(cfg["interface"]),
                out_ep=(int(cfg["out_endpoint"]) if cfg["out_endpoint"] is not None else None),
                timeout=0,
            )
            logo = self._logo_image(ctx.get("logo_path"))
            if logo is not None:
                printer.set(align="center")
                printer.image(logo, impl="bitImageRaster")
                printer.text("\n")

            printer.set(align="center", bold=True)
            printer.text(f"{ctx.get('tagline', '')}\n")
            printer.text(f"{ctx.get('restaurant_name', '')}\n")
            if ctx.get("address"):
                printer.text(f"{ctx['address']}\n")
            if ctx.get("phone"):
                printer.text(f"Tel: {ctx['phone']}\n")
            printer.text("-" * 42 + "\n")
            printer.set(align="center", bold=True, width=2, height=2)
            printer.text(f"{ctx.get('service_type_label', '')}\n")
            printer.set(align="left", bold=False, width=1, height=1)
            printer.text(f"Atendido por: {ctx.get('cashier_name', '-')}\n")
            printer.text(f"Orden #{ctx.get('order_number', '-')}\n")
            printer.text(f"{ctx.get('order_datetime').strftime('%Y-%m-%d %H:%M')}\n")
            printer.text("-" * 42 + "\n")
            printer.text("CANT DESCRIPCION           P.UNIT     TOTAL\n")
            printer.text("-" * 42 + "\n")
            for item in ctx.get("items", []):
                qty = str(item.get("qty", ""))[:3].ljust(3)
                name = str(item.get("name", ""))[:20].ljust(20)
                unit = f"${Decimal(item.get('unit_price', 0)):.2f}".rjust(8)
                total = f"${Decimal(item.get('line_total', 0)):.2f}".rjust(9)
                printer.text(f"{qty} {name} {unit} {total}\n")
            totals = ctx.get("totals", {})
            printer.text("-" * 42 + "\n")
            subtotal_txt = f"${Decimal(totals.get('subtotal', 0)):.2f}"
            iva_txt = f"${Decimal(totals.get('iva', 0)):.2f}"
            total_txt = f"${Decimal(totals.get('total', 0)):.2f}"
            printer.text(f"Subtotal:{subtotal_txt.rjust(32)}\n")
            printer.text(f"IVA:{iva_txt.rjust(37)}\n")
            iva_rete1 = Decimal(totals.get("iva_rete1", 0))
            if iva_rete1 > 0:
                printer.text(f"IVA Retenido 1%:{f'${iva_rete1:.2f}'.rjust(26)}\n")
            printer.text(f"Total:{total_txt.rjust(35)}\n")
            payment = ctx.get("payment", {})
            printer.text("-" * 42 + "\n")
            printer.text(f"Metodo de pago: {payment.get('method_label_es', '-')}\n")
            printer.text(f"Monto pagado: ${Decimal(payment.get('amount_paid', 0)):.2f}\n")
            printer.text("-" * 42 + "\n")
            dte = ctx.get("dte", {})
            printer.text("Datos DTE\n")
            printer.text(f"No. Control: {dte.get('numero_control') or '-'}\n")
            printer.text(f"Codigo Gen: {dte.get('codigo_generacion') or '-'}\n")
            printer.text(f"Fecha DTE: {dte.get('fecha_dte') or '-'}\n")
            printer.set(align="center")
            public_url = str(ctx.get("public_url") or "")
            qr_printed = False
            if public_url:
                try:
                    printer.qr(public_url, size=7, ec=2)
                    qr_printed = True
                except Exception:
                    logger.warning("receipt_printer.native_qr_failed", exc_info=True)
                if not qr_printed:
                    qr_img = self._qr_image(public_url)
                    if qr_img is not None:
                        printer.image(qr_img, impl="bitImageRaster")
                        qr_printed = True
                printer.text("\n")
                printer.set(align="left")
                printer.text(f"{public_url}\n")
            printer.set(align="center", bold=True)
            printer.text("Gracias por su visita\n")
            printer.text(f"Order No: {ctx.get('order_number', '-')}\n")
            printer.text(f"{ctx.get('order_datetime').strftime('%Y-%m-%d %H:%M')}\n")
            printer.text("\n\n")
            if cfg["cut_enabled"]:
                printer.cut()
            printer.close()
            return True, None
        except Exception as exc:
            logger.warning("receipt_printer.rich_receipt_failed", exc_info=True)
            return self._print_text_usb(text, cfg)
