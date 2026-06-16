import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { OpsProtectedRoute } from "./components/OpsProtectedRoute";
import { DashboardPage } from "./pages/DashboardPage";
import { DealerProfileSettingsPage } from "./pages/DealerProfileSettingsPage";
import { DealerStorefrontPage } from "./pages/DealerStorefrontPage";
import { EmailImportsPage } from "./pages/EmailImportsPage";
import { InventoryDetailPage } from "./pages/InventoryDetailPage";
import { AcquisitionsPage } from "./pages/AcquisitionsPage";
import { AcquisitionWizardPage } from "./pages/AcquisitionWizardPage";
import { AcquisitionDetailPage } from "./pages/AcquisitionDetailPage";
import { AcquisitionsNeedsReviewPage } from "./pages/AcquisitionsNeedsReviewPage";
import { PlaceholderMatchQueuePage } from "./pages/PlaceholderMatchQueuePage";
import { CatalogUniversePage } from "./pages/CatalogUniversePage";
import { IntegrationsPage } from "./pages/IntegrationsPage";
import { AccountSettingsPage } from "./pages/AccountSettingsPage";
import { ConnectedRetailersPage } from "./pages/ConnectedRetailersPage";
import { MarketplaceSearchDashboardPage } from "./pages/MarketplaceSearchDashboardPage";
import { MarketplaceCommandCenterPage } from "./pages/MarketplaceCommandCenterPage";
import { MarketplaceCoverageDashboardPage } from "./pages/MarketplaceCoverageDashboardPage";
import { ImportsPage } from "./pages/ImportsPage";
import { LoginPage } from "./pages/LoginPage";
import { OrderDetailPage } from "./pages/OrderDetailPage";
import { OrderImportPage } from "./pages/OrderImportPage";
import { OrderNewPage } from "./pages/OrderNewPage";
import { OrdersPage } from "./pages/OrdersPage";
import { OperationsPage } from "./pages/OperationsPage";
import { RegisterPage } from "./pages/RegisterPage";
import { PrivacyPolicyPage } from "./pages/PrivacyPolicyPage";
import { MidtownBrowserSessionPage } from "./pages/MidtownBrowserSessionPage";
import { MidtownBrowserOrdersPage } from "./pages/MidtownBrowserOrdersPage";
import { MidtownOrderHtmlUploadPage } from "./pages/MidtownOrderHtmlUploadPage";
import { RetailerHtmlImportPage } from "./pages/RetailerHtmlImportPage";
import { RetailerOrderDetailPage } from "./pages/RetailerOrderDetailPage";
import { RetailerOrdersPage } from "./pages/RetailerOrdersPage";
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
import { RecognitionTestPage } from "./pages/RecognitionTestPage";
import { ConventionScanPage } from "./pages/ConventionScanPage";
import { MobileLiveCapturePage, WebcamLiveCapturePage } from "./pages/LiveCapturePage";
import { ReceivingStationPage } from "./pages/ReceivingStationPage";
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
import { MobileScanPlatformPage } from "./pages/MobileScanPlatformPage";
import { MobileScanResultPage } from "./pages/MobileScanResultPage";
import { MobileIntakePage } from "./pages/MobileIntakePage";
import { MobileStoragePage } from "./pages/MobileStoragePage";
import { MobileAuditPage } from "./pages/MobileAuditPage";
import { MobileOperationsPage } from "./pages/MobileOperationsPage";
import { CollectorAssistantPage } from "./pages/CollectorAssistantPage";
import { CollectorConventionPage } from "./pages/CollectorConventionPage";
import { CollectorDashboardPage } from "./pages/CollectorDashboardPage";
import { CollectorProfilePage } from "./pages/CollectorProfilePage";
import { CollectorOnboardingPage } from "./pages/CollectorOnboardingPage";
import { GuidedImportWizardPage } from "./pages/GuidedImportWizardPage";
import { CollectorOnboardingGate } from "./components/CollectorOnboardingGate";
import { CollectorGoalsPage } from "./pages/CollectorGoalsPage";
import { CollectorBudgetPage } from "./pages/CollectorBudgetPage";
import { CollectorRecommendationsPage } from "./pages/CollectorRecommendationsPage";
import { CollectorBudgetDashboardPage } from "./pages/CollectorBudgetDashboardPage";
import { CollectorQuantityIntelligencePage } from "./pages/CollectorQuantityIntelligencePage";
import { CollectorAnalyticsPage } from "./pages/CollectorAnalyticsPage";
import { SellQueuePage } from "./pages/SellQueuePage";
import { ListingDraftsPage } from "./pages/ListingDraftsPage";
import { ListingDraftReviewPage } from "./pages/ListingDraftReviewPage";
import { ListingManagementPage } from "./pages/ListingManagementPage";
import { ListingManagementDetailPage } from "./pages/ListingManagementDetailPage";
import { SellCommandCenterPage } from "./pages/SellCommandCenterPage";
import { ListingsPage } from "./pages/ListingsPage";
import { SellingAnalyticsPage } from "./pages/SellingAnalyticsPage";
import { BundleOpportunitiesPage } from "./pages/BundleOpportunitiesPage";
import { DiscoveryFeedPage } from "./pages/DiscoveryFeedPage";
import { DiscoveryDashboardPage } from "./pages/DiscoveryDashboardPage";
import { DiscoveryOpportunitiesPage } from "./pages/DiscoveryOpportunitiesPage";
import { DiscoveryOpportunityDetailPage } from "./pages/DiscoveryOpportunityDetailPage";
import { FuturePullListPage } from "./pages/FuturePullListPage";
import { DiscoveryWatchlistsPage } from "./pages/DiscoveryWatchlistsPage";
import { DiscoveryAlertsPage } from "./pages/DiscoveryAlertsPage";
import { DiscoveryAnalyticsPage } from "./pages/DiscoveryAnalyticsPage";
import { MarketplaceMonitoringPage } from "./pages/MarketplaceMonitoringPage";
import { MarketplaceOpportunitiesPage } from "./pages/MarketplaceOpportunitiesPage";
import { MarketplaceOpportunityDetailPage } from "./pages/MarketplaceOpportunityDetailPage";
import { MarketplaceAcquisitionDashboardPage } from "./pages/MarketplaceAcquisitionDashboardPage";
import { CollectionForecastPage } from "./pages/CollectionForecastPage";
import { CollectionRiskPage } from "./pages/CollectionRiskPage";
import { CollectionScenariosPage } from "./pages/CollectionScenariosPage";
import { CollectionOptimizationPage } from "./pages/CollectionOptimizationPage";
import { CollectionValuationDashboardPage } from "./pages/CollectionValuationDashboardPage";
import { CollectorNotificationsPage } from "./pages/CollectorNotificationsPage";
import { CollectorNotificationDashboardPage } from "./pages/CollectorNotificationDashboardPage";
import { DailyBriefingPage } from "./pages/DailyBriefingPage";
import { WeeklyBriefingPage } from "./pages/WeeklyBriefingPage";
import { CollectorCommandCenterPage } from "./pages/CollectorCommandCenterPage";
import { CollectorHomePage } from "./pages/CollectorHomePage";
import { AutomationCenterPage } from "./pages/AutomationCenterPage";
import { FmvIntelligencePage } from "./pages/FmvIntelligencePage";
import { FmvDiagnosticsPage } from "./pages/FmvDiagnosticsPage";
import { PlatformCertificationPage } from "./pages/PlatformCertificationPage";
import { WorkflowHealthPage } from "./pages/WorkflowHealthPage";
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
import { GradingOperationsDashboardPage } from "./pages/GradingOperationsDashboardPage";
import { GradingQueuePage } from "./pages/GradingQueuePage";
import { GradingSubmissionBatchesPage } from "./pages/GradingSubmissionBatchesPage";
import { GradingAnalyticsDashboardPage } from "./pages/GradingAnalyticsDashboardPage";
import { RecommendationAnalyticsPage } from "./pages/RecommendationAnalyticsPage";
import { RecommendationFeedbackPage } from "./pages/RecommendationFeedbackPage";
import { GradingValidationPage } from "./pages/GradingValidationPage";
import { GradingPlatformPage } from "./pages/GradingPlatformPage";
import { ReleaseIntelligencePage } from "./pages/ReleaseIntelligencePage";
import { ReleaseLifecyclePage } from "./pages/ReleaseLifecyclePage";
import { ReleaseMonitoringPage } from "./pages/ReleaseMonitoringPage";
import { FocPurchaseIntelligencePage } from "./pages/FocPurchaseIntelligencePage";
import { ReleaseIntelligenceAnalyticsPage } from "./pages/ReleaseIntelligenceAnalyticsPage";
import { StorageAssignmentPage } from "./pages/StorageAssignmentPage";
import { StorageDashboardPage } from "./pages/StorageDashboardPage";
import { InventoryLocatorPage } from "./pages/InventoryLocatorPage";
import { StorageBoxContentsPage } from "./pages/StorageBoxContentsPage";
import { StorageAuditPage } from "./pages/StorageAuditPage";
import { StorageLabelPreviewPage } from "./pages/StorageLabelPreviewPage";
import { StorageAnalyticsPage } from "./pages/StorageAnalyticsPage";
import { StorageLocationsPage } from "./pages/StorageLocationsPage";
import { ReleaseWatchlistPage } from "./pages/ReleaseWatchlistPage";
import { SpecIntelligencePage } from "./pages/SpecIntelligencePage";
import { ReleasePlatformPage } from "./pages/ReleasePlatformPage";
import { ReleasePlatformCertificationPage } from "./pages/ReleasePlatformCertificationPage";
import { KeyIssueIntelligencePage } from "./pages/KeyIssueIntelligencePage";
import { MarketUserIntelligencePage } from "./pages/MarketUserIntelligencePage";
import { SellCandidatePage } from "./pages/SellCandidatePage";
import { MarketPricingPage } from "./pages/MarketPricingPage";
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
import { ComicOSIntelligenceDashboardPage } from "./pages/ComicOSIntelligenceDashboardPage";
import { CollectorWorkspacePage } from "./pages/CollectorWorkspacePage";
import { PortfolioAnalyticsPage } from "./pages/PortfolioAnalyticsPage";
import { SellIntelligencePage } from "./pages/SellIntelligencePage";
import { ReleaseImportsPage } from "./pages/ReleaseImportsPage";
import { LunarFeedPage } from "./pages/LunarFeedPage";
import { OrganizationsPage } from "./pages/OrganizationsPage";
import { ScanSessionsPage } from "./pages/ScanSessionsPage";
import { ScannerProfilesPage } from "./pages/ScannerProfilesPage";

function HomeRedirect() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-slate-950 px-6 text-center text-slate-200">
        <p>Loading ComicOS...</p>
        <p className="max-w-md text-sm text-slate-500">
          If this takes more than a few seconds, confirm the API is running and{" "}
          <code className="text-slate-400">VITE_API_BASE_URL</code> is set correctly.
        </p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Navigate to="/collector-home" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/privacy" element={<PrivacyPolicyPage />} />
      <Route path="/storefront/:publicSlug" element={<DealerStorefrontPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<CollectorOnboardingGate />}>
        <Route path="/collector-onboarding" element={<CollectorOnboardingPage />} />
        <Route path="/dashboard" element={<DashboardPage loadProfile="portfolio" />} />
        <Route path="/dashboard/collection" element={<DashboardPage loadProfile="collection" />} />
        <Route path="/dashboard/market" element={<DashboardPage loadProfile="market" />} />
        <Route path="/dashboard/grading" element={<DashboardPage loadProfile="grading" />} />
        <Route path="/dashboard/dealer" element={<DashboardPage loadProfile="dealer" />} />
        <Route path="/dashboard/full" element={<DashboardPage loadProfile="full" />} />
        <Route path="/comicos-intelligence" element={<ComicOSIntelligenceDashboardPage />} />
        <Route path="/collector-workspace" element={<CollectorWorkspacePage />} />
        <Route path="/portfolio-analytics" element={<PortfolioAnalyticsPage />} />
        <Route path="/sell-intelligence" element={<SellIntelligencePage />} />
        <Route path="/executive-dashboard" element={<Navigate to="/collector-home" replace />} />
        <Route path="/agent-dashboard" element={<AgentDashboardPage />} />
        <Route path="/marketplace-dashboard" element={<MarketplaceDashboardPage />} />
        <Route path="/dealer-copilot" element={<DealerCopilotPage />} />
        <Route path="/forecast-platform" element={<ForecastPlatformPage />} />
        <Route path="/data-protection" element={<DataProtectionPage />} />
        <Route path="/operations-reliability" element={<OperationsReliabilityPage />} />
        <Route path="/production-readiness" element={<ProductionReadinessPage />} />
        <Route path="/condition-intelligence" element={<ConditionIntelligencePage />} />
        <Route path="/grading-intelligence" element={<GradingIntelligencePage />} />
        <Route path="/grading-operations" element={<GradingOperationsDashboardPage />} />
        <Route path="/grading-queue" element={<GradingQueuePage />} />
        <Route path="/grading-batches" element={<GradingSubmissionBatchesPage />} />
        <Route path="/grading-analytics" element={<GradingAnalyticsDashboardPage />} />
        <Route path="/recommendation-feedback" element={<RecommendationFeedbackPage />} />
        <Route path="/recommendation-analytics" element={<RecommendationAnalyticsPage />} />
        <Route path="/grading-validation" element={<GradingValidationPage />} />
        <Route path="/grading-platform" element={<GradingPlatformPage />} />
        <Route path="/release-intelligence" element={<ReleaseIntelligencePage />} />
        <Route path="/release-monitoring" element={<ReleaseMonitoringPage />} />
        <Route path="/release-lifecycle" element={<ReleaseLifecyclePage />} />
        <Route path="/foc-purchase-intelligence" element={<FocPurchaseIntelligencePage />} />
        <Route path="/release-intelligence-analytics" element={<ReleaseIntelligenceAnalyticsPage />} />
        <Route path="/storage-locations" element={<StorageLocationsPage />} />
        <Route path="/storage-assignment" element={<StorageAssignmentPage />} />
        <Route path="/storage-dashboard" element={<StorageDashboardPage />} />
        <Route path="/inventory-locator" element={<InventoryLocatorPage />} />
        <Route path="/mobile-scan" element={<MobileScanPlatformPage />} />
        <Route path="/mobile-scan/:scanId" element={<MobileScanResultPage />} />
        <Route path="/mobile-intake" element={<MobileIntakePage />} />
        <Route path="/mobile-storage" element={<MobileStoragePage />} />
        <Route path="/mobile-audit" element={<MobileAuditPage />} />
        <Route path="/mobile-operations" element={<MobileOperationsPage />} />
        <Route path="/collector-assistant" element={<CollectorAssistantPage />} />
        <Route path="/convention-mode" element={<CollectorConventionPage />} />
        <Route path="/collector-dashboard" element={<CollectorDashboardPage />} />
        <Route path="/collector-profile" element={<CollectorProfilePage />} />
        <Route path="/collector-goals" element={<CollectorGoalsPage />} />
        <Route path="/collector-budget" element={<CollectorBudgetPage />} />
        <Route path="/collector-recommendations" element={<CollectorRecommendationsPage />} />
        <Route path="/collector-budget-dashboard" element={<CollectorBudgetDashboardPage />} />
        <Route path="/collector-quantity-intelligence" element={<CollectorQuantityIntelligencePage />} />
        <Route path="/collector-analytics" element={<CollectorAnalyticsPage />} />
        <Route path="/sell-queue" element={<SellQueuePage />} />
        <Route path="/listing-drafts" element={<ListingDraftsPage />} />
        <Route path="/listing-drafts/:id" element={<ListingDraftReviewPage />} />
        <Route path="/listing-management" element={<ListingManagementPage />} />
        <Route path="/listing-management/:id" element={<ListingManagementDetailPage />} />
        <Route path="/bundle-opportunities" element={<BundleOpportunitiesPage />} />
        <Route path="/listings" element={<ListingsPage />} />
        <Route path="/selling-analytics" element={<SellingAnalyticsPage />} />
        <Route path="/discovery-feed" element={<DiscoveryFeedPage />} />
        <Route path="/discovery-dashboard" element={<DiscoveryDashboardPage />} />
        <Route path="/discovery-opportunities" element={<DiscoveryOpportunitiesPage />} />
        <Route path="/discovery-opportunity/:id" element={<DiscoveryOpportunityDetailPage />} />
        <Route path="/future-pull-list" element={<FuturePullListPage />} />
        <Route path="/discovery-watchlists" element={<DiscoveryWatchlistsPage />} />
        <Route path="/discovery-alerts" element={<DiscoveryAlertsPage />} />
        <Route path="/discovery-analytics" element={<DiscoveryAnalyticsPage />} />
        <Route path="/marketplace-opportunities" element={<MarketplaceOpportunitiesPage />} />
        <Route path="/buy-opportunities" element={<MarketplaceOpportunitiesPage />} />
        <Route path="/marketplace-monitoring" element={<MarketplaceMonitoringPage />} />
        <Route path="/marketplace-command-center" element={<MarketplaceCommandCenterPage />} />
        <Route path="/marketplace-opportunity/:id" element={<MarketplaceOpportunityDetailPage />} />
        <Route path="/marketplace-acquisition-dashboard" element={<MarketplaceAcquisitionDashboardPage />} />
        <Route path="/collection-forecast" element={<CollectionForecastPage />} />
        <Route path="/collection-risk" element={<CollectionRiskPage />} />
        <Route path="/collection-scenarios" element={<CollectionScenariosPage />} />
        <Route path="/collection-optimization" element={<CollectionOptimizationPage />} />
        <Route path="/collection-valuation-dashboard" element={<CollectionValuationDashboardPage />} />
        <Route path="/notifications" element={<CollectorNotificationsPage />} />
        <Route path="/notification-dashboard" element={<CollectorNotificationDashboardPage />} />
        <Route path="/daily-briefing" element={<DailyBriefingPage />} />
        <Route path="/weekly-briefing" element={<WeeklyBriefingPage />} />
        <Route path="/collector-command-center" element={<CollectorCommandCenterPage />} />
        <Route path="/collector-home" element={<CollectorHomePage />} />
        <Route path="/automation-center" element={<AutomationCenterPage />} />
        <Route path="/fmv-intelligence" element={<FmvIntelligencePage />} />
        <Route path="/platform-certification" element={<PlatformCertificationPage />} />
        <Route path="/workflow-health" element={<WorkflowHealthPage />} />
        <Route path="/storage-box-contents" element={<StorageBoxContentsPage />} />
        <Route path="/storage-audit" element={<StorageAuditPage />} />
        <Route path="/storage-label-preview" element={<StorageLabelPreviewPage />} />
        <Route path="/storage-analytics" element={<StorageAnalyticsPage />} />
        <Route path="/release-watchlists" element={<ReleaseWatchlistPage />} />
        <Route path="/pull-lists" element={<PullListPage />} />
        <Route path="/pull-list-decisions" element={<PullListDecisionsPage />} />
        <Route path="/foc-dashboard" element={<FocDashboardPage />} />
        <Route path="/purchase-profile" element={<PurchaseProfilePage />} />
        <Route path="/purchase-quantities" element={<PurchaseQuantityPage />} />
        <Route path="/purchase-variants" element={<PurchaseVariantPage />} />
        <Route path="/purchase-budget" element={<Navigate to="/collector-budget" replace />} />
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
        <Route path="/sell-command-center" element={<SellCommandCenterPage />} />
        <Route path="/sell-candidates" element={<SellCandidatePage />} />
        <Route path="/market-pricing" element={<MarketPricingPage />} />
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
        <Route path="/recognition-test" element={<RecognitionTestPage />} />
        <Route path="/receiving/live" element={<WebcamLiveCapturePage />} />
        <Route path="/receiving/mobile" element={<MobileLiveCapturePage />} />
        <Route path="/convention-scan" element={<ConventionScanPage />} />
        <Route path="/receiving" element={<ReceivingStationPage />} />
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
        <Route path="/acquisitions" element={<AcquisitionsPage />} />
        <Route path="/acquisitions/new" element={<AcquisitionWizardPage />} />
        <Route path="/acquisitions/needs-review" element={<AcquisitionsNeedsReviewPage />} />
        <Route path="/acquisitions/:acquisitionId" element={<AcquisitionDetailPage />} />
        <Route path="/catalog-universe" element={<CatalogUniversePage />} />
        <Route path="/catalog-universe/placeholders" element={<PlaceholderMatchQueuePage />} />
        <Route path="/imports" element={<ImportsPage />} />
        <Route path="/imports/guided" element={<GuidedImportWizardPage />} />
        <Route path="/imports/guided/:importId" element={<GuidedImportWizardPage />} />
        <Route path="/imports/email" element={<EmailImportsPage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/orders/:orderId" element={<OrderDetailPage />} />
        <Route path="/orders/import" element={<OrderImportPage />} />
        <Route path="/orders/new" element={<OrderNewPage />} />
        <Route path="/retailer-orders" element={<RetailerOrdersPage />} />
        <Route path="/retailer-orders/:id" element={<RetailerOrderDetailPage />} />
        <Route path="/connected-retailers" element={<ConnectedRetailersPage />} />
        <Route path="/connected-retailers/import" element={<RetailerHtmlImportPage />} />
        <Route path="/retailer-orders/import" element={<RetailerHtmlImportPage />} />
        <Route path="/connected-retailers/midtown" element={<MidtownBrowserSessionPage />} />
        <Route path="/connected-retailers/midtown/orders" element={<MidtownBrowserOrdersPage />} />
        <Route path="/connected-retailers/midtown/upload" element={<MidtownOrderHtmlUploadPage />} />
        <Route path="/settings/connected-retailers" element={<ConnectedRetailersPage />} />
        <Route path="/settings/integrations" element={<IntegrationsPage />} />
        <Route path="/settings/account" element={<AccountSettingsPage />} />
        <Route path="/settings/scanner-profiles" element={<ScannerProfilesPage />} />
        </Route>
      </Route>
      <Route element={<OpsProtectedRoute />}>
        <Route path="/ops" element={<OperationsPage />} />
        <Route path="/ops/marketplace-search" element={<MarketplaceSearchDashboardPage />} />
        <Route path="/ops/marketplace-coverage" element={<MarketplaceCoverageDashboardPage />} />
        <Route path="/ops/fmv-diagnostics" element={<FmvDiagnosticsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
