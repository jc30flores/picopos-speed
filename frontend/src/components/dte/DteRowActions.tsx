import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Eye, Mail, MessageCircle, RefreshCw, FileMinus, Ban } from "lucide-react";
import type { DTERecord } from "@/lib/api";

type ActionType = "view" | "email" | "whatsapp" | "resend" | "credit_note" | "invalidate";

type Props = {
  row: DTERecord;
  loadingAction?: ActionType | null;
  onAction: (action: ActionType, row: DTERecord) => void;
};

const canManuallySendEmail = (row: DTERecord): boolean => Boolean(row?.id);

const ActionIcon = ({ action, loading }: { action: ActionType; loading: boolean }) => {
  if (loading) return <RefreshCw className="h-4 w-4 animate-spin" />;
  if (action === "view") return <Eye className="h-4 w-4" />;
  if (action === "email") return <Mail className="h-4 w-4" />;
  if (action === "whatsapp") return <MessageCircle className="h-4 w-4" />;
  if (action === "resend") return <RefreshCw className="h-4 w-4" />;
  if (action === "credit_note") return <FileMinus className="h-4 w-4" />;
  return <Ban className="h-4 w-4" />;
};

const actionConfig = (row: DTERecord) => [
  { key: "view" as const, label: "Ver detalle", enabled: true, reason: "" },
  {
    key: "email" as const,
    label: "Enviar correo",
    enabled: canManuallySendEmail(row),
    reason: canManuallySendEmail(row) ? "" : "DTE no emitido",
  },
  { key: "whatsapp" as const, label: "Enviar WhatsApp", enabled: Boolean(row.can_send_whatsapp), reason: row.missing_phone_reason || "" },
  { key: "resend" as const, label: "Reenviar Hacienda", enabled: Boolean(row.can_resend), reason: "Solo disponible en pendientes" },
  { key: "credit_note" as const, label: "Nota de crédito", enabled: Boolean(row.can_credit_note), reason: row.credit_note_reason || "" },
  { key: "invalidate" as const, label: "Invalidar", enabled: Boolean(row.can_invalidate), reason: row.invalidate_reason || "" },
];

export function DteRowActions({ row, loadingAction, onAction }: Props) {
  return (
    <TooltipProvider delayDuration={120}>
      <div className="flex items-center justify-end gap-1">
        {actionConfig(row).map((action) => {
          const isLoading = loadingAction === action.key;
          const disabled = (loadingAction && loadingAction !== action.key) || (!action.enabled && action.key !== "view") || Boolean(isLoading);
          const tip = action.key === "email" && action.enabled && row.missing_email_reason
            ? `${action.label} (si falta correo se mostrará error al enviar)`
            : (action.enabled || action.key === "view" ? action.label : (action.reason || `${action.label} no disponible`));
          return (
            <Tooltip key={action.key}>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-10 w-10"
                  disabled={Boolean(disabled)}
                  onClick={() => onAction(action.key, row)}
                >
                  <ActionIcon action={action.key} loading={Boolean(isLoading)} />
                </Button>
              </TooltipTrigger>
              <TooltipContent>{tip}</TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </TooltipProvider>
  );
}
