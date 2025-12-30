import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { PrintJob } from "@/lib/api";
import { toast } from "sonner";

interface PrintPreviewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  job: PrintJob | null;
  onMarkPrinted: () => Promise<void>;
  onReprint: () => Promise<void>;
}

export const PrintPreviewDialog = ({
  open,
  onOpenChange,
  job,
  onMarkPrinted,
  onReprint,
}: PrintPreviewDialogProps) => {
  const handleCopy = async () => {
    if (!job) return;
    await navigator.clipboard.writeText(job.contentText);
    toast.success("Ticket copiado");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Vista previa de impresión</DialogTitle>
        </DialogHeader>
        {job ? (
          <div className="space-y-4">
            <pre className="bg-muted p-3 rounded-md text-xs font-mono whitespace-pre-wrap">
              {job.contentText}
            </pre>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={handleCopy}>
                Copiar texto
              </Button>
              <Button variant="outline" onClick={onReprint}>
                Reimprimir
              </Button>
              <Button onClick={onMarkPrinted}>Marcar impreso</Button>
            </div>
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">No hay contenido disponible.</div>
        )}
      </DialogContent>
    </Dialog>
  );
};
