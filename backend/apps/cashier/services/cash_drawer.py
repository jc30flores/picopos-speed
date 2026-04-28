from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

from apps.printing.services.system_printer import DRAWER_RAW_COMMAND, SystemPrinterService

logger = logging.getLogger(__name__)


class CashDrawerError(Exception):
    pass


class CashDrawerRuntimeError(CashDrawerError):
    pass


@dataclass
class CashDrawerOpenResult:
    success: bool
    message: str = ""
    error: str = ""
    vendor_id: int | None = None
    product_id: int | None = None
    interface: int | None = None
    out_endpoint: int | None = None
    variant: int = 0
    on: int = 25
    off: int = 250
    command_hex: str = ""


class CashDrawerService:
    # kept for backwards compatibility in tests
    LEGACY_DRAWER_PRIME_BYTES = b"\n"

    def open_drawer(self, *, variant: int | None = None, on: int | None = None, off: int | None = None) -> CashDrawerOpenResult:
        if not settings.CASH_DRAWER_ENABLED:
            return CashDrawerOpenResult(success=False, error="DISABLED", message="Integración de gaveta deshabilitada")

        mode = (settings.CASH_DRAWER_MODE or "cups").lower()
        if mode == "mock":
            logger.info("cash_drawer.open.mock_pulse")
            return CashDrawerOpenResult(success=True, message="Gaveta abierta", vendor_id=0, product_id=0, interface=0, out_endpoint=0)
        if mode not in {"cups", "usb"}:
            return CashDrawerOpenResult(success=False, error="MODE", message=f"Modo no soportado: {mode}")

        service = SystemPrinterService()
        opened, error = service.open_cash_drawer(context={"event": "cashier.drawer.open"}, endpoint="cashier.drawer.open")
        if opened:
            return CashDrawerOpenResult(success=True, message="Gaveta abierta", command_hex=DRAWER_RAW_COMMAND)
        return CashDrawerOpenResult(success=False, error="RUNTIME", message=error or "No se pudo abrir la gaveta", command_hex=DRAWER_RAW_COMMAND)

    def status(self) -> dict[str, object]:
        service = SystemPrinterService()
        available = service.is_printer_available(context={"event": "cashier.drawer.status"}, endpoint="cashier.drawer.status")
        return {
            "enabled": bool(settings.CASH_DRAWER_ENABLED),
            "mode": (settings.CASH_DRAWER_MODE or "cups"),
            "configured": bool(available),
            "missing": [] if available else ["TSP143-(STR_T-001)"],
            "vendor_id": None,
            "product_id": None,
            "interface": None,
            "out_endpoint": None,
            "in_endpoint": None,
        }
