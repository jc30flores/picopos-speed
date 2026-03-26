from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "List detected USB devices to help configure CASH_DRAWER_VENDOR_ID/CASH_DRAWER_PRODUCT_ID."

    def handle(self, *args, **options):
        try:
            import usb.core
            import usb.util
        except Exception:
            self.stderr.write("pyusb is not installed. Add pyusb to backend requirements.")
            return

        devices = list(usb.core.find(find_all=True) or [])
        if not devices:
            self.stdout.write("No USB devices detected.")
            return

        self.stdout.write("Detected USB devices:")
        for device in devices:
            vendor = f"0x{device.idVendor:04x}"
            product = f"0x{device.idProduct:04x}"
            manufacturer = usb.util.get_string(device, device.iManufacturer) if getattr(device, "iManufacturer", None) else ""
            product_name = usb.util.get_string(device, device.iProduct) if getattr(device, "iProduct", None) else ""
            serial = usb.util.get_string(device, device.iSerialNumber) if getattr(device, "iSerialNumber", None) else ""
            self.stdout.write(f"- vendor_id={vendor} product_id={product} manufacturer={manufacturer} product={product_name} serial={serial}")
