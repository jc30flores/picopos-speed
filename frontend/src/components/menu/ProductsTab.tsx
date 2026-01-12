import { useEffect, useState } from "react";
import { Search, Plus, Edit, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { ModifierPanel } from "./ModifierPanel";
import { ProductFormDialog } from "./ProductFormDialog";
import { getCategories, getModifierGroups, getProducts, updateProductAvailability, Category, ModifierGroup, Product } from "@/lib/api";
import { toast } from "sonner";

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

  const loadMenuData = async (productId: number | null = selectedProduct?.id ?? null) => {
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
  };

  useEffect(() => {
    loadMenuData().catch((error) => {
      console.error("Failed to load menu data", error);
    });
  }, []);

  const categoryNames = ["Todos", ...categories.map((cat) => cat.name)];

  const filteredProducts = products.filter((product) => {
    const matchesCategory = selectedCategory === "Todos" || product.category === selectedCategory;
    const matchesSearch = product.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      {/* Left: Products Table (60%) */}
      <div className="lg:col-span-3 space-y-4">
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold">Productos del Menú</h2>
            <Button
              variant="default"
              className="bg-secondary hover:bg-secondary/90"
              onClick={handleNewProduct}
            >
              <Plus className="h-4 w-4 mr-2" />
              Nuevo Producto
            </Button>
          </div>

          <div className="space-y-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar productos..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            <div className="flex gap-2 flex-wrap">
              {categoryNames.map((cat) => (
                <Badge
                  key={cat}
                  variant={selectedCategory === cat ? "default" : "outline"}
                  className={cn(
                    "cursor-pointer transition-all hover:scale-105",
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
                  <TableHead>Producto</TableHead>
                  <TableHead>Categoría</TableHead>
                  <TableHead>Precio</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredProducts.map((product) => (
                  <TableRow key={product.id}>
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
                          onClick={() => handleEditProduct(product)}
                        >
                          <Edit className="h-4 w-4 mr-1" />
                          Editar
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setSelectedProduct(product)}
                        >
                          <Settings className="h-4 w-4 mr-1" />
                          Modificadores
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      </div>

      {/* Right: Modifier Panel (40%) */}
      <div className="lg:col-span-2">
        <ModifierPanel
          selectedProduct={selectedProduct}
          modifierGroups={modifierGroups}
          onModifierGroupsUpdated={loadMenuData}
        />
      </div>

      {/* Product Form Dialog */}
      <ProductFormDialog
        open={showProductForm}
        onOpenChange={setShowProductForm}
        editingProduct={editingProduct}
        categories={categories}
        onSaved={loadMenuData}
      />
    </div>
  );
};
