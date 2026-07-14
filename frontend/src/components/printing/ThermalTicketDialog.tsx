import { useMemo, useState } from "react";
import { Bluetooth, BluetoothConnected, Printer, Unplug } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

type TicketWidth = "58mm" | "80mm";

type BluetoothCharacteristicLike = {
  properties?: { write?: boolean; writeWithoutResponse?: boolean };
  writeValue: (value: BufferSource) => Promise<void>;
};

type BluetoothServiceLike = {
  getCharacteristics: () => Promise<BluetoothCharacteristicLike[]>;
};

type BluetoothServerLike = {
  getPrimaryServices: () => Promise<BluetoothServiceLike[]>;
};

type BluetoothDeviceLike = {
  name?: string;
  gatt?: {
    connected?: boolean;
    connect: () => Promise<BluetoothServerLike>;
    disconnect: () => void;
  };
  addEventListener?: (type: string, listener: () => void) => void;
};

type BluetoothNavigator = Navigator & {
  bluetooth?: {
    requestDevice: (options: {
      acceptAllDevices: boolean;
      optionalServices: Array<number | string>;
    }) => Promise<BluetoothDeviceLike>;
  };
};

interface ThermalTicketDialogProps {
  open: boolean;
  title?: string;
  subtitle?: string;
  ticketText: string;
  logoUrl?: string | null;
  width?: TicketWidth;
  onWidthChange?: (width: TicketWidth) => void;
  onOpenChange: (open: boolean) => void;
}

const THERMAL_SERVICE_UUIDS: Array<number | string> = [
  0xffe0,
  0xff00,
  0x18f0,
  "0000ffe0-0000-1000-8000-00805f9b34fb",
  "0000ff00-0000-1000-8000-00805f9b34fb",
  "49535343-fe7d-4ae5-8fa9-9fafd205e455",
];

const chunkBytes = (bytes: Uint8Array, size = 180) => {
  const chunks: Uint8Array[] = [];
  for (let index = 0; index < bytes.length; index += size) {
    chunks.push(bytes.slice(index, index + size));
  }
  return chunks;
};

const isBluetoothChooserCancelled = (error: unknown) => {
  if (!(error instanceof Error)) return false;
  const name = error.name.toLowerCase();
  const message = error.message.toLowerCase();
  return name === "notfounderror" || message.includes("cancel") || message.includes("chooser") || message.includes("user cancelled");
};

export const ThermalTicketDialog = ({
  open,
  title = "Vista previa de ticket",
  subtitle = "Ticket térmico local para impresoras 58mm/80mm.",
  ticketText,
  logoUrl = null,
  width = "58mm",
  onWidthChange,
  onOpenChange,
}: ThermalTicketDialogProps) => {
  const [device, setDevice] = useState<BluetoothDeviceLike | null>(null);
  const [characteristic, setCharacteristic] = useState<BluetoothCharacteristicLike | null>(null);
  const [status, setStatus] = useState<"disconnected" | "connecting" | "connected" | "printing" | "error">("disconnected");
  const [error, setError] = useState<string | null>(null);

  const previewWidth = width === "58mm" ? 384 : 576;
  const connected = Boolean(device?.gatt?.connected && characteristic);
  const statusLabel = connected ? "Conectada" : status === "connecting" ? "Conectando" : status === "printing" ? "Imprimiendo" : status === "error" ? "Error" : "Desconectada";

  const printableHtml = useMemo(() => {
    const entities: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;" };
    const escaped = ticketText.replace(/[&<>]/g, (char) => entities[char] ?? char);
    const logo = logoUrl ? `<img src="${logoUrl}" alt="Logo" style="display:block;max-width:160px;max-height:72px;margin:0 auto 10px;object-fit:contain;" />` : "";
    return `<!doctype html><html><head><meta charset="utf-8" /><title>${title}</title><style>@page{margin:0}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}body{margin:0;background:#fff;color:#000}.ticket{width:${previewWidth}px;margin:0 auto;padding:14px 12px;background:#fff;color:#000;font:13px/1.34 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;white-space:pre-wrap}.ticket pre{margin:0;color:#000;white-space:pre-wrap;word-break:break-word}</style></head><body><div class="ticket">${logo}<pre>${escaped}</pre></div></body></html>`;
  }, [logoUrl, previewWidth, ticketText, title]);

  const openBrowserPrint = () => {
    const win = window.open("", "_blank", "noopener,noreferrer,width=520,height=800");
    if (!win) {
      toast.error("No se pudo abrir la vista de impresion del navegador.");
      return;
    }
    win.document.open();
    win.document.write(printableHtml);
    win.document.close();
    win.focus();
    win.addEventListener("load", () => win.print(), { once: true });
    window.setTimeout(() => win.print(), 250);
  };

  const connectPrinter = async () => {
    setError(null);
    const bluetooth = (navigator as BluetoothNavigator).bluetooth;
    if (!bluetooth) {
      setStatus("error");
      setError("Bluetooth no está disponible en este navegador. Puedes usar impresión del navegador.");
      return;
    }
    try {
      setStatus("connecting");
      const nextDevice = await bluetooth.requestDevice({
        acceptAllDevices: true,
        optionalServices: THERMAL_SERVICE_UUIDS,
      });
      nextDevice.addEventListener?.("gattserverdisconnected", () => {
        setCharacteristic(null);
        setStatus("disconnected");
      });
      const server = await nextDevice.gatt?.connect();
      if (!server) throw new Error("No se pudo conectar con la impresora.");
      const services = await server.getPrimaryServices();
      for (const service of services) {
        const characteristics = await service.getCharacteristics();
        const writable = characteristics.find((candidate) => candidate.properties?.write || candidate.properties?.writeWithoutResponse);
        if (writable) {
          setDevice(nextDevice);
          setCharacteristic(writable);
          setStatus("connected");
          toast.success(`Impresora conectada${nextDevice.name ? `: ${nextDevice.name}` : ""}.`);
          return;
        }
      }
      throw new Error("No se pudo preparar la impresora para recibir el ticket.");
    } catch (err) {
      if (isBluetoothChooserCancelled(err)) {
        setStatus("disconnected");
        setError(null);
        toast.info("No se seleccionó ninguna impresora.");
        return;
      }
      const message = "No se pudo conectar con la impresora. Verifica que esté encendida y cerca.";
      setStatus("error");
      setError(message);
      toast.error(message);
    }
  };

  const disconnectPrinter = () => {
    device?.gatt?.disconnect();
    setDevice(null);
    setCharacteristic(null);
    setStatus("disconnected");
  };

  const printBluetooth = async () => {
    if (!characteristic) {
      toast.info("No hay impresora Bluetooth conectada. Se abrirá impresión del navegador.");
      openBrowserPrint();
      return;
    }
    try {
      setStatus("printing");
      const encoder = new TextEncoder();
      const escpos = new Uint8Array([
        0x1b, 0x40,
        ...Array.from(encoder.encode(ticketText)),
        0x0a, 0x0a, 0x0a,
        0x1d, 0x56, 0x41, 0x10,
      ]);
      for (const chunk of chunkBytes(escpos)) {
        await characteristic.writeValue(chunk);
      }
      setStatus("connected");
      toast.success("Ticket enviado a impresora.");
    } catch {
      const message = "No se pudo imprimir. Revisa la conexión de la impresora.";
      setStatus("error");
      setError(message);
      toast.error(message);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[calc(100dvh-2rem)] w-[min(96vw,56rem)] max-w-4xl flex-col overflow-hidden p-0">
        <DialogHeader className="shrink-0 border-b bg-background px-5 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <DialogTitle>{title}</DialogTitle>
              <DialogDescription>{subtitle}</DialogDescription>
            </div>
            <Badge
              variant="outline"
              className={cn(
                "gap-1 border-[color:var(--app-border-strong)] bg-[var(--badge-bg)] text-[var(--badge-text)]",
                connected && "border-emerald-500/50 text-emerald-600 dark:text-emerald-300",
                status === "error" && "border-destructive/50 text-destructive",
              )}
            >
              {connected ? <BluetoothConnected className="h-3.5 w-3.5" /> : <Bluetooth className="h-3.5 w-3.5" />}
              {statusLabel}
            </Badge>
          </div>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-auto bg-[var(--app-surface-soft)] p-4">
          <div
            className="mx-auto rounded-md bg-white px-3 py-4 text-black shadow"
            style={{
              width: `${previewWidth}px`,
              maxWidth: "100%",
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              fontSize: width === "58mm" ? 13 : 14,
              lineHeight: 1.34,
              color: "#000000",
            }}
          >
            {logoUrl ? <img src={logoUrl} alt="Logo" className="mx-auto mb-3 max-h-[72px] max-w-[160px] object-contain" /> : null}
            <pre className="m-0 whitespace-pre-wrap break-words text-black opacity-100">{ticketText}</pre>
          </div>
        </div>

        {error ? <div className="shrink-0 border-t px-5 py-2 text-sm text-destructive">{error}</div> : null}

        <DialogFooter className="shrink-0 gap-2 border-t bg-background px-5 py-4 sm:justify-between [&>*]:w-full sm:[&>*]:w-auto">
          <div className="flex w-full flex-wrap gap-2 sm:w-auto">
            <Select value={width} onValueChange={(value) => onWidthChange?.(value as TicketWidth)}>
              <SelectTrigger className="h-10 w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="58mm">58mm</SelectItem>
                <SelectItem value="80mm">80mm</SelectItem>
              </SelectContent>
            </Select>
            {connected ? (
              <Button type="button" variant="outline" onClick={disconnectPrinter}>
                <Unplug className="mr-2 h-4 w-4" /> Desconectar
              </Button>
            ) : (
              <Button type="button" variant="outline" onClick={() => void connectPrinter()} disabled={status === "connecting"}>
                <Bluetooth className="mr-2 h-4 w-4" /> Conectar impresora
              </Button>
            )}
          </div>
          <div className="flex w-full flex-wrap gap-2 sm:w-auto">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cerrar</Button>
            <Button type="button" onClick={() => void printBluetooth()} disabled={status === "printing"}>
              <Printer className="mr-2 h-4 w-4" /> Imprimir
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
