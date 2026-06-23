import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Printer } from "lucide-react";

interface TicketPreviewDialogProps {
  open: boolean;
  title?: string;
  subtitle?: string;
  ticketUrl: string | null;
  loading?: boolean;
  error?: string | null;
  onClose: () => void;
}

export const TicketPreviewDialog = ({
  open,
  title = "Vista previa de ticket",
  subtitle = "Formato térmico optimizado para impresora 80POS genérica.",
  ticketUrl,
  loading = false,
  error = null,
  onClose,
}: TicketPreviewDialogProps) => {
  const handlePrint = () => {
    if (!ticketUrl) return;
    const frame = document.getElementById("ticket-preview-frame") as HTMLIFrameElement | null;
    try {
      frame?.contentWindow?.focus();
      frame?.contentWindow?.print();
      return;
    } catch {
      // Fall through to popup fallback below.
    }
    const win = window.open(ticketUrl, "_blank", "noopener,noreferrer,width=520,height=800");
    if (!win) return;
    win.addEventListener("load", () => win.print(), { once: true });
  };

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => { if (!nextOpen) onClose(); }}>
      <DialogContent className="flex h-[90vh] w-[94vw] max-w-4xl flex-col rounded-2xl p-0">
        <DialogHeader className="border-b px-5 py-4">
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{subtitle}</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 bg-slate-100 p-3">
          {loading ? <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Preparando ticket...</div> : null}
          {error ? <div className="flex h-full items-center justify-center text-sm text-destructive">{error}</div> : null}
          {!loading && !error && ticketUrl ? (
            <iframe id="ticket-preview-frame" title="Vista previa de ticket" src={ticketUrl} className="mx-auto h-full w-full max-w-[520px] rounded bg-white shadow" />
          ) : null}
        </div>
        <DialogFooter className="border-t px-5 py-4">
          <Button type="button" variant="outline" onClick={onClose}>Cerrar</Button>
          <Button type="button" onClick={handlePrint} disabled={!ticketUrl || loading || Boolean(error)}>
            <Printer className="mr-2 h-4 w-4" /> Imprimir
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
