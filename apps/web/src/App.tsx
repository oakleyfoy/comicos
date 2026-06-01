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
import { MarketplaceDashboardPage } from "./pages/MarketplaceDashboardPage";
import { DealerCopilotPage } from "./pages/DealerCopilotPage";
import { ForecastPlatformPage } from "./pages/ForecastPlatformPage";
import { DataProtectionPage } from "./pages/DataProtectionPage";
import { OperationsReliabilityPage } from "./pages/OperationsReliabilityPage";
import { ProductionReadinessPage } from "./pages/ProductionReadinessPage";
import { ConditionIntelligencePage } from "./pages/ConditionIntelligencePage";
import { GradingIntelligencePage } from "./pages/GradingIntelligencePage";
import { GradingValidationPage } from "./pages/GradingValidationPage";
import { GradingPlatformPage } from "./pages/GradingPlatformPage";
import { ReleaseIntelligencePage } from "./pages/ReleaseIntelligencePage";
import { ReleaseWatchlistPage } from "./pages/ReleaseWatchlistPage";
import { SpecIntelligencePage } from "./pages/SpecIntelligencePage";
import { ReleasePlatformPage } from "./pages/ReleasePlatformPage";
import { ReleasePlatformCertificationPage } from "./pages/ReleasePlatformCertificationPage";
import { KeyIssueIntelligencePage } from "./pages/KeyIssueIntelligencePage";
import { MarketUserIntelligencePage } from "./pages/MarketUserIntelligencePage";
import { SellCandidatePage } from "./pages/SellCandidatePage";
import { WantListPage } from "./pages/WantListPage";
import { CollectionGapPage } from "./pages/CollectionGapPage";
import { CollectedRunsPage } from "./pages/CollectedRunsPage";
import { NextIssuesPage } from "./pages/NextIssuesPage";
import { FutureReleasesPage } from "./pages/FutureReleasesPage";
import { FutureReleaseActionsPage } from "./pages/FutureReleaseActionsPage";
import { FutureReleaseDashboardPage } from "./pages/FutureReleaseDashboardPage";
import { IndustryPublishersPage } from "./pages/IndustryPublishersPage";
import { IndustryReleaseScannerPage } from "./pages/IndustryReleaseScannerPage";
import { IndustrySignalsPage } from "./pages/IndustrySignalsPage";
import { IndustryOpportunitiesPage } from "./pages/IndustryOpportunitiesPage";
import { WeeklySpecDashboardPage } from "./pages/WeeklySpecDashboardPage";
import { TopSpecPicksPage } from "./pages/TopSpecPicksPage";
import { AISpecEvaluationsPage } from "./pages/AISpecEvaluationsPage";
import { SpecBaselinePage } from "./pages/SpecBaselinePage";
import { SpecInputsPage } from "./pages/SpecInputsPage";
import { IndustryScannerDashboardPage } from "./pages/IndustryScannerDashboardPage";
import { AcquisitionOpportunityPage } from "./pages/AcquisitionOpportunityPage";
import { MarketplaceAcquisitionPage } from "./pages/MarketplaceAcquisitionPage";
import { AcquisitionDashboardPage } from "./pages/AcquisitionDashboardPage";
import { ExitCandidatePage } from "./pages/ExitCandidatePage";
import { HoldSellPage } from "./pages/HoldSellPage";
import { GradeBeforeSellPage } from "./pages/GradeBeforeSellPage";
import { PortfolioRebalancingPage } from "./pages/PortfolioRebalancingPage";
import { ExitDashboardPage } from "./pages/ExitDashboardPage";
import { UnifiedCollectorPage } from "./pages/UnifiedCollectorPage";
import { DailyActionPage } from "./pages/DailyActionPage";
import { CrossSystemRecommendationPage } from "./pages/CrossSystemRecommendationPage";
import { ExecutiveDashboardPage } from "./pages/ExecutiveDashboardPage";
import { PullListDecisionsPage } from "./pages/PullListDecisionsPage";
import { FocDashboardPage } from "./pages/FocDashboardPage";
import { PurchaseProfilePage } from "./pages/PurchaseProfilePage";
import { PurchaseQuantityPage } from "./pages/PurchaseQuantityPage";
import { PurchaseVariantPage } from "./pages/PurchaseVariantPage";
import { PurchaseBudgetPage } from "./pages/PurchaseBudgetPage";
import { PullListPage } from "./pages/PullListPage";
import { RecommendationsV2Page } from "./pages/RecommendationsV2Page";
import { RecommendationIntelligenceCertificationPage } from "./pages/RecommendationIntelligenceCertificationPage";
import { IntelligencePage } from "./pages/IntelligencePage";
import { ReleaseImportsPage } from "./pages/ReleaseImportsPage";
import { LunarFeedPage } from "./pages/LunarFeedPage";
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

  return <Navigate to="/executive-dashboard" replace />;
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
        <Route path="/executive-dashboard" element={<ExecutiveDashboardPage />} />
        <Route path="/agent-dashboard" element={<AgentDashboardPage />} />
        <Route path="/marketplace-dashboard" element={<MarketplaceDashboardPage />} />
        <Route path="/dealer-copilot" element={<DealerCopilotPage />} />
        <Route path="/forecast-platform" element={<ForecastPlatformPage />} />
        <Route path="/data-protection" element={<DataProtectionPage />} />
        <Route path="/operations-reliability" element={<OperationsReliabilityPage />} />
        <Route path="/production-readiness" element={<ProductionReadinessPage />} />
        <Route path="/condition-intelligence" element={<ConditionIntelligencePage />} />
        <Route path="/grading-intelligence" element={<GradingIntelligencePage />} />
        <Route path="/grading-validation" element={<GradingValidationPage />} />
        <Route path="/grading-platform" element={<GradingPlatformPage />} />
        <Route path="/release-intelligence" element={<ReleaseIntelligencePage />} />
        <Route path="/release-watchlists" element={<ReleaseWatchlistPage />} />
        <Route path="/pull-lists" element={<PullListPage />} />
        <Route path="/pull-list-decisions" element={<PullListDecisionsPage />} />
        <Route path="/foc-dashboard" element={<FocDashboardPage />} />
        <Route path="/purchase-profile" element={<PurchaseProfilePage />} />
        <Route path="/purchase-quantities" element={<PurchaseQuantityPage />} />
        <Route path="/purchase-variants" element={<PurchaseVariantPage />} />
        <Route path="/purchase-budget" element={<PurchaseBudgetPage />} />
        <Route path="/spec-intelligence" element={<SpecIntelligencePage />} />
        <Route path="/spec-inputs" element={<SpecInputsPage />} />
        <Route path="/spec-baseline" element={<SpecBaselinePage />} />
        <Route path="/ai-spec-evaluations" element={<AISpecEvaluationsPage />} />
        <Route path="/top-spec-picks" element={<TopSpecPicksPage />} />
        <Route path="/weekly-spec-dashboard" element={<WeeklySpecDashboardPage />} />
        <Route path="/release-platform" element={<ReleasePlatformPage />} />
        <Route path="/release-platform-certification" element={<ReleasePlatformCertificationPage />} />
        <Route path="/intelligence" element={<IntelligencePage />} />
        <Route path="/key-issues" element={<KeyIssueIntelligencePage />} />
        <Route path="/market-user-intelligence" element={<MarketUserIntelligencePage />} />
        <Route path="/sell-candidates" element={<SellCandidatePage />} />
        <Route path="/want-lists" element={<WantListPage />} />
        <Route path="/collection-gaps" element={<CollectionGapPage />} />
        <Route path="/collected-runs" element={<CollectedRunsPage />} />
        <Route path="/next-issues" element={<NextIssuesPage />} />
        <Route path="/future-releases" element={<FutureReleasesPage />} />
        <Route path="/future-release-actions" element={<FutureReleaseActionsPage />} />
        <Route path="/future-release-dashboard" element={<FutureReleaseDashboardPage />} />
        <Route path="/industry-publishers" element={<IndustryPublishersPage />} />
        <Route path="/industry-release-scanner" element={<IndustryReleaseScannerPage />} />
        <Route path="/industry-signals" element={<IndustrySignalsPage />} />
        <Route path="/industry-opportunities" element={<IndustryOpportunitiesPage />} />
        <Route path="/industry-scanner-dashboard" element={<IndustryScannerDashboardPage />} />
        <Route path="/acquisition-opportunities" element={<AcquisitionOpportunityPage />} />
        <Route path="/marketplace-acquisitions" element={<MarketplaceAcquisitionPage />} />
        <Route path="/acquisition-dashboard" element={<AcquisitionDashboardPage />} />
        <Route path="/exit-candidates" element={<ExitCandidatePage />} />
        <Route path="/hold-sell" element={<HoldSellPage />} />
        <Route path="/grade-before-sell" element={<GradeBeforeSellPage />} />
        <Route path="/portfolio-rebalancing" element={<PortfolioRebalancingPage />} />
        <Route path="/exit-dashboard" element={<ExitDashboardPage />} />
        <Route path="/unified-intelligence" element={<UnifiedCollectorPage />} />
        <Route path="/daily-actions" element={<DailyActionPage />} />
        <Route path="/cross-system-recommendations" element={<CrossSystemRecommendationPage />} />
        <Route path="/recommendations-v2" element={<RecommendationsV2Page />} />
        <Route path="/recommendation-intelligence-certification" element={<RecommendationIntelligenceCertificationPage />} />
        <Route path="/release-imports" element={<ReleaseImportsPage />} />
        <Route path="/lunar-feed" element={<LunarFeedPage />} />
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
