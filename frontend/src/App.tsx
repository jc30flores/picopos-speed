import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import Kiosk from "./pages/Kiosk";
import Kitchen from "./pages/Kitchen";
import CustomerDisplay from "./pages/CustomerDisplay";
import Menu from "./pages/Menu";
import ReportsHistory from "./pages/ReportsHistory";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";
import Login from "./pages/Login";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/"
              element={
                <ProtectedRoute allowedRoles={["cashier", "admin", "manager"]}>
                  <Index />
                </ProtectedRoute>
              }
            />
            <Route
              path="/kiosk"
              element={
                <ProtectedRoute allowedRoles={["cashier", "admin", "manager"]}>
                  <Kiosk />
                </ProtectedRoute>
              }
            />
            <Route
              path="/kitchen"
              element={
                <ProtectedRoute allowedRoles={["kitchen", "admin", "manager"]}>
                  <Kitchen />
                </ProtectedRoute>
              }
            />
            <Route path="/customer-display" element={<CustomerDisplay />} />
            <Route
              path="/menu"
              element={
                <ProtectedRoute allowedRoles={["admin", "manager"]}>
                  <Menu />
                </ProtectedRoute>
              }
            />
            <Route
              path="/reports-history"
              element={
                <ProtectedRoute allowedRoles={["admin", "manager"]}>
                  <ReportsHistory />
                </ProtectedRoute>
              }
            />
            <Route
              path="/settings"
              element={
                <ProtectedRoute allowedRoles={["admin", "manager"]}>
                  <Settings />
                </ProtectedRoute>
              }
            />
            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
