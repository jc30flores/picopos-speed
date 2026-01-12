import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Check, Eye } from "lucide-react";
import { cn } from "@/lib/utils";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import {
  createOrder,
  getCategories,
  getModifierGroups,
  getProducts,
  Category,
  ModifierGroup,
  Product,
} from "@/lib/api";
import { getProductImageSrc } from "@/lib/media";
import { ProductImagePreviewModal } from "@/components/kiosk/ProductImagePreviewModal";
import { toast } from "sonner";

type Step = "welcome" | "category" | "products" | "modifiers" | "review" | "payment" | "complete";

interface CartItem {
  id: string;
  productId: number;
  name: string;
  basePrice: number;
  quantity: number;
  modifiers: Array<{ name: string; price: number }>;
}

const Kiosk = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("category");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [cart, setCart] = useState<CartItem[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [selectedModifiers, setSelectedModifiers] = useState<Record<string, string[]>>({});
  const [orderNumber, setOrderNumber] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [modifierGroups, setModifierGroups] = useState<ModifierGroup[]>([]);
  const [imageErrors, setImageErrors] = useState<Record<number, boolean>>({});
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewItem, setPreviewItem] = useState<Product | null>(null);

  useEffect(() => {
    Promise.all([getCategories(), getProducts(), getModifierGroups()])
      .then(([categoriesResponse, productsResponse, modifierGroupsResponse]) => {
        setCategories(categoriesResponse);
        setProducts(productsResponse);
        setModifierGroups(modifierGroupsResponse);
      })
      .catch((error) => {
        console.error("Failed to load kiosk menu data", error);
      });
  }, []);

  const handleCategorySelect = (category: string) => {
    setSelectedCategory(category);
    setStep("products");
  };

  const handleProductSelect = (product: Product) => {
    setSelectedProduct(product);
    setSelectedModifiers({});
    if (product.modifierGroups && product.modifierGroups.length > 0) {
      setStep("modifiers");
    } else {
      addToCart(product, []);
      setStep("review");
    }
  };

  const handlePreview = (product: Product) => {
    setPreviewItem(product);
    setPreviewOpen(true);
  };

  const addToCart = (product: Product, modifiers: Array<{ name: string; price: number }>) => {
    setCart([
      ...cart,
      {
        id: `${product.id}-${Date.now()}`,
        productId: product.id,
        name: product.name,
        basePrice: product.price,
        quantity: 1,
        modifiers,
      },
    ]);
  };

  const handleAddModifiers = () => {
    const selectedMods: Array<{ name: string; price: number }> = [];
    
    if (!selectedProduct) return;

    selectedProduct.modifierGroups.forEach((groupId: number) => {
      const group = modifierGroups.find((g) => g.id === groupId);
      if (group && selectedModifiers[groupId]) {
        selectedModifiers[groupId].forEach((modId) => {
          const mod = group.modifiers.find((m) => String(m.id) === modId);
          if (mod) selectedMods.push({ name: mod.name, price: mod.price });
        });
      }
    });

    addToCart(selectedProduct, selectedMods);
    setStep("review");
  };

  const canContinue = () => {
    if (!selectedProduct?.modifierGroups) return true;
    
    return selectedProduct.modifierGroups.every((groupId: number) => {
      const group = modifierGroups.find((g) => g.id === groupId);
      if (!group) return true;
      
      const selectedCount = selectedModifiers[groupId]?.length || 0;
      return selectedCount >= group.minSelection && selectedCount <= group.maxSelection;
    });
  };

  const getItemTotal = (item: CartItem) => {
    const modifiersTotal = item.modifiers.reduce((sum, mod) => sum + mod.price, 0);
    return (item.basePrice + modifiersTotal) * item.quantity;
  };

  const total = cart.reduce((sum, item) => sum + getItemTotal(item), 0);

  const handleSubmitOrder = async () => {
    if (cart.length === 0) return;
    setIsSubmitting(true);
    try {
      const order = await createOrder({
        serviceType: "kiosk",
        source: "kiosk",
        channel: "kiosk",
        items: cart.map((item) => ({
          productId: item.productId,
          productName: item.name,
          price: item.basePrice,
          quantity: item.quantity,
          modifiers: item.modifiers,
        })),
      });
      setOrderNumber(order.orderNumber);
      setStep("complete");
    } catch (error) {
      console.error("Failed to create kiosk order", error);
      toast.error("No se pudo enviar el pedido, intenta de nuevo");
    } finally {
      setIsSubmitting(false);
    }
  };


  if (step === "category") {
    const filteredCategories = categories.map((cat) => cat.name);
    
    return (
      <div className="min-h-screen bg-background p-4 sm:p-8">
        <div className="max-w-6xl mx-auto">
          <Button
            variant="outline"
            size="lg"
            onClick={() => navigate(-1)}
            className="mb-6"
          >
            <ArrowLeft className="mr-2" />
            Volver
          </Button>

          <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-8 text-center break-words">
            Selecciona una Categoría
          </h1>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 sm:gap-6">
            {filteredCategories.map((category) => (
              <Card
                key={category}
                className="p-6 sm:p-8 cursor-pointer hover-lift text-center"
                onClick={() => handleCategorySelect(category)}
              >
                <h3 className="text-xl sm:text-2xl font-bold break-words">{category}</h3>
              </Card>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (step === "products") {
    const productsForCategory = products.filter((p) => p.category === selectedCategory && p.available);
    
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
            {productsForCategory.map((product) => (
              <Card
                key={product.id}
                className="p-6 cursor-pointer hover-lift"
                onClick={() => handleProductSelect(product)}
              >
                {(() => {
                  const imageSrc = getProductImageSrc(product);
                  if (!imageSrc || imageErrors[product.id]) {
                    return (
                      <div className="relative mb-4 flex h-32 items-center justify-center rounded-md bg-muted text-sm text-muted-foreground">
                        Sin imagen
                      </div>
                    );
                  }
                  return (
                    <div className="relative mb-4">
                      <img
                        src={imageSrc}
                        alt={product.name}
                        className="h-32 w-full rounded-md object-cover"
                        onError={(event) => {
                          event.currentTarget.style.display = "none";
                          setImageErrors((prev) => ({ ...prev, [product.id]: true }));
                        }}
                      />
                      <button
                        type="button"
                        title="Ver imagen"
                        aria-label="Ver imagen"
                        className="absolute right-2 top-2 rounded-full bg-black/50 p-2 text-white hover:bg-black/70 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                        onClick={(event) => {
                          event.stopPropagation();
                          handlePreview(product);
                        }}
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                    </div>
                  );
                })()}
                <h3 className="font-bold text-xl mb-2 text-center">{product.name}</h3>
                <p className="text-2xl font-bold text-secondary text-center">
                  ${product.price.toFixed(2)}
                </p>
              </Card>
            ))}
          </div>
          <ProductImagePreviewModal
            open={previewOpen}
            item={previewItem}
            onClose={() => setPreviewOpen(false)}
          />
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
            {selectedProduct?.modifierGroups?.map((groupId: number) => {
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
                            <RadioGroupItem value={String(mod.id)} id={String(mod.id)} />
                            <Label htmlFor={String(mod.id)} className="flex-1 cursor-pointer text-lg">
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
                            id={String(mod.id)}
                            checked={selectedModifiers[groupId]?.includes(String(mod.id)) || false}
                            onCheckedChange={(checked) => {
                              const current = selectedModifiers[groupId] || [];
                              if (checked && current.length < group.maxSelection) {
                                setSelectedModifiers({
                                  ...selectedModifiers,
                                  [groupId]: [...current, String(mod.id)],
                                });
                              } else if (!checked) {
                                setSelectedModifiers({
                                  ...selectedModifiers,
                                  [groupId]: current.filter((id) => id !== String(mod.id)),
                                });
                              }
                            }}
                            disabled={
                              !selectedModifiers[groupId]?.includes(String(mod.id)) &&
                              (selectedModifiers[groupId]?.length || 0) >= group.maxSelection
                            }
                          />
                          <Label htmlFor={String(mod.id)} className="flex-1 cursor-pointer text-lg">
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
            variant="default"
            className="w-full mt-8 text-xl py-8"
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
      <div className="min-h-screen bg-background p-4 sm:p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl sm:text-4xl font-bold mb-8 text-center break-words">
            Resumen de Pedido
          </h1>

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
                  <div className="text-2xl font-bold text-secondary">
                    ${getItemTotal(item).toFixed(2)}
                  </div>
                </div>
              </Card>
            ))}
          </div>

          <Card className="p-6 mb-8">
            <div className="text-2xl sm:text-3xl font-bold text-center break-words">
              Total: <span className="text-secondary">${total.toFixed(2)}</span>
            </div>
          </Card>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Button
              size="lg"
              variant="outline"
              className="text-lg sm:text-xl py-6 sm:py-8 w-full"
              onClick={() => setStep("category")}
            >
              <span className="truncate">Agregar Más</span>
            </Button>
            <Button
              size="lg"
              variant="default"
              className="text-lg sm:text-xl py-6 sm:py-8 w-full"
              onClick={() => setStep("payment")}
              disabled={cart.length === 0}
            >
              <span className="truncate">Proceder al Pago</span>
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
            <Card
              className={cn("p-8 cursor-pointer hover-lift", isSubmitting && "opacity-70")}
              onClick={() => {
                if (!isSubmitting) {
                  handleSubmitOrder();
                }
              }}
            >
              <h3 className="text-2xl font-bold">💳 Pagar con Tarjeta</h3>
              <p className="text-muted-foreground mt-2">Inserta o acerca tu tarjeta</p>
            </Card>

            <Card
              className={cn("p-8 cursor-pointer hover-lift", isSubmitting && "opacity-70")}
              onClick={() => {
                if (!isSubmitting) {
                  handleSubmitOrder();
                }
              }}
            >
              <h3 className="text-2xl font-bold">💵 Pagar en Caja</h3>
              <p className="text-muted-foreground mt-2">Dirígete a caja para pagar</p>
            </Card>
          </div>

          <Button
            variant="outline"
            size="lg"
            onClick={() => setStep("review")}
            disabled={isSubmitting}
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
      <div className="min-h-screen bg-gradient-primary flex items-center justify-center p-4 sm:p-8">
        <Card className="max-w-2xl w-full p-6 sm:p-12 text-center space-y-6 sm:space-y-8 shadow-2xl">
          <div className="w-20 h-20 sm:w-24 sm:h-24 bg-gradient-accent rounded-full flex items-center justify-center mx-auto shadow-xl">
            <Check className="w-12 h-12 sm:w-16 sm:h-16 text-primary" />
          </div>
          
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold mb-4 break-words">¡Pedido Confirmado!</h1>
            <p className="text-lg sm:text-xl text-muted-foreground mb-6 sm:mb-8 break-words">
              Tu número de pedido es:
            </p>
            <div className="text-6xl sm:text-7xl md:text-9xl font-black text-secondary mb-6 sm:mb-8 break-all">
              #{orderNumber ?? "..."}
            </div>
            <p className="text-lg sm:text-xl text-muted-foreground break-words">
              Por favor espera a que tu pedido esté listo
            </p>
          </div>

          <Button
            size="lg"
            className="w-full text-xl sm:text-2xl py-6 sm:py-8"
            onClick={() => {
              setStep("category");
              setCart([]);
              setSelectedCategory("");
              setOrderNumber(null);
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
