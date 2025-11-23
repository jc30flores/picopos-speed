import { Navigation } from "@/components/Navigation";
import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ProductsTab } from "@/components/menu/ProductsTab";
import { DiscountsTab } from "@/components/menu/DiscountsTab";

const Menu = () => {
  const [activeTab, setActiveTab] = useState("products");

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="pt-20 px-4 pb-4">
        <div className="max-w-[1600px] mx-auto">
          <h1 className="text-3xl font-bold mb-6">Menú & Modificadores</h1>
          
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="mb-6">
              <TabsTrigger value="products">Productos & Modificadores</TabsTrigger>
              <TabsTrigger value="discounts">Descuentos</TabsTrigger>
            </TabsList>

            <TabsContent value="products" className="mt-0">
              <ProductsTab />
            </TabsContent>

            <TabsContent value="discounts" className="mt-0">
              <DiscountsTab />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
};

export default Menu;
