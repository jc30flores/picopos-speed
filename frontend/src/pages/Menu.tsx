import { useState } from "react";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import { PageTabs } from "@/components/ui/page-tabs";
import { ProductsTab } from "@/components/menu/ProductsTab";
import { DiscountsTab } from "@/components/menu/DiscountsTab";
import { PageLayout } from "@/components/layout/PageLayout";

const Menu = () => {
  const [activeTab, setActiveTab] = useState("products");

  return (
    <PageLayout
      maxWidthClassName="max-w-[1600px]"
      title="Menú y Descuentos"
      subtitle="Administra productos, modificadores y descuentos del sistema."
    >

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
    </PageLayout>
  );
};

export default Menu;
