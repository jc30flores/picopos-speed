from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class CashDrawerError(Exception):
    pass


class CashDrawerService:
    TEST_LINE = "ABRIENDO CAJON DE DINERO.\n"

    def _validate_usb_config(self) -> tuple[int, int, int, int, int, int]:
        fields = {
            "CASH_DRAWER_VENDOR_ID": settings.CASH_DRAWER_VENDOR_ID,
            "CASH_DRAWER_PRODUCT_ID": settings.CASH_DRAWER_PRODUCT_ID,
            "CASH_DRAWER_INTERFACE": settings.CASH_DRAWER_INTERFACE,
            "CASH_DRAWER_IN_EP": settings.CASH_DRAWER_IN_EP,
            "CASH_DRAWER_OUT_EP": settings.CASH_DRAWER_OUT_EP,
            "CASH_DRAWER_PIN": settings.CASH_DRAWER_PIN,
        }
        missing = [name for name, value in fields.items() if value is None]
        if missing:
            raise CashDrawerError(f"Missing cash drawer configuration: {', '.join(missing)}")
        return (
            int(fields["CASH_DRAWER_VENDOR_ID"]),
            int(fields["CASH_DRAWER_PRODUCT_ID"]),
            int(fields["CASH_DRAWER_INTERFACE"]),
            int(fields["CASH_DRAWER_IN_EP"]),
            int(fields["CASH_DRAWER_OUT_EP"]),
            int(fields["CASH_DRAWER_PIN"]),
        )

    def open_drawer(self, *, print_test_line: bool = True) -> None:
        if not settings.CASH_DRAWER_ENABLED:
            raise CashDrawerError("Cash drawer integration is disabled")

        mode = (settings.CASH_DRAWER_MODE or "mock").lower()
        if mode == "mock":
            if print_test_line:
                logger.info(self.TEST_LINE.strip())
            return
        if mode != "usb":
            raise CashDrawerError(f"Unsupported CASH_DRAWER_MODE: {mode}")

        vendor_id, product_id, interface, in_ep, out_ep, pin = self._validate_usb_config()

        try:
            from escpos.printer import Usb
        except Exception as exc:  # pragma: no cover - depends on OS/hardware libs
            raise CashDrawerError("Printer driver not available") from exc

        printer = None
        try:
            printer = Usb(
                idVendor=vendor_id,
                idProduct=product_id,
                interface=interface,
                in_ep=in_ep,
                out_ep=out_ep,
            )
            if print_test_line:
                printer.text(self.TEST_LINE)
            printer.cashdraw(pin)
            printer.cut()
        except CashDrawerError:
            raise
        except Exception as exc:  # pragma: no cover - hardware-specific
            raise CashDrawerError("Unable to communicate with printer") from exc
        finally:
            if printer is not None:
                try:
                    printer.close()
                except Exception:
                    logger.warning("Unable to close cash drawer printer connection cleanly", exc_info=True)
