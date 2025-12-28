import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { categories } from "@/data/mockProducts";

interface ProductFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingProduct?: any;
}

export const ProductFormDialog = ({
  open,
  onOpenChange,
  editingProduct,
}: ProductFormDialogProps) => {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState(0);
  const [category, setCategory] = useState("");
  const [image, setImage] = useState("");
  const [available, setAvailable] = useState(true);

  useEffect(() => {
    if (editingProduct) {
      setName(editingProduct.name);
      setDescription(editingProduct.description);
      setPrice(editingProduct.price);
      setCategory(editingProduct.category);
      setImage(editingProduct.image);
      setAvailable(editingProduct.available);
    } else {
      setName("");
      setDescription("");
      setPrice(0);
      setCategory("");
      setImage("🍽️");
      setAvailable(true);
    }
  }, [editingProduct, open]);

  const isValid = () => {
    return name.trim() !== "" && category !== "" && price > 0;
  };

  const handleSave = () => {
    if (!isValid()) return;
    // Mock save - in real app would save to backend
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {editingProduct ? "Editar" : "Nuevo"} producto
          </DialogTitle>
          <DialogDescription>
            Configura la información del producto
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <Label htmlFor="product-name">Nombre del producto</Label>
              <Input
                id="product-name"
                placeholder="Ej: Taco de Carne Asada"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1"
              />
            </div>

            <div className="col-span-2">
              <Label htmlFor="product-description">Descripción</Label>
              <Textarea
                id="product-description"
                placeholder="Descripción breve del producto"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="mt-1"
                rows={3}
              />
            </div>

            <div>
              <Label htmlFor="product-price">Precio</Label>
              <Input
                id="product-price"
                type="number"
                step="0.01"
                min={0}
                placeholder="0.00"
                value={price}
                onChange={(e) => setPrice(parseFloat(e.target.value) || 0)}
                className="mt-1"
              />
            </div>

            <div>
              <Label htmlFor="product-category">Categoría</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Selecciona categoría" />
                </SelectTrigger>
                <SelectContent>
                  {categories.filter(c => c !== "Todos").map((cat) => (
                    <SelectItem key={cat} value={cat}>
                      {cat}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="product-image">Emoji / Ícono</Label>
              <Input
                id="product-image"
                placeholder="🌮"
                value={image}
                onChange={(e) => setImage(e.target.value)}
                className="mt-1 text-2xl text-center"
                maxLength={2}
              />
            </div>

            <div className="flex items-center space-x-2 pt-6">
              <Checkbox
                id="available"
                checked={available}
                onCheckedChange={(checked) => setAvailable(checked as boolean)}
              />
              <Label htmlFor="available" className="cursor-pointer">
                Disponible
              </Label>
            </div>
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
            Guardar producto
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
