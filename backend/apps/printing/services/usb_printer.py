from __future__ import annotations

import logging

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
