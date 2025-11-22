import { Navigation } from "@/components/Navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { mockProducts, categories, modifierGroups } from "@/data/mockProducts";
import { Search, Plus, Minus, Trash2, ShoppingCart } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";

interface CartItem {
  id: string;
  productId: string;
  name: string;
  price: number;
  quantity: number;
  modifiers: Array<{ name: string; price: number }>;
}

const POS = () => {
  const [selectedCategory, setSelectedCategory] = useState("Todos");
  const [searchQuery, setSearchQuery] = useState("");
  const [cart, setCart] = useState<CartItem[]>([]);
  const [serviceType, setServiceType] = useState<"dine-in" | "takeout" | "delivery">("dine-in");
  const [showModifierDialog, setShowModifierDialog] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<any>(null);
  const [selectedModifiers, setSelectedModifiers] = useState<Record<string, string[]>>({});

  const filteredProducts = mockProducts.filter((product) => {
    const matchesCategory = selectedCategory === "Todos" || product.category === selectedCategory;
    const matchesSearch = product.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch && product.available;
  });

  const handleProductClick = (product: any) => {
    if (product.modifierGroups && product.modifierGroups.length > 0) {
      setSelectedProduct(product);
      setSelectedModifiers({});
      setShowModifierDialog(true);
    } else {
      addToCart(product, []);
    }
  };

  const addToCart = (product: any, modifiers: Array<{ name: string; price: number }>) => {
    const modifierPrice = modifiers.reduce((sum, mod) => sum + mod.price, 0);
    const totalPrice = product.price + modifierPrice;

    const existingItemIndex = cart.findIndex(
      (item) =>
        item.productId === product.id &&
        JSON.stringify(item.modifiers) === JSON.stringify(modifiers)
    );

    if (existingItemIndex >= 0) {
      const newCart = [...cart];
      newCart[existingItemIndex].quantity += 1;
      setCart(newCart);
    } else {
      setCart([
        ...cart,
        {
          id: `${product.id}-${Date.now()}`,
          productId: product.id,
          name: product.name,
          price: totalPrice,
          quantity: 1,
          modifiers,
        },
      ]);
    }
    setShowModifierDialog(false);
  };

  const updateQuantity = (itemId: string, delta: number) => {
    setCart(
      cart
        .map((item) =>
          item.id === itemId ? { ...item, quantity: item.quantity + delta } : item
        )
        .filter((item) => item.quantity > 0)
    );
  };

  const removeItem = (itemId: string) => {
    setCart(cart.filter((item) => item.id !== itemId));
  };

  const subtotal = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const tax = subtotal * 0.08;
  const total = subtotal + tax;

  const handleAddModifiers = () => {
    const selectedMods: Array<{ name: string; price: number }> = [];
    
    selectedProduct.modifierGroups.forEach((groupId: string) => {
      const group = modifierGroups.find((g) => g.id === groupId);
      if (group && selectedModifiers[groupId]) {
        selectedModifiers[groupId].forEach((modId) => {
          const mod = group.modifiers.find((m) => m.id === modId);
          if (mod) selectedMods.push({ name: mod.name, price: mod.price });
        });
      }
    });

    addToCart(selectedProduct, selectedMods);
  };

  const canAddToCart = () => {
    if (!selectedProduct?.modifierGroups) return true;
    
    return selectedProduct.modifierGroups.every((groupId: string) => {
      const group = modifierGroups.find((g) => g.id === groupId);
      if (!group) return true;
      
      const selectedCount = selectedModifiers[groupId]?.length || 0;
      return selectedCount >= group.minSelection && selectedCount <= group.maxSelection;
    });
  };

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      
      <div className="pt-20 px-2 lg:px-4 pb-4">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:h-[calc(100vh-6rem)]">
          {/* Products Section */}
          <div className="lg:col-span-2 flex flex-col gap-4 h-auto lg:overflow-hidden">
            {/* Search & Filters */}
            <Card className="p-4">
              <div className="flex flex-col gap-3">
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
                  {categories.map((cat) => (
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
            </Card>

            {/* Products Grid */}
            <div className="lg:flex-1 lg:overflow-y-auto pb-4 lg:pb-0">
              <div className="grid grid-cols-3 md:grid-cols-4 xl:grid-cols-5 gap-2">
                {filteredProducts.map((product) => (
                  <Card
                    key={product.id}
                    className="p-3 cursor-pointer hover-lift"
                    onClick={() => handleProductClick(product)}
                  >
                    <h3 className="font-semibold text-sm mb-1 line-clamp-2">{product.name}</h3>
                    <p className="text-base font-bold text-secondary">${product.price.toFixed(2)}</p>
                    {product.modifierGroups && product.modifierGroups.length > 0 && (
                      <Badge variant="secondary" className="mt-1 text-xs">
                        Personalizable
                      </Badge>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          </div>

          {/* Cart Section */}
          <Card className="flex flex-col overflow-hidden">
            <div className="p-4 border-b">
              <h2 className="text-xl font-bold mb-3">Pedido Actual</h2>
              
              <div className="flex gap-2">
                <Button
                  variant={serviceType === "dine-in" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setServiceType("dine-in")}
                  className="flex-1"
                >
                  En Local
                </Button>
                <Button
                  variant={serviceType === "takeout" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setServiceType("takeout")}
                  className="flex-1"
                >
                  Para Llevar
                </Button>
                <Button
                  variant={serviceType === "delivery" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setServiceType("delivery")}
                  className="flex-1"
                >
                  Delivery
                </Button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              {cart.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                  <ShoppingCart className="h-16 w-16 mb-3 opacity-50" />
                  <p>Carrito vacío</p>
                  <p className="text-sm">Agrega productos para empezar</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {cart.map((item) => (
                    <Card key={item.id} className="p-3">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <h4 className="font-semibold text-sm">{item.name}</h4>
                          {item.modifiers.length > 0 && (
                            <div className="text-xs text-muted-foreground mt-1">
                              {item.modifiers.map((mod) => mod.name).join(", ")}
                            </div>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removeItem(item.id)}
                          className="h-7 w-7 text-danger"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => updateQuantity(item.id, -1)}
                            className="h-7 w-7"
                          >
                            <Minus className="h-3 w-3" />
                          </Button>
                          <span className="w-8 text-center font-semibold">{item.quantity}</span>
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => updateQuantity(item.id, 1)}
                            className="h-7 w-7"
                          >
                            <Plus className="h-3 w-3" />
                          </Button>
                        </div>
                        <span className="font-bold">${(item.price * item.quantity).toFixed(2)}</span>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </div>

            <div className="p-4 border-t space-y-3">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span>Subtotal</span>
                  <span>${subtotal.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Impuesto (8%)</span>
                  <span>${tax.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-lg font-bold">
                  <span>Total</span>
                  <span className="text-secondary">${total.toFixed(2)}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <Button variant="outline" disabled={cart.length === 0}>
                  Guardar
                </Button>
                <Button variant="outline" onClick={() => setCart([])}>
                  Cancelar
                </Button>
              </div>
              
              <Button 
                variant="default"
                className="w-full font-bold"
                size="lg"
                disabled={cart.length === 0}
              >
                Cobrar ${total.toFixed(2)}
              </Button>
            </div>
          </Card>
        </div>
      </div>

      {/* Modifier Dialog */}
      <Dialog open={showModifierDialog} onOpenChange={setShowModifierDialog}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Personalizar {selectedProduct?.name}</DialogTitle>
            <DialogDescription>
              Selecciona tus opciones favoritas
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            {selectedProduct?.modifierGroups?.map((groupId: string) => {
              const group = modifierGroups.find((g) => g.id === groupId);
              if (!group) return null;

              const selectedCount = selectedModifiers[groupId]?.length || 0;
              const isValid = selectedCount >= group.minSelection && selectedCount <= group.maxSelection;

              return (
                <div key={groupId} className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold">
                      {group.name}
                      {group.required && <span className="text-danger ml-1">*</span>}
                    </h3>
                    <Badge variant={isValid ? "default" : "destructive"}>
                      {selectedCount}/{group.maxSelection} seleccionados
                    </Badge>
                  </div>

                  {group.maxSelection === 1 ? (
                    <RadioGroup
                      value={selectedModifiers[groupId]?.[0] || ""}
                      onValueChange={(value) =>
                        setSelectedModifiers({ ...selectedModifiers, [groupId]: [value] })
                      }
                    >
                      {group.modifiers.map((mod) => (
                        <div key={mod.id} className="flex items-center space-x-2 p-2 rounded hover:bg-muted">
                          <RadioGroupItem value={mod.id} id={mod.id} />
                          <Label htmlFor={mod.id} className="flex-1 cursor-pointer">
                            {mod.name}
                          </Label>
                          {mod.price > 0 && (
                            <span className="text-sm text-muted-foreground">+${mod.price.toFixed(2)}</span>
                          )}
                        </div>
                      ))}
                    </RadioGroup>
                  ) : (
                    <div className="space-y-2">
                      {group.modifiers.map((mod) => (
                        <div key={mod.id} className="flex items-center space-x-2 p-2 rounded hover:bg-muted">
                          <Checkbox
                            id={mod.id}
                            checked={selectedModifiers[groupId]?.includes(mod.id) || false}
                            onCheckedChange={(checked) => {
                              const current = selectedModifiers[groupId] || [];
                              if (checked && current.length < group.maxSelection) {
                                setSelectedModifiers({
                                  ...selectedModifiers,
                                  [groupId]: [...current, mod.id],
                                });
                              } else if (!checked) {
                                setSelectedModifiers({
                                  ...selectedModifiers,
                                  [groupId]: current.filter((id) => id !== mod.id),
                                });
                              }
                            }}
                            disabled={
                              !selectedModifiers[groupId]?.includes(mod.id) &&
                              (selectedModifiers[groupId]?.length || 0) >= group.maxSelection
                            }
                          />
                          <Label htmlFor={mod.id} className="flex-1 cursor-pointer">
                            {mod.name}
                          </Label>
                          {mod.price > 0 && (
                            <span className="text-sm text-muted-foreground">+${mod.price.toFixed(2)}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <Button
            className="w-full"
            onClick={handleAddModifiers}
            disabled={!canAddToCart()}
          >
            Agregar al Pedido
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default POS;
