import { Navigation } from "@/components/Navigation";
import { useState } from "react";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import { PageTabs } from "@/components/ui/page-tabs";
import { ProductsTab } from "@/components/menu/ProductsTab";
import { DiscountsTab } from "@/components/menu/DiscountsTab";

const Menu = () => {
  const [activeTab, setActiveTab] = useState("products");

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="px-4 pb-4 pt-4">
        <div className="mx-auto max-w-[1600px]">
          <div className="mb-4 space-y-1">
            <h1 className="text-2xl font-bold sm:text-3xl">Menú y Descuentos</h1>
            <p className="text-sm text-muted-foreground">Administra productos, modificadores y descuentos del sistema.</p>
          </div>

          <PageTabs
            tabs={[
              { label: "Productos & Modificadores", value: "products" },
              { label: "Descuentos", value: "discounts" },
            ]}
            activeValue={activeTab}
            onChange={setActiveTab}
          />

          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
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
