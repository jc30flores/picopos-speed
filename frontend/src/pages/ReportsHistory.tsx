import { Navigation } from "@/components/Navigation";
import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ReportsTab } from "@/components/reports/ReportsTab";
import { SalesHistoryTab } from "@/components/reports/SalesHistoryTab";

const ReportsHistory = () => {
  const [activeTab, setActiveTab] = useState("reports");

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="pt-20 px-4 pb-8">
        <div className="max-w-7xl mx-auto">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="mb-6">
              <TabsTrigger value="reports">Reportes</TabsTrigger>
              <TabsTrigger value="sales-history">Historial de Ventas</TabsTrigger>
            </TabsList>

            <TabsContent value="reports" className="mt-0">
              <ReportsTab />
            </TabsContent>

            <TabsContent value="sales-history" className="mt-0">
              <SalesHistoryTab />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
};

export default ReportsHistory;
