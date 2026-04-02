import { Navigation } from "@/components/Navigation";
import { useState } from "react";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import { PageTabs } from "@/components/ui/page-tabs";
import { ReportsTab } from "@/components/reports/ReportsTab";
import { SalesHistoryTab } from "@/components/reports/SalesHistoryTab";
import { CashHistoryTab } from "@/components/reports/CashHistoryTab";

const ReportsHistory = () => {
  const [activeTab, setActiveTab] = useState("reports");

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="px-4 pb-8 pt-4">
        <div className="mx-auto max-w-7xl">
          <div className="mb-4 space-y-1">
            <h1 className="text-2xl font-bold sm:text-3xl">Reportes & Historial</h1>
            <p className="text-sm text-muted-foreground">Consulta métricas operativas y el historial de ventas.</p>
          </div>

          <PageTabs
            tabs={[
              { label: "Reportes", value: "reports" },
              { label: "Historial de Ventas", value: "sales-history" },
              { label: "Historial de Caja", value: "cash-history" },
            ]}
            activeValue={activeTab}
            onChange={setActiveTab}
          />

          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsContent value="reports" className="mt-0">
              <ReportsTab />
            </TabsContent>

            <TabsContent value="sales-history" className="mt-0">
              <SalesHistoryTab />
            </TabsContent>

            <TabsContent value="cash-history" className="mt-0">
              <CashHistoryTab />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
};

export default ReportsHistory;
