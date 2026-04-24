import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import {
  dteDeliver,
  dteCreateCreditNote,
  dteInvalidate,
  dteIssuedDetail,
  dteIssuedList,
  dteResend,
  type DTERecord,
} from "@/lib/api";
import { formatDateTimeSV } from "@/lib/datetime";
import { Copy } from "lucide-react";
import { DteRowActions } from "@/components/dte/DteRowActions";
import { PageLayout } from "@/components/layout/PageLayout";
import { useAuth } from "@/context/useAuth";
import { WhatsAppPhoneInput } from "@/components/dte/WhatsAppPhoneInput";
import { maskPhoneForLog, resolveWhatsappDestination, type WhatsAppCountry } from "@/lib/whatsappClientPhone";

type ActionType = "view" | "email" | "whatsapp" | "resend" | "credit_note" | "invalidate";

const statusLabel = (status: string) => {
  const normalized = (status || "").toUpperCase();
  if (normalized === "ACEPTADO") return "Aceptado";
  if (normalized === "PENDIENTE" || normalized === "ENVIANDO") return "Pendiente";
  if (normalized === "RECHAZADO") return "Rechazado";
  if (normalized === "INVALIDADO") return "Invalidado";
  return normalized;
};

const statusBadgeClass = (status: string) => {
  const normalized = (status || "").toUpperCase();
  if (normalized === "ACEPTADO") return "bg-emerald-600 text-white";
  if (normalized === "PENDIENTE" || normalized === "ENVIANDO") return "bg-amber-500 text-black";
  if (normalized === "RECHAZADO") return "bg-red-600 text-white";
  if (normalized === "INVALIDADO") return "bg-zinc-600 text-white";
  return "bg-muted text-foreground";
};

const typeToChip = (dteType: string) => {
  if (dteType.startsWith("CF")) return "CF";
  if (dteType.startsWith("CCF")) return "CCF";
  if (dteType.startsWith("SE")) return "SX";
  return dteType;
};

const formatMoney = (amount: number) => `$${Number(amount || 0).toFixed(2)}`;

const truncate = (value?: string, size = 14) => {
  if (!value) return "-";
  if (value.length <= size) return value;
  return `${value.slice(0, size)}…`;
};

const JsonBlock = ({ title, payload }: { title: string; payload: unknown }) => {
  const text = JSON.stringify(payload ?? {}, null, 2);
  return (
    <details className="rounded-md border bg-muted/20">
      <summary className="cursor-pointer px-3 py-2 text-sm font-medium">{title}</summary>
      <div className="space-y-2 p-3">
        <Button size="sm" variant="outline" onClick={() => navigator.clipboard.writeText(text)}>Copiar JSON</Button>
        <pre className="max-h-[300px] overflow-auto rounded bg-black/30 p-3 text-xs">{text}</pre>
      </div>
    </details>
  );
};

export default function DTEPage({ embedded = false }: { embedded?: boolean }) {
  const { toast } = useToast();
  const { user } = useAuth();
  const [rows, setRows] = useState<DTERecord[]>([]);
  const [selected, setSelected] = useState<DTERecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionsLoading, setActionsLoading] = useState<Record<number, ActionType | null>>({});
  const [invalidateDialogOpen, setInvalidateDialogOpen] = useState(false);
  const [invalidateTarget, setInvalidateTarget] = useState<DTERecord | null>(null);
  const [invalidateMotivo, setInvalidateMotivo] = useState("Invalidación desde panel DTE");
  const [invalidateDoc, setInvalidateDoc] = useState("");
  const [invalidateInlineError, setInvalidateInlineError] = useState("");
  const [whatsModalOpen, setWhatsModalOpen] = useState(false);
  const [whatsTarget, setWhatsTarget] = useState<DTERecord | null>(null);
  const [whatsCountry, setWhatsCountry] = useState<WhatsAppCountry>("ESA");
  const [whatsInput, setWhatsInput] = useState("");
  const [whatsError, setWhatsError] = useState("");

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [type, setType] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [count, setCount] = useState(0);
  const [totalAmountSum, setTotalAmountSum] = useState(0);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 400);
    return () => window.clearTimeout(timeout);
  }, [searchInput]);

  const filters = useMemo(
    () => ({
      search: search || undefined,
      status: status === "all" ? undefined : status,
      type: type === "all" ? undefined : type,
      dateFrom: dateFrom || undefined,
      dateTo: dateTo || undefined,
      page,
      pageSize,
    }),
    [search, status, type, dateFrom, dateTo, page, pageSize],
  );

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await dteIssuedList(filters);
      setRows(data.results);
      setCount(data.count);
      setTotalAmountSum(data.totalAmountSum);
    } catch (err) {
      const message = String(err);
      setError(message);
      toast({ title: "Error cargando DTE", description: message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [filters]);

  const copy = async (value?: string, title = "Copiado") => {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    toast({ title });
  };

  const patchRow = (updated?: DTERecord | null) => {
    if (!updated) return;
    setRows((prev) => prev.map((row) => (row.id === updated.id ? { ...row, ...updated } : row)));
    setSelected((prev) => (prev && prev.id === updated.id ? { ...prev, ...updated } : prev));
  };

  const onRowAction = async (action: ActionType, row: DTERecord) => {
    if (action === "view") {
      try {
        const detail = await dteIssuedDetail(row.id);
        setSelected(detail);
      } catch (err) {
        toast({ title: "No se pudo cargar detalle", description: String(err), variant: "destructive" });
      }
      return;
    }

    setActionsLoading((prev) => ({ ...prev, [row.id]: action }));
    try {
      if (action === "resend") {
        const result = await dteResend(row.id);
        patchRow(result.record);
        const semanticVariant =
          result.record.status === "ACEPTADO"
            ? "default"
            : result.record.status === "PENDIENTE"
              ? "default"
              : "destructive";
        toast({
          title: "Hacienda",
          description: `${result.message} (estado: ${statusLabel(result.record.status)})`,
          variant: semanticVariant,
        });
      }
      if (action === "email") {
        const result = await dteDeliver(row.id, ["email"]);
        const channel = result.results?.email;
        const failureMessage = channel?.error || row.missing_email_reason || "No se pudo enviar el DTE por correo.";
        toast({
          title: "Correo",
          description: channel?.ok ? "Correo enviado correctamente." : failureMessage,
          variant: channel?.ok ? "default" : "destructive",
        });
      }
      if (action === "whatsapp") {
        setWhatsTarget(row);
        setWhatsCountry("ESA");
        setWhatsInput("");
        setWhatsError("");
        setWhatsModalOpen(true);
        return;
      }
      if (action === "credit_note") {
        if (!window.confirm("¿Crear nota de crédito para este DTE?")) return;
        const result = await dteCreateCreditNote(row.id, "Nota de crédito desde panel DTE");
        patchRow(result.record);
        toast({ title: "Nota de crédito", description: result.message });
      }
      if (action === "invalidate") {
        setInvalidateTarget(row);
        setInvalidateMotivo("Invalidación desde panel DTE");
        setInvalidateDoc("");
        setInvalidateInlineError("");
        setInvalidateDialogOpen(true);
        return;
      }
      await load();
    } catch (err) {
      toast({ title: "Acción fallida", description: String(err), variant: "destructive" });
    } finally {
      setActionsLoading((prev) => ({ ...prev, [row.id]: null }));
    }
  };

  const submitInvalidation = async () => {
    if (!invalidateTarget) return;
    const motivo = invalidateMotivo.trim();
    const documento = invalidateDoc.trim();
    if (!motivo) {
      setInvalidateInlineError("El motivo de invalidación es obligatorio.");
      return;
    }
    if (!documento) {
      setInvalidateInlineError("El número de documento responsable es obligatorio.");
      return;
    }
    setInvalidateInlineError("");
    setActionsLoading((prev) => ({ ...prev, [invalidateTarget.id]: "invalidate" }));
    try {
      const result = await dteInvalidate(invalidateTarget.id, {
        motivoAnulacion: motivo,
        numDocResponsable: documento,
      });
      patchRow(result.record);
      toast({ title: "Invalidación", description: result.message });
      setInvalidateDialogOpen(false);
      setInvalidateTarget(null);
      await load();
    } catch (err) {
      toast({ title: "Acción fallida", description: String(err), variant: "destructive" });
    } finally {
      setActionsLoading((prev) => ({ ...prev, [invalidateTarget.id]: null }));
    }
  };

  const submitWhatsAppDelivery = async () => {
    if (!whatsTarget) return;
    const receptorPhone = String(
      (whatsTarget.requestPayload?.dte?.receptor?.telefono ||
        whatsTarget.responsePayload?.dte?.receptor?.telefono ||
        "")
    ).trim();
    const resolved = resolveWhatsappDestination({
      manualPhone: whatsInput,
      manualCountry: whatsCountry,
      receptorPhone,
    });
    console.info("dte.whatsapp.modal.submit", {
      dte_id: whatsTarget.id,
      selected_country: whatsCountry,
      raw_input: whatsInput,
      fallback_receptor_phone: maskPhoneForLog(receptorPhone),
      resolved_ok: resolved.ok,
      resolved_source: resolved.ok ? resolved.source : "invalid",
      resolved_phone: resolved.ok ? maskPhoneForLog(resolved.phone) : "***",
      reason: resolved.ok ? "" : resolved.reason,
    });
    if (!resolved.ok) {
      setWhatsError(resolved.reason);
      toast({
        title: "WhatsApp",
        description: resolved.reason,
        variant: "destructive",
      });
      return;
    }
    setWhatsError("");
    setActionsLoading((prev) => ({ ...prev, [whatsTarget.id]: "whatsapp" }));
    try {
      const result = await dteDeliver(whatsTarget.id, ["whatsapp"], { phone: resolved.phone });
      const channel = result.results?.whatsapp;
      toast({
        title: "WhatsApp",
        description: channel?.ok ? "WhatsApp enviado correctamente." : (channel?.error || result.summary),
        variant: channel?.ok ? "default" : "destructive",
      });
      if (channel?.ok) {
        setWhatsModalOpen(false);
      }
    } catch (err) {
      toast({ title: "Acción fallida", description: String(err), variant: "destructive" });
    } finally {
      setActionsLoading((prev) => ({ ...prev, [whatsTarget.id]: null }));
    }
  };

  const totalPages = Math.max(1, Math.ceil(count / pageSize));

  const content = (
      <div className="space-y-4">
        <div className="space-y-3 rounded-xl border bg-card/40 p-4">
          <div className="grid grid-cols-1 gap-2 lg:grid-cols-12">
            <Input
              className="lg:col-span-5"
              placeholder="Buscar por cliente, No. control, código generación…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
            <Select value={status} onValueChange={(value) => { setStatus(value); setPage(1); }}>
              <SelectTrigger className="lg:col-span-2"><SelectValue placeholder="Estado" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="PENDIENTE">Pendiente</SelectItem>
                <SelectItem value="ACEPTADO">Aceptado</SelectItem>
                <SelectItem value="RECHAZADO">Rechazado</SelectItem>
                <SelectItem value="INVALIDADO">Invalidado</SelectItem>
              </SelectContent>
            </Select>
            <Select value={type} onValueChange={(value) => { setType(value); setPage(1); }}>
              <SelectTrigger className="lg:col-span-2"><SelectValue placeholder="Tipo" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="CF">CF</SelectItem>
                <SelectItem value="CCF">CCF</SelectItem>
                <SelectItem value="SX">SX</SelectItem>
              </SelectContent>
            </Select>
            <Input className="lg:col-span-1" type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }} />
            <Input className="lg:col-span-1" type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }} />
            <div className="flex gap-2 lg:col-span-2">
              <Button variant="outline" className="w-full" onClick={load}>Aplicar</Button>
              <Button
                variant="ghost"
                className="w-full min-w-[96px]"
                onClick={() => {
                  setSearchInput("");
                  setSearch("");
                  setStatus("all");
                  setType("all");
                  setDateFrom("");
                  setDateTo("");
                  setPage(1);
                }}
              >
                Limpiar
              </Button>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-3 text-sm text-muted-foreground">
            <span># docs: <strong className="text-foreground">{count}</strong></span>
            <span>Total según filtros: <strong className="text-foreground">{formatMoney(totalAmountSum)}</strong></span>
          </div>
        </div>

        <div className="overflow-auto rounded-xl border">
          <table className="min-w-[980px] w-full text-sm">
            <thead className="sticky top-0 z-10 bg-background/95 backdrop-blur">
              <tr className="border-b text-muted-foreground">
                <th className="p-3 text-left">No. Control</th>
                <th className="p-3 text-left">Fecha/Hora</th>
                <th className="p-3 text-left">Cliente</th>
                <th className="p-3 text-left">Tipo</th>
                <th className="p-3 text-left">Estado</th>
                <th className="p-3 text-right">Total</th>
                <th className="p-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {!loading && rows.length === 0 && (
                <tr>
                  <td className="p-8 text-center text-muted-foreground" colSpan={7}>Sin documentos para los filtros seleccionados.</td>
                </tr>
              )}
              {rows.map((row) => (
                <tr key={row.id} className="border-b transition-colors hover:bg-muted/20">
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <span title={row.control_number}>{truncate(row.control_number, 18)}</span>
                      <Button type="button" variant="ghost" size="icon" className="h-8 w-8" onClick={() => copy(row.control_number, "No. control copiado")}>
                        <Copy className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </td>
                  <td className="p-3">{formatDateTimeSV(row.issued_at || row.created_at)}</td>
                  <td className="p-3" title={row.receiver_name}>{truncate(row.receiver_name, 28)}</td>
                  <td className="p-3"><Badge variant="outline">{typeToChip(row.dte_type)}</Badge></td>
                  <td className="p-3"><Badge className={statusBadgeClass(row.status)}>{statusLabel(row.status)}</Badge></td>
                  <td className="p-3 text-right font-semibold">{formatMoney(Number(row.total_amount || 0))}</td>
                  <td className="p-3 text-right">
                    <DteRowActions row={row} loadingAction={actionsLoading[row.id]} onAction={onRowAction} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Página {page} de {totalPages}</span>
            <Select value={String(pageSize)} onValueChange={(value) => { setPageSize(Number(value)); setPage(1); }}>
              <SelectTrigger className="h-8 w-24"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="10">10</SelectItem>
                <SelectItem value="20">20</SelectItem>
                <SelectItem value="50">50</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" disabled={page <= 1} onClick={() => setPage((prev) => Math.max(prev - 1, 1))}>Anterior</Button>
            <Button variant="outline" disabled={page >= totalPages} onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}>Siguiente</Button>
          </div>
        </div>

        {error && <div className="rounded border border-red-600/50 bg-red-950/30 p-3 text-sm text-red-200">{error}</div>}

      <Dialog
        open={invalidateDialogOpen}
        onOpenChange={(open) => {
          if (!open) {
            setInvalidateDialogOpen(false);
            setInvalidateTarget(null);
            setInvalidateInlineError("");
          }
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Invalidar DTE</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Se requiere el documento del responsable para completar la invalidación.
          </p>
          <div className="space-y-3">
            <label className="block space-y-1">
              <span className="text-sm font-medium">Motivo de invalidación</span>
              <Textarea
                value={invalidateMotivo}
                onChange={(e) => setInvalidateMotivo(e.target.value)}
                placeholder="Describe el motivo de invalidación"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-sm font-medium">Número de documento responsable</span>
              <Input
                value={invalidateDoc}
                onChange={(e) => setInvalidateDoc(e.target.value)}
                placeholder="Ej. 01234567-8"
              />
            </label>
            {invalidateInlineError ? <p className="text-sm text-destructive">{invalidateInlineError}</p> : null}
            <p className="text-xs text-muted-foreground">Usuario: {user?.username || "actual"}</p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setInvalidateDialogOpen(false)}>
                Cancelar
              </Button>
              <Button
                onClick={() => void submitInvalidation()}
                disabled={!invalidateMotivo.trim() || !invalidateDoc.trim() || !invalidateTarget}
              >
                Confirmar invalidación
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={whatsModalOpen} onOpenChange={setWhatsModalOpen}>
        <DialogContent className="w-[95vw] max-w-xl">
          <DialogHeader>
            <DialogTitle>Enviar DTE por WhatsApp</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <WhatsAppPhoneInput
              label="Número para envío por WhatsApp"
              helpText="Déjalo vacío para usar receptor.telefono del JSON del DTE."
              country={whatsCountry}
              onCountryChange={(country) => {
                setWhatsCountry(country);
                setWhatsError("");
              }}
              value={whatsInput}
              onValueChange={(value) => {
                setWhatsInput(value);
                setWhatsError("");
              }}
              error={whatsError}
            />
            <div className="flex gap-2">
              <Button variant="outline" className="h-12 flex-1" onClick={() => setWhatsModalOpen(false)}>
                Cancelar
              </Button>
              <Button
                className="h-12 flex-1"
                onClick={() => void submitWhatsAppDelivery()}
                disabled={!whatsTarget || actionsLoading[whatsTarget.id] === "whatsapp"}
              >
                Enviar
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(selected)} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-h-[88vh] max-w-4xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Detalle DTE</DialogTitle>
          </DialogHeader>
          {selected && (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-1 gap-3 rounded-lg border p-3 md:grid-cols-2">
                <div><strong>Estado:</strong> {statusLabel(selected.status)}</div>
                <div><strong>Tipo:</strong> {typeToChip(selected.dte_type)}</div>
                <div className="flex items-center gap-2"><strong>No. Control:</strong> {selected.control_number} <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => copy(selected.control_number)}><Copy className="h-3.5 w-3.5" /></Button></div>
                <div className="flex items-center gap-2"><strong>Código generación:</strong> {selected.codigo_generacion} <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => copy(selected.codigo_generacion)}><Copy className="h-3.5 w-3.5" /></Button></div>
                <div><strong>Sello recibido:</strong> {selected.sello_recibido || selected.sello_recepcion || "-"}</div>
                <div><strong>Firma:</strong> {selected.firma || "-"}</div>
                <div><strong>Recibido:</strong> {selected.recibido_at ? formatDateTimeSV(selected.recibido_at) : "-"}</div>
                <div><strong>Último envío:</strong> {selected.last_sent_at ? formatDateTimeSV(selected.last_sent_at) : "-"} ({selected.attempts ?? 0} intentos)</div>
                <div className="md:col-span-2"><strong>Último error:</strong> {selected.error_message || "-"}</div>
              </div>

              <JsonBlock title="Ver JSON enviado" payload={selected.request_payload || {}} />
              <JsonBlock title="Ver respuesta Hacienda" payload={selected.response_payload || selected.mh_response_json || {}} />
            </div>
          )}
        </DialogContent>
      </Dialog>
      </div>
  );

  if (embedded) return content;

  return (
    <PageLayout
      title="DTE"
      subtitle="Consulta, reenvía e invalida documentos electrónicos."
      maxWidthClassName="max-w-[1600px]"
    >
      {content}
    </PageLayout>
  );
}
