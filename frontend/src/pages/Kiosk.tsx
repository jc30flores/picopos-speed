import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Check, ImageIcon, Minus, Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import {
  createOrder,
  getCategories,
  getModifierGroups,
  getProducts,
  Category,
  Modifier,
  ModifierGroup,
  Product,
} from "@/lib/api";
import { getEntityImageSrc, getProductImageSrc } from "@/lib/media";
import { KioskImage } from "@/components/kiosk/KioskImage";
import { KioskImageLightbox } from "@/components/kiosk/KioskImageLightbox";
import { toast } from "sonner";

type Step = "welcome" | "category" | "products" | "modifiers" | "review" | "payment" | "complete";

interface CartModifier {
  id?: number;
  groupId?: number;
  name: string;
  price: number;
}

interface CartItem {
  id: string;
  productId: number;
  name: string;
  basePrice: number;
  quantity: number;
  modifiers: CartModifier[];
}

interface PreviewState {
  open: boolean;
  title: string;
  subtitle?: string;
  imageSrc?: string | null;
}

const buildItemSignature = (item: CartItem) => {
  const mods = [...item.modifiers]
    .map((mod) => `${mod.groupId ?? "g"}:${mod.id ?? mod.name}:${mod.price}`)
    .sort()
    .join("|");
  return `${item.productId}::${mods}`;
};

const Kiosk = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("category");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [cart, setCart] = useState<CartItem[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [selectedModifiers, setSelectedModifiers] = useState<Record<string, string[]>>({});
  const [editingCartItemId, setEditingCartItemId] = useState<string | null>(null);
  const [unitPicker, setUnitPicker] = useState<{ open: boolean; itemIds: string[]; title: string }>({ open: false, itemIds: [], title: "" });
  const [orderNumber, setOrderNumber] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [modifierGroups, setModifierGroups] = useState<ModifierGroup[]>([]);
  const [failedImages, setFailedImages] = useState<Record<string, boolean>>({});
  const [preview, setPreview] = useState<PreviewState>({ open: false, title: "" });

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

  useEffect(() => {
    const preload = (urls: Array<string | null>) => {
      urls.filter(Boolean).slice(0, 10).forEach((src) => {
        const img = new Image();
        img.src = src as string;
      });
    };

    if (step === "category") {
      preload(categories.map((cat) => getEntityImageSrc(cat)));
    }
    if (step === "products") {
      preload(
        products
          .filter((p) => p.category === selectedCategory && p.available)
          .map((p) => getProductImageSrc(p)),
      );
    }
  }, [categories, products, selectedCategory, step]);

  const categoriesForGrid = useMemo(() => categories.filter((cat) => !cat.isHidden), [categories]);

  const groupedCart = useMemo(() => {
    const map = new Map<string, { signature: string; representative: CartItem; itemIds: string[] }>();
    cart.forEach((item) => {
      const signature = buildItemSignature(item);
      const entry = map.get(signature);
      if (!entry) {
        map.set(signature, { signature, representative: item, itemIds: [item.id] });
      } else {
        entry.itemIds.push(item.id);
      }
    });
    return Array.from(map.values());
  }, [cart]);

  const getSafeImage = (key: string, src: string | null) => {
    if (!src || failedImages[key]) return null;
    return src;
  };

  const markImageFailed = (key: string) => {
    setFailedImages((prev) => (prev[key] ? prev : { ...prev, [key]: true }));
    setPreview((current) => (current.imageSrc ? { ...current, open: false } : current));
  };

  const openPreview = (title: string, imageSrc?: string | null, subtitle?: string) => {
    if (!imageSrc) return;
    setPreview({ open: true, title, subtitle, imageSrc });
  };

  const addToCart = (product: Product, modifiers: CartModifier[]) => {
    setCart((previous) => [
      ...previous,
      {
        id: `${product.id}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        productId: product.id,
        name: product.name,
        basePrice: product.price,
        quantity: 1,
        modifiers,
      },
    ]);
  };

  const cloneCartItemUnit = (sourceItemId: string) => {
    const source = cart.find((item) => item.id === sourceItemId);
    if (!source) return;
    const product = products.find((candidate) => candidate.id === source.productId);
    if (!product) return;
    addToCart(product, source.modifiers.map((mod) => ({ ...mod })));
  };

  const removeCartItemById = (itemId: string) => {
    setCart((previous) => previous.filter((item) => item.id !== itemId));
  };

  const handleCategorySelect = (category: string) => {
    setSelectedCategory(category);
    setStep("products");
  };

  const handleProductSelect = (product: Product) => {
    setEditingCartItemId(null);
    setSelectedProduct(product);
    setSelectedModifiers({});
    if (product.modifierGroups?.length) {
      setStep("modifiers");
      return;
    }
    addToCart(product, []);
    setStep("review");
  };

  const handleEditCartItem = (itemId: string) => {
    const item = cart.find((candidate) => candidate.id === itemId);
    if (!item) return;
    const product = products.find((candidate) => candidate.id === item.productId);
    if (!product) return;

    const nextSelected: Record<string, string[]> = {};
    item.modifiers.forEach((mod) => {
      if (!mod.groupId || !mod.id) return;
      const key = String(mod.groupId);
      nextSelected[key] = [...(nextSelected[key] ?? []), String(mod.id)];
    });

    setEditingCartItemId(item.id);
    setSelectedProduct(product);
    setSelectedModifiers(nextSelected);
    setStep("modifiers");
  };

  const handleAddModifiers = () => {
    if (!selectedProduct) return;

    const selectedMods: CartModifier[] = [];
    selectedProduct.modifierGroups.forEach((groupId) => {
      const group = modifierGroups.find((g) => g.id === groupId);
      const selectedInGroup = selectedModifiers[String(groupId)] || [];
      if (!group) return;
      selectedInGroup.forEach((modId) => {
        const mod = group.modifiers.find((m) => String(m.id) === modId);
        if (mod) selectedMods.push({ id: mod.id, groupId: group.id, name: mod.name, price: mod.price });
      });
    });

    if (editingCartItemId) {
      setCart((previous) => previous.map((item) => (item.id === editingCartItemId ? { ...item, modifiers: selectedMods } : item)));
      setEditingCartItemId(null);
    } else {
      addToCart(selectedProduct, selectedMods);
    }

    setStep("review");
  };

  const canContinue = () => {
    if (!selectedProduct?.modifierGroups) return true;
    return selectedProduct.modifierGroups.every((groupId) => {
      const group = modifierGroups.find((g) => g.id === groupId);
      if (!group) return true;
      const selectedCount = selectedModifiers[String(groupId)]?.length || 0;
      return selectedCount >= group.minSelection && selectedCount <= group.maxSelection;
    });
  };

  const handleSubmitOrder = async () => {
    if (!cart.length) return;
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
          modifiers: item.modifiers.map(({ name, price }) => ({ name, price })),
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

  const getModifierImageSrc = (image?: string | null, imagePath?: string | null) =>
    getProductImageSrc({ image: image ?? null, imagePath: imagePath ?? null });

  const getItemTotal = (item: CartItem) => {
    const modifiersTotal = item.modifiers.reduce((sum, mod) => sum + mod.price, 0);
    return (item.basePrice + modifiersTotal) * item.quantity;
  };
  const total = cart.reduce((sum, item) => sum + getItemTotal(item), 0);

  const renderModifierTile = (group: ModifierGroup, mod: Modifier, singleSelection: boolean) => {
    const checked = selectedModifiers[String(group.id)]?.includes(String(mod.id)) || false;
    const disabled = !singleSelection && !checked && (selectedModifiers[String(group.id)]?.length || 0) >= group.maxSelection;
    const imageKey = `option-${mod.id}`;
    const imageSrc = getSafeImage(imageKey, getModifierImageSrc(mod.image, mod.imagePath));

    return (
      <div
        className={cn(
          "flex min-h-[150px] flex-col gap-3 rounded-2xl border p-3 md:p-4",
          checked ? "border-primary bg-primary/10" : "border-white/10 bg-card/40",
          disabled ? "opacity-60" : "hover:bg-muted/80",
        )}
      >
        <div className="flex items-center justify-between">
          <div className="shrink-0">
            {singleSelection ? (
              <RadioGroupItem value={String(mod.id)} id={`radio-${group.id}-${mod.id}`} />
            ) : (
              <Checkbox
                id={`check-${group.id}-${mod.id}`}
                checked={checked}
                onCheckedChange={(nextChecked) => {
                  const current = selectedModifiers[String(group.id)] || [];
                  if (nextChecked && current.length < group.maxSelection) {
                    setSelectedModifiers({ ...selectedModifiers, [String(group.id)]: [...current, String(mod.id)] });
                  } else if (!nextChecked) {
                    setSelectedModifiers({
                      ...selectedModifiers,
                      [String(group.id)]: current.filter((id) => id !== String(mod.id)),
                    });
                  }
                }}
                disabled={disabled}
              />
            )}
          </div>
          <span className="shrink-0 text-base font-semibold text-secondary md:text-lg">
            {mod.price > 0 ? `+$${mod.price.toFixed(2)}` : "Incluido"}
          </span>
        </div>

        <div className="h-[160px] w-full">
          <KioskImage
            src={imageSrc}
            alt={mod.name}
            ratio="16 / 10"
            className="h-full w-full rounded-xl"
            imageClassName="p-2"
            sizes="(min-width: 1280px) 24vw, 40vw"
            onPreview={() => openPreview(mod.name, imageSrc, group.name)}
            onImageError={() => markImageFailed(imageKey)}
          />
        </div>

        <Label
          htmlFor={singleSelection ? `radio-${group.id}-${mod.id}` : `check-${group.id}-${mod.id}`}
          className="flex cursor-pointer items-center justify-between gap-3"
        >
          <span className="text-lg font-semibold leading-tight md:text-xl">{mod.name}</span>
        </Label>
      </div>
    );
  };

  if (step === "category") {
    return (
      <div className="min-h-screen bg-background p-4 sm:p-8">
        <div className="mx-auto max-w-7xl">
          <Button variant="outline" size="lg" onClick={() => navigate(-1)} className="mb-6 text-lg">
            <ArrowLeft className="mr-2" />
            Volver
          </Button>
          <h1 className="mb-8 text-center text-3xl font-bold break-words sm:text-4xl md:text-5xl">Selecciona una Categoría</h1>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 sm:gap-6">
            {categoriesForGrid.map((category) => {
              const src = getSafeImage(`category-${category.id}`, getEntityImageSrc(category));
              return (
                <Card
                  key={category.id}
                  className="cursor-pointer p-4 text-center transition hover:bg-muted/70 active:scale-[0.99] sm:p-6"
                  onClick={() => handleCategorySelect(category.name)}
                >
                  <div className="mb-3 h-28 w-full">
                    {src ? (
                      <KioskImage src={src} alt={category.name} ratio="16 / 10" sizes="(min-width: 768px) 30vw, 45vw" onImageError={() => markImageFailed(`category-${category.id}`)} />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center rounded-2xl border border-white/10 bg-white text-slate-500">
                        <ImageIcon className="h-10 w-10" />
                      </div>
                    )}
                  </div>
                  <h3 className="text-xl font-bold break-words sm:text-2xl">{category.name}</h3>
                </Card>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  if (step === "products") {
    const productsForCategory = products.filter((p) => p.category === selectedCategory && p.available);
    return (
      <>
        <div className="min-h-screen bg-background p-4 md:p-8">
          <div className="mx-auto max-w-[1440px]">
            <Button variant="outline" size="lg" onClick={() => setStep("category")} className="mb-6 text-lg">
              <ArrowLeft className="mr-2" />
              Volver
            </Button>

            <h1 className="mb-8 text-center text-4xl font-bold md:text-5xl">{selectedCategory}</h1>

            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-3">
              {productsForCategory.map((product) => {
                const imageKey = `product-${product.id}`;
                const imageSrc = getSafeImage(imageKey, getProductImageSrc(product));
                return (
                  <Card
                    key={product.id}
                    className="group cursor-pointer overflow-hidden rounded-3xl border-white/10 bg-card/70 p-0 shadow-lg transition-transform duration-150 hover:-translate-y-0.5 hover:shadow-2xl active:scale-[0.995]"
                    onClick={() => handleProductSelect(product)}
                  >
                    <div className="p-4 pb-2 md:p-5 md:pb-3">
                      <KioskImage
                        src={imageSrc}
                        alt={product.name}
                        ratio="16 / 10"
                        loading="lazy"
                        sizes="(min-width: 1280px) 33vw, (min-width: 640px) 50vw, 100vw"
                        className="w-full rounded-2xl"
                        onPreview={() => openPreview(product.name, imageSrc, selectedCategory)}
                        onImageError={() => markImageFailed(imageKey)}
                      />
                    </div>
                    <div className="px-5 pb-5 pt-3">
                      <h3 className="line-clamp-2 text-2xl font-extrabold leading-tight">{product.name}</h3>
                      <p className="mt-2 text-3xl font-black text-secondary">${product.price.toFixed(2)}</p>
                    </div>
                  </Card>
                );
              })}
            </div>
          </div>
        </div>

        <KioskImageLightbox
          open={preview.open}
          title={preview.title}
          subtitle={preview.subtitle}
          imageSrc={preview.imageSrc}
          onClose={() => setPreview({ open: false, title: "" })}
        />
      </>
    );
  }

  if (step === "modifiers") {
    return (
      <>
        <div className="min-h-screen bg-background p-4 md:p-8">
          <div className="mx-auto max-w-[1520px]">
            <Button variant="outline" size="lg" onClick={() => setStep("products")} className="mb-6 text-lg">
              <ArrowLeft className="mr-2" />
              Volver
            </Button>

            <h1 className="mb-2 text-center text-4xl font-bold md:text-5xl">Personaliza tu {selectedProduct?.name}</h1>
            <p className="mb-8 text-center text-xl text-muted-foreground md:text-2xl">Selecciona tus opciones favoritas</p>

            <div className="space-y-8">
              {selectedProduct?.modifierGroups?.map((groupId: number) => {
                const group = modifierGroups.find((g) => g.id === groupId);
                if (!group) return null;

                const selectedCount = selectedModifiers[String(groupId)]?.length || 0;
                const groupImageKey = `group-${group.id}`;
                const groupImageSrc = getSafeImage(groupImageKey, getModifierImageSrc(group.image, group.imagePath));

                return (
                  <Card key={groupId} className="rounded-3xl border-white/10 p-4 md:p-6">
                    <div className="mb-5 flex items-center justify-between gap-3">
                      <div className="flex min-w-0 items-center gap-4">
                        <div className="h-24 w-24 shrink-0 md:h-28 md:w-28">
                          <KioskImage
                            src={groupImageSrc}
                            alt={group.name}
                            ratio="1 / 1"
                            className="h-full w-full rounded-2xl"
                            imageClassName="p-2"
                            sizes="112px"
                            onPreview={() => openPreview(group.name, groupImageSrc, "Grupo de modificadores")}
                            onImageError={() => markImageFailed(groupImageKey)}
                          />
                        </div>
                        <div className="min-w-0">
                          <h3 className="text-2xl font-black leading-tight md:text-3xl">
                            {group.name}
                            {group.required && <span className="ml-1 text-danger">*</span>}
                          </h3>
                          <p className="mt-1 text-sm text-muted-foreground md:text-base">
                            Selecciona entre {group.minSelection} y {group.maxSelection} opciones
                          </p>
                        </div>
                      </div>
                      <Badge
                        variant={selectedCount >= group.minSelection ? "default" : "destructive"}
                        className="px-4 py-2 text-base font-bold md:text-lg"
                      >
                        {selectedCount}/{group.maxSelection}
                      </Badge>
                    </div>

                    {group.maxSelection === 1 ? (
                      <RadioGroup
                        value={selectedModifiers[String(groupId)]?.[0] || ""}
                        onValueChange={(value) => setSelectedModifiers({ ...selectedModifiers, [String(groupId)]: [value] })}
                      >
                        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                          {group.modifiers.map((mod) => (
                            <div key={mod.id}>{renderModifierTile(group, mod, true)}</div>
                          ))}
                        </div>
                      </RadioGroup>
                    ) : (
                      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                        {group.modifiers.map((mod) => (
                          <div key={mod.id}>{renderModifierTile(group, mod, false)}</div>
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
              className="mt-8 w-full py-8 text-xl font-bold md:text-2xl"
              onClick={handleAddModifiers}
              disabled={!canContinue()}
            >
              Continuar
            </Button>
          </div>
        </div>

        <KioskImageLightbox
          open={preview.open}
          title={preview.title}
          subtitle={preview.subtitle}
          imageSrc={preview.imageSrc}
          onClose={() => setPreview({ open: false, title: "" })}
        />
      </>
    );
  }

  if (step === "review") {
    return (
      <div className="min-h-screen bg-background p-4 sm:p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl sm:text-4xl font-bold mb-8 text-center break-words">Resumen de Pedido</h1>

          <div className="space-y-4 mb-8">
            {groupedCart.map((grouped) => {
              const item = grouped.representative;
              const unitCount = grouped.itemIds.length;
              const groupUnitPrice = getItemTotal(item);
              return (
                <Card key={grouped.signature} className="p-6">
                  <div className="flex flex-col gap-4">
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex-1">
                        <h3 className="text-xl font-bold">{item.name}</h3>
                        {item.modifiers.length > 0 && (
                          <div className="text-sm text-muted-foreground mt-2 space-y-1">
                            {item.modifiers.map((mod, idx) => (
                              <div key={`${mod.name}-${idx}`}>• {mod.name}</div>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="text-2xl font-bold text-secondary">${(groupUnitPrice * unitCount).toFixed(2)}</div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-card/40 p-1">
                        <Button className="h-14 w-14" variant="outline" size="icon" onClick={() => removeCartItemById(grouped.itemIds[grouped.itemIds.length - 1])}>
                          <Minus className="h-8 w-8" />
                        </Button>
                        <div className="min-w-14 text-center text-2xl font-black">{unitCount}</div>
                        <Button className="h-14 w-14" variant="outline" size="icon" onClick={() => cloneCartItemUnit(grouped.itemIds[0])}>
                          <Plus className="h-8 w-8" />
                        </Button>
                      </div>

                      <Button
                        className="h-14 w-14"
                        variant="outline"
                        size="icon"
                        onClick={() => {
                          if (unitCount === 1) {
                            handleEditCartItem(grouped.itemIds[0]);
                          } else {
                            setUnitPicker({ open: true, itemIds: grouped.itemIds, title: item.name });
                          }
                        }}
                      >
                        <Pencil className="h-8 w-8" />
                      </Button>

                      <Button className="h-14 w-14" variant="outline" size="icon" onClick={() => setCart((prev) => prev.filter((cartItem) => !grouped.itemIds.includes(cartItem.id)))}>
                        <Trash2 className="h-8 w-8 text-destructive" />
                      </Button>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>

          <Card className="p-6 mb-8">
            <div className="text-2xl sm:text-3xl font-bold text-center break-words">
              Total: <span className="text-secondary">${total.toFixed(2)}</span>
            </div>
          </Card>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Button size="lg" variant="outline" className="text-lg sm:text-xl py-6 sm:py-8 w-full" onClick={() => setStep("category")}>
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

        <Dialog open={unitPicker.open} onOpenChange={(open) => setUnitPicker((prev) => ({ ...prev, open }))}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Selecciona unidad a editar</DialogTitle>
              <DialogDescription>{unitPicker.title}</DialogDescription>
            </DialogHeader>
            <div className="grid grid-cols-3 gap-2">
              {unitPicker.itemIds.map((id, index) => (
                <Button
                  key={id}
                  className="h-14 text-lg"
                  onClick={() => {
                    setUnitPicker({ open: false, itemIds: [], title: "" });
                    handleEditCartItem(id);
                  }}
                >
                  Unidad {index + 1}
                </Button>
              ))}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  if (step === "payment") {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="max-w-2xl mx-auto text-center">
          <h1 className="text-4xl font-bold mb-8">Método de Pago</h1>

          <div className="grid gap-6 mb-8">
            <Card className={cn("p-8 cursor-pointer hover-lift", isSubmitting && "opacity-70")} onClick={() => { if (!isSubmitting) handleSubmitOrder(); }}>
              <h3 className="text-2xl font-bold">💳 Pagar con Tarjeta</h3>
              <p className="text-muted-foreground mt-2">Inserta o acerca tu tarjeta</p>
            </Card>

            <Card className={cn("p-8 cursor-pointer hover-lift", isSubmitting && "opacity-70")} onClick={() => { if (!isSubmitting) handleSubmitOrder(); }}>
              <h3 className="text-2xl font-bold">💵 Pagar en Caja</h3>
              <p className="text-muted-foreground mt-2">Dirígete a caja para pagar</p>
            </Card>
          </div>

          <Button variant="outline" size="lg" onClick={() => setStep("review")} disabled={isSubmitting}>
            <ArrowLeft className="mr-2" />
            Volver
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-primary flex items-center justify-center p-4 sm:p-8">
      <Card className="max-w-2xl w-full p-6 sm:p-12 text-center space-y-6 sm:space-y-8 shadow-2xl">
        <div className="w-20 h-20 sm:w-24 sm:h-24 bg-gradient-accent rounded-full flex items-center justify-center mx-auto shadow-xl">
          <Check className="w-12 h-12 sm:w-16 sm:h-16 text-primary" />
        </div>

        <div>
          <h1 className="text-2xl sm:text-3xl font-bold mb-4 break-words">¡Pedido Confirmado!</h1>
          <p className="text-lg sm:text-xl text-muted-foreground mb-6 sm:mb-8 break-words">Tu número de pedido es:</p>
          <div className="text-6xl sm:text-7xl md:text-9xl font-black text-secondary mb-6 sm:mb-8 break-all">#{orderNumber ?? "..."}</div>
          <p className="text-lg sm:text-xl text-muted-foreground break-words">Por favor espera a que tu pedido esté listo</p>
        </div>

        <Button
          size="lg"
          className="w-full text-xl sm:text-2xl py-6 sm:py-8"
          onClick={() => {
            setStep("category");
            setCart([]);
            setSelectedCategory("");
            setOrderNumber(null);
            setSelectedProduct(null);
            setEditingCartItemId(null);
          }}
        >
          Finalizar
        </Button>
      </Card>
    </div>
  );
};

export default Kiosk;
