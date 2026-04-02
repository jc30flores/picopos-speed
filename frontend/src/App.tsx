import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Index from "./pages/Index";
import MainMenu from "./pages/MainMenu";
import Kiosk from "./pages/Kiosk";
import Kitchen from "./pages/Kitchen";
import CustomerDisplay from "./pages/CustomerDisplay";
import Menu from "./pages/Menu";
import RegistrosVentas from "./pages/RegistrosVentas";
import RegistrosCaja from "./pages/RegistrosCaja";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";
import Login from "./pages/Login";
import DTEPage from "./pages/DTE";
import CustomersPage from "./pages/Customers";
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
                  <MainMenu />
                </ProtectedRoute>
              }
            />
            <Route
              path="/pos"
              element={
                <ProtectedRoute allowedRoles={["cashier", "admin", "manager"]}>
                  <Index />
                </ProtectedRoute>
              }
            />
            <Route
              path="/kiosk"
              element={
                <ProtectedRoute allowedRoles={["admin"]}>
                  <Kiosk />
                </ProtectedRoute>
              }
            />
            <Route
              path="/kitchen"
              element={
                <ProtectedRoute allowedRoles={["kitchen", "admin"]}>
                  <Kitchen />
                </ProtectedRoute>
              }
            />
            <Route path="/customer-display" element={<ProtectedRoute allowedRoles={["admin"]}><CustomerDisplay /></ProtectedRoute>} />
            <Route path="/clientes" element={<ProtectedRoute allowedRoles={["admin", "manager"]}><CustomersPage /></ProtectedRoute>} />
            <Route
              path="/menu"
              element={
                <ProtectedRoute allowedRoles={["admin", "manager"]}>
                  <Menu />
                </ProtectedRoute>
              }
            />
            <Route
              path="/registros/ventas"
              element={
                <ProtectedRoute allowedRoles={["admin", "manager", "cashier"]}>
                  <RegistrosVentas />
                </ProtectedRoute>
              }
            />
            <Route
              path="/registros/caja"
              element={
                <ProtectedRoute allowedRoles={["admin"]}>
                  <RegistrosCaja />
                </ProtectedRoute>
              }
            />
            <Route path="/reports-history" element={<Navigate to="/registros/ventas" replace />} />
            <Route
              path="/dte"
              element={
                <ProtectedRoute allowedRoles={["admin"]}>
                  <DTEPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/settings"
              element={
                <ProtectedRoute allowedRoles={["admin"]}>
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
