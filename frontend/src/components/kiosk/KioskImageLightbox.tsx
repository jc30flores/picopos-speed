import { useEffect } from "react";
import { X } from "lucide-react";
import { KioskImage } from "@/components/kiosk/KioskImage";

interface KioskImageLightboxProps {
  open: boolean;
  title: string;
  subtitle?: string;
  imageSrc?: string | null;
  onClose: () => void;
}

export const KioskImageLightbox = ({ open, title, subtitle, imageSrc, onClose }: KioskImageLightboxProps) => {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open || !imageSrc) return null;

  return (
    <div
      className="fixed inset-0 z-[1000] bg-black/80 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="mx-auto flex h-full w-full max-w-6xl flex-col rounded-3xl border border-white/10 bg-background/95 p-4 md:p-6">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            {subtitle ? <p className="text-sm uppercase tracking-wide text-muted-foreground">{subtitle}</p> : null}
            <h2 className="text-2xl font-extrabold md:text-4xl">{title}</h2>
          </div>
          <button
            type="button"
            className="rounded-xl bg-white/10 p-3 transition hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            onClick={onClose}
            aria-label="Cerrar vista ampliada"
          >
            <X className="h-7 w-7" />
          </button>
        </div>

        <div className="min-h-0 flex-1">
          <KioskImage
            src={imageSrc}
            alt={title}
            ratio="16 / 9"
            loading="eager"
            className="h-full w-full rounded-2xl"
            imageClassName="p-4 md:p-8"
          />
        </div>
      </div>
    </div>
  );
};
