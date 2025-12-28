import { useState, useEffect } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface ModifierOption {
  id: string;
  name: string;
  price: number;
  defaultSelected: boolean;
}

interface ModifierGroupFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingGroup?: any;
}

export const ModifierGroupFormDialog = ({
  open,
  onOpenChange,
  editingGroup,
}: ModifierGroupFormDialogProps) => {
  const [name, setName] = useState("");
  const [required, setRequired] = useState(false);
  const [minSelection, setMinSelection] = useState(0);
  const [maxSelection, setMaxSelection] = useState(1);
  const [options, setOptions] = useState<ModifierOption[]>([]);

  useEffect(() => {
    if (editingGroup) {
      setName(editingGroup.name);
      setRequired(editingGroup.required);
      setMinSelection(editingGroup.minSelection);
      setMaxSelection(editingGroup.maxSelection);
      setOptions(
        editingGroup.modifiers.map((m: any) => ({
          id: m.id,
          name: m.name,
          price: m.price,
          defaultSelected: false,
        }))
      );
    } else {
      setName("");
      setRequired(false);
      setMinSelection(0);
      setMaxSelection(1);
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
      },
    ]);
  };

  const removeOption = (id: string) => {
    setOptions(options.filter((opt) => opt.id !== id));
  };

  const updateOption = (id: string, field: keyof ModifierOption, value: any) => {
    setOptions(
      options.map((opt) => (opt.id === id ? { ...opt, [field]: value } : opt))
    );
  };

  const isValid = () => {
    return (
      name.trim() !== "" &&
      minSelection >= 0 &&
      maxSelection >= minSelection &&
      options.length > 0 &&
      options.every((opt) => opt.name.trim() !== "")
    );
  };

  const handleSave = () => {
    if (!isValid()) return;
    // Mock save - in real app would save to backend
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {editingGroup ? "Editar" : "Nuevo"} grupo de modificadores
          </DialogTitle>
          <DialogDescription>
            Configura el grupo y sus opciones disponibles
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Basic Info */}
          <div className="space-y-4">
            <div>
              <Label htmlFor="group-name">Nombre del grupo</Label>
              <Input
                id="group-name"
                placeholder="Ej: Tipo de tortilla"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1"
              />
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="required"
                checked={required}
                onCheckedChange={(checked) => setRequired(checked as boolean)}
              />
              <Label htmlFor="required" className="cursor-pointer">
                Obligatorio (el cliente debe seleccionar)
              </Label>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="min-selection">Mínimo de selección</Label>
                <Input
                  id="min-selection"
                  type="number"
                  min={0}
                  value={minSelection}
                  onChange={(e) => setMinSelection(parseInt(e.target.value) || 0)}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="max-selection">Máximo de selección</Label>
                <Input
                  id="max-selection"
                  type="number"
                  min={minSelection}
                  value={maxSelection}
                  onChange={(e) => setMaxSelection(parseInt(e.target.value) || 1)}
                  className="mt-1"
                />
              </div>
            </div>

            {minSelection > maxSelection && (
              <Badge variant="destructive">
                El mínimo no puede ser mayor que el máximo
              </Badge>
            )}
          </div>

          {/* Options */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Opciones del grupo</Label>
              <Button variant="outline" size="sm" onClick={addOption}>
                <Plus className="h-4 w-4 mr-1" />
                Agregar opción
              </Button>
            </div>

            {options.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground border rounded-lg">
                No hay opciones. Agrega al menos una opción.
              </div>
            ) : (
              <div className="space-y-3">
                {options.map((option, index) => (
                  <Card key={option.id} className="p-4">
                    <div className="flex gap-3">
                      <div className="flex-1 space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label className="text-xs">Nombre</Label>
                            <Input
                              placeholder="Ej: Salsa Verde"
                              value={option.name}
                              onChange={(e) =>
                                updateOption(option.id, "name", e.target.value)
                              }
                              className="mt-1"
                            />
                          </div>
                          <div>
                            <Label className="text-xs">Precio adicional</Label>
                            <Input
                              type="number"
                              step="0.01"
                              min={0}
                              placeholder="0.00"
                              value={option.price}
                              onChange={(e) =>
                                updateOption(
                                  option.id,
                                  "price",
                                  parseFloat(e.target.value) || 0
                                )
                              }
                              className="mt-1"
                            />
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Checkbox
                            id={`default-${option.id}`}
                            checked={option.defaultSelected}
                            onCheckedChange={(checked) =>
                              updateOption(option.id, "defaultSelected", checked)
                            }
                          />
                          <Label
                            htmlFor={`default-${option.id}`}
                            className="text-sm cursor-pointer"
                          >
                            Seleccionado por defecto
                          </Label>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => removeOption(option.id)}
                      >
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
          <Button variant="outline" onClick={() => onOpenChange(false)} className="flex-1">
            Cancelar
          </Button>
          <Button
            onClick={handleSave}
            disabled={!isValid()}
            className="flex-1 bg-secondary hover:bg-secondary/90"
          >
            Guardar grupo
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
