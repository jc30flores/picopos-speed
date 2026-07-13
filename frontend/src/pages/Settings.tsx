import { useState } from "react";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import { PageTabs } from "@/components/ui/page-tabs";
import { EmployeesTab } from "@/components/settings/EmployeesTab";
import { SchedulesTab } from "@/components/settings/SchedulesTab";
import { FeatureFlagsTab } from "@/components/settings/FeatureFlagsTab";
import { OrderTypesTab } from "@/components/settings/OrderTypesTab";
import { PaymentMethodsTab } from "@/components/settings/PaymentMethodsTab";
import { AppearanceTab } from "@/components/settings/AppearanceTab";
import { DteSettingsTab } from "@/components/settings/DteSettingsTab";
import { PageLayout } from "@/components/layout/PageLayout";
import { useAuth } from "@/context/useAuth";

const Settings = () => {
  const [activeTab, setActiveTab] = useState("employees");
  const { user } = useAuth();
  const isSuperadmin = Boolean(user?.permissions?.isSuperadmin || user?.role === "superadmin");
  const tabs = [
    { label: "Empleados", value: "employees" },
    { label: "Horarios", value: "schedules" },
    ...(isSuperadmin ? [{ label: "Funciones", value: "features" }] : []),
    { label: "Apariencia", value: "appearance" },
    ...(isSuperadmin ? [{ label: "Hacienda / DTE", value: "dte-settings" }] : []),
    { label: "Tipos de Pedido", value: "order-types" },
    { label: "Métodos de Pago", value: "payment-methods" },
  ];

  return (
    <PageLayout
      title="Configuración"
      subtitle="Gestiona usuarios, horarios del personal y funciones avanzadas del sistema."
    >
      <PageTabs
        tabs={tabs}
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
          {isSuperadmin ? <FeatureFlagsTab /> : (
            <div className="rounded-md border p-4 text-sm text-muted-foreground">No tienes permiso para esta sección.</div>
          )}
        </TabsContent>

        <TabsContent value="appearance" className="mt-0">
          <AppearanceTab />
        </TabsContent>

        <TabsContent value="dte-settings" className="mt-0">
          {isSuperadmin ? <DteSettingsTab /> : (
            <div className="rounded-md border p-4 text-sm text-muted-foreground">No tienes permiso para esta sección.</div>
          )}
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
