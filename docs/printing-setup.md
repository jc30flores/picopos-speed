# Printing setup (sales + end of day)

## Environment variables

```env
PRINTER_ENABLED=1

# Receipt printer (sale + end-of-day)
RECEIPT_PRINTER_MODE=usb
RECEIPT_PRINTER_USB_VENDOR_ID=0x1fc9
RECEIPT_PRINTER_USB_PRODUCT_ID=0x2016
RECEIPT_PRINTER_USB_INTERFACE=0
RECEIPT_PRINTER_USB_OUT_ENDPOINT=0x03
RECEIPT_PRINTER_CUT_ENABLED=1
```

> `RECEIPT_PRINTER_*` values fall back to existing `PRINTER_*` and `CASH_DRAWER_*` settings.

## Notes

- Sale payment printing is best-effort: payment success is never rolled back if print fails.
- End-of-day close printing is also best-effort and returns `printed` / `print_error` fields.
- Mock mode can be used with `RECEIPT_PRINTER_MODE=mock`.
