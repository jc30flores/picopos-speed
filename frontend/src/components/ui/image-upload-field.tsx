import { ChangeEvent, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

interface ImageUploadFieldProps {
  id: string;
  label: string;
  file: File | null;
  previewUrl?: string | null;
  onChange: (file: File | null) => void;
}

export const ImageUploadField = ({ id, label, file, previewUrl, onChange }: ImageUploadFieldProps) => {
  const [localPreview, setLocalPreview] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setLocalPreview(null);
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    setLocalPreview(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    onChange(event.target.files?.[0] ?? null);
  };

  const src = localPreview ?? previewUrl ?? null;

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <div className="rounded-lg border border-border bg-muted/20 p-3">
        <div className="flex items-center gap-3">
          <Button type="button" variant="outline" onClick={() => document.getElementById(id)?.click()}>
            Seleccionar imagen
          </Button>
          <span className="text-sm text-muted-foreground">{file ? file.name : "Ningún archivo seleccionado"}</span>
        </div>
        <input id={id} type="file" accept="image/*" className="hidden" onChange={handleChange} />
        {src ? (
          <img src={src} alt={label} className="mt-3 h-14 w-14 rounded-md object-cover" loading="lazy" />
        ) : null}
      </div>
    </div>
  );
};
