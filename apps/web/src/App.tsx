import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { OpsProtectedRoute } from "./components/OpsProtectedRoute";
import { DashboardPage } from "./pages/DashboardPage";
import { EmailImportsPage } from "./pages/EmailImportsPage";
import { InventoryDetailPage } from "./pages/InventoryDetailPage";
import { IntegrationsPage } from "./pages/IntegrationsPage";
import { ImportsPage } from "./pages/ImportsPage";
import { LoginPage } from "./pages/LoginPage";
import { OrderDetailPage } from "./pages/OrderDetailPage";
import { OrderImportPage } from "./pages/OrderImportPage";
import { OrderNewPage } from "./pages/OrderNewPage";
import { OrdersPage } from "./pages/OrdersPage";
import { OperationsPage } from "./pages/OperationsPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ScanIngestionPage } from "./pages/ScanIngestionPage";
import { ScanNormalizationPage } from "./pages/ScanNormalizationPage";
import { ScanBoundaryPage } from "./pages/ScanBoundaryPage";
import { ScanOcrPage } from "./pages/ScanOcrPage";
import { ScanReconciliationPage } from "./pages/ScanReconciliationPage";
import { ScanDefectsPage } from "./pages/ScanDefectsPage";
import { ScanSessionsPage } from "./pages/ScanSessionsPage";
import { ScannerProfilesPage } from "./pages/ScannerProfilesPage";

function HomeRedirect() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-200">
        Loading ComicOS...
      </div>
    );
  }

  return <Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/scan-ingestion" element={<ScanIngestionPage />} />
        <Route path="/scan-normalization" element={<ScanNormalizationPage />} />
        <Route path="/scan-boundary" element={<ScanBoundaryPage />} />
        <Route path="/scan-ocr" element={<ScanOcrPage />} />
        <Route path="/scan-reconciliation" element={<ScanReconciliationPage />} />
        <Route path="/scan-defects" element={<ScanDefectsPage />} />
        <Route path="/scan-sessions" element={<ScanSessionsPage />} />
        <Route path="/inventory/:inventoryCopyId" element={<InventoryDetailPage />} />
        <Route path="/imports" element={<ImportsPage />} />
        <Route path="/imports/email" element={<EmailImportsPage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/orders/:orderId" element={<OrderDetailPage />} />
        <Route path="/orders/import" element={<OrderImportPage />} />
        <Route path="/orders/new" element={<OrderNewPage />} />
        <Route path="/settings/integrations" element={<IntegrationsPage />} />
        <Route path="/settings/scanner-profiles" element={<ScannerProfilesPage />} />
      </Route>
      <Route element={<OpsProtectedRoute />}>
        <Route path="/ops" element={<OperationsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
