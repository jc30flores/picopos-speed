import { memo, useEffect, useState } from "react";
import { ImageOff } from "lucide-react";
import { cn } from "@/lib/utils";

interface KioskImageProps {
  src?: string | null;
  alt: string;
  ratio?: string;
  className?: string;
  imageClassName?: string;
  placeholderLabel?: string;
  loading?: "lazy" | "eager";
  sizes?: string;
  onPreview?: () => void;
}

export const KioskImage = memo(
  ({
    src,
    alt,
    ratio = "4 / 3",
    className,
    imageClassName,
    placeholderLabel = "Sin imagen",
    loading = "lazy",
    sizes,
    onPreview,
  }: KioskImageProps) => {
    const [isLoading, setIsLoading] = useState(Boolean(src));
    const [hasError, setHasError] = useState(false);

    useEffect(() => {
      setHasError(false);
      setIsLoading(Boolean(src));
    }, [src]);

    const showImage = Boolean(src) && !hasError;

    return (
      <div
        className={cn(
          "relative overflow-hidden rounded-2xl border border-white/10 bg-muted/60",
          onPreview && "cursor-zoom-in",
          className,
        )}
        style={{ aspectRatio: ratio }}
      >
        {showImage ? (
          <>
            <img
              src={src ?? undefined}
              alt=""
              aria-hidden="true"
              className="absolute inset-0 h-full w-full scale-110 object-cover blur-xl opacity-40"
            />
            <img
              src={src ?? undefined}
              alt={alt}
              loading={loading}
              decoding="async"
              sizes={sizes}
              className={cn(
                "relative z-10 h-full w-full object-contain p-2 md:p-3",
                imageClassName,
              )}
              onLoad={() => setIsLoading(false)}
              onError={() => {
                setHasError(true);
                setIsLoading(false);
              }}
            />
          </>
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-gradient-to-br from-muted to-muted/40 text-muted-foreground">
            <ImageOff className="h-8 w-8" aria-hidden="true" />
            <span className="text-sm font-medium">{placeholderLabel}</span>
          </div>
        )}

        {isLoading && (
          <div className="absolute inset-0 z-20 animate-pulse bg-gradient-to-br from-white/10 via-white/5 to-transparent" />
        )}

        {onPreview && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onPreview();
            }}
            className="absolute right-3 top-3 z-30 rounded-full bg-black/55 px-3 py-1.5 text-xs font-semibold text-white shadow-lg transition hover:bg-black/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            aria-label={`Ampliar imagen de ${alt}`}
          >
            Ampliar
          </button>
        )}
      </div>
    );
  },
);

KioskImage.displayName = "KioskImage";
