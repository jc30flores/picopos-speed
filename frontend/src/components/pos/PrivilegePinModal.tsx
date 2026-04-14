import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { verifyPrivilegedPin } from "@/lib/api";

const sanitizePin = (value: string) => value.replace(/\D/g, "").slice(0, 6);

export const PrivilegePinModal = ({
  open,
  onCancel,
  onSuccess,
}: {
  open: boolean;
  onCancel: () => void;
  onSuccess: (pin: string) => void;
}) => {
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const press = (digit: string) => setPin((prev) => sanitizePin(prev + digit));

  const submit = async () => {
    if (pin.length !== 6 || loading) return;
    try {
      setLoading(true);
      setError("");
      const result = await verifyPrivilegedPin(pin);
      if (!result.ok) {
        setError("Código inválido");
        return;
      }
      const approvedPin = pin;
      setPin("");
      onSuccess(approvedPin);
    } catch {
      setError("Código inválido");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onCancel()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Acceso con código</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="text-center text-2xl tracking-[0.4em] py-2 border rounded-md min-h-12">{pin.replace(/./g, "•")}</div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <div className="grid grid-cols-3 gap-2">
            {["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"].map((d) => (
              <Button key={d} type="button" className="h-12 text-lg" onClick={() => press(d)}>{d}</Button>
            ))}
            <Button variant="outline" className="h-12" onClick={() => setPin("")}>Limpiar</Button>
            <Button variant="outline" className="h-12" onClick={() => setPin((prev) => prev.slice(0, -1))}>Borrar</Button>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onCancel}>Cancelar</Button>
            <Button onClick={submit} disabled={pin.length !== 6 || loading}>{loading ? "Validando..." : "Confirmar"}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
