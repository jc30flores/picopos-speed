import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { mockProducts, categories, modifierGroups } from "@/data/mockProducts";
import { ArrowLeft, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";

type Step = "welcome" | "category" | "products" | "modifiers" | "review" | "payment" | "complete";

interface CartItem {
  id: string;
  name: string;
  price: number;
  quantity: number;
  modifiers: Array<{ name: string; price: number }>;
}

const Kiosk = () => {
  const [step, setStep] = useState<Step>("welcome");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [cart, setCart] = useState<CartItem[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<any>(null);
  const [selectedModifiers, setSelectedModifiers] = useState<Record<string, string[]>>({});
  const [orderNumber] = useState(Math.floor(Math.random() * 900) + 100);

  const handleCategorySelect = (category: string) => {
    setSelectedCategory(category);
    setStep("products");
  };

  const handleProductSelect = (product: any) => {
    setSelectedProduct(product);
    setSelectedModifiers({});
    if (product.modifierGroups && product.modifierGroups.length > 0) {
      setStep("modifiers");
    } else {
      addToCart(product, []);
      setStep("review");
    }
  };

  const addToCart = (product: any, modifiers: Array<{ name: string; price: number }>) => {
    const modifierPrice = modifiers.reduce((sum, mod) => sum + mod.price, 0);
    const totalPrice = product.price + modifierPrice;

    setCart([
      ...cart,
      {
        id: `${product.id}-${Date.now()}`,
        name: product.name,
        price: totalPrice,
        quantity: 1,
        modifiers,
      },
    ]);
  };

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
    setStep("review");
  };

  const canContinue = () => {
    if (!selectedProduct?.modifierGroups) return true;
    
    return selectedProduct.modifierGroups.every((groupId: string) => {
      const group = modifierGroups.find((g) => g.id === groupId);
      if (!group) return true;
      
      const selectedCount = selectedModifiers[groupId]?.length || 0;
      return selectedCount >= group.minSelection && selectedCount <= group.maxSelection;
    });
  };

  const total = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);

  if (step === "welcome") {
    return (
      <div className="min-h-screen bg-gradient-primary flex items-center justify-center p-8">
        <Card className="max-w-2xl w-full p-12 text-center space-y-8 shadow-2xl">
          <div className="w-24 h-24 bg-gradient-accent rounded-3xl flex items-center justify-center mx-auto shadow-xl">
            <span className="text-6xl">🌶️</span>
          </div>
          <div>
            <h1 className="text-5xl font-bold mb-3">Pico de Gallo</h1>
            <p className="text-xl text-muted-foreground">Autoservicio - Kiosk</p>
          </div>
          <Button
            size="lg"
            className="w-full text-2xl py-8 bg-gradient-accent text-primary-foreground font-bold hover:scale-105 transition-transform"
            onClick={() => setStep("category")}
          >
            Empezar Pedido
          </Button>
          <div className="flex gap-4 justify-center">
            <Button variant="outline" size="lg">Español</Button>
            <Button variant="outline" size="lg">English</Button>
          </div>
        </Card>
      </div>
    );
  }

  if (step === "category") {
    const filteredCategories = categories.filter((cat) => cat !== "Todos");
    
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="max-w-6xl mx-auto">
          <Button
            variant="outline"
            size="lg"
            onClick={() => setStep("welcome")}
            className="mb-6"
          >
            <ArrowLeft className="mr-2" />
            Volver
          </Button>

          <h1 className="text-4xl font-bold mb-8 text-center">Selecciona una Categoría</h1>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
            {filteredCategories.map((category) => (
              <Card
                key={category}
                className="p-8 cursor-pointer hover-lift text-center"
                onClick={() => handleCategorySelect(category)}
              >
                <h3 className="text-2xl font-bold">{category}</h3>
              </Card>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (step === "products") {
    const products = mockProducts.filter((p) => p.category === selectedCategory && p.available);
    
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="max-w-6xl mx-auto">
          <Button
            variant="outline"
            size="lg"
            onClick={() => setStep("category")}
            className="mb-6"
          >
            <ArrowLeft className="mr-2" />
            Volver
          </Button>

          <h1 className="text-4xl font-bold mb-8 text-center">{selectedCategory}</h1>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
            {products.map((product) => (
              <Card
                key={product.id}
                className="p-6 cursor-pointer hover-lift"
                onClick={() => handleProductSelect(product)}
              >
                <div className="text-7xl text-center mb-4">{product.image}</div>
                <h3 className="font-bold text-xl mb-2 text-center">{product.name}</h3>
                <p className="text-2xl font-bold text-secondary text-center">
                  ${product.price.toFixed(2)}
                </p>
              </Card>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (step === "modifiers") {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="max-w-4xl mx-auto">
          <Button
            variant="outline"
            size="lg"
            onClick={() => setStep("products")}
            className="mb-6"
          >
            <ArrowLeft className="mr-2" />
            Volver
          </Button>

          <h1 className="text-4xl font-bold mb-2 text-center">Personaliza tu {selectedProduct?.name}</h1>
          <p className="text-xl text-muted-foreground text-center mb-8">
            Selecciona tus opciones favoritas
          </p>

          <div className="space-y-8">
            {selectedProduct?.modifierGroups?.map((groupId: string) => {
              const group = modifierGroups.find((g) => g.id === groupId);
              if (!group) return null;

              const selectedCount = selectedModifiers[groupId]?.length || 0;

              return (
                <Card key={groupId} className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-2xl font-bold">
                      {group.name}
                      {group.required && <span className="text-danger ml-1">*</span>}
                    </h3>
                    <Badge variant={selectedCount >= group.minSelection ? "default" : "destructive"} className="text-lg px-4 py-1">
                      {selectedCount}/{group.maxSelection}
                    </Badge>
                  </div>

                  {group.maxSelection === 1 ? (
                    <RadioGroup
                      value={selectedModifiers[groupId]?.[0] || ""}
                      onValueChange={(value) =>
                        setSelectedModifiers({ ...selectedModifiers, [groupId]: [value] })
                      }
                    >
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {group.modifiers.map((mod) => (
                          <div key={mod.id} className="flex items-center space-x-3 p-4 rounded-lg border hover:bg-muted cursor-pointer">
                            <RadioGroupItem value={mod.id} id={mod.id} />
                            <Label htmlFor={mod.id} className="flex-1 cursor-pointer text-lg">
                              {mod.name}
                            </Label>
                            {mod.price > 0 && (
                              <span className="text-lg font-semibold">+${mod.price.toFixed(2)}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </RadioGroup>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {group.modifiers.map((mod) => (
                        <div key={mod.id} className="flex items-center space-x-3 p-4 rounded-lg border hover:bg-muted">
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
                          <Label htmlFor={mod.id} className="flex-1 cursor-pointer text-lg">
                            {mod.name}
                          </Label>
                          {mod.price > 0 && (
                            <span className="text-lg font-semibold">+${mod.price.toFixed(2)}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              );
            })}
          </div>

          <Button
            size="lg"
            className="w-full mt-8 text-xl py-8 bg-gradient-accent"
            onClick={handleAddModifiers}
            disabled={!canContinue()}
          >
            Continuar
          </Button>
        </div>
      </div>
    );
  }

  if (step === "review") {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold mb-8 text-center">Resumen de Pedido</h1>

          <div className="space-y-4 mb-8">
            {cart.map((item) => (
              <Card key={item.id} className="p-6">
                <div className="flex justify-between items-start mb-2">
                  <div className="flex-1">
                    <h3 className="text-xl font-bold">{item.name}</h3>
                    {item.modifiers.length > 0 && (
                      <div className="text-sm text-muted-foreground mt-2 space-y-1">
                        {item.modifiers.map((mod, idx) => (
                          <div key={idx}>• {mod.name}</div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="text-2xl font-bold text-secondary">${item.price.toFixed(2)}</div>
                </div>
              </Card>
            ))}
          </div>

          <Card className="p-6 mb-8">
            <div className="text-3xl font-bold text-center">
              Total: <span className="text-secondary">${total.toFixed(2)}</span>
            </div>
          </Card>

          <div className="grid grid-cols-2 gap-4">
            <Button
              size="lg"
              variant="outline"
              className="text-xl py-8"
              onClick={() => setStep("category")}
            >
              Agregar Más
            </Button>
            <Button
              size="lg"
              className="text-xl py-8 bg-gradient-accent"
              onClick={() => setStep("payment")}
            >
              Proceder al Pago
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (step === "payment") {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="max-w-2xl mx-auto text-center">
          <h1 className="text-4xl font-bold mb-8">Método de Pago</h1>

          <div className="grid gap-6 mb-8">
            <Card className="p-8 cursor-pointer hover-lift" onClick={() => setStep("complete")}>
              <h3 className="text-2xl font-bold">💳 Pagar con Tarjeta</h3>
              <p className="text-muted-foreground mt-2">Inserta o acerca tu tarjeta</p>
            </Card>

            <Card className="p-8 cursor-pointer hover-lift" onClick={() => setStep("complete")}>
              <h3 className="text-2xl font-bold">💵 Pagar en Caja</h3>
              <p className="text-muted-foreground mt-2">Dirígete a caja para pagar</p>
            </Card>
          </div>

          <Button
            variant="outline"
            size="lg"
            onClick={() => setStep("review")}
          >
            <ArrowLeft className="mr-2" />
            Volver
          </Button>
        </div>
      </div>
    );
  }

  if (step === "complete") {
    return (
      <div className="min-h-screen bg-gradient-primary flex items-center justify-center p-8">
        <Card className="max-w-2xl w-full p-12 text-center space-y-8 shadow-2xl">
          <div className="w-24 h-24 bg-gradient-accent rounded-full flex items-center justify-center mx-auto shadow-xl">
            <Check className="w-16 h-16 text-primary" />
          </div>
          
          <div>
            <h1 className="text-3xl font-bold mb-4">¡Pedido Confirmado!</h1>
            <p className="text-xl text-muted-foreground mb-8">Tu número de pedido es:</p>
            <div className="text-9xl font-black text-secondary mb-8">
              #{orderNumber}
            </div>
            <p className="text-xl text-muted-foreground">
              Por favor espera a que tu pedido esté listo
            </p>
          </div>

          <Button
            size="lg"
            className="w-full text-2xl py-8"
            onClick={() => {
              setStep("welcome");
              setCart([]);
              setSelectedCategory("");
            }}
          >
            Finalizar
          </Button>
        </Card>
      </div>
    );
  }

  return null;
};

export default Kiosk;
