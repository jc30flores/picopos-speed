from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class CashDrawerError(Exception):
    pass


class CashDrawerService:
    TEST_LINE = "ABRIENDO CAJON DE DINERO.\n"

    def open_drawer(self, *, print_test_line: bool = True) -> None:
        if not settings.CASH_DRAWER_ENABLED:
            raise CashDrawerError("Printer not configured")

        mode = (settings.CASH_DRAWER_MODE or "mock").lower()
        if mode == "mock":
            if print_test_line:
                logger.info(self.TEST_LINE.strip())
            return
        if mode != "usb":
            raise CashDrawerError("Printer not configured")

        vendor_id = settings.CASH_DRAWER_VENDOR_ID
        product_id = settings.CASH_DRAWER_PRODUCT_ID
        if vendor_id is None or product_id is None:
            raise CashDrawerError("Printer not configured")

        try:
            from escpos.printer import Usb
        except Exception as exc:  # pragma: no cover - depends on OS/hardware libs
            raise CashDrawerError("Printer driver not available") from exc

        printer = None
        try:
            printer = Usb(
                idVendor=vendor_id,
                idProduct=product_id,
                interface=settings.CASH_DRAWER_INTERFACE,
                in_ep=settings.CASH_DRAWER_IN_EP,
                out_ep=settings.CASH_DRAWER_OUT_EP,
            )
            if print_test_line:
                printer.text(self.TEST_LINE)
            printer.cashdraw(
                pin=settings.CASH_DRAWER_PIN,
                on_ms=settings.CASH_DRAWER_PULSE_ON,
                off_ms=settings.CASH_DRAWER_PULSE_OFF,
            )
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
