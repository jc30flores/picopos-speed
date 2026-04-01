from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)


class CashDrawerError(Exception):
    pass


class CashDrawerRuntimeError(CashDrawerError):
    pass


@dataclass
class CashDrawerOpenResult:
    vendor_id: int
    product_id: int
    interface: int
    out_endpoint: int
    in_endpoint: int | None


class CashDrawerService:
    def _parse_hex_bytes(self, value: str) -> bytes:
        chunks = [chunk for chunk in value.replace(",", " ").split() if chunk]
        if not chunks:
            raise ValueError("empty pulse command")
        return bytes(int(chunk, 16) for chunk in chunks)

    def _default_pulse_command(self, pin: int | None) -> bytes:
        drawer_selector = 0 if pin in (None, 2) else 1
        return bytes((0x1B, 0x70, drawer_selector, 0x19, 0xFA))

    def _build_pulse_command(self) -> bytes:
        if settings.CASH_DRAWER_PULSE_COMMAND:
            try:
                return self._parse_hex_bytes(settings.CASH_DRAWER_PULSE_COMMAND)
            except Exception as exc:
                raise CashDrawerError("Invalid CASH_DRAWER_PULSE_COMMAND format") from exc
        return self._default_pulse_command(settings.CASH_DRAWER_PIN)

    def _missing_configuration(self) -> list[str]:
        required = {
            "CASH_DRAWER_USB_VENDOR_ID": settings.CASH_DRAWER_USB_VENDOR_ID,
            "CASH_DRAWER_USB_PRODUCT_ID": settings.CASH_DRAWER_USB_PRODUCT_ID,
            "CASH_DRAWER_USB_INTERFACE": settings.CASH_DRAWER_USB_INTERFACE,
        }
        return [name for name, value in required.items() if value is None]

    def _open_drawer_usb(self) -> CashDrawerOpenResult:
        try:
            import usb.core
            import usb.util
        except Exception as exc:  # pragma: no cover
            raise CashDrawerRuntimeError("pyusb is not available in this environment") from exc

        missing = self._missing_configuration()
        if missing:
            raise CashDrawerError(f"Printer not configured. Missing: {', '.join(missing)}")

        vendor_id = int(settings.CASH_DRAWER_USB_VENDOR_ID)
        product_id = int(settings.CASH_DRAWER_USB_PRODUCT_ID)
        interface_number = int(settings.CASH_DRAWER_USB_INTERFACE)
        configured_out_ep = settings.CASH_DRAWER_USB_OUT_ENDPOINT
        configured_in_ep = settings.CASH_DRAWER_USB_IN_ENDPOINT
        pulse_command = self._build_pulse_command()

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

            if in_endpoint_address is None:
                bulk_in = usb.util.find_descriptor(
                    interface,
                    custom_match=lambda endpoint: usb.util.endpoint_direction(endpoint.bEndpointAddress) == usb.util.ENDPOINT_IN
                    and usb.util.endpoint_type(endpoint.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK,
                )
                in_endpoint_address = int(bulk_in.bEndpointAddress) if bulk_in is not None else None

            device.write(out_endpoint_address, pulse_command)

            return CashDrawerOpenResult(
                vendor_id=vendor_id,
                product_id=product_id,
                interface=interface_number,
                out_endpoint=out_endpoint_address,
                in_endpoint=in_endpoint_address,
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

    def open_drawer(self) -> CashDrawerOpenResult:
        if not settings.CASH_DRAWER_ENABLED:
            raise CashDrawerError("Cash drawer integration is disabled")

        mode = (settings.CASH_DRAWER_MODE or "mock").lower()
        if mode == "mock":
            logger.info("cash_drawer.open.mock_pulse")
            return CashDrawerOpenResult(vendor_id=0, product_id=0, interface=0, out_endpoint=0, in_endpoint=None)
        if mode != "usb":
            raise CashDrawerError(f"Unsupported CASH_DRAWER_MODE: {mode}")
        return self._open_drawer_usb()

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
