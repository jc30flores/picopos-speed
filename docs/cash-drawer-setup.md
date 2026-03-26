# Cash Drawer Setup (Linux + 3nStar RPT004 USB)

Este proyecto abre el cajón enviando comandos ESC/POS por USB desde backend Django.

## 1) Verificar dispositivo USB

```bash
lsusb -d 1fc9:2016
```

O listar impresoras:

```bash
lsusb | grep -i printer
```

## 2) Variables de entorno requeridas

```env
CASH_DRAWER_ENABLED=1
CASH_DRAWER_MODE=usb
CASH_DRAWER_USB_VENDOR_ID=0x1fc9
CASH_DRAWER_USB_PRODUCT_ID=0x2016
CASH_DRAWER_USB_INTERFACE=0
CASH_DRAWER_USB_OUT_ENDPOINT=0x03
CASH_DRAWER_USB_IN_ENDPOINT=0x81
# opcional:
# CASH_DRAWER_PIN=2
# CASH_DRAWER_PULSE_COMMAND=1B 70 00 19 FA

# impresión de tickets (cierre de caja)
PRINTER_ENABLED=1
RECEIPT_PRINTER_MODE=usb
RECEIPT_PRINTER_USB_VENDOR_ID=0x1fc9
RECEIPT_PRINTER_USB_PRODUCT_ID=0x2016
RECEIPT_PRINTER_USB_INTERFACE=0
RECEIPT_PRINTER_USB_OUT_ENDPOINT=0x03
RECEIPT_PRINTER_CUT_ENABLED=1
```

## 3) Permisos USB (servicio en producción)

Crear regla udev:

`/etc/udev/rules.d/99-thermal-printer.rules`

```udev
SUBSYSTEM=="usb", ATTR{idVendor}=="1fc9", ATTR{idProduct}=="2016", MODE="0666", GROUP="plugdev"
```

Aplicar:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Asegura que el usuario del backend pertenezca a `plugdev`.

## 4) Diagnóstico desde backend

Estado de configuración:

```bash
curl -X GET http://localhost:8102/api/cashier/drawer/status/ -b "sessionid=<tu_sessionid>"
```

Listar USB detectados:

```bash
python manage.py list_usb_devices
```

Prueba real de apertura:

```bash
python manage.py cash_drawer_test
```

## 5) Endpoint API

- Abrir cajón: `POST /api/cashier/drawer/open/`
- Estado cajón: `GET /api/cashier/drawer/status/`
- Cierre de caja imprime ticket automáticamente al cerrar sesión.

Respuesta exitosa esperada:

```json
{
  "ok": true,
  "message": "Cash drawer opened successfully"
}
```

## 6) Errores comunes

- `Cash drawer integration is disabled`  
  Activa `CASH_DRAWER_ENABLED=1`.

- `Printer not configured...`  
  Faltan variables `CASH_DRAWER_USB_*`.

- `USBError: Resource busy`  
  El dispositivo está ocupado o permisos incompletos. Verifica udev y usuario del servicio.
