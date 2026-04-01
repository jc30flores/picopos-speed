from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from django.conf import settings

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
    def _parse_hex_bytes(self, value: str) -> bytes:
        chunks = [chunk for chunk in value.replace(",", " ").split() if chunk]
        if not chunks:
            raise ValueError("empty pulse command")
        return bytes(int(chunk, 16) for chunk in chunks)

    def _default_pulse_command(self, variant: int, on: int, off: int) -> bytes:
        return bytes((0x1B, 0x70, variant, on, off))

    def _build_pulse_command(self, *, variant: int | None = None, on: int | None = None, off: int | None = None) -> tuple[bytes, int, int, int]:
        final_variant = int(variant if variant is not None else (getattr(settings, "CASH_DRAWER_KICK_VARIANT", 0) or 0))
        final_on = int(on if on is not None else (getattr(settings, "CASH_DRAWER_KICK_ON", 25) or 25))
        final_off = int(off if off is not None else (getattr(settings, "CASH_DRAWER_KICK_OFF", 250) or 250))
        if getattr(settings, "CASH_DRAWER_PULSE_COMMAND", ""):
            try:
                return self._parse_hex_bytes(settings.CASH_DRAWER_PULSE_COMMAND), final_variant, final_on, final_off
            except Exception as exc:
                raise CashDrawerError("Invalid CASH_DRAWER_PULSE_COMMAND format") from exc
        return self._default_pulse_command(final_variant, final_on, final_off), final_variant, final_on, final_off

    def _missing_configuration(self) -> list[str]:
        required = {
            "USB_VENDOR_ID": getattr(settings, "CASH_DRAWER_USB_VENDOR_ID", None) or getattr(settings, "RECEIPT_PRINTER_USB_VENDOR_ID", None) or getattr(settings, "PRINTER_USB_VENDOR_ID", None),
            "USB_PRODUCT_ID": getattr(settings, "CASH_DRAWER_USB_PRODUCT_ID", None) or getattr(settings, "RECEIPT_PRINTER_USB_PRODUCT_ID", None) or getattr(settings, "PRINTER_USB_PRODUCT_ID", None),
            "USB_INTERFACE": getattr(settings, "CASH_DRAWER_USB_INTERFACE", None) or getattr(settings, "RECEIPT_PRINTER_USB_INTERFACE", None) or getattr(settings, "PRINTER_USB_INTERFACE", None),
        }
        return [name for name, value in required.items() if value is None]

    def _open_drawer_usb(self, *, variant: int | None = None, on: int | None = None, off: int | None = None) -> CashDrawerOpenResult:
        try:
            import usb.core
            import usb.util
        except Exception as exc:  # pragma: no cover
            raise CashDrawerRuntimeError("pyusb is not available in this environment") from exc

        missing = self._missing_configuration()
        if missing:
            raise CashDrawerError(f"Printer not configured. Missing: {', '.join(missing)}")

        vendor_id = int(getattr(settings, "CASH_DRAWER_USB_VENDOR_ID", None) or getattr(settings, "RECEIPT_PRINTER_USB_VENDOR_ID", None) or getattr(settings, "PRINTER_USB_VENDOR_ID", 0))
        product_id = int(getattr(settings, "CASH_DRAWER_USB_PRODUCT_ID", None) or getattr(settings, "RECEIPT_PRINTER_USB_PRODUCT_ID", None) or getattr(settings, "PRINTER_USB_PRODUCT_ID", 0))
        interface_number = int(getattr(settings, "CASH_DRAWER_USB_INTERFACE", None) or getattr(settings, "RECEIPT_PRINTER_USB_INTERFACE", None) or getattr(settings, "PRINTER_USB_INTERFACE", 0))
        configured_out_ep = getattr(settings, "CASH_DRAWER_USB_OUT_ENDPOINT", None) or getattr(settings, "RECEIPT_PRINTER_USB_OUT_ENDPOINT", None) or getattr(settings, "PRINTER_USB_OUT_ENDPOINT", None)
        configured_in_ep = settings.CASH_DRAWER_USB_IN_ENDPOINT
        pulse_command, final_variant, final_on, final_off = self._build_pulse_command(variant=variant, on=on, off=off)

        device = usb.core.find(idVendor=vendor_id, idProduct=product_id)
        if device is None:
            raise CashDrawerRuntimeError("Printer not found on USB bus")

        detached_kernel = False
        out_endpoint_address = None
        in_endpoint_address = configured_in_ep if configured_in_ep is not None else None

        try:
            device.set_configuration()
            config = device.get_active_configuration()
            interface = usb.util.find_descriptor(config, bInterfaceNumber=interface_number)
            if interface is None:
                raise CashDrawerError(f"Configured interface not found: {interface_number}")

            try:
                if device.is_kernel_driver_active(interface_number):
                    device.detach_kernel_driver(interface_number)
                    detached_kernel = True
            except (NotImplementedError, usb.core.USBError):
                pass

            if configured_out_ep is not None:
                out_endpoint_address = int(configured_out_ep)
            else:
                bulk_out = usb.util.find_descriptor(
                    interface,
                    custom_match=lambda endpoint: usb.util.endpoint_direction(endpoint.bEndpointAddress) == usb.util.ENDPOINT_OUT
                    and usb.util.endpoint_type(endpoint.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK,
                )
                if bulk_out is None:
                    raise CashDrawerError("No BULK OUT endpoint found on configured interface")
                out_endpoint_address = int(bulk_out.bEndpointAddress)

            attempts = 0
            while attempts < 2:
                attempts += 1
                try:
                    device.write(out_endpoint_address, pulse_command)
                    break
                except usb.core.USBError as exc:
                    if attempts >= 2:
                        raise
                    if "busy" in str(exc).lower() or "resource" in str(exc).lower():
                        time.sleep(0.15)
                        continue
                    raise

            return CashDrawerOpenResult(
                success=True,
                message="Pulso enviado a la gaveta",
                vendor_id=vendor_id,
                product_id=product_id,
                interface=interface_number,
                out_endpoint=out_endpoint_address,
                variant=final_variant,
                on=final_on,
                off=final_off,
                command_hex=pulse_command.hex(),
            )
        except CashDrawerError:
            raise
        except usb.core.USBError as exc:
            raise CashDrawerRuntimeError(f"USBError: {exc}") from exc
        except Exception as exc:
            raise CashDrawerRuntimeError(f"Unexpected USB error: {exc}") from exc
        finally:
            try:
                usb.util.dispose_resources(device)
            except Exception:
                logger.debug("Unable to dispose USB resources cleanly", exc_info=True)
            if detached_kernel:
                try:
                    device.attach_kernel_driver(interface_number)
                except Exception:
                    logger.debug("Unable to re-attach USB kernel driver", exc_info=True)

    def open_drawer(self, *, variant: int | None = None, on: int | None = None, off: int | None = None) -> CashDrawerOpenResult:
        if not settings.CASH_DRAWER_ENABLED:
            return CashDrawerOpenResult(success=False, error="DISABLED", message="Integración de gaveta deshabilitada")

        mode = (settings.CASH_DRAWER_MODE or "mock").lower()
        if mode == "mock":
            logger.info("cash_drawer.open.mock_pulse")
            pulse, final_variant, final_on, final_off = self._build_pulse_command(variant=variant, on=on, off=off)
            return CashDrawerOpenResult(
                success=True,
                message="Pulso enviado a la gaveta",
                vendor_id=0,
                product_id=0,
                interface=0,
                out_endpoint=0,
                variant=final_variant,
                on=final_on,
                off=final_off,
                command_hex=pulse.hex(),
            )
        if mode != "usb":
            return CashDrawerOpenResult(success=False, error="MODE", message=f"Modo no soportado: {mode}")
        try:
            return self._open_drawer_usb(variant=variant, on=on, off=off)
        except CashDrawerRuntimeError as exc:
            logger.warning("cash_drawer.open.runtime_error error=%s", exc)
            return CashDrawerOpenResult(success=False, error="RUNTIME", message=str(exc), variant=int(variant or 0), on=int(on or 25), off=int(off or 250))
        except CashDrawerError as exc:
            logger.warning("cash_drawer.open.config_error error=%s", exc)
            return CashDrawerOpenResult(success=False, error="CONFIG", message=str(exc), variant=int(variant or 0), on=int(on or 25), off=int(off or 250))
        except Exception as exc:  # noqa: BLE001
            logger.warning("cash_drawer.open.error error=%s", exc)
            return CashDrawerOpenResult(success=False, error="UNKNOWN", message="No se pudo enviar pulso a la gaveta", variant=int(variant or 0), on=int(on or 25), off=int(off or 250))

    def status(self) -> dict[str, object]:
        missing = self._missing_configuration()
        configured = len(missing) == 0
        return {
            "enabled": bool(settings.CASH_DRAWER_ENABLED),
            "mode": settings.CASH_DRAWER_MODE,
            "configured": configured,
            "missing": missing,
            "vendor_id": settings.CASH_DRAWER_USB_VENDOR_ID,
            "product_id": settings.CASH_DRAWER_USB_PRODUCT_ID,
            "interface": settings.CASH_DRAWER_USB_INTERFACE,
            "out_endpoint": settings.CASH_DRAWER_USB_OUT_ENDPOINT,
            "in_endpoint": settings.CASH_DRAWER_USB_IN_ENDPOINT,
        }
