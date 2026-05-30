import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { OpsProtectedRoute } from "./components/OpsProtectedRoute";
import { DashboardPage } from "./pages/DashboardPage";
import { DealerProfileSettingsPage } from "./pages/DealerProfileSettingsPage";
import { DealerStorefrontPage } from "./pages/DealerStorefrontPage";
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
import { ScanSpineTicksPage } from "./pages/ScanSpineTicksPage";
import { ScanCornerEdgesPage } from "./pages/ScanCornerEdgesPage";
import { ScanSurfaceDefectsPage } from "./pages/ScanSurfaceDefectsPage";
import { ScanStructuralDamagePage } from "./pages/ScanStructuralDamagePage";
import { ScanDefectAggregationPage } from "./pages/ScanDefectAggregationPage";
import { ScanGradingAssistancePage } from "./pages/ScanGradingAssistancePage";
import { ScanVisualEvidencePage } from "./pages/ScanVisualEvidencePage";
import { ScanReviewWorkspacePage } from "./pages/ScanReviewWorkspacePage";
import { ScanHistoricalComparisonPage } from "./pages/ScanHistoricalComparisonPage";
import { ScanAuthenticationPage } from "./pages/ScanAuthenticationPage";
import { ScanIntelligenceFeedPage } from "./pages/ScanIntelligenceFeedPage";
import { ScanReplayPage } from "./pages/ScanReplayPage";
import { AutomationJobsPage } from "./pages/AutomationJobsPage";
import { AutomationBatchPage } from "./pages/AutomationBatchPage";
import { AutomationNotificationsPage } from "./pages/AutomationNotificationsPage";
import { AutomationAnalyticsPage } from "./pages/AutomationAnalyticsPage";
import { AutomationOpsDashboardPage } from "./pages/AutomationOpsDashboardPage";
import { AutomationRulesPage } from "./pages/AutomationRulesPage";
import { AutomationRecoveryPage } from "./pages/AutomationRecoveryPage";
import { AutomationWorkersPage } from "./pages/AutomationWorkersPage";
import { AutomationWorkflowsPage } from "./pages/AutomationWorkflowsPage";
import { OrganizationDetailPage } from "./pages/OrganizationDetailPage";
import { MobileFoundationPage } from "./pages/MobileFoundationPage";
import { OfflineInventoryPage } from "./pages/OfflineInventoryPage";
import { ConventionModePage } from "./pages/ConventionModePage";
import { MobileScanningPage } from "./pages/MobileScanningPage";
import { QuickSalesPage } from "./pages/QuickSalesPage";
import { MobileOpsDashboardPage } from "./pages/MobileOpsDashboardPage";
import { MobileDeviceSecurityPage } from "./pages/MobileDeviceSecurityPage";
import { MobileAnalyticsPage } from "./pages/MobileAnalyticsPage";
import { MarketplaceAccountsPage } from "./pages/MarketplaceAccountsPage";
import { MarketplaceEventsPage } from "./pages/MarketplaceEventsPage";
import { MarketplaceInventorySyncPage } from "./pages/MarketplaceInventorySyncPage";
import { MarketplaceListingsPage } from "./pages/MarketplaceListingsPage";
import { MarketplaceOrdersPage } from "./pages/MarketplaceOrdersPage";
import { MarketplacePricingPage } from "./pages/MarketplacePricingPage";
import { LiveSalesPage } from "./pages/LiveSalesPage";
import { MarketplaceOpsDashboardPage } from "./pages/MarketplaceOpsDashboardPage";
import { MarketplaceAnalyticsPage } from "./pages/MarketplaceAnalyticsPage";
import { ShopifySyncPage } from "./pages/ShopifySyncPage";
import { OrganizationInventoryPage } from "./pages/OrganizationInventoryPage";
import { OrganizationReviewsPage } from "./pages/OrganizationReviewsPage";
import { OrganizationActivityPage } from "./pages/OrganizationActivityPage";
import { OrganizationAuditPage } from "./pages/OrganizationAuditPage";
import { DealerOperationsDashboardPage } from "./pages/DealerOperationsDashboardPage";
import { AgentDashboardPage } from "./pages/AgentDashboardPage";
import { OrganizationsPage } from "./pages/OrganizationsPage";
import { ScanSessionsPage } from "./pages/ScanSessionsPage";
import { ScannerProfilesPage } from "./pages/ScannerProfilesPage";

function HomeRedirect() {
  const { isAuthenticated, isLoading, securityContext } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-200">
        Loading ComicOS...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (securityContext?.active_organization_id) {
    return <Navigate to={`/organizations/${securityContext.active_organization_id}`} replace />;
  }

  return <Navigate to="/organizations" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/storefront/:publicSlug" element={<DealerStorefrontPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/agent-dashboard" element={<AgentDashboardPage />} />
        <Route path="/scan-ingestion" element={<ScanIngestionPage />} />
        <Route path="/scan-normalization" element={<ScanNormalizationPage />} />
        <Route path="/scan-boundary" element={<ScanBoundaryPage />} />
        <Route path="/scan-ocr" element={<ScanOcrPage />} />
        <Route path="/scan-reconciliation" element={<ScanReconciliationPage />} />
        <Route path="/scan-defects" element={<ScanDefectsPage />} />
        <Route path="/scan-spine-ticks" element={<ScanSpineTicksPage />} />
        <Route path="/scan-corner-edges" element={<ScanCornerEdgesPage />} />
        <Route path="/scan-surface-defects" element={<ScanSurfaceDefectsPage />} />
        <Route path="/scan-structural-damage" element={<ScanStructuralDamagePage />} />
        <Route path="/scan-defect-aggregation" element={<ScanDefectAggregationPage />} />
        <Route path="/scan-grading-assistance" element={<ScanGradingAssistancePage />} />
        <Route path="/scan-visual-evidence" element={<ScanVisualEvidencePage />} />
        <Route path="/scan-review" element={<ScanReviewWorkspacePage />} />
        <Route path="/scan-historical-comparison" element={<ScanHistoricalComparisonPage />} />
        <Route path="/scan-authentication" element={<ScanAuthenticationPage />} />
        <Route path="/scan-intelligence-feed" element={<ScanIntelligenceFeedPage />} />
        <Route path="/scan-replay" element={<ScanReplayPage />} />
        <Route path="/automation-jobs" element={<AutomationJobsPage />} />
        <Route path="/automation-batch" element={<AutomationBatchPage />} />
        <Route path="/automation-notifications" element={<AutomationNotificationsPage />} />
        <Route path="/automation-analytics" element={<AutomationAnalyticsPage />} />
        <Route path="/automation-ops" element={<AutomationOpsDashboardPage />} />
        <Route path="/automation-rules" element={<AutomationRulesPage />} />
        <Route path="/automation-recovery" element={<AutomationRecoveryPage />} />
        <Route path="/automation-workers" element={<AutomationWorkersPage />} />
        <Route path="/automation-workflows" element={<AutomationWorkflowsPage />} />
        <Route path="/organizations" element={<OrganizationsPage />} />
        <Route path="/organizations/:organizationId" element={<OrganizationDetailPage />} />
        <Route path="/organizations/:organizationId/mobile" element={<MobileFoundationPage />} />
        <Route path="/organizations/:organizationId/offline-inventory" element={<OfflineInventoryPage />} />
        <Route path="/organizations/:organizationId/mobile-scanning" element={<MobileScanningPage />} />
        <Route path="/organizations/:organizationId/convention-mode" element={<ConventionModePage />} />
        <Route path="/organizations/:organizationId/quick-sales" element={<QuickSalesPage />} />
        <Route path="/organizations/:organizationId/mobile-ops" element={<MobileOpsDashboardPage />} />
        <Route path="/organizations/:organizationId/mobile-security" element={<MobileDeviceSecurityPage />} />
        <Route path="/organizations/:organizationId/mobile-analytics" element={<MobileAnalyticsPage />} />
        <Route path="/organizations/:organizationId/marketplaces" element={<MarketplaceAccountsPage />} />
        <Route path="/organizations/:organizationId/marketplace-events" element={<MarketplaceEventsPage />} />
        <Route path="/organizations/:organizationId/live-sales" element={<LiveSalesPage />} />
        <Route path="/organizations/:organizationId/marketplace-ops" element={<MarketplaceOpsDashboardPage />} />
        <Route path="/organizations/:organizationId/marketplace-analytics" element={<MarketplaceAnalyticsPage />} />
        <Route path="/organizations/:organizationId/marketplace-sync" element={<MarketplaceInventorySyncPage />} />
        <Route path="/organizations/:organizationId/shopify" element={<ShopifySyncPage />} />
        <Route path="/organizations/:organizationId/marketplace-listings" element={<MarketplaceListingsPage />} />
        <Route path="/organizations/:organizationId/marketplace-orders" element={<MarketplaceOrdersPage />} />
        <Route path="/organizations/:organizationId/marketplace-pricing" element={<MarketplacePricingPage />} />
        <Route path="/organizations/:organizationId/inventory" element={<OrganizationInventoryPage />} />
        <Route path="/organizations/:organizationId/reviews" element={<OrganizationReviewsPage />} />
        <Route path="/organizations/:organizationId/activity" element={<OrganizationActivityPage />} />
        <Route path="/organizations/:organizationId/audit" element={<OrganizationAuditPage />} />
        <Route path="/organizations/:organizationId/dashboard" element={<DealerOperationsDashboardPage />} />
        <Route path="/organizations/:organizationId/storefront" element={<DealerProfileSettingsPage />} />
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
