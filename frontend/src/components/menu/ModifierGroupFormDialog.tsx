import { useState, useEffect } from "react";
import { GripVertical, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ImageUploadField } from "@/components/ui/image-upload-field";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  createModifierGroup,
  ModifierGroup,
  reorderModifierGroupOptions,
  updateModifierGroup,
  uploadModifierGroupImage,
  uploadModifierOptionImage,
} from "@/lib/api";
import { toast } from "sonner";

interface ModifierOption {
  id: string;
  name: string;
  price: number;
  defaultSelected: boolean;
  image?: string | null;
  imageFile?: File | null;
}

interface ModifierGroupFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingGroup?: ModifierGroup | null;
  onSaved: () => Promise<void>;
}

export const ModifierGroupFormDialog = ({
  open,
  onOpenChange,
  editingGroup,
  onSaved,
}: ModifierGroupFormDialogProps) => {
  const [name, setName] = useState("");
  const [required, setRequired] = useState(false);
  const [minSelection, setMinSelection] = useState(0);
  const [maxSelection, setMaxSelection] = useState(1);
  const [groupImage, setGroupImage] = useState("");
  const [groupImageFile, setGroupImageFile] = useState<File | null>(null);
  const [options, setOptions] = useState<ModifierOption[]>([]);
  const [draggingOptionId, setDraggingOptionId] = useState<string | null>(null);
  const [isSavingOrder, setIsSavingOrder] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (editingGroup) {
      setName(editingGroup.name);
      setRequired(editingGroup.required);
      setMinSelection(editingGroup.minSelection);
      setMaxSelection(editingGroup.maxSelection);
      setGroupImage(editingGroup.imagePath ?? editingGroup.image ?? "");
      setGroupImageFile(null);
      setOptions(
        editingGroup.modifiers.map((m) => ({
          id: String(m.id),
          name: m.name,
          price: m.price,
          defaultSelected: false,
          image: m.imagePath ?? m.image ?? "",
          imageFile: null,
        }))
      );
    } else {
      setName("");
      setRequired(false);
      setMinSelection(0);
      setMaxSelection(1);
      setGroupImage("");
      setGroupImageFile(null);
      setOptions([]);
    }
  }, [editingGroup, open]);

  const addOption = () => {
    setOptions([
      ...options,
      {
        id: `opt-${Date.now()}`,
        name: "",
        price: 0,
        defaultSelected: false,
        image: "",
        imageFile: null,
      },
    ]);
  };

  const removeOption = (id: string) => {
    const confirmed = window.confirm("¿Eliminar esta opción del grupo?");
    if (!confirmed) return;
    setOptions(options.filter((opt) => opt.id !== id));
  };

  const updateOption = (id: string, field: keyof ModifierOption, value: unknown) => {
    setOptions(options.map((opt) => (opt.id === id ? { ...opt, [field]: value } : opt)));
  };

  const isValid = () =>
    name.trim() !== "" &&
    minSelection >= 0 &&
    maxSelection >= minSelection &&
    options.length > 0 &&
    options.every((opt) => opt.name.trim() !== "");

  const handleSave = async () => {
    if (!isValid()) return;
    setIsSaving(true);
    try {
      if (!editingGroup) {
        await createModifierGroup({
          name,
          required,
          minSelection,
          maxSelection,
          image: groupImageFile ?? null,
          modifiers: options.map((option) => ({
            name: option.name,
            price: option.price,
            image: option.imageFile ?? null,
          })),
        });
      } else {
        const baseGroup = await updateModifierGroup(editingGroup.id, {
          name,
          required,
          minSelection,
          maxSelection,
          modifiers: options.map((option) => ({
            id: Number.isFinite(Number(option.id)) ? Number(option.id) : undefined,
            name: option.name,
            price: option.price,
          })),
        });

        if (groupImageFile) {
          await uploadModifierGroupImage(baseGroup.id, groupImageFile);
        }

        for (let i = 0; i < options.length; i += 1) {
          const optionFile = options[i].imageFile;
          if (!optionFile) continue;
          const savedOption = baseGroup.modifiers[i];
          if (!savedOption?.id) continue;
          await uploadModifierOptionImage(savedOption.id, optionFile);
        }
      }

      await onSaved();
      onOpenChange(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo guardar el grupo de modificadores";
      toast.error(message || "No se pudo guardar el grupo de modificadores");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDropOption = async (targetOptionId: string) => {
    if (!draggingOptionId || draggingOptionId === targetOptionId || isSavingOrder) return;
    const current = [...options];
    const from = current.findIndex((opt) => opt.id === draggingOptionId);
    const to = current.findIndex((opt) => opt.id === targetOptionId);
    if (from < 0 || to < 0) return;
    const [moved] = current.splice(from, 1);
    current.splice(to, 0, moved);
    const previous = [...options];
    setOptions(current);
    if (!editingGroup) return;
    const orderedIds = current.map((opt) => Number(opt.id)).filter((id) => Number.isFinite(id));
    setIsSavingOrder(true);
    try {
      await reorderModifierGroupOptions(editingGroup.id, orderedIds);
    } catch {
      setOptions(previous);
    } finally {
      setIsSavingOrder(false);
      setDraggingOptionId(null);
    }
  };

  const handleDragEnterOption = (targetOptionId: string) => {
    if (!draggingOptionId || draggingOptionId === targetOptionId || isSavingOrder) return;
    const current = [...options];
    const from = current.findIndex((opt) => opt.id === draggingOptionId);
    const to = current.findIndex((opt) => opt.id === targetOptionId);
    if (from < 0 || to < 0) return;
    const [moved] = current.splice(from, 1);
    current.splice(to, 0, moved);
    setOptions(current);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editingGroup ? "Editar" : "Nuevo"} grupo de modificadores</DialogTitle>
          <DialogDescription>Configura el grupo y sus opciones disponibles</DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          <div className="space-y-4">
            <div>
              <Label htmlFor="group-name">Nombre del grupo</Label>
              <Input id="group-name" placeholder="Ej: Tipo de tortilla" value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
            </div>

            <ImageUploadField id="group-image" label="Imagen del grupo" file={groupImageFile} previewUrl={groupImage} onChange={setGroupImageFile} />

            <div className="flex items-center space-x-2">
              <Checkbox id="required" checked={required} onCheckedChange={(checked) => setRequired(checked as boolean)} />
              <Label htmlFor="required" className="cursor-pointer">Obligatorio (el cliente debe seleccionar)</Label>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="min-selection">Mínimo de selección</Label>
                <Input id="min-selection" type="number" min={0} value={minSelection} onChange={(e) => setMinSelection(parseInt(e.target.value, 10) || 0)} className="mt-1" />
              </div>
              <div>
                <Label htmlFor="max-selection">Máximo de selección</Label>
                <Input id="max-selection" type="number" min={minSelection} value={maxSelection} onChange={(e) => setMaxSelection(parseInt(e.target.value, 10) || 1)} className="mt-1" />
              </div>
            </div>

            {minSelection > maxSelection && <Badge variant="destructive">El mínimo no puede ser mayor que el máximo</Badge>}
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Opciones del grupo</Label>
              <Button variant="outline" size="sm" onClick={addOption}>
                <Plus className="mr-1 h-4 w-4" />
                Agregar opción
              </Button>
            </div>

            {options.length === 0 ? (
              <div className="rounded-lg border py-8 text-center text-muted-foreground">No hay opciones. Agrega al menos una opción.</div>
            ) : (
              <div className="space-y-3">
                {options.map((option) => (
                  <Card
                    key={option.id}
                    className={`p-4 transition-all ${draggingOptionId === option.id ? "opacity-50 ring-2 ring-primary/50" : ""}`}
                    onDragOver={(event) => event.preventDefault()}
                    onDragEnter={() => handleDragEnterOption(option.id)}
                    onDrop={() => handleDropOption(option.id)}
                  >
                    <div className="flex gap-3">
                      <button
                        type="button"
                        className="text-muted-foreground"
                        draggable={!isSavingOrder}
                        onDragStart={() => setDraggingOptionId(option.id)}
                        onDragEnd={() => setDraggingOptionId(null)}
                        title="Arrastrar para reordenar"
                      >
                        <GripVertical className="h-4 w-4" />
                      </button>
                      <div className="flex-1 space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label className="text-xs">Nombre</Label>
                            <Input placeholder="Ej: Salsa Verde" value={option.name} onChange={(e) => updateOption(option.id, "name", e.target.value)} className="mt-1" />
                          </div>
                          <div>
                            <Label className="text-xs">Precio adicional</Label>
                            <Input
                              type="number"
                              step="0.01"
                              min={0}
                              placeholder="0.00"
                              value={option.price}
                              onChange={(e) => updateOption(option.id, "price", parseFloat(e.target.value) || 0)}
                              className="mt-1"
                            />
                          </div>
                        </div>
                        <ImageUploadField
                          id={`option-image-${option.id}`}
                          label="Imagen de la opción"
                          file={option.imageFile ?? null}
                          previewUrl={option.image ?? null}
                          onChange={(file) => updateOption(option.id, "imageFile", file)}
                        />
                        <div className="flex items-center space-x-2">
                          <Checkbox id={`default-${option.id}`} checked={option.defaultSelected} onCheckedChange={(checked) => updateOption(option.id, "defaultSelected", checked)} />
                          <Label htmlFor={`default-${option.id}`} className="cursor-pointer text-sm">Seleccionado por defecto</Label>
                        </div>
                      </div>
                      <Button variant="ghost" size="icon" onClick={() => removeOption(option.id)}>
                        <Trash2 className="h-4 w-4 text-danger" />
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex gap-3 pt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)} className="flex-1">Cancelar</Button>
          <Button onClick={handleSave} disabled={!isValid() || isSaving} className="flex-1 bg-secondary hover:bg-secondary/90">
            {isSaving ? "Guardando..." : "Guardar grupo"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
