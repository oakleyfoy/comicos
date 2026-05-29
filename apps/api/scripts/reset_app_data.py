from __future__ import annotations

import argparse
import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, func, select, update
from sqlalchemy.sql.ddl import sort_tables

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models as models
from app.core.config import get_settings
from app.db.session import get_engine


@dataclass(frozen=True)
class ResetTarget:
    label: str
    model: type


RESET_TARGETS: tuple[ResetTarget, ...] = (
    # Organization / auth / storefront / marketplace foundation
    ResetTarget("organization_notification_receipts", models.OrganizationNotificationReceipt),
    ResetTarget("organization_notifications", models.OrganizationNotification),
    ResetTarget("organization_activity_events", models.OrganizationActivityEvent),
    ResetTarget("organization_audit_access_logs", models.OrganizationAuditAccessLog),
    ResetTarget("organization_compliance_events", models.OrganizationComplianceEvent),
    ResetTarget("organization_audit_ledger", models.OrganizationAuditLedger),
    ResetTarget("organization_review_events", models.OrganizationReviewEvent),
    ResetTarget("organization_approval_queues", models.OrganizationApprovalQueue),
    ResetTarget("organization_review_decisions", models.OrganizationReviewDecision),
    ResetTarget("organization_reviews", models.OrganizationReview),
    ResetTarget("organization_inventory_workflow_events", models.OrganizationInventoryWorkflowEvent),
    ResetTarget("organization_inventory_queues", models.OrganizationInventoryQueue),
    ResetTarget("organization_inventory_assignments", models.OrganizationInventoryAssignment),
    ResetTarget("marketplace_connection_events", models.MarketplaceConnectionEvent),
    ResetTarget("marketplace_order_events", models.MarketplaceOrderEvent),
    ResetTarget("marketplace_transactions", models.MarketplaceTransaction),
    ResetTarget("marketplace_order_line_items", models.MarketplaceOrderLineItem),
    ResetTarget("marketplace_orders", models.MarketplaceOrder),
    ResetTarget("live_sale_events", models.LiveSaleEvent),
    ResetTarget("live_sale_claims", models.LiveSaleClaim),
    ResetTarget("live_sale_queue_items", models.LiveSaleQueueItem),
    ResetTarget("live_sale_sessions", models.LiveSaleSession),
    ResetTarget("marketplace_analytics_events", models.MarketplaceAnalyticsEvent),
    ResetTarget("marketplace_performance_trends", models.MarketplacePerformanceTrend),
    ResetTarget("marketplace_metrics", models.MarketplaceMetric),
    ResetTarget("marketplace_analytics_snapshots", models.MarketplaceAnalyticsSnapshot),
    ResetTarget("marketplace_ops_events", models.MarketplaceOpsEvent),
    ResetTarget("marketplace_ops_diagnostics", models.MarketplaceOpsDiagnostic),
    ResetTarget("marketplace_ops_metrics", models.MarketplaceOpsMetric),
    ResetTarget("marketplace_ops_snapshots", models.MarketplaceOpsSnapshot),
    ResetTarget("shopify_sync_events", models.ShopifySyncEvent),
    ResetTarget("shopify_sync_states", models.ShopifySyncState),
    ResetTarget("shopify_product_mappings", models.ShopifyProductMapping),
    ResetTarget("shopify_storefronts", models.ShopifyStorefront),
    ResetTarget("marketplace_event_lineage", models.MarketplaceEventLineage),
    ResetTarget("marketplace_event_processing_runs", models.MarketplaceEventProcessingRun),
    ResetTarget("marketplace_webhook_endpoints", models.MarketplaceWebhookEndpoint),
    ResetTarget("marketplace_events", models.MarketplaceEvent),
    ResetTarget("marketplace_pricing_events", models.MarketplacePricingEvent),
    ResetTarget("marketplace_offers", models.MarketplaceOffer),
    ResetTarget("marketplace_price_recommendations", models.MarketplacePriceRecommendation),
    ResetTarget("marketplace_pricing_rules", models.MarketplacePricingRule),
    ResetTarget("marketplace_inventory_sync_events", models.MarketplaceInventorySyncEvent),
    ResetTarget("marketplace_inventory_conflicts", models.MarketplaceInventoryConflict),
    ResetTarget("marketplace_inventory_states", models.MarketplaceInventoryState),
    ResetTarget("marketplace_inventory_sync_runs", models.MarketplaceInventorySyncRun),
    ResetTarget("marketplace_listing_events", models.MarketplaceListingEvent),
    ResetTarget("marketplace_listing_projections", models.MarketplaceListingProjection),
    ResetTarget("marketplace_listing_drafts", models.MarketplaceListingDraft),
    ResetTarget("marketplace_credentials", models.MarketplaceCredential),
    ResetTarget("marketplace_accounts", models.MarketplaceAccount),
    ResetTarget("dealer_storefront_events", models.DealerStorefrontEvent),
    ResetTarget("dealer_storefront_settings", models.DealerStorefrontSettings),
    ResetTarget("dealer_profiles", models.DealerProfile),
    ResetTarget("organization_dealer_dashboard_events", models.OrganizationDealerDashboardEvent),
    ResetTarget("organization_dealer_operational_metrics", models.OrganizationDealerOperationalMetric),
    ResetTarget("organization_dealer_dashboard_snapshots", models.OrganizationDealerDashboardSnapshot),
    ResetTarget("organization_permission_audits", models.OrganizationPermissionAudit),
    ResetTarget("organization_membership_roles", models.OrganizationMembershipRole),
    ResetTarget("organization_roles", models.OrganizationRole),
    ResetTarget("organization_events", models.OrganizationEvent),
    ResetTarget("organization_invitations", models.OrganizationInvitation),
    ResetTarget("organization_members", models.OrganizationMember),
    ResetTarget("organization_security_contexts", models.OrganizationSecurityContext),
    ResetTarget("user_auth_session_events", models.UserAuthSessionEvent),
    ResetTarget("user_auth_sessions", models.UserAuthSession),
    # Listing / dashboard / reporting
    ResetTarget("listing_images", models.ListingImage),
    ResetTarget("listing_inventory_links", models.ListingInventoryLink),
    ResetTarget("listing_price_history", models.ListingPriceHistory),
    ResetTarget("listing_lifecycle_events", models.ListingLifecycleEvent),
    ResetTarget("listings", models.Listing),
    ResetTarget("listing_export_run_items", models.ListingExportRunItem),
    ResetTarget("listing_export_files", models.ListingExportFile),
    ResetTarget("listing_export_runs", models.ListingExportRun),
    ResetTarget("listing_export_templates", models.ListingExportTemplate),
    ResetTarget("listing_intelligence_evidence", models.ListingIntelligenceEvidence),
    ResetTarget("listing_intelligence_snapshots", models.ListingIntelligenceSnapshot),
    ResetTarget("listing_channel_performance_snapshots", models.ListingChannelPerformanceSnapshot),
    ResetTarget("listing_completeness_checks", models.ListingCompletenessCheck),
    ResetTarget("dealer_dashboard_feed_events", models.DealerDashboardFeedEvent),
    ResetTarget("dealer_dashboard_alerts", models.DealerDashboardAlert),
    ResetTarget("dealer_dashboard_metrics", models.DealerDashboardMetric),
    ResetTarget("dealer_dashboard_snapshots", models.DealerDashboardSnapshot),
    ResetTarget("dealer_grading_dashboard_feed_events", models.DealerGradingDashboardFeedEvent),
    ResetTarget("dealer_grading_dashboard_alerts", models.DealerGradingDashboardAlert),
    ResetTarget("dealer_grading_dashboard_metrics", models.DealerGradingDashboardMetric),
    ResetTarget("dealer_grading_dashboard_snapshots", models.DealerGradingDashboardSnapshot),
    ResetTarget("portfolio_strategy_dashboard_feed_events", models.PortfolioStrategyDashboardFeedEvent),
    ResetTarget("portfolio_strategy_dashboard_alerts", models.PortfolioStrategyDashboardAlert),
    ResetTarget("portfolio_strategy_dashboard_metrics", models.PortfolioStrategyDashboardMetric),
    ResetTarget("portfolio_strategy_dashboard_snapshots", models.PortfolioStrategyDashboardSnapshot),
    ResetTarget("operational_report_items", models.OperationalReportItem),
    ResetTarget("operational_report_files", models.OperationalReportFile),
    ResetTarget("operational_report_runs", models.OperationalReportRun),
    ResetTarget("grading_operational_report_items", models.GradingOperationalReportItem),
    ResetTarget("grading_operational_report_files", models.GradingOperationalReportFile),
    ResetTarget("grading_operational_report_runs", models.GradingOperationalReportRun),
    # Portfolio / strategy / market engines
    ResetTarget("portfolio_lifecycle_events", models.PortfolioLifecycleEvent),
    ResetTarget("portfolio_items", models.PortfolioItem),
    ResetTarget("portfolio_exposure_evidence", models.PortfolioExposureEvidence),
    ResetTarget("portfolio_exposure_snapshots", models.PortfolioExposureSnapshot),
    ResetTarget("portfolio_allocation_snapshots", models.PortfolioAllocationSnapshot),
    ResetTarget("portfolios", models.Portfolio),
    ResetTarget("duplicate_cluster_items", models.DuplicateClusterItem),
    ResetTarget("duplicate_consolidation_recommendations", models.DuplicateConsolidationRecommendation),
    ResetTarget("duplicate_history_snapshots", models.DuplicateHistorySnapshot),
    ResetTarget("duplicate_clusters", models.DuplicateCluster),
    ResetTarget("portfolio_liquidity_evidence", models.PortfolioLiquidityEvidence),
    ResetTarget("portfolio_liquidity_history", models.PortfolioLiquidityHistory),
    ResetTarget("portfolio_liquidity_buckets", models.PortfolioLiquidityBucket),
    ResetTarget("portfolio_liquidity_snapshots", models.PortfolioLiquiditySnapshot),
    ResetTarget("portfolio_recommendation_evidence", models.PortfolioRecommendationEvidence),
    ResetTarget("portfolio_recommendation_history", models.PortfolioRecommendationHistory),
    ResetTarget("portfolio_recommendation_scenarios", models.PortfolioRecommendationScenario),
    ResetTarget("portfolio_recommendations", models.PortfolioRecommendation),
    ResetTarget("acquisition_priority_evidence", models.AcquisitionPriorityEvidence),
    ResetTarget("acquisition_priority_history", models.AcquisitionPriorityHistory),
    ResetTarget("acquisition_priority_scenarios", models.AcquisitionPriorityScenario),
    ResetTarget("acquisition_priority_snapshots", models.AcquisitionPrioritySnapshot),
    ResetTarget("concentration_risk_evidence", models.ConcentrationRiskEvidence),
    ResetTarget("concentration_risk_history", models.ConcentrationRiskHistory),
    ResetTarget("concentration_risk_factors", models.ConcentrationRiskFactor),
    ResetTarget("concentration_risk_snapshots", models.ConcentrationRiskSnapshot),
    ResetTarget("portfolio_market_coupling_evidence", models.PortfolioMarketCouplingEvidence),
    ResetTarget("portfolio_market_coupling_history", models.PortfolioMarketCouplingHistory),
    ResetTarget("portfolio_market_coupling_edges", models.PortfolioMarketCouplingEdge),
    ResetTarget("portfolio_market_coupling_snapshots", models.PortfolioMarketCouplingSnapshot),
    ResetTarget("market_acquisition_opportunity_evidence", models.MarketAcquisitionOpportunityEvidence),
    ResetTarget("market_acquisition_opportunity_history", models.MarketAcquisitionOpportunityHistory),
    ResetTarget("market_acquisition_opportunity_items", models.MarketAcquisitionOpportunityItem),
    ResetTarget("market_acquisition_opportunity_snapshots", models.MarketAcquisitionOpportunitySnapshot),
    ResetTarget("market_acquisition_signal_evidence", models.MarketAcquisitionSignalEvidence),
    ResetTarget("market_acquisition_signal_history", models.MarketAcquisitionSignalHistory),
    ResetTarget("market_acquisition_signals", models.MarketAcquisitionSignal),
    ResetTarget("market_acquisition_signal_snapshots", models.MarketAcquisitionSignalSnapshot),
    ResetTarget("market_acquisition_score_evidence", models.MarketAcquisitionScoreEvidence),
    ResetTarget("market_acquisition_score_history", models.MarketAcquisitionScoreHistory),
    ResetTarget("market_acquisition_scores", models.MarketAcquisitionScore),
    ResetTarget("market_acquisition_score_snapshots", models.MarketAcquisitionScoreSnapshot),
    ResetTarget("market_acquisition_normalization_events", models.MarketAcquisitionNormalizationEvent),
    ResetTarget("market_acquisition_normalization_issues", models.MarketAcquisitionNormalizationIssue),
    ResetTarget("market_acquisition_normalized_candidates", models.MarketAcquisitionNormalizedCandidate),
    ResetTarget("market_acquisition_normalization_runs", models.MarketAcquisitionNormalizationRun),
    ResetTarget("market_acquisition_ingestion_events", models.MarketAcquisitionIngestionEvent),
    ResetTarget("market_acquisition_raw_sources", models.MarketAcquisitionRawSource),
    ResetTarget("market_acquisition_candidates", models.MarketAcquisitionCandidate),
    ResetTarget("market_acquisition_ingestion_batches", models.MarketAcquisitionIngestionBatch),
    ResetTarget("market_source_import_run_events", models.MarketSourceImportRunEvent),
    ResetTarget("market_source_import_runs", models.MarketSourceImportRun),
    ResetTarget("market_sale_record_images", models.MarketSaleRecordImage),
    ResetTarget("market_sale_review_actions", models.MarketSaleReviewAction),
    ResetTarget("market_sale_normalization_issues", models.MarketSaleNormalizationIssue),
    ResetTarget("market_sale_match_suggestions", models.MarketSaleMatchSuggestion),
    ResetTarget("market_sale_records", models.MarketSaleRecord),
    ResetTarget("market_fmv_comp_references", models.MarketFmvCompReference),
    ResetTarget("market_fmv_snapshots", models.MarketFmvSnapshot),
    ResetTarget("market_trend_evidence", models.MarketTrendEvidence),
    ResetTarget("market_trend_snapshots", models.MarketTrendSnapshot),
    ResetTarget("market_source_snapshots", models.MarketSourceSnapshot),
    ResetTarget("market_sources", models.MarketSource),
    ResetTarget("market_feed_events", models.MarketIntelligenceFeedEvent),
    ResetTarget("market_feed_history", models.MarketIntelligenceFeedHistory),
    ResetTarget("market_feed_cursors", models.MarketIntelligenceFeedCursor),
    ResetTarget("market_feed_snapshots", models.MarketIntelligenceFeedSnapshot),
    # Grading / sales / conventions / liquidity
    ResetTarget("grading_candidate_evidence", models.GradingCandidateEvidence),
    ResetTarget("grading_candidate_lifecycle_events", models.GradingCandidateLifecycleEvent),
    ResetTarget("grading_candidate_snapshots", models.GradingCandidateSnapshot),
    ResetTarget("grading_candidates", models.GradingCandidate),
    ResetTarget("grading_spread_evidence", models.GradingSpreadEvidence),
    ResetTarget("grading_spread_history", models.GradingSpreadHistory),
    ResetTarget("grading_spread_bands", models.GradingSpreadBand),
    ResetTarget("grading_spread_snapshots", models.GradingSpreadSnapshot),
    ResetTarget("grading_roi_evidence", models.GradingRoiEvidence),
    ResetTarget("grading_roi_history", models.GradingRoiHistory),
    ResetTarget("grading_roi_scenarios", models.GradingRoiScenario),
    ResetTarget("grading_roi_snapshots", models.GradingRoiSnapshot),
    ResetTarget("grading_submission_items", models.GradingSubmissionItem),
    ResetTarget("grading_submission_shipments", models.GradingSubmissionShipment),
    ResetTarget("grading_submission_lifecycle_events", models.GradingSubmissionLifecycleEvent),
    ResetTarget("grading_submission_cost_snapshots", models.GradingSubmissionCostSnapshot),
    ResetTarget("grading_submission_batches", models.GradingSubmissionBatch),
    ResetTarget("grading_reconciliation_evidence", models.GradingReconciliationEvidence),
    ResetTarget("grading_reconciliation_history", models.GradingReconciliationHistory),
    ResetTarget("grading_reconciliation_records", models.GradingReconciliationRecord),
    ResetTarget("grader_performance_snapshots", models.GraderPerformanceSnapshot),
    ResetTarget("grading_recommendation_evidence", models.GradingRecommendationEvidence),
    ResetTarget("grading_recommendation_history", models.GradingRecommendationHistory),
    ResetTarget("grading_recommendation_scenarios", models.GradingRecommendationScenario),
    ResetTarget("grading_recommendations", models.GradingRecommendation),
    ResetTarget("grading_risk_evidence", models.GradingRiskEvidence),
    ResetTarget("risk_history", models.RiskHistory),
    ResetTarget("confidence_factor_snapshots", models.ConfidenceFactorSnapshot),
    ResetTarget("grading_risk_snapshots", models.GradingRiskSnapshot),
    ResetTarget("inventory_liquidity_evidence", models.InventoryLiquidityEvidence),
    ResetTarget("listing_staleness_events", models.ListingStalenessEvent),
    ResetTarget("listing_velocity_snapshots", models.ListingVelocitySnapshot),
    ResetTarget("sale_financial_adjustments", models.SaleFinancialAdjustment),
    ResetTarget("sale_lifecycle_events", models.SaleLifecycleEvent),
    ResetTarget("sale_record_line_items", models.SaleRecordLineItem),
    ResetTarget("sale_records", models.SaleRecord),
    ResetTarget("convention_inventory_movements", models.ConventionInventoryMovement),
    ResetTarget("convention_inventory_assignments", models.ConventionInventoryAssignment),
    ResetTarget("convention_price_snapshots", models.ConventionPriceSnapshot),
    ResetTarget("convention_sale_sessions", models.ConventionSaleSession),
    ResetTarget("convention_events", models.ConventionEvent),
    # Scan / OCR / cover / replay pipelines
    ResetTarget("scan_replay_steps", models.ScanReplayStep),
    ResetTarget("scan_replay_checks", models.ScanReplayCheck),
    ResetTarget("scan_replay_discrepancies", models.ScanReplayDiscrepancy),
    ResetTarget("scan_replay_artifacts", models.ScanReplayArtifact),
    ResetTarget("scan_replay_issues", models.ScanReplayIssue),
    ResetTarget("scan_replay_history", models.ScanReplayHistory),
    ResetTarget("scan_replay_runs", models.ScanReplayRun),
    ResetTarget("scan_intelligence_feed_artifacts", models.ScanIntelligenceFeedArtifact),
    ResetTarget("scan_intelligence_feed_events", models.ScanIntelligenceFeedEvent),
    ResetTarget("scan_intelligence_feed_history", models.ScanIntelligenceFeedHistory),
    ResetTarget("scan_intelligence_feed_issues", models.ScanIntelligenceFeedIssue),
    ResetTarget("scan_intelligence_feed_runs", models.ScanIntelligenceFeedRun),
    ResetTarget("scan_authentication_artifacts", models.ScanAuthenticationArtifact),
    ResetTarget("scan_authentication_findings", models.ScanAuthenticationFinding),
    ResetTarget("scan_authentication_signals", models.ScanAuthenticationSignal),
    ResetTarget("scan_authentication_history", models.ScanAuthenticationHistory),
    ResetTarget("scan_authentication_issues", models.ScanAuthenticationIssue),
    ResetTarget("scan_authentication_runs", models.ScanAuthenticationRun),
    ResetTarget("scan_historical_comparison_artifacts", models.ScanHistoricalComparisonArtifact),
    ResetTarget("scan_historical_comparison_deltas", models.ScanHistoricalComparisonDelta),
    ResetTarget("scan_historical_comparison_pairs", models.ScanHistoricalComparisonPair),
    ResetTarget("scan_historical_comparison_history", models.ScanHistoricalComparisonHistory),
    ResetTarget("scan_historical_comparison_issues", models.ScanHistoricalComparisonIssue),
    ResetTarget("scan_historical_comparison_runs", models.ScanHistoricalComparisonRun),
    ResetTarget("scan_review_notes", models.ScanReviewNote),
    ResetTarget("scan_review_decisions", models.ScanReviewDecision),
    ResetTarget("scan_review_evidence_actions", models.ScanReviewEvidenceAction),
    ResetTarget("scan_review_artifacts", models.ScanReviewArtifact),
    ResetTarget("scan_review_history", models.ScanReviewHistory),
    ResetTarget("scan_review_issues", models.ScanReviewIssue),
    ResetTarget("scan_review_sessions", models.ScanReviewSession),
    ResetTarget("scan_visual_evidence_annotations", models.ScanVisualEvidenceAnnotation),
    ResetTarget("scan_visual_evidence_artifacts", models.ScanVisualEvidenceArtifact),
    ResetTarget("scan_visual_evidence_items", models.ScanVisualEvidenceItem),
    ResetTarget("scan_visual_evidence_history", models.ScanVisualEvidenceHistory),
    ResetTarget("scan_visual_evidence_issues", models.ScanVisualEvidenceIssue),
    ResetTarget("scan_visual_evidence_packages", models.ScanVisualEvidencePackage),
    ResetTarget("scan_visual_evidence_runs", models.ScanVisualEvidenceRun),
    ResetTarget("scan_grading_assistance_findings", models.ScanGradingAssistanceFinding),
    ResetTarget("scan_grading_assistance_categories", models.ScanGradingAssistanceCategory),
    ResetTarget("scan_grading_assistance_artifacts", models.ScanGradingAssistanceArtifact),
    ResetTarget("scan_grading_assistance_history", models.ScanGradingAssistanceHistory),
    ResetTarget("scan_grading_assistance_issues", models.ScanGradingAssistanceIssue),
    ResetTarget("scan_grading_assistance_runs", models.ScanGradingAssistanceRun),
    ResetTarget("scan_defect_aggregate_clusters", models.ScanDefectAggregateCluster),
    ResetTarget("scan_defect_aggregation_evidence", models.ScanDefectAggregateEvidence),
    ResetTarget("scan_defect_aggregation_artifacts", models.ScanDefectAggregationArtifact),
    ResetTarget("scan_defect_aggregation_history", models.ScanDefectAggregationHistory),
    ResetTarget("scan_defect_aggregation_issues", models.ScanDefectAggregationIssue),
    ResetTarget("scan_defect_aggregation_runs", models.ScanDefectAggregationRun),
    ResetTarget("scan_structural_damage_evidence", models.ScanStructuralDamageEvidence),
    ResetTarget("scan_structural_damage_artifacts", models.ScanStructuralDamageArtifact),
    ResetTarget("scan_structural_damage_history", models.ScanStructuralDamageHistory),
    ResetTarget("scan_structural_damage_issues", models.ScanStructuralDamageIssue),
    ResetTarget("scan_structural_damage_runs", models.ScanStructuralDamageRun),
    ResetTarget("scan_surface_defect_evidence", models.ScanSurfaceDefectEvidence),
    ResetTarget("scan_surface_defect_artifacts", models.ScanSurfaceDefectArtifact),
    ResetTarget("scan_surface_defect_history", models.ScanSurfaceDefectHistory),
    ResetTarget("scan_surface_defect_issues", models.ScanSurfaceDefectIssue),
    ResetTarget("scan_surface_defect_runs", models.ScanSurfaceDefectRun),
    ResetTarget("scan_corner_edge_evidence", models.ScanCornerEdgeEvidence),
    ResetTarget("scan_corner_edge_artifacts", models.ScanCornerEdgeArtifact),
    ResetTarget("scan_corner_edge_history", models.ScanCornerEdgeHistory),
    ResetTarget("scan_corner_edge_issues", models.ScanCornerEdgeIssue),
    ResetTarget("scan_corner_edge_runs", models.ScanCornerEdgeRun),
    ResetTarget("scan_spine_tick_evidence", models.ScanSpineTickEvidence),
    ResetTarget("scan_spine_tick_artifacts", models.ScanSpineTickArtifact),
    ResetTarget("scan_spine_tick_history", models.ScanSpineTickHistory),
    ResetTarget("scan_spine_tick_issues", models.ScanSpineTickIssue),
    ResetTarget("scan_spine_tick_runs", models.ScanSpineTickRun),
    ResetTarget("scan_defect_evidence", models.ScanDefectEvidence),
    ResetTarget("scan_defect_regions", models.ScanDefectRegion),
    ResetTarget("scan_defect_artifacts", models.ScanDefectArtifact),
    ResetTarget("scan_defect_history", models.ScanDefectHistory),
    ResetTarget("scan_defect_issues", models.ScanDefectIssue),
    ResetTarget("scan_defect_runs", models.ScanDefectRun),
    ResetTarget("scan_reconciliation_artifacts", models.ScanReconciliationArtifact),
    ResetTarget("scan_reconciliation_decisions", models.ScanReconciliationDecision),
    ResetTarget("scan_reconciliation_candidates", models.ScanReconciliationCandidate),
    ResetTarget("scan_reconciliation_history", models.ScanReconciliationHistory),
    ResetTarget("scan_reconciliation_issues", models.ScanReconciliationIssue),
    ResetTarget("scan_reconciliation_runs", models.ScanReconciliationRun),
    ResetTarget("scan_ocr_text_regions", models.ScanOcrTextRegion),
    ResetTarget("scan_ocr_candidates", models.ScanOcrCandidate),
    ResetTarget("scan_ocr_artifacts", models.ScanOcrArtifact),
    ResetTarget("scan_ocr_history", models.ScanOcrHistory),
    ResetTarget("scan_ocr_issues", models.ScanOcrIssue),
    ResetTarget("scan_ocr_runs", models.ScanOcrRun),
    ResetTarget("scan_boundary_artifacts", models.ScanBoundaryArtifact),
    ResetTarget("scan_boundary_history", models.ScanBoundaryHistory),
    ResetTarget("scan_boundary_issues", models.ScanBoundaryIssue),
    ResetTarget("scan_boundary_runs", models.ScanBoundaryRun),
    ResetTarget("scan_normalization_artifacts", models.ScanNormalizationArtifact),
    ResetTarget("scan_normalization_history", models.ScanNormalizationHistory),
    ResetTarget("scan_normalization_issues", models.ScanNormalizationIssue),
    ResetTarget("scan_normalization_runs", models.ScanNormalizationRun),
    ResetTarget("scan_ingestion_events", models.ScanIngestionEvent),
    ResetTarget("scan_image_variants", models.ScanImageVariant),
    ResetTarget("scan_images", models.ScanImage),
    ResetTarget("scan_ingestion_batches", models.ScanIngestionBatch),
    ResetTarget("scan_upload_sessions", models.ScanUploadSession),
    ResetTarget("scan_session_items", models.ScanSessionItem),
    ResetTarget("scan_sessions", models.ScanSession),
    ResetTarget("scanner_profiles", models.ScannerProfile),
    ResetTarget("ocr_batch_items", models.OcrBatchItem),
    ResetTarget("ocr_batches", models.OcrBatch),
    ResetTarget("ocr_replay_items", models.OcrReplayItem),
    ResetTarget("ocr_replay_runs", models.OcrReplayRun),
    ResetTarget("relationship_replay_items", models.RelationshipReplayItem),
    ResetTarget("relationship_replay_runs", models.RelationshipReplayRun),
    ResetTarget("cover_relationship_conflicts", models.CoverRelationshipConflict),
    ResetTarget("canonical_issue_link_suggestions", models.CanonicalIssueLinkSuggestion),
    ResetTarget("duplicate_candidate_reviews", models.DuplicateCandidateReview),
    ResetTarget("cover_image_link_decisions", models.CoverImageLinkDecision),
    ResetTarget("cover_image_match_candidates", models.CoverImageMatchCandidate),
    ResetTarget("cover_image_ocr_candidates", models.CoverImageOcrCandidate),
    ResetTarget("cover_image_ocr_quality_analysis", models.CoverImageOcrQualityAnalysis),
    ResetTarget("cover_image_ocr_reconciliation_warnings", models.CoverImageOcrReconciliationWarning),
    ResetTarget("cover_image_ocr_regions", models.CoverImageOcrRegion),
    ResetTarget("cover_image_ocr_results", models.CoverImageOcrResult),
    ResetTarget("cover_image_barcode_candidates", models.CoverImageBarcodeCandidate),
    ResetTarget("cover_image_fingerprints", models.CoverImageFingerprint),
    ResetTarget("cover_image_derivatives", models.CoverImageDerivative),
    ResetTarget("cover_images", models.CoverImage),
    ResetTarget("high_res_review_requests", models.HighResReviewRequest),
    # Orders / imports / inventory / gmail
    ResetTarget("gmail_import_records", models.GmailImportRecord),
    ResetTarget("gmail_accounts", models.GmailAccount),
    ResetTarget("ops_events", models.OpsEvent),
    ResetTarget("draft_imports", models.DraftImport),
    ResetTarget("order_items", models.OrderItem),
    ResetTarget("customer_orders", models.Order),
    ResetTarget("inventory_fmv_snapshots", models.InventoryFmvSnapshot),
    ResetTarget("inventory_copies", models.InventoryCopy),
    # Automation engines
    ResetTarget("automation_job_artifacts", models.AutomationJobArtifact),
    ResetTarget("automation_job_issues", models.AutomationJobIssue),
    ResetTarget("automation_job_history", models.AutomationJobHistory),
    ResetTarget("automation_job_attempts", models.AutomationJobAttempt),
    ResetTarget("automation_job_dependencies", models.AutomationJobDependency),
    ResetTarget("automation_jobs", models.AutomationJob),
    ResetTarget("automation_queues", models.AutomationQueue),
    ResetTarget("automation_worker_heartbeats", models.AutomationWorkerHeartbeat),
    ResetTarget("automation_worker_leases", models.AutomationWorkerLease),
    ResetTarget("automation_worker_executions", models.AutomationWorkerExecution),
    ResetTarget("automation_worker_issues", models.AutomationWorkerIssue),
    ResetTarget("automation_worker_history", models.AutomationWorkerHistory),
    ResetTarget("automation_workers", models.AutomationWorker),
    ResetTarget("automation_workflow_steps", models.AutomationWorkflowStep),
    ResetTarget("automation_workflow_executions", models.AutomationWorkflowExecution),
    ResetTarget("automation_workflow_issues", models.AutomationWorkflowIssue),
    ResetTarget("automation_workflow_history", models.AutomationWorkflowHistory),
    ResetTarget("automation_workflows", models.AutomationWorkflow),
    ResetTarget("automation_triggers", models.AutomationTrigger),
    ResetTarget("automation_schedules", models.AutomationSchedule),
    ResetTarget("automation_dead_letter_jobs", models.AutomationDeadLetterJob),
    ResetTarget("automation_failure_events", models.AutomationFailureEvent),
    ResetTarget("automation_recovery_artifacts", models.AutomationRecoveryArtifact),
    ResetTarget("automation_recovery_issues", models.AutomationRecoveryIssue),
    ResetTarget("automation_recovery_history", models.AutomationRecoveryHistory),
    ResetTarget("automation_retry_policies", models.AutomationRetryPolicy),
    ResetTarget("automation_recovery_runs", models.AutomationRecoveryRun),
    ResetTarget("automation_batch_chunks", models.AutomationBatchChunk),
    ResetTarget("automation_maintenance_jobs", models.AutomationMaintenanceJob),
    ResetTarget("automation_maintenance_results", models.AutomationMaintenanceResult),
    ResetTarget("automation_batch_artifacts", models.AutomationBatchArtifact),
    ResetTarget("automation_batch_issues", models.AutomationBatchIssue),
    ResetTarget("automation_batch_history", models.AutomationBatchHistory),
    ResetTarget("automation_batch_runs", models.AutomationBatchRun),
    ResetTarget("automation_notification_deliveries", models.AutomationNotificationDelivery),
    ResetTarget("automation_notifications", models.AutomationNotification),
    ResetTarget("automation_notification_preferences", models.AutomationNotificationPreference),
    ResetTarget("automation_notification_templates", models.AutomationNotificationTemplate),
    ResetTarget("automation_alerts", models.AutomationAlert),
    ResetTarget("automation_notification_issues", models.AutomationNotificationIssue),
    ResetTarget("automation_notification_history", models.AutomationNotificationHistory),
    ResetTarget("automation_ops_audits", models.AutomationOpsAudit),
    ResetTarget("automation_ops_controls", models.AutomationOpsControl),
    ResetTarget("automation_ops_artifacts", models.AutomationOpsArtifact),
    ResetTarget("automation_ops_issues", models.AutomationOpsIssue),
    ResetTarget("automation_ops_history", models.AutomationOpsHistory),
    ResetTarget("automation_ops_metrics", models.AutomationOpsMetric),
    ResetTarget("automation_ops_snapshots", models.AutomationOpsSnapshot),
    ResetTarget("automation_rule_actions", models.AutomationRuleAction),
    ResetTarget("automation_rule_evaluations", models.AutomationRuleEvaluation),
    ResetTarget("automation_rule_artifacts", models.AutomationRuleArtifact),
    ResetTarget("automation_rule_issues", models.AutomationRuleIssue),
    ResetTarget("automation_rule_history", models.AutomationRuleHistory),
    ResetTarget("automation_rule_versions", models.AutomationRuleVersion),
    ResetTarget("automation_rules", models.AutomationRule),
    ResetTarget("automation_analytics_trends", models.AutomationAnalyticsTrend),
    ResetTarget("automation_analytics_comparisons", models.AutomationAnalyticsComparison),
    ResetTarget("automation_analytics_artifacts", models.AutomationAnalyticsArtifact),
    ResetTarget("automation_analytics_issues", models.AutomationAnalyticsIssue),
    ResetTarget("automation_analytics_history", models.AutomationAnalyticsHistory),
    ResetTarget("automation_analytics_metrics", models.AutomationAnalyticsMetric),
    ResetTarget("automation_analytics_snapshots", models.AutomationAnalyticsSnapshot),
    # Finally, users and organization roots
    ResetTarget("organizations", models.Organization),
    ResetTarget("users", models.User),
)

RELATIVE_ORDER_CONSTRAINTS: tuple[tuple[str, str], ...] = (
    ("automation_rule_versions", "automation_rules"),
    ("cover_images", "draft_imports"),
    ("cover_images", "inventory_copies"),
    ("inventory_copies", "order_items"),
    ("draft_imports", "customer_orders"),
    ("inventory_fmv_snapshots", "inventory_copies"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset ComicOS application data rows without dropping schema objects.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the destructive reset. Without this flag the script only reports counts.",
    )
    return parser.parse_args()


def resolved_database_url() -> str:
    settings = get_settings()
    database_url = (settings.database_url or "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is missing. Refusing to continue.")
    return database_url


def ordered_reset_targets() -> list[ResetTarget]:
    table_by_name = {target.model.__table__.name: target for target in RESET_TARGETS}
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Cannot correctly sort tables;.*",
        )
        sorted_allowed_tables = sort_tables([target.model.__table__ for target in RESET_TARGETS])
    ordered = [table_by_name[table.name] for table in reversed(sorted_allowed_tables) if table.name in table_by_name]
    by_label = {target.label: target for target in ordered}
    for move_label, before_label in RELATIVE_ORDER_CONSTRAINTS:
        move_target = by_label[move_label]
        before_target = by_label[before_label]
        ordered.remove(move_target)
        before_index = ordered.index(before_target)
        ordered.insert(before_index, move_target)
    if len(ordered) != len(RESET_TARGETS):
        missing = sorted({target.model.__table__.name for target in RESET_TARGETS} - {target.model.__table__.name for target in ordered})
        raise RuntimeError(f"Reset target ordering mismatch: {missing}")
    return ordered


def row_count(connection, target: ResetTarget) -> int:
    return int(connection.execute(select(func.count()).select_from(target.model.__table__)).scalar_one())


def break_delete_cycles(connection) -> None:
    connection.execute(update(models.AutomationRule.__table__).values(current_version_id=None))
    connection.execute(update(models.InventoryCopy.__table__).values(primary_cover_image_id=None))
    connection.execute(update(models.DraftImport.__table__).values(primary_cover_image_id=None))


def main() -> int:
    args = parse_args()
    database_url = resolved_database_url()
    engine = get_engine()
    ordered_targets = ordered_reset_targets()

    print(f"ComicOS app-data reset {'EXECUTE' if args.execute else 'DRY RUN'}")
    print(f"Database: {database_url}")
    print("Never touched: alembic_version, schema definitions, migration files, source files")
    print()

    with engine.connect() as connection:
        counts = [(target, row_count(connection, target)) for target in ordered_targets]

    total_rows = sum(count for _, count in counts)
    print("Affected tables:")
    for target, count in counts:
        print(f"  - {target.label}: {count}")
    print(f"Total rows across allowlist: {total_rows}")
    print()

    if not args.execute:
        print("Dry run only. Re-run with --execute to delete rows.")
        return 0

    deleted_total = 0
    with engine.begin() as connection:
        break_delete_cycles(connection)
        for target, expected_count in counts:
            result = connection.execute(delete(target.model.__table__))
            deleted = int(result.rowcount or 0)
            deleted_total += deleted
            print(f"deleted {target.label}: {deleted} rows (expected {expected_count})")

    print()
    print(f"Reset complete. Deleted {deleted_total} rows from {len(counts)} allowlisted tables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
