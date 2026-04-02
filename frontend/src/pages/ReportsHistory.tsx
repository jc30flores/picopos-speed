import { useState } from "react";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import { PageTabs } from "@/components/ui/page-tabs";
import { ReportsTab } from "@/components/reports/ReportsTab";
import { SalesHistoryTab } from "@/components/reports/SalesHistoryTab";
import { CashHistoryTab } from "@/components/reports/CashHistoryTab";
import { PageLayout } from "@/components/layout/PageLayout";

const ReportsHistory = () => {
  const [activeTab, setActiveTab] = useState("reports");

  return (
    <PageLayout title="Reportes & Historial" subtitle="Consulta métricas operativas y el historial de ventas.">

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
    </PageLayout>
  );
};

export default ReportsHistory;
