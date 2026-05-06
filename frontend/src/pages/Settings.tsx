import { useState } from "react";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import { PageTabs } from "@/components/ui/page-tabs";
import { EmployeesTab } from "@/components/settings/EmployeesTab";
import { SchedulesTab } from "@/components/settings/SchedulesTab";
import { FeatureFlagsTab } from "@/components/settings/FeatureFlagsTab";
import { OrderTypesTab } from "@/components/settings/OrderTypesTab";
import { PaymentMethodsTab } from "@/components/settings/PaymentMethodsTab";
import { PageLayout } from "@/components/layout/PageLayout";

const Settings = () => {
  const [activeTab, setActiveTab] = useState("employees");

  return (
    <PageLayout
      title="Configuración"
      subtitle="Gestiona usuarios, horarios del personal y funciones avanzadas del sistema."
    >
      <PageTabs
        tabs={[
          { label: "Empleados", value: "employees" },
          { label: "Horarios", value: "schedules" },
          { label: "Funciones", value: "features" },
          { label: "Tipos de Pedido", value: "order-types" },
          { label: "Métodos de Pago", value: "payment-methods" },
        ]}
        activeValue={activeTab}
        onChange={setActiveTab}
      />

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsContent value="employees" className="mt-0">
          <EmployeesTab />
        </TabsContent>

        <TabsContent value="schedules" className="mt-0">
          <SchedulesTab />
        </TabsContent>

        <TabsContent value="features" className="mt-0">
          <FeatureFlagsTab />
        </TabsContent>

        <TabsContent value="order-types" className="mt-0">
          <OrderTypesTab />
        </TabsContent>

        <TabsContent value="payment-methods" className="mt-0">
          <PaymentMethodsTab />
        </TabsContent>
      </Tabs>
    </PageLayout>
  );
};

export default Settings;
