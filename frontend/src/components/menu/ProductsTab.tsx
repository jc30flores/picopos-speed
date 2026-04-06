import { useCallback, useEffect, useMemo, useState } from "react";
import { Search, Plus, Edit, Settings, Trash2, GripVertical, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ImageUploadField } from "@/components/ui/image-upload-field";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { getEntityImageSrc } from "@/lib/media";
import { ModifierGroupsAdminModal } from "./ModifierGroupsAdminModal";
import { ProductModifiersModal } from "./ProductModifiersModal";
import { ProductFormDialog } from "./ProductFormDialog";
import { getCategories, getModifierGroups, getProducts, updateProductAvailability, deleteProduct, deleteCategory, createCategory, updateCategory, reorderCategories, reorderProducts, duplicateProduct, Category, ModifierGroup, Product, type CategoryDeleteConflictError } from "@/lib/api";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { useReorderableList } from "@/hooks/useReorderableList";

interface InlineStatusToggleProps {
  product: Product;
  onUpdated: (updated: Product) => void;
}

const InlineStatusToggle = ({ product, onUpdated }: InlineStatusToggleProps) => {
  const [isUpdating, setIsUpdating] = useState(false);

  const handleToggle = async () => {
    if (isUpdating) return;
    const nextValue = !product.available;
    setIsUpdating(true);
    try {
      const updated = await updateProductAvailability(product.id, nextValue);
      onUpdated(updated);
    } catch (error) {
      console.error("Failed to update product availability", error);
      toast.error("No se pudo cambiar el estado");
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleToggle}
      disabled={isUpdating}
      className="inline-flex"
      aria-pressed={product.available}
    >
      <Badge
        variant={product.available ? "default" : "outline"}
        className={cn(
          "transition-opacity",
          isUpdating ? "opacity-60" : "cursor-pointer hover:opacity-80"
        )}
      >
        {product.available ? "Activo" : "Inactivo"}
      </Badge>
    </button>
  );
};

export const ProductsTab = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("Todos");
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [showProductForm, setShowProductForm] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [modifierGroups, setModifierGroups] = useState<ModifierGroup[]>([]);
  const [productToDelete, setProductToDelete] = useState<Product | null>(null);
  const [categoryToDelete, setCategoryToDelete] = useState<Category | null>(null);
  const [isDeletingCategory, setIsDeletingCategory] = useState(false);
  const [categoryDeleteError, setCategoryDeleteError] = useState<string | null>(null);
  const [categoryDeleteActiveProducts, setCategoryDeleteActiveProducts] = useState<string[]>([]);
  const [isCategoryManagerOpen, setIsCategoryManagerOpen] = useState(false);
  const [isModifierGroupsAdminOpen, setIsModifierGroupsAdminOpen] = useState(false);
  const [isProductModifiersOpen, setIsProductModifiersOpen] = useState(false);
  const [menuLoadError, setMenuLoadError] = useState<string | null>(null);
  const [isMenuLoading, setIsMenuLoading] = useState(true);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);
  const [editingCategoryName, setEditingCategoryName] = useState("");
  const [editingCategoryImage, setEditingCategoryImage] = useState<File | null>(null);
  const [removeEditingCategoryImage, setRemoveEditingCategoryImage] = useState(false);
  const [draggingCategoryId, setDraggingCategoryId] = useState<number | null>(null);
  const [dragOverCategoryId, setDragOverCategoryId] = useState<number | null>(null);
  const [isSavingCategoryOrder, setIsSavingCategoryOrder] = useState(false);
  const [draggingProductId, setDraggingProductId] = useState<number | null>(null);
  const [dragOverProductId, setDragOverProductId] = useState<number | null>(null);
  const [isSavingProductOrder, setIsSavingProductOrder] = useState(false);

  const loadMenuData = useCallback(async (productId: number | null = selectedProduct?.id ?? null) => {
    setIsMenuLoading(true);
    setMenuLoadError(null);
    try {
      const [categoriesResponse, productsResponse, modifierGroupsResponse] = await Promise.all([
        getCategories(),
        getProducts(),
        getModifierGroups(),
      ]);
      setCategories(categoriesResponse);
      setProducts(productsResponse);
      setModifierGroups(modifierGroupsResponse);
      if (productId) {
        const updatedProduct = productsResponse.find((product) => product.id === productId) ?? null;
        setSelectedProduct(updatedProduct);
      }
    } catch (error) {
      setMenuLoadError(error instanceof Error ? error.message : "No se pudo cargar el menú");
      throw error;
    } finally {
      setIsMenuLoading(false);
    }
  }, [selectedProduct?.id]);

  useEffect(() => {
    loadMenuData().catch((error) => {
      console.error("Failed to load menu data", error);
      toast.error("No se pudo cargar el menú");
    });
  }, [loadMenuData]);

  const visibleCategories = categories.filter((cat) => !cat.isHidden && !cat.name.toUpperCase().includes("SIN CATEGORÍA"));
  const categoryNames = ["Todos", ...visibleCategories.map((cat) => cat.name)];

  const filteredProducts = useMemo(() => products.filter((product) => {
    const matchesCategory = selectedCategory === "Todos" || product.category === selectedCategory;
    const matchesSearch = product.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  }), [products, searchQuery, selectedCategory]);

  const canReorderProducts = selectedCategory !== "Todos" && !searchQuery.trim();
  const productReorderHint = selectedCategory === "Todos"
    ? "Selecciona una categoría para ordenar productos."
    : searchQuery.trim()
      ? "Limpia la búsqueda para ordenar productos."
      : null;

  const categoryReorder = useReorderableList(visibleCategories, (category) => category.id);

  const selectedCategoryId = useMemo(
    () =>
      selectedCategory === "Todos"
        ? null
        : categories.find((category) => category.name === selectedCategory)?.id ?? null,
    [categories, selectedCategory]
  );
  const categoryProducts = useMemo(() => {
    if (!selectedCategoryId) return [];
    return products.filter((product) => {
      const category = categories.find((candidate) => candidate.name === product.category);
      return category?.id === selectedCategoryId;
    });
  }, [categories, products, selectedCategoryId]);
  const productReorder = useReorderableList(categoryProducts, (product) => product.id);

  const handleNewProduct = () => {
    setEditingProduct(null);
    setShowProductForm(true);
  };

  const handleEditProduct = (product: Product) => {
    setEditingProduct(product);
    setShowProductForm(true);
  };

  const handleStatusUpdated = (updated: Product) => {
    setProducts((prev) => prev.map((product) => (product.id === updated.id ? updated : product)));
    setSelectedProduct((prev) => (prev?.id === updated.id ? updated : prev));
  };

  const handleDeleteProduct = async () => {
    if (!productToDelete) return;
    try {
      const result = await deleteProduct(productToDelete.id);
      await loadMenuData();
      toast.success(result.detail || "Producto eliminado");
      setProductToDelete(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo eliminar el producto");
    }
  };

  const handleDuplicateProduct = async (product: Product) => {
    if (!window.confirm("¿Duplicar producto?")) return;
    try {
      await duplicateProduct(product.id);
      await loadMenuData(product.id);
      toast.success("Producto duplicado");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo duplicar el producto");
    }
  };

  const handleDeleteCategory = async () => {
    if (!categoryToDelete || isDeletingCategory) return;
    setIsDeletingCategory(true);
    try {
      await deleteCategory(categoryToDelete.id);
      setCategories((prev) => prev.filter((category) => category.id !== categoryToDelete.id));
      if (selectedCategory === categoryToDelete.name) {
        setSelectedCategory("Todos");
      }
      await loadMenuData();
      toast.success("Categoría eliminada");
      setCategoryDeleteError(null);
      setCategoryDeleteActiveProducts([]);
      setCategoryToDelete(null);
    } catch (error) {
      const conflictError = error as CategoryDeleteConflictError;
      setCategoryDeleteError(conflictError.message || "No se pudo eliminar la categoría");
      setCategoryDeleteActiveProducts(conflictError.activeProducts ?? []);
      toast.error(conflictError.message || "No se pudo eliminar la categoría");
    } finally {
      setIsDeletingCategory(false);
    }
  };

  const handleCreateCategory = async () => {
    const normalized = newCategoryName.trim().toUpperCase();
    if (!normalized) return;
    try {
      await createCategory({ name: normalized });
      setNewCategoryName("");
      await loadMenuData();
      toast.success("Categoría creada");
    } catch (error) {
      toast.error("No se pudo crear la categoría");
    }
  };

  const handleUpdateCategory = async () => {
    if (!editingCategoryId) return;
    const normalized = editingCategoryName.trim().toUpperCase();
    if (!normalized) return;
    try {
      await updateCategory(editingCategoryId, {
        name: normalized,
        image: editingCategoryImage,
        removeImage: removeEditingCategoryImage,
      });
      setEditingCategoryId(null);
      setEditingCategoryName("");
      setEditingCategoryImage(null);
      setRemoveEditingCategoryImage(false);
      await loadMenuData();
      toast.success("Categoría actualizada");
    } catch (error) {
      console.error("Failed to update category", error);
      toast.error("No se pudo actualizar la categoría");
    }
  };


  const handleCategoryDragEnter = (targetCategoryId: number) => {
    if (draggingCategoryId === null || draggingCategoryId === targetCategoryId || isSavingCategoryOrder) return;
    categoryReorder.moveById(draggingCategoryId, targetCategoryId);
    setDragOverCategoryId(targetCategoryId);
  };

  const handleSaveCategoryOrder = async () => {
    if (isSavingCategoryOrder || !categoryReorder.isDirty) return;
    setIsSavingCategoryOrder(true);
    try {
      const ordered = await reorderCategories(categoryReorder.currentItems.map((category) => category.id));
      setCategories((prev) => {
        const hidden = prev.filter((category) => category.isHidden || category.name.toUpperCase().includes("SIN CATEGORÍA"));
        return [...ordered, ...hidden];
      });
      categoryReorder.markSaved();
      toast.success("Orden de categorías guardado");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo guardar el orden de categorías");
    } finally {
      setIsSavingCategoryOrder(false);
      setDraggingCategoryId(null);
      setDragOverCategoryId(null);
    }
  };

  const handleProductDragEnter = (targetProductId: number) => {
    if (draggingProductId === null || draggingProductId === targetProductId || isSavingProductOrder || !canReorderProducts) return;
    productReorder.moveById(draggingProductId, targetProductId);
    setDragOverProductId(targetProductId);
  };

  const handleSaveProductOrder = async () => {
    if (isSavingProductOrder || !canReorderProducts || !productReorder.isDirty || !selectedCategoryId) return;
    setIsSavingProductOrder(true);
    try {
      await reorderProducts({
        categoryId: selectedCategoryId,
        orderedIds: productReorder.currentItems.map((product) => product.id),
      });
      productReorder.markSaved();
      toast.success("Orden de productos guardado");
      await loadMenuData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo guardar el orden de productos");
    } finally {
      setIsSavingProductOrder(false);
      setDraggingProductId(null);
      setDragOverProductId(null);
    }
  };

  const displayProducts = useMemo(() => {
    if (!canReorderProducts || !selectedCategoryId) return filteredProducts;
    const orderedIds = new Set(productReorder.currentItems.map((product) => product.id));
    const outsideCategory = filteredProducts.filter((product) => !orderedIds.has(product.id));
    return [...productReorder.currentItems, ...outsideCategory];
  }, [canReorderProducts, filteredProducts, productReorder.currentItems, selectedCategoryId]);


  return (
    <div className="space-y-6">
      {/* Left: Products Table (60%) */}
      <div className="space-y-4">
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold">Productos del Menú</h2>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setIsCategoryManagerOpen(true)}>
                Gestionar categorías
              </Button>
              <Button variant="outline" onClick={() => setIsModifierGroupsAdminOpen(true)}>
                Gestionar modificadores
              </Button>
              <Button
                variant="default"
                className="bg-secondary hover:bg-secondary/90"
                onClick={handleNewProduct}
              >
                <Plus className="h-4 w-4 mr-2" />
                Nuevo Producto
              </Button>
            </div>
          </div>

          <div className="space-y-4">
            {menuLoadError && (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                <p>{menuLoadError}</p>
                <Button variant="outline" size="sm" className="mt-2" onClick={() => loadMenuData().catch(() => undefined)}>
                  Reintentar
                </Button>
              </div>
            )}

            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar productos..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            <div className="flex gap-2.5 overflow-x-auto pb-1">
              {categoryNames.map((cat) => (
                <Badge
                  key={cat}
                  variant={selectedCategory === cat ? "default" : "outline"}
                  className={cn(
                    "cursor-pointer transition-all whitespace-nowrap rounded-full px-4 py-2 text-sm min-h-10 inline-flex items-center",
                    selectedCategory === cat && "bg-primary text-primary-foreground"
                  )}
                  onClick={() => setSelectedCategory(cat)}
                >
                  {cat}
                </Badge>
              ))}
            </div>
          </div>

          <div className="mt-6 border rounded-lg overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10"></TableHead>
                  <TableHead>Producto</TableHead>
                  <TableHead>Categoría</TableHead>
                  <TableHead>Precio</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isMenuLoading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-sm text-muted-foreground">Cargando productos...</TableCell>
                  </TableRow>
                ) : displayProducts.map((product) => (
                  <TableRow
                    key={product.id}
                    className={cn(
                      canReorderProducts && "cursor-move transition-all",
                      draggingProductId === product.id && "opacity-60 ring-2 ring-primary/50",
                      dragOverProductId === product.id && draggingProductId !== product.id && "bg-muted/40"
                    )}
                    onDragOver={(event) => {
                      if (!canReorderProducts) return;
                      event.preventDefault();
                    }}
                    onDragEnter={() => handleProductDragEnter(product.id)}
                    onDrop={() => setDragOverProductId(product.id)}
                  >
                    <TableCell>
                      <button
                        type="button"
                        className="cursor-grab rounded-md border border-border p-1 text-muted-foreground hover:bg-muted disabled:cursor-not-allowed"
                        draggable={canReorderProducts && !isSavingProductOrder}
                        disabled={!canReorderProducts || isSavingProductOrder}
                        onDragStart={() => setDraggingProductId(product.id)}
                        onDragEnd={() => { setDraggingProductId(null); setDragOverProductId(null); }}
                        aria-label={`Mover producto ${product.name}`}
                        title={canReorderProducts ? "Arrastrar para reordenar" : "Selecciona una categoría y limpia búsqueda"}
                      >
                        <GripVertical className="h-4 w-4" />
                      </button>
                    </TableCell>
                    <TableCell>
                      <div>
                        <div className="font-semibold">{product.name}</div>
                        <div className="text-sm text-muted-foreground line-clamp-1">
                          {product.description}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{product.category}</Badge>
                    </TableCell>
                    <TableCell className="font-semibold text-secondary">
                      ${product.price.toFixed(2)}
                    </TableCell>
                    <TableCell>
                      <InlineStatusToggle product={product} onUpdated={handleStatusUpdated} />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSelectedProduct(product);
                            setIsProductModifiersOpen(true);
                          }}
                        >
                          <Settings className="h-4 w-4 mr-1" />
                          Modificadores
                        </Button>
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => handleDuplicateProduct(product)}
                          title="Duplicar"
                          aria-label="Duplicar producto"
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => handleEditProduct(product)}
                          title="Editar"
                          aria-label="Editar producto"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => setProductToDelete(product)}
                          title="Eliminar"
                          aria-label="Eliminar producto"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {canReorderProducts && productReorder.isDirty && (
            <div className="mt-4 flex items-center justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  productReorder.reset();
                  setDraggingProductId(null);
                  setDragOverProductId(null);
                }}
                disabled={isSavingProductOrder}
              >
                Deshacer cambios
              </Button>
              <Button variant="outline" onClick={() => void handleSaveProductOrder()} disabled={isSavingProductOrder}>
                {isSavingProductOrder ? "Guardando..." : "Guardar orden"}
              </Button>
            </div>
          )}
        </Card>
      </div>


      <ModifierGroupsAdminModal
        open={isModifierGroupsAdminOpen}
        onOpenChange={setIsModifierGroupsAdminOpen}
        modifierGroups={modifierGroups}
        onUpdated={() => loadMenuData()}
      />

      <ProductModifiersModal
        open={isProductModifiersOpen}
        onOpenChange={setIsProductModifiersOpen}
        selectedProduct={selectedProduct}
        modifierGroups={modifierGroups}
        onUpdated={loadMenuData}
      />


      {/* Product Form Dialog */}
      <ProductFormDialog
        open={showProductForm}
        onOpenChange={setShowProductForm}
        editingProduct={editingProduct}
        categories={categories}
        onSaved={loadMenuData}
      />

      <Dialog open={Boolean(productToDelete)} onOpenChange={(open) => !open && setProductToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Eliminar producto: {productToDelete?.name}</DialogTitle>
            <DialogDescription>
              Si el producto tiene ventas históricas, se archivará para preservar integridad.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setProductToDelete(null)}>Cancelar</Button>
            <Button variant="destructive" onClick={handleDeleteProduct}>Eliminar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(categoryToDelete)} onOpenChange={(open) => { if (!open) { setCategoryToDelete(null); setCategoryDeleteError(null); setCategoryDeleteActiveProducts([]); setIsDeletingCategory(false); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Eliminar categoría: {categoryToDelete?.name}</DialogTitle>
            <DialogDescription>
              Solo se puede eliminar si no tiene productos activos asociados.
            </DialogDescription>
            {categoryDeleteError && (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                <p>{categoryDeleteError}</p>
                {categoryDeleteActiveProducts.length > 0 && (
                  <ul className="mt-2 list-disc space-y-1 pl-5">
                    {categoryDeleteActiveProducts.map((productName) => (
                      <li key={productName}>{productName}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCategoryToDelete(null)}>Cancelar</Button>
            <Button variant="destructive" onClick={handleDeleteCategory} disabled={isDeletingCategory}>{isDeletingCategory ? "Eliminando..." : "Eliminar"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isCategoryManagerOpen} onOpenChange={setIsCategoryManagerOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Gestión de Categorías</DialogTitle>
            <DialogDescription>Crear, editar y eliminar categorías desde un solo lugar.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex gap-2">
              <Input value={newCategoryName} onChange={(e) => setNewCategoryName(e.target.value)} placeholder="Nueva categoría" />
              <Button onClick={handleCreateCategory}>Crear</Button>
            </div>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {categoryReorder.currentItems.map((category) => (
                <div
                  key={category.id}
                  className={cn(
                    "flex items-center gap-2 rounded-lg border p-2 transition-all",
                    draggingCategoryId === category.id && "opacity-50 ring-2 ring-primary/50",
                    dragOverCategoryId === category.id && draggingCategoryId !== category.id && "bg-muted/40"
                  )}
                  onDragOver={(event) => {
                    event.preventDefault();
                    if (draggingCategoryId !== null) {
                      event.dataTransfer.dropEffect = "move";
                    }
                  }}
                  onDragEnter={() => handleCategoryDragEnter(category.id)}
                  onDrop={() => setDragOverCategoryId(category.id)}
                >
                  {editingCategoryId === category.id ? (
                    <div className="flex w-full flex-col gap-2">
                      <Input value={editingCategoryName} onChange={(e) => setEditingCategoryName(e.target.value)} />
                      <ImageUploadField
                        id={`edit-category-image-${category.id}`}
                        label="Imagen"
                        file={editingCategoryImage}
                        previewUrl={removeEditingCategoryImage ? null : getEntityImageSrc(category)}
                        onChange={(file) => {
                          setEditingCategoryImage(file);
                          if (file) setRemoveEditingCategoryImage(false);
                        }}
                      />
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" onClick={() => { setEditingCategoryImage(null); setRemoveEditingCategoryImage(true); }}>
                          Quitar imagen
                        </Button>
                        <Button size="sm" onClick={handleUpdateCategory}>Guardar</Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      {getEntityImageSrc(category) ? <img src={getEntityImageSrc(category) ?? ""} alt={category.name} className="h-10 w-10 rounded-md border object-cover" /> : null}
                      <button
                        type="button"
                        className="cursor-grab rounded-md border border-border p-1 text-muted-foreground hover:bg-muted"
                        draggable={!isSavingCategoryOrder}
                        onDragStart={() => setDraggingCategoryId(category.id)}
                        onDragEnd={() => { setDraggingCategoryId(null); setDragOverCategoryId(null); }}
                        aria-label={`Mover categoría ${category.name}`}
                        title="Arrastrar para reordenar"
                      >
                        <GripVertical className="h-4 w-4" />
                      </button>
                      <div className="flex-1 font-medium">{category.name}</div>
                      <Button size="sm" variant="outline" onClick={() => { setEditingCategoryId(category.id); setEditingCategoryName(category.name); setEditingCategoryImage(null); setRemoveEditingCategoryImage(false); }}>
                        Editar
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => { setCategoryDeleteError(null); setCategoryDeleteActiveProducts([]); setCategoryToDelete(category); }}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </>
                  )}
                </div>
              ))}
            </div>
            {categoryReorder.isDirty && (
              <div className="flex items-center justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    categoryReorder.reset();
                    setDraggingCategoryId(null);
                    setDragOverCategoryId(null);
                  }}
                  disabled={isSavingCategoryOrder}
                >
                  Deshacer cambios
                </Button>
                <Button
                  variant="outline"
                  onClick={() => void handleSaveCategoryOrder()}
                  disabled={isSavingCategoryOrder}
                >
                  {isSavingCategoryOrder ? "Guardando..." : "Guardar orden"}
                </Button>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
