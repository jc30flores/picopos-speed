import { useEffect } from "react";
import { Eye, X } from "lucide-react";
import { resolveImageUrl, Product } from "@/lib/api";

interface ProductImagePreviewModalProps {
  open: boolean;
  item: Product | null;
  onClose: () => void;
}

export const ProductImagePreviewModal = ({ open, item, onClose }: ProductImagePreviewModalProps) => {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open || !item) return null;

  const imageSrc = resolveImageUrl(item.imagePath ?? item.imageUrl);

  return (
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-4xl overflow-hidden rounded-2xl border border-slate-200 bg-white text-slate-900 shadow-2xl dark:border-white/10 dark:bg-slate-950 dark:text-white">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-white/10">
          <div className="flex items-center gap-2">
            <Eye className="h-5 w-5 opacity-80" />
            <div className="font-semibold">{item.name}</div>
          </div>
          <button
            type="button"
            className="rounded-lg p-2 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:hover:bg-white/10"
            onClick={onClose}
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid grid-cols-1 gap-0 md:grid-cols-5">
          <div className="flex items-center justify-center bg-slate-50 p-4 md:col-span-3 dark:bg-black/30">
            {imageSrc ? (
              <img
                src={imageSrc}
                alt={item.name}
                className="max-h-[70vh] w-full rounded-xl object-contain"
              />
            ) : (
              <div className="flex h-[320px] w-full items-center justify-center rounded-xl bg-slate-100 text-slate-500 dark:bg-white/5 dark:text-white/60">
                Sin imagen
              </div>
            )}
          </div>

          <div className="p-5 md:col-span-2">
            <div className="text-sm uppercase tracking-wide text-slate-500 dark:text-white/60">
              {item.categoryName || item.category || "CATEGORÍA"}
            </div>
            <div className="mt-2 text-2xl font-bold">{item.name}</div>
            {item.description ? (
              <p className="mt-3 text-base leading-relaxed text-slate-700 dark:text-white/85">
                {item.description}
              </p>
            ) : (
              <p className="mt-3 text-base text-slate-500 dark:text-white/50">Sin descripción.</p>
            )}
            <div className="mt-6 flex items-center justify-between">
              <div className="text-slate-600 dark:text-white/70">Precio</div>
              <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                ${Number(item.price).toFixed(2)}
              </div>
            </div>
            <div className="mt-4 text-xs text-slate-500 dark:text-white/40">
              Tip: puedes cerrar tocando fuera o con ESC.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
