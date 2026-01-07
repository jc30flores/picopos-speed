import { useMemo, useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator } from "@/components/ui/command";
import { Category, createCategory, createProduct, getCategories, Product, updateProduct } from "@/lib/api";

interface ProductFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingProduct?: Product | null;
  categories: Category[];
  onSaved: () => Promise<void>;
}

export const ProductFormDialog = ({
  open,
  onOpenChange,
  editingProduct,
  categories,
  onSaved,
}: ProductFormDialogProps) => {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [categoryQuery, setCategoryQuery] = useState("");
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [categoryOptions, setCategoryOptions] = useState<Category[]>(categories);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [isFetchingCategories, setIsFetchingCategories] = useState(false);
  const [isCreatingCategory, setIsCreatingCategory] = useState(false);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [existingImageUrl, setExistingImageUrl] = useState<string | null>(null);
  const [localImageUrl, setLocalImageUrl] = useState<string | null>(null);
  const [available, setAvailable] = useState(true);

  useEffect(() => {
    if (editingProduct) {
      setName(editingProduct.name);
      setDescription(editingProduct.description);
      setPrice(editingProduct.price ? String(editingProduct.price) : "");
      setCategoryQuery(editingProduct.category);
      setSelectedCategoryId(editingProduct.categoryId);
      setImageFile(null);
      setExistingImageUrl(editingProduct.imageUrl ?? null);
      setAvailable(editingProduct.available);
    } else {
      setName("");
      setDescription("");
      setPrice("");
      setCategoryQuery("");
      setSelectedCategoryId(null);
      setImageFile(null);
      setExistingImageUrl(null);
      setAvailable(true);
    }
  }, [editingProduct, open]);

  useEffect(() => {
    if (!imageFile) {
      setLocalImageUrl(null);
      return;
    }
    const previewUrl = URL.createObjectURL(imageFile);
    setLocalImageUrl(previewUrl);
    return () => {
      URL.revokeObjectURL(previewUrl);
    };
  }, [imageFile]);

  useEffect(() => {
    const handler = window.setTimeout(async () => {
      setIsFetchingCategories(true);
      try {
        const data = await getCategories(categoryQuery.trim() || undefined);
        setCategoryOptions(data);
      } finally {
        setIsFetchingCategories(false);
      }
    }, 300);
    return () => window.clearTimeout(handler);
  }, [categoryQuery]);

  useEffect(() => {
    if (!categoryQuery.trim()) {
      setCategoryOptions(categories);
    }
  }, [categories, categoryQuery]);

  const selectedCategoryName = useMemo(() => {
    if (selectedCategoryId) {
      return (
        categoryOptions.find((cat) => cat.id === selectedCategoryId)?.name ||
        categories.find((cat) => cat.id === selectedCategoryId)?.name ||
        ""
      );
    }
    return "";
  }, [categoryOptions, categories, selectedCategoryId]);

  const canCreateCategory = useMemo(() => {
    const normalized = categoryQuery.trim().toUpperCase();
    if (!normalized) return false;
    return !categoryOptions.some((cat) => cat.name.toUpperCase() === normalized);
  }, [categoryOptions, categoryQuery]);

  const isValid = () => {
    const parsed = price === "" ? NaN : Number(price);
    return name.trim() !== "" && selectedCategoryId !== null && Number.isFinite(parsed) && parsed > 0;
  };

  const handleSave = async () => {
    if (!isValid()) return;

    const parsedPrice = price === "" ? NaN : Number(price);
    if (!Number.isFinite(parsedPrice) || parsedPrice <= 0) return;

    if (editingProduct) {
      await updateProduct(editingProduct.id, {
        name,
        description,
        price: parsedPrice,
        categoryId: selectedCategoryId ?? 0,
        image: imageFile,
        available,
      });
    } else {
      await createProduct({
        name,
        description,
        price: parsedPrice,
        categoryId: selectedCategoryId ?? 0,
        image: imageFile,
        available,
      });
    }
    await onSaved();
    onOpenChange(false);
  };

  const handleSelectCategory = (categoryItem: Category) => {
    setSelectedCategoryId(categoryItem.id);
    setCategoryQuery(categoryItem.name);
    setCategoryOpen(false);
  };

  const handleCreateCategory = async () => {
    const normalized = categoryQuery.trim().toUpperCase();
    if (!normalized || isCreatingCategory) return;
    setIsCreatingCategory(true);
    try {
      const created = await createCategory(normalized);
      setCategoryOptions((prev) => {
        if (prev.some((cat) => cat.id === created.id)) return prev;
        return [...prev, created];
      });
      setSelectedCategoryId(created.id);
      setCategoryQuery(created.name);
      setCategoryOpen(false);
    } finally {
      setIsCreatingCategory(false);
    }
  };

  const previewUrl = localImageUrl ?? existingImageUrl;

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
                type="text"
                inputMode="decimal"
                placeholder="0.00"
                value={price}
                onChange={(e) => {
                  const value = e.target.value;
                  if (value === "" || /^\d*\.?\d*$/.test(value)) {
                    setPrice(value);
                  }
                }}
                className="mt-1"
              />
            </div>

            <div>
              <Label htmlFor="product-category">Categoría</Label>
              <Popover open={categoryOpen} onOpenChange={setCategoryOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    className="mt-1 w-full justify-between"
                  >
                    {selectedCategoryName || "Selecciona categoría"}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[320px] p-0" align="start">
                  <Command shouldFilter={false}>
                    <CommandInput
                      placeholder="Buscar categoría..."
                      value={categoryQuery}
                      onValueChange={(value) => {
                        setCategoryQuery(value.toUpperCase());
                        setSelectedCategoryId(null);
                      }}
                      className="uppercase"
                    />
                    <CommandList>
                      {isFetchingCategories && (
                        <CommandItem disabled>Buscando categorías...</CommandItem>
                      )}
                      {!isFetchingCategories && categoryOptions.length === 0 && (
                        <div className="py-6 text-center text-sm text-muted-foreground">
                          Sin coincidencias
                        </div>
                      )}
                      {categoryOptions.length > 0 && (
                        <CommandGroup heading="Categorías">
                          {categoryOptions.map((cat) => (
                            <CommandItem
                              key={cat.id}
                              value={cat.name}
                              onSelect={() => handleSelectCategory(cat)}
                            >
                              {cat.name}
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      )}
                      {canCreateCategory && (
                        <>
                          <CommandSeparator />
                          <CommandGroup heading="Crear">
                            <CommandItem onSelect={handleCreateCategory}>
                              {isCreatingCategory
                                ? "Creando categoría..."
                                : `Crear categoría: ${categoryQuery.trim().toUpperCase()}`}
                            </CommandItem>
                          </CommandGroup>
                        </>
                      )}
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            <div>
              <Label htmlFor="product-image">Imagen</Label>
              <Input
                id="product-image"
                type="file"
                accept="image/*"
                capture="environment"
                onChange={(e) => setImageFile(e.target.files?.[0] ?? null)}
                className="mt-1"
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
          {previewUrl && (
            <div className="mt-4">
              <Label className="text-sm">Vista previa</Label>
              <div className="mt-2 flex justify-center">
                <img
                  src={previewUrl}
                  alt="Vista previa del producto"
                  className="h-32 w-32 rounded-lg object-cover border"
                />
              </div>
            </div>
          )}
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
