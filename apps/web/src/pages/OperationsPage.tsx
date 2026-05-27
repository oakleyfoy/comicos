import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  resolveCoverImageOcrHeadline,
  type CoverMatchConfidenceBucket,
  type CoverImageOcrHeadlineStatus,
  type CoverOcrQualitySeverity,
  type CoverOcrQualityType,
  type CoverImageSourceType,
  type DuplicateCandidateReviewDecisionPayload,
  type InventoryDuplicatesReviewFilter,
  type InventoryIntelligenceBreakdownResponse,
  type InventoryIntelligenceHealthRollup,
  type InventoryIntelligenceRollupSummary,
  type CollectionAnalyticsSummary,
  type CollectionCompositionResponse,
  type CollectionPublisherAnalyticsResponse,
  type CollectionQualityAnalyticsResponse,
  type CollectionTimelineResponse,
  type InventoryRiskListResponse,
  type InventoryActionCenterCategory,
  type InventoryActionCenterItem,
  type InventoryActionCenterListResponse,
  type InventoryRiskPriority,
  type InventoryRiskRead,
  type InventoryRiskType,
  type InventoryResponse,
  type MetadataAlias,
  type MetadataAliasType,
  type OcrBatch,
  type OcrReplayRun,
  type OcrReplayType,
  type OpsScanQaFleetSummaryRead,
  type RelationshipReplayRun,
  type RelationshipReplayType,
  type OpsCanonicalCreatorRow,
  type OpsCanonicalSeriesRow,
  type OpsDashboardResponse,
  type QueueRoutingListResponse,
  type OpsInventoryDuplicateCandidateGroup,
  type OpsMetadataAuditRow,
  type OpsRecentCoverImageRow,
  type OpsCoverDuplicateGroup,
  type OrderArrivalClassification,
  type OrderArrivalIntelCalendarResponse,
  type OrderArrivalIntelListResponse,
  type CoverRelationshipGraphEdge,
  type CoverRelationshipGraphRead,
  type DuplicateScanClassificationFilter,
  type DuplicateScanClustersListResponse,
  type DuplicateOwnershipClassification,
  type DuplicateOwnershipGroup,
  type DuplicateOwnershipListResponse,
  type MissingIssueClassification,
  type CanonicalIssueSuggestionConfidenceBucket,
  type CanonicalIssueSuggestionOpsListResponse,
  type CanonicalIssueSuggestionReviewState,
  type CanonicalIssueSuggestionType,
  type HighResReviewRequestPriority,
  type HighResReviewRequestReason,
  type HighResReviewRequestStatsRead,
  type HighResReviewRequestStatus,
  type MarketSaleRead,
  type MarketSaleMatchSuggestionConfidenceBucket,
  type MarketSaleMatchSuggestionOpsListResponse,
  type MarketSaleMatchSuggestionRead,
  type MarketSaleMatchSuggestionReviewState,
  type MarketSaleMatchSuggestionType,
  type MarketSaleNormalizationUpdatePayload,
  type MarketSaleReviewActionPayload,
  type MarketSaleReviewClassification,
  type MarketSaleReviewPriority,
  type MarketSaleReviewQueueResponse,
  type MarketSaleReviewQueueSummaryRead,
  type MarketSaleReviewStatus,
  type MarketCompEligibilityClassification,
  type MarketSaleCompEligibilityListResponse,
  type MarketSaleCompEligibilityRead,
  type MarketCompEligibilityStatus,
  type MarketComparableListResponse,
  type MarketFmvConfidenceBucket,
  type MarketFmvGenerateResponse,
  type MarketFmvLiquidityBucket,
  type MarketFmvSnapshotListResponse,
  type MarketFmvSnapshotRead,
  type MarketFmvSnapshotScope,
  type MarketTrendDirection,
  type MarketTrendGenerateResponse,
  type MarketTrendLiquidityDirection,
  type MarketTrendSnapshotListResponse,
  type MarketTrendSnapshotRead,
  type MarketTrendSnapshotScope,
  type MarketTrendStrength,
  type MarketTrendWindow,
  type MarketSaleSummaryRead,
  type MarketAcquisitionIngestionBatchListResponse,
  type MarketAcquisitionIngestionBatchRead,
  type MarketAcquisitionRawSourceRead,
  type MarketAcquisitionNormalizedCandidateRead,
  type MarketAcquisitionScoreDetailRead,
  type MarketAcquisitionScoreHistoryRead,
  type MarketAcquisitionScoreRead,
  type MarketAcquisitionScoreSnapshotListResponse,
  type MarketAcquisitionSignalDetailRead,
  type MarketAcquisitionSignalEvidenceRead,
  type MarketAcquisitionSignalHistoryRead,
  type MarketAcquisitionSignalRead,
  type MarketAcquisitionSignalSnapshotListResponse,
  type MarketAcquisitionOpportunityDetailRead,
  type MarketAcquisitionOpportunityEvidenceRead,
  type MarketAcquisitionOpportunityHistoryRead,
  type MarketAcquisitionOpportunityItemRead,
  type MarketAcquisitionOpportunitySnapshotListResponse,
  type MarketDeterminismInvariantRead,
  type MarketDeterminismReplayAuditRead,
  type MarketDeterminismValidationRunListResponse,
  type PortfolioMarketCouplingSnapshotListResponse,
  type PortfolioMarketCouplingDetailRead,
  type PortfolioMarketCouplingEdgeRead,
  type PortfolioMarketCouplingHistoryRead,
  type MarketNormalizationIssueRead,
  type MarketNormalizationRunDetailRead,
  type MarketNormalizationRunListResponse,
  type HighResReviewRequestSummary,
  type RelationshipConflictDetectResponse,
  type RelationshipConflictListResponse,
  type RelationshipConflictSeverity,
  type RelationshipConflictStatus,
  type RelationshipConflictType,
  type RunDetectionListResponse,
  type RunDetectionSeries,
  type RunDetectionSeriesStatus,
  type ScanPipelineReplayRunRead,
  type ScanPipelineDashboardResponse,
  type ScanSessionDetail,
  type ScanSessionSummary,
  type PortfolioAllocationSnapshotListResponse,
  type PortfolioExposureEvidenceListResponse,
  type PortfolioExposureSnapshotListResponse,
  type PortfolioItemListResponse,
  type PortfolioListResponse,
  type DuplicateClusterItemListResponse,
  type DuplicateClusterListResponse,
  type DuplicateConsolidationRecommendationListResponse,
  type DuplicateHistoryListResponse,
  type PortfolioLiquidityEvidenceListResponse,
  type PortfolioLiquidityHistoryListResponse,
  type PortfolioLiquiditySnapshotDetailResponse,
  type PortfolioLiquiditySnapshotListResponse,
  type PortfolioRecommendationDetailRead,
  type PortfolioRecommendationEvidenceListResponse,
  type PortfolioRecommendationHistoryListResponse,
  type PortfolioRecommendationListResponse,
  type AcquisitionPriorityDetailRead,
  type AcquisitionPriorityEvidenceListResponse,
  type AcquisitionPriorityHistoryListResponse,
  type AcquisitionPriorityListResponse,
  type ConcentrationRiskDetailRead,
  type ConcentrationRiskEvidenceListResponse,
  type ConcentrationRiskFactorListResponse,
  type ConcentrationRiskHistoryListResponse,
  type ConcentrationRiskListResponse,
  type PortfolioValueSummaryResponse,
  type VariantFamilyClassificationFilter,
  type VariantFamilyClustersListResponse,
  type CollectionHistoricalTimelineEventKind,
  type CollectionHistoricalTimelineEventsResponse,
  type CollectionHistoricalTimelineGrouping,
  type CollectionHistoricalTimelineSort,
  type InventoryItem,
  type InventoryOwnershipNormalized,
  type PhysicalIntakeItemRead,
  type PhysicalIntakeListResponse,
  type PhysicalIntakeState,
  type PhysicalIntakeSummaryResponse,
  type InventoryLiquidityEvidenceRead,
  type InventoryLiquidityListResponse,
  type InventoryLiquiditySnapshotRead,
  type ConventionDashboardSummary,
  type ConventionEventListResponse,
  type ConventionAssignmentListResponse,
  type ConventionMovementListResponse,
  type ConventionPriceSnapshotListResponse,
  type ConventionSaleSessionListResponse,
  type LiquidityDashboardSummary,
  type ListingIntelligenceDashboardSummary,
  type ListingIntelligenceSnapshotRead,
  type ListingIntelligenceEvidenceRead,
  type ListingCompletenessCheckRead,
  type ListingChannelPerformanceSnapshotRead,
  type ListingStalenessEventListResponse,
  type ListingStalenessEventRead,
  type ListingVelocityListResponse,
  type ListingVelocitySnapshotRead,
  type ListingOpsStatusDistribution,
  type OpsListingLifecycleEventListResponse,
  type ListingExportRunListResponse,
  type OperationalReportRunListResponse,
  type GradingOperationalReportRunListResponse,
  type GradingCandidateListResponse,
  type GradingRecommendationListResponse,
  type GradingRiskListResponse,
  type GradingReconciliationListResponse,
  type GradingSpreadListResponse,
  type GradingRoiListResponse,
  type GradingSubmissionListResponse,
  type DealerDashboardAlertRead,
  type DealerDashboardFeedEventRead,
  type DealerDashboardGetResponse,
  type DealerDashboardMetricRead,
  type PortfolioStrategyDashboardAlertRead,
  type PortfolioStrategyDashboardFeedEventRead,
  type PortfolioStrategyDashboardGetResponse,
  type PortfolioStrategyDashboardMetricRead,
  type DealerGradingDashboardAlertRead,
  type DealerGradingDashboardFeedEventRead,
  type DealerGradingDashboardGetResponse,
  type DealerGradingDashboardMetricRead,
  type SaleRecordRead,
} from "../api/client";
import { describeHistoricalTimelineEvent, timelineDotClass } from "../lib/collectionHistoricalTimelineUi";
import { AppShell } from "../components/AppShell";
import { LoadingState } from "../components/LoadingState";
import { MarketIntelligenceFeedPanel } from "../components/MarketIntelligenceFeedPanel";
import { MarketIntelligenceOpsDiagnostics } from "../components/MarketIntelligenceOpsDiagnostics";
import { OcrReviewWorkspace } from "../components/ocr-review/OcrReviewWorkspace";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function formatCanonicalReleaseCalendar(value: string | null): string {
  if (!value) {
    return "—";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function parseOptionalYear(value: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const year = Number(trimmed);
  if (!Number.isInteger(year) || year < 1800 || year > 2999) {
    return undefined;
  }
  return year;
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function abbrevExportChecksum(value: string | null): string {
  if (!value) {
    return "—";
  }
  if (value.length <= 18) {
    return value;
  }
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}

function determinismTone(status: string): string {
  switch (status) {
    case "PASS":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "WARNING":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "FAIL":
    default:
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
  }
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function formatCurrency(value: string | null): string {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

function formatCurrencyWithCode(value: string | null, currencyCode: string): string {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currencyCode || "USD",
  }).format(amount);
}

function marketSaleStatusTone(status: MarketSaleSummaryRead["normalization_status"]): string {
  switch (status) {
    case "normalized":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "partially_normalized":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "normalization_failed":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "ignored":
      return "border-slate-400/35 bg-slate-400/10 text-slate-100";
    case "raw":
    default:
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
  }
}

function marketSaleIssueTone(severity: string): string {
  switch (severity) {
    case "critical":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "warning":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    default:
      return "border-slate-400/30 bg-white/5 text-slate-200";
  }
}

function marketSaleReviewPriorityTone(priority: MarketSaleReviewPriority): string {
  switch (priority) {
    case "critical":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "high":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "medium":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "low":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "info":
    default:
      return "border-slate-400/35 bg-slate-400/10 text-slate-100";
  }
}

function marketSaleReviewClassificationLabel(classification: MarketSaleReviewClassification): string {
  return classification.replace(/_/g, " ");
}

function marketSaleReviewStatusLabel(status: MarketSaleReviewStatus): string {
  return status.replace(/_/g, " ");
}

function marketCompEligibilityStatusLabel(status: MarketCompEligibilityStatus): string {
  return status.replace(/_/g, " ");
}

function marketCompEligibilityClassificationLabel(classification: MarketCompEligibilityClassification): string {
  return classification.replace(/_/g, " ");
}

function marketCompEligibilityStatusTone(status: MarketCompEligibilityStatus): string {
  switch (status) {
    case "eligible":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "needs_review":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "ineligible":
    default:
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
  }
}

function marketFmvBucketTone(bucket: string): string {
  switch (bucket) {
    case "very_high":
    case "high":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "medium":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "moderate":
    case "low":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "volatile":
    case "very_low":
    default:
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
  }
}

function marketFmvScopeLabel(scope: MarketFmvSnapshotScope): string {
  return scope.replace(/_/g, " ");
}

function marketTrendLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function marketTrendTone(value: string): string {
  switch (value) {
    case "rising":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "stable":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "falling":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "volatile":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    default:
      return "border-white/10 bg-white/5 text-slate-300";
  }
}

function marketSaleMatchSuggestionTone(bucket: MarketSaleMatchSuggestionConfidenceBucket): string {
  switch (bucket) {
    case "very_high":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "high":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "medium":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "low":
      return "border-slate-400/35 bg-slate-400/10 text-slate-100";
    case "very_low":
    default:
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
  }
}

function marketSaleMatchSuggestionLabel(value: MarketSaleMatchSuggestionType | MarketSaleMatchSuggestionReviewState | string): string {
  return value.replace(/_/g, " ");
}

function marketComparableClassificationLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function marketComparableTone(value: string): string {
  switch (value) {
    case "included_comp":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "excluded_stale":
    case "excluded_missing_price":
    case "excluded_unsupported_currency":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "excluded_duplicate":
    case "excluded_wrong_scope":
    case "excluded_wrong_grade":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "excluded_review_required":
    case "excluded_unresolved_identity":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    default:
      return "border-white/10 bg-white/5 text-slate-300";
  }
}

function compQualityTone(value: string): string {
  switch (value) {
    case "fresh":
    case "recent":
    case "high":
    case "consistent":
    case "low":
    case "stable":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "aged":
    case "medium":
    case "moderate":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "stale":
    case "wide":
    case "volatile":
    case "mismatched":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    default:
      return "border-white/10 bg-white/5 text-slate-300";
  }
}

const OPS_HIGH_RES_STATUSES: HighResReviewRequestStatus[] = [
  "pending",
  "scanned",
  "linked",
  "review_complete",
  "cancelled",
];

const OPS_HIGH_RES_PRIORITIES: HighResReviewRequestPriority[] = ["high", "medium", "low"];

const OPS_HIGH_RES_REASONS: HighResReviewRequestReason[] = [
  "low_quality_scan",
  "failed_ocr",
  "poor_match_confidence",
  "valuable_review_candidate",
  "manual_review",
  "rescan_required",
];

const OPS_MARKET_SALE_REVIEW_CLASSIFICATIONS: MarketSaleReviewClassification[] = [
  "needs_title_review",
  "needs_issue_review",
  "needs_variant_review",
  "needs_grade_review",
  "needs_price_review",
  "possible_duplicate",
  "unsupported_currency",
  "ready_for_comp_review",
  "ignored",
];

const OPS_MARKET_SALE_REVIEW_PRIORITIES: MarketSaleReviewPriority[] = [
  "critical",
  "high",
  "medium",
  "low",
  "info",
];

const OPS_MARKET_COMP_ELIGIBILITY_STATUSES: MarketCompEligibilityStatus[] = ["eligible", "needs_review", "ineligible"];

const OPS_MARKET_COMP_ELIGIBILITY_CLASSIFICATIONS: MarketCompEligibilityClassification[] = [
  "eligible_graded_comp",
  "eligible_raw_comp",
  "needs_review_before_comp",
  "ineligible_missing_price",
  "ineligible_unsupported_currency",
  "ineligible_unresolved_identity",
  "ineligible_duplicate_listing",
  "ineligible_ignored_record",
  "ineligible_invalid_grade",
];

const OPS_MARKET_MATCH_SUGGESTION_TYPES: MarketSaleMatchSuggestionType[] = [
  "exact_identity_key",
  "normalized_title_issue_publisher",
  "normalized_title_issue",
  "publisher_series_issue",
  "barcode_supported",
  "inventory_context_supported",
  "unresolved_ambiguous",
];

const OPS_MARKET_FMV_SCOPES: MarketFmvSnapshotScope[] = ["raw", "graded", "graded_by_company", "graded_by_grade"];

type OpsHistoricalTimelineFilters = {
  event_type: "" | CollectionHistoricalTimelineEventKind;
  publisher: string;
  ownership_state: "" | InventoryOwnershipNormalized;
  release_status: "" | InventoryItem["release_status"];
  start_date: string;
  end_date: string;
  preorder_only: boolean;
  in_hand_only: boolean;
  grouping: CollectionHistoricalTimelineGrouping;
  sort: CollectionHistoricalTimelineSort;
};

function defaultOpsHistoricalTimelineFilters(): OpsHistoricalTimelineFilters {
  return {
    event_type: "",
    publisher: "",
    ownership_state: "",
    release_status: "",
    start_date: "",
    end_date: "",
    preorder_only: false,
    in_hand_only: false,
    grouping: "day",
    sort: "desc",
  };
}

/** Deterministic enumeration for timeline filter selects (aligned with backend event kinds). */
const OPS_COLLECTION_HISTORICAL_EVENT_TYPES: CollectionHistoricalTimelineEventKind[] = [
  "inventory_added",
  "preorder_created",
  "release_day",
  "expected_ship_window",
  "inventory_received",
  "scan_completed",
  "ocr_completed",
  "ocr_failed",
  "relationship_reviewed",
  "canonical_suggestion_reviewed",
  "conflict_detected",
  "conflict_resolved",
  "duplicate_detected",
  "variant_family_detected",
];

function inventoryRiskPriorityTone(priority: InventoryRiskPriority): string {
  switch (priority) {
    case "critical":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "high":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "medium":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "low":
      return "border-violet-400/35 bg-violet-400/10 text-violet-100";
    default:
      return "border-slate-400/30 bg-white/5 text-slate-200";
  }
}

function inventoryRiskLabel(value: InventoryRiskType): string {
  switch (value) {
    case "needs_canonical_review":
      return "Canonical review";
    case "needs_conflict_review":
      return "Conflict review";
    case "needs_scan":
      return "Needs scan";
    case "needs_ocr_retry":
      return "OCR retry";
    case "needs_cover_processing_review":
      return "Cover proc review";
    case "preorder_missing_release_date":
      return "Preorder calendar gap";
    case "released_not_received":
      return "Released / not received";
    case "duplicate_uncertainty":
      return "Duplicate uncertainty";
    case "run_gap_detected":
      return "Run gap";
    case "low_quality_scan":
      return "Low-quality scan";
    case "high_confidence_match_unreviewed":
      return "Unreviewed match";
    default:
      return value;
  }
}

function inventoryRiskEvidenceSummary(risk: InventoryRiskRead): string {
  const entries = Object.entries(risk.evidence_json);
  if (!entries.length) {
    return "No evidence payload";
  }
  return entries
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : String(value)}`)
    .join(" · ");
}

function inventoryActionCenterCategoryUiLabel(cat: InventoryActionCenterCategory): string {
  switch (cat) {
    case "review_relationship_conflict":
      return "Relationship conflict";
    case "review_canonical_suggestion":
      return "Canonical suggestion";
    case "review_duplicate_ownership":
      return "Duplicate ownership";
    case "review_duplicate_scan":
      return "Duplicate scan cluster";
    case "review_variant_family":
      return "Variant family";
    case "retry_ocr":
      return "Retry OCR";
    case "review_cover_processing":
      return "Cover processing";
    case "scan_missing_cover":
      return "Missing cover scan";
    case "update_preorder_metadata":
      return "Preorder metadata";
    case "review_run_gap":
      return "Run gap";
    case "review_high_confidence_match":
      return "High-confidence match";
    default:
      return cat;
  }
}

function inventoryActionEvidenceSummary(action: InventoryActionCenterItem): string {
  if (action.evidence_summary_lines.length) {
    return action.evidence_summary_lines.slice(0, 2).join(" · ");
  }
  const entries = Object.entries(action.evidence_json);
  if (!entries.length) {
    return "No evidence payload";
  }
  return entries
    .slice(0, 2)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : String(value)}`)
    .join(" · ");
}

function opsOrderArrivalTone(value: OrderArrivalClassification): string {
  switch (value) {
    case "overdue_expected_ship":
    case "released_not_received":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "missing_release_date":
    case "missing_expected_ship_date":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "expected_to_ship_soon":
      return "border-violet-400/35 bg-violet-400/10 text-violet-100";
    default:
      return "border-white/15 bg-white/5 text-slate-300";
  }
}

function opsOrderArrivalShortLabel(value: OrderArrivalClassification): string {
  switch (value) {
    case "upcoming_preorder":
      return "Upcoming preorder";
    case "releases_this_week":
      return "Week release";
    case "released_not_received":
      return "Released not recv";
    case "expected_to_ship_soon":
      return "Shipping soon";
    case "overdue_expected_ship":
      return "Shipment overdue";
    case "received_recently":
      return "Recently received";
    case "cancelled_order":
      return "Cancelled";
    case "missing_release_date":
      return "Missing release date";
    case "missing_expected_ship_date":
      return "Missing ship date";
    default:
      return value;
  }
}

function relationshipConflictSeverityTone(severity: RelationshipConflictSeverity): string {
  switch (severity) {
    case "critical":
      return "border-rose-400/30 bg-rose-400/10 text-rose-100";
    case "warning":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    default:
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
  }
}

function formatOpsCoverDimensions(width: number | null, height: number | null): string {
  if (width != null && height != null) {
    return `${width} × ${height} px`;
  }
  return "—";
}

function formatOpsCoverFileSize(bytes: number | null): string {
  if (bytes === null || bytes === undefined) {
    return "—";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(bytes < 10 * 1024 ? 1 : 0)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function shortSha256(hex: string): string {
  if (hex.length <= 16) {
    return hex;
  }
  return `${hex.slice(0, 12)}…`;
}

const MANUAL_COVER_ASSIGN_INFO_OPS =
  "Manual assignment links the existing image record. It does not duplicate or analyze the image.";
const MANUAL_COVER_ASSIGN_MULTI_COPY_OPS =
  "Use this when an import created multiple inventory copies and the cover scan needs to be attached to the correct copy.";
const COVER_PROCESSING_INFO_OPS =
  "Reprocess metadata only re-reads the stored file and refreshes deterministic MIME, dimensions, file size, and processing status.";
const OPS_COVER_GRAPH_LANES: CoverRelationshipGraphEdge["display_lane"][] = [
  "strong",
  "related",
  "needs_review",
  "blocked",
];

function opsCoverGraphLaneLabel(lane: CoverRelationshipGraphEdge["display_lane"]): string {
  switch (lane) {
    case "strong":
      return "Strong (approved duplicate-scan / same-cover)";
    case "related":
      return "Related (approved same-issue / variant-family)";
    case "blocked":
      return "Blocked / rejected unrelated";
    case "needs_review":
      return "Needs review";
    default:
      return lane;
  }
}

function coverProcessingTone(status: OpsRecentCoverImageRow["processing_status"]): string {
  switch (status) {
    case "processed":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
    case "processing":
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-200";
    case "failed":
      return "border-rose-400/30 bg-rose-400/10 text-rose-200";
    default:
      return "border-white/10 bg-white/5 text-slate-300";
  }
}

function coverMatchingTone(status: OpsRecentCoverImageRow["matching_status"]): string {
  switch (status) {
    case "ready":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
    case "needs_review":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "failed":
      return "border-rose-400/30 bg-rose-400/10 text-rose-200";
    default:
      return "border-white/10 bg-white/5 text-slate-300";
  }
}

function coverOcrHeadlineTone(headline: CoverImageOcrHeadlineStatus): string {
  switch (headline) {
    case "processed":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
    case "processing":
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-200";
    case "failed":
      return "border-rose-400/30 bg-rose-400/10 text-rose-200";
    case "queued":
      return "border-violet-400/30 bg-violet-400/10 text-violet-100";
    default:
      return "border-white/10 bg-white/5 text-slate-300";
  }
}

function matchCandidateFilterPasses(
  row: OpsRecentCoverImageRow,
  confidenceBucket: "all" | CoverMatchConfidenceBucket,
  candidateType: "all" | "fingerprint_similarity" | "barcode_similarity" | "ocr_similarity" | "combined_similarity",
): boolean {
  const candidates = row.match_candidates ?? [];
  if (confidenceBucket === "all" && candidateType === "all") {
    return true;
  }
  return candidates.some((candidate) => {
    if (confidenceBucket !== "all" && candidate.confidence_bucket !== confidenceBucket) {
      return false;
    }
    if (candidateType !== "all" && candidate.candidate_type !== candidateType) {
      return false;
    }
    return true;
  });
}

function matchCandidateTone(bucket: CoverMatchConfidenceBucket): string {
  switch (bucket) {
    case "very_high":
      return "border-emerald-300/40 bg-emerald-400/15 text-emerald-50";
    case "high":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "medium":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "low":
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
    default:
      return "border-slate-500/30 bg-slate-500/10 text-slate-200";
  }
}

function formatMatchGroupingType(value: string | null): string {
  return value ? value.replace(/_/g, " ") : "ungrouped";
}

function qualitySeverityTone(severity: CoverOcrQualitySeverity): string {
  switch (severity) {
    case "critical":
      return "border-rose-400/30 bg-rose-400/10 text-rose-100";
    case "warning":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    default:
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
  }
}

function ocrQualityFilterPasses(
  row: OpsRecentCoverImageRow,
  severity: "all" | CoverOcrQualitySeverity,
  qualityType: "all" | CoverOcrQualityType,
): boolean {
  const analyses = row.ocr_quality_analyses ?? [];
  if (severity === "all" && qualityType === "all") {
    return true;
  }
  return analyses.some((analysis) => {
    if (severity !== "all" && analysis.severity !== severity) {
      return false;
    }
    if (qualityType !== "all" && analysis.quality_type !== qualityType) {
      return false;
    }
    return true;
  });
}

function ocrBatchStatusTone(status: OcrBatch["status"]): string {
  switch (status) {
    case "completed":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "completed_with_errors":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "failed":
    case "cancelled":
      return "border-rose-400/30 bg-rose-400/10 text-rose-100";
    case "running":
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
    default:
      return "border-white/10 bg-white/5 text-slate-200";
  }
}

function ocrReplayStatusTone(status: OcrReplayRun["status"]): string {
  switch (status) {
    case "completed":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "completed_with_changes":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "failed":
    case "cancelled":
      return "border-rose-400/30 bg-rose-400/10 text-rose-100";
    case "running":
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
    default:
      return "border-white/10 bg-white/5 text-slate-200";
  }
}

function relationshipReplayStatusTone(status: RelationshipReplayRun["status"]): string {
  switch (status) {
    case "completed":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "completed_with_changes":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "failed":
    case "cancelled":
      return "border-rose-400/30 bg-rose-400/10 text-rose-100";
    case "running":
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
    default:
      return "border-white/10 bg-white/5 text-slate-200";
  }
}

function scanPipelineReplayStatusTone(status: ScanPipelineReplayRunRead["status"]): string {
  switch (status) {
    case "completed":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "completed_with_failures":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "cancelled":
      return "border-rose-400/30 bg-rose-400/10 text-rose-100";
    case "running":
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
    default:
      return "border-white/10 bg-white/5 text-slate-200";
  }
}

function summarizeAuditSnapshot(snapshot: Record<string, unknown> | null): string {
  if (!snapshot) {
    return "—";
  }
  const preferredKeys = [
    "status",
    "linked_order_id",
    "metadata_identity_key",
    "canonical_series_id",
    "entity_type",
    "entity_id",
    "parsed_payload_json",
  ];
  for (const key of preferredKeys) {
    if (key in snapshot) {
      const value = snapshot[key];
      if (key === "parsed_payload_json" && value && typeof value === "object") {
        const parsed = value as Record<string, unknown>;
        const items = Array.isArray(parsed.items) ? parsed.items.length : 0;
        return `payload: ${items} item(s), warnings ${Array.isArray(parsed.warnings) ? parsed.warnings.length : 0}`;
      }
      if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
        return `${key}: ${String(value)}`;
      }
    }
  }
  const keys = Object.keys(snapshot);
  return keys.length ? keys.slice(0, 4).join(", ") : "snapshot";
}

function duplicateOwnershipClassificationLabel(value: DuplicateOwnershipClassification): string {
  switch (value) {
    case "intentional_multi_copy":
      return "Intentional multi-copy";
    case "probable_accidental_duplicate":
      return "Probable accidental duplicate";
    case "duplicate_scan_only":
      return "Duplicate scan match";
    case "preorder_plus_owned":
      return "Preorder + received copy";
    case "graded_plus_raw":
      return "Graded + raw pairing";
    case "unresolved_duplicate":
      return "Unresolved duplicate review";
    default:
      return value;
  }
}

function runDetectionStatusLabel(value: RunDetectionSeriesStatus): string {
  switch (value) {
    case "partial_run":
      return "Partial run";
    case "complete_limited_series":
      return "Complete limited series";
    case "incomplete_limited_series":
      return "Incomplete limited series";
    case "probable_ongoing_series":
      return "Probable ongoing series";
    case "isolated_special_annual":
      return "Special / annual isolated";
    default:
      return value;
  }
}

function OpsScanSessionInspectionPanel(props: {
  selectedId: number | null;
  loading: boolean;
  detail: ScanSessionDetail | null;
}): JSX.Element | null {
  const { selectedId, loading, detail } = props;
  if (selectedId == null) {
    return null;
  }
  return (
    <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
          Session #{selectedId}{" "}
          {loading ? "(loading)" : detail ? "" : "(unavailable)"}
        </p>
      </div>
      {detail ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <article className="rounded-xl border border-white/10 bg-slate-950/60 p-3">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Lifecycle</p>
              <p className="mt-1 text-sm text-white">
                {detail.status.replace(/_/g, " ")} · Started{" "}
                {detail.started_at ? formatDateTime(detail.started_at) : "—"}
              </p>
              <p className="mt-1 text-xs text-slate-400">
                Completed {detail.completed_at ? formatDateTime(detail.completed_at) : "—"}
              </p>
            </article>
            <article className="rounded-xl border border-white/10 bg-slate-950/60 p-3">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">OCR / review rollups</p>
              <p className="mt-2 text-xs text-slate-300">
                OCR complete: {detail.statistics.ocr_completed} · OCR pending:{" "}
                {detail.statistics.ocr_pending}
              </p>
              <p className="mt-1 text-xs text-slate-300">
                Review required: {detail.statistics.review_required} · Failures: {detail.statistics.failures} · Skipped
                : {detail.statistics.skipped}
              </p>
            </article>
            <article className="rounded-xl border border-white/10 bg-slate-950/60 p-3">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Duplicates</p>
              <p className="mt-2 text-xs text-slate-300">
                Filename dup groups (+ excess rows): {detail.statistics.duplicate_filename_groups} (+
                {detail.statistics.duplicate_filename_excess_rows})
              </p>
              <p className="mt-1 text-xs text-slate-300">
                Hash dup groups (+ excess rows): {detail.statistics.duplicate_image_hash_groups} (+
                {detail.statistics.duplicate_image_hash_excess_rows})
              </p>
            </article>
            <article className="rounded-xl border border-white/10 bg-slate-950/60 p-3">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Averages</p>
              <p className="mt-2 text-xs text-slate-300">
                Avg dimensions:{" "}
                {detail.statistics.average_image_width != null && detail.statistics.average_image_height != null
                  ? `${Math.round(detail.statistics.average_image_width)}×${Math.round(
                      detail.statistics.average_image_height,
                    )}`
                  : "—"}
              </p>
              <p className="mt-1 text-xs text-slate-400">
                Ordering is deterministic across items (sequence index, identifier).
              </p>
            </article>
          </div>
          {detail.items.some((item) => ["failed", "review_required"].includes(item.ingest_status)) ? (
            <div className="mt-4 overflow-auto rounded-xl border border-amber-400/25 bg-amber-400/10 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-100">
                Rows needing attention (failed / review required)
              </p>
              <ul className="mt-2 space-y-1 text-xs text-amber-50/95">
                {detail.items
                  .filter((item) => ["failed", "review_required"].includes(item.ingest_status))
                  .map((item) => (
                    <li key={item.id}>
                      Seq {item.sequence_index} · {item.ingest_status.replace(/_/g, " ")}
                      {item.source_filename ? ` · ${item.source_filename}` : ""}
                      {item.ingest_error ? ` — ${item.ingest_error}` : ""}
                    </li>
                  ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : loading ? (
        <p className="mt-3 text-sm text-slate-400">Hydrating deterministic rollups...</p>
      ) : (
        <p className="mt-3 text-sm text-slate-500">Unable to load session detail.</p>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-3 text-2xl font-semibold text-white">{value}</p>
    </article>
  );
}

function TableSection({
  title,
  description,
  headers,
  rows,
}: {
  title: string;
  description: string;
  headers: string[];
  rows: Array<Array<string | JSX.Element>>;
}) {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/70 shadow-xl shadow-black/20">
      <div className="border-b border-white/10 px-5 py-4">
        <h2 className="text-xl font-semibold text-white">{title}</h2>
        <p className="mt-2 text-sm text-slate-400">{description}</p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-white/10">
          <thead className="bg-slate-950/60">
            <tr>
              {headers.map((header) => (
                <th
                  key={header}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.16em] text-slate-500"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rows.length > 0 ? (
              rows.map((row, rowIndex) => (
                <tr key={`${title}-${rowIndex}`} className="align-top">
                  {row.map((cell, cellIndex) => (
                    <td key={`${title}-${rowIndex}-${cellIndex}`} className="px-4 py-3 text-sm text-slate-200">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={headers.length} className="px-4 py-6 text-sm text-slate-400">
                  No recent records.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function OperationsPage() {
  const [dashboard, setDashboard] = useState<OpsDashboardResponse | null>(null);
  const [portfolioValueSummary, setPortfolioValueSummary] = useState<PortfolioValueSummaryResponse | null>(null);
  const [inventoryFmvCoverage, setInventoryFmvCoverage] = useState<InventoryResponse | null>(null);
  const [inventoryFmvLowConfidence, setInventoryFmvLowConfidence] = useState<InventoryResponse | null>(null);
  const [inventoryFmvStale, setInventoryFmvStale] = useState<InventoryResponse | null>(null);
  const [inventoryFmvNoMarketData, setInventoryFmvNoMarketData] = useState<InventoryResponse | null>(null);
  const [inventoryFmvLoading, setInventoryFmvLoading] = useState(true);
  const [inventoryFmvError, setInventoryFmvError] = useState<string | null>(null);
  const [coverLinkDecisions, setCoverLinkDecisions] = useState<
    Awaited<ReturnType<typeof apiClient.listCoverLinkDecisionsForOps>>
  >([]);
  const [metadataAliases, setMetadataAliases] = useState<MetadataAlias[]>([]);
  const [duplicateCandidates, setDuplicateCandidates] = useState<OpsInventoryDuplicateCandidateGroup[]>(
    [],
  );
  const [duplicateReviewFilter, setDuplicateReviewFilter] =
    useState<InventoryDuplicatesReviewFilter>("all");
  const [duplicateCandidatesLoading, setDuplicateCandidatesLoading] = useState(true);
  const [duplicateCandidatesError, setDuplicateCandidatesError] = useState<string | null>(null);
  const [busyDuplicateIdentityKey, setBusyDuplicateIdentityKey] = useState<string | null>(null);
  const [duplicateNotesDraft, setDuplicateNotesDraft] = useState<Record<string, string>>({});
  const [canonicalSeries, setCanonicalSeries] = useState<OpsCanonicalSeriesRow[]>([]);
  const [canonicalSeriesLoading, setCanonicalSeriesLoading] = useState(true);
  const [canonicalSeriesError, setCanonicalSeriesError] = useState<string | null>(null);
  const [canonicalSeriesPublisherFilter, setCanonicalSeriesPublisherFilter] = useState("");
  const [canonicalSeriesTitleFilter, setCanonicalSeriesTitleFilter] = useState("");
  const [canonicalSeriesEarliestYearMin, setCanonicalSeriesEarliestYearMin] = useState("");
  const [canonicalSeriesEarliestYearMax, setCanonicalSeriesEarliestYearMax] = useState("");
  const [canonicalSeriesLatestYearMin, setCanonicalSeriesLatestYearMin] = useState("");
  const [canonicalSeriesLatestYearMax, setCanonicalSeriesLatestYearMax] = useState("");
  const [canonicalCreators, setCanonicalCreators] = useState<OpsCanonicalCreatorRow[]>([]);
  const [canonicalCreatorsLoading, setCanonicalCreatorsLoading] = useState(true);
  const [canonicalCreatorsError, setCanonicalCreatorsError] = useState<string | null>(null);
  const [canonicalCreatorsBroadFilter, setCanonicalCreatorsBroadFilter] = useState("");
  const [canonicalCreatorsCanonicalNameFilter, setCanonicalCreatorsCanonicalNameFilter] =
    useState("");
  const [canonicalCreatorsNormalizedNameFilter, setCanonicalCreatorsNormalizedNameFilter] =
    useState("");
  const [canonicalCreatorsKeyFilter, setCanonicalCreatorsKeyFilter] = useState("");
  const [canonicalCreatorsShowKeyColumn, setCanonicalCreatorsShowKeyColumn] = useState(true);
  const [metadataAudits, setMetadataAudits] = useState<OpsMetadataAuditRow[]>([]);
  const [metadataAuditsLoading, setMetadataAuditsLoading] = useState(true);
  const [metadataAuditsError, setMetadataAuditsError] = useState<string | null>(null);
  const [reenrichDraftImportId, setReenrichDraftImportId] = useState("");
  const [reenrichInventoryCopyId, setReenrichInventoryCopyId] = useState("");
  const [reenrichReason, setReenrichReason] = useState("");
  const [reenrichBusyKey, setReenrichBusyKey] = useState<string | null>(null);
  const [reenrichMessage, setReenrichMessage] = useState<string | null>(null);

  const [ocrBatches, setOcrBatches] = useState<OcrBatch[]>([]);
  const [ocrBatchesLoading, setOcrBatchesLoading] = useState(true);
  const [ocrBatchesError, setOcrBatchesError] = useState<string | null>(null);
  const [ocrBatchCoverIdsDraft, setOcrBatchCoverIdsDraft] = useState("");
  const [ocrBatchBusyAction, setOcrBatchBusyAction] = useState<string | null>(null);
  const [ocrBatchMessage, setOcrBatchMessage] = useState<string | null>(null);
  const [ocrReplays, setOcrReplays] = useState<OcrReplayRun[]>([]);
  const [ocrReplaysLoading, setOcrReplaysLoading] = useState(true);
  const [ocrReplaysError, setOcrReplaysError] = useState<string | null>(null);
  const [ocrReplayCoverIdsDraft, setOcrReplayCoverIdsDraft] = useState("");
  const [ocrReplayTypeDraft, setOcrReplayTypeDraft] = useState<OcrReplayType>("full_pipeline");
  const [ocrReplayBusyAction, setOcrReplayBusyAction] = useState<string | null>(null);
  const [ocrReplayMessage, setOcrReplayMessage] = useState<string | null>(null);
  const [relationshipReplays, setRelationshipReplays] = useState<RelationshipReplayRun[]>([]);
  const [relationshipReplaysLoading, setRelationshipReplaysLoading] = useState(true);
  const [relationshipReplaysError, setRelationshipReplaysError] = useState<string | null>(null);
  const [relationshipReplayCoverIdsDraft, setRelationshipReplayCoverIdsDraft] = useState("");
  const [relationshipReplayTypeDraft, setRelationshipReplayTypeDraft] =
    useState<RelationshipReplayType>("full_relationship_pipeline");
  const [relationshipReplayBusyAction, setRelationshipReplayBusyAction] = useState<string | null>(null);
  const [relationshipReplayMessage, setRelationshipReplayMessage] = useState<string | null>(null);

  const [recentCoverImages, setRecentCoverImages] = useState<OpsRecentCoverImageRow[]>([]);
  const [recentCoversLoading, setRecentCoversLoading] = useState(true);
  const [recentCoversError, setRecentCoversError] = useState<string | null>(null);
  const [coverOpsLimit, setCoverOpsLimit] = useState<number>(50);
  const [coverOpsLinkage, setCoverOpsLinkage] = useState<"all" | "inventory" | "import">("all");
  const [coverOpsSource, setCoverOpsSource] = useState<"all" | CoverImageSourceType>("all");
  const [coverOpsMatchingStatus, setCoverOpsMatchingStatus] = useState<
    "all" | "ready" | "needs_review" | "failed" | "not_ready"
  >("all");
  const [coverThumbUrls, setCoverThumbUrls] = useState<Record<number, string>>({});
  const [coverThumbErrors, setCoverThumbErrors] = useState<Record<number, boolean>>({});
  const [coverOpsAssignBusyId, setCoverOpsAssignBusyId] = useState<number | null>(null);
  const [coverOpsAssignInvDraft, setCoverOpsAssignInvDraft] = useState<Record<number, string>>({});
  const [coverOpsAssignPrimary, setCoverOpsAssignPrimary] = useState<Record<number, boolean>>({});
  const [coverOpsAssignMessage, setCoverOpsAssignMessage] = useState<Record<number, string>>({});
  const [coverOpsProcessBusyId, setCoverOpsProcessBusyId] = useState<number | null>(null);
  const [coverOpsProcessMessage, setCoverOpsProcessMessage] = useState<Record<number, string>>({});
  const [coverOpsEvaluateBusyId, setCoverOpsEvaluateBusyId] = useState<number | null>(null);
  const [coverOpsEvaluateMessage, setCoverOpsEvaluateMessage] = useState<Record<number, string>>({});
  const [coverOpsOcrBusyId, setCoverOpsOcrBusyId] = useState<number | null>(null);

  const [graphQuickCoverIdDraft, setGraphQuickCoverIdDraft] = useState("");
  const [graphQuickBusy, setGraphQuickBusy] = useState(false);
  const [graphQuickError, setGraphQuickError] = useState<string | null>(null);
  const [graphQuickPayload, setGraphQuickPayload] = useState<CoverRelationshipGraphRead | null>(null);
  const [coverOpsFingerprintBusyId, setCoverOpsFingerprintBusyId] = useState<number | null>(null);
  const [coverOpsFingerprintMessage, setCoverOpsFingerprintMessage] = useState<Record<number, string>>({});
  const [coverOpsQualityBusyId, setCoverOpsQualityBusyId] = useState<number | null>(null);
  const [coverOpsQualityMessage, setCoverOpsQualityMessage] = useState<Record<number, string>>({});
  const [coverOpsQualitySeverityFilter, setCoverOpsQualitySeverityFilter] = useState<
    "all" | CoverOcrQualitySeverity
  >("all");
  const [coverOpsQualityTypeFilter, setCoverOpsQualityTypeFilter] = useState<
    "all" | CoverOcrQualityType
  >("all");
  const [coverOpsMatchConfidenceFilter, setCoverOpsMatchConfidenceFilter] = useState<
    "all" | CoverMatchConfidenceBucket
  >("all");
  const [coverOpsMatchTypeFilter, setCoverOpsMatchTypeFilter] = useState<
    "all" | "fingerprint_similarity" | "barcode_similarity" | "ocr_similarity" | "combined_similarity"
  >("all");

  const [duplicateCoverGroups, setDuplicateCoverGroups] = useState<OpsCoverDuplicateGroup[]>([]);
  const [duplicateCoversLoading, setDuplicateCoversLoading] = useState(true);
  const [duplicateCoversError, setDuplicateCoversError] = useState<string | null>(null);
  const [dupCoverLimit, setDupCoverLimit] = useState<number>(50);
  const [dupCoverMinCount, setDupCoverMinCount] = useState<number>(2);
  const [dupCoverSource, setDupCoverSource] = useState<"all" | CoverImageSourceType>("all");
  const [dupCoverLinkage, setDupCoverLinkage] = useState<
    "all" | "inventory" | "import" | "unlinked"
  >("all");
  const [dupCoverThumbUrls, setDupCoverThumbUrls] = useState<Record<number, string>>({});
  const [dupCoverThumbErrors, setDupCoverThumbErrors] = useState<Record<number, boolean>>({});

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeAliasId, setActiveAliasId] = useState<number | null>(null);
  const [aliasTypeFilter, setAliasTypeFilter] = useState<MetadataAliasType | "all">("all");
  const [pipelineRecoverBusy, setPipelineRecoverBusy] = useState(false);
  const [pipelineRecoverMessage, setPipelineRecoverMessage] = useState<string | null>(null);

  const [inventoryIntelOpsSummary, setInventoryIntelOpsSummary] = useState<
    InventoryIntelligenceRollupSummary | null
  >(null);
  const [inventoryIntelOpsHealth, setInventoryIntelOpsHealth] = useState<
    InventoryIntelligenceHealthRollup | null
  >(null);
  const [inventoryIntelOpsBreakdown, setInventoryIntelOpsBreakdown] = useState<
    InventoryIntelligenceBreakdownResponse | null
  >(null);
  const [inventoryIntelOpsError, setInventoryIntelOpsError] = useState<string | null>(null);
  const [opsInventoryRiskReport, setOpsInventoryRiskReport] = useState<InventoryRiskListResponse | null>(null);
  const [opsInventoryRiskPriority, setOpsInventoryRiskPriority] = useState<"" | InventoryRiskPriority>("");
  const [opsInventoryRiskType, setOpsInventoryRiskType] = useState<"" | InventoryRiskType>("");
  const [opsInventoryRiskOpenOnly, setOpsInventoryRiskOpenOnly] = useState(true);
  const [opsInventoryRiskError, setOpsInventoryRiskError] = useState<string | null>(null);

  const [opsIacReport, setOpsIacReport] = useState<InventoryActionCenterListResponse | null>(null);
  const [opsIacPriority, setOpsIacPriority] = useState<"" | InventoryRiskPriority>("");
  const [opsIacCategory, setOpsIacCategory] = useState<"" | InventoryActionCenterCategory>("");
  const [opsIacError, setOpsIacError] = useState<string | null>(null);

  const [opsOrderArrivalReport, setOpsOrderArrivalReport] = useState<OrderArrivalIntelListResponse | null>(null);
  const [opsOrderArrivalCalendar, setOpsOrderArrivalCalendar] = useState<OrderArrivalIntelCalendarResponse | null>(
    null,
  );
  const [opsOrderArrivalClassification, setOpsOrderArrivalClassification] = useState<
    "" | OrderArrivalClassification
  >("");
  const [opsOrderArrivalError, setOpsOrderArrivalError] = useState<string | null>(null);

  const [opsPhysicalIntakeSummary, setOpsPhysicalIntakeSummary] = useState<PhysicalIntakeSummaryResponse | null>(
    null,
  );
  const [opsPhysicalIntakeList, setOpsPhysicalIntakeList] = useState<PhysicalIntakeListResponse | null>(null);
  const [opsPhysicalIntakeStateFilter, setOpsPhysicalIntakeStateFilter] = useState<"" | PhysicalIntakeState>(
    "",
  );
  const [opsPhysicalIntakeError, setOpsPhysicalIntakeError] = useState<string | null>(null);

  const [opsCollectionSummary, setOpsCollectionSummary] = useState<CollectionAnalyticsSummary | null>(null);
  const [opsCollectionPublishers, setOpsCollectionPublishers] =
    useState<CollectionPublisherAnalyticsResponse | null>(null);
  const [opsCollectionQuality, setOpsCollectionQuality] = useState<CollectionQualityAnalyticsResponse | null>(null);
  const [opsCollectionComposition, setOpsCollectionComposition] =
    useState<CollectionCompositionResponse | null>(null);
  const [opsCollectionTimeline, setOpsCollectionTimeline] = useState<CollectionTimelineResponse | null>(null);
  const [opsCollectionAnalyticsError, setOpsCollectionAnalyticsError] = useState<string | null>(null);

  const [opsHistoricalTimelineDraft, setOpsHistoricalTimelineDraft] = useState<OpsHistoricalTimelineFilters>(() =>
    defaultOpsHistoricalTimelineFilters(),
  );
  const [opsHistoricalTimelineApplied, setOpsHistoricalTimelineApplied] = useState<OpsHistoricalTimelineFilters>(() =>
    defaultOpsHistoricalTimelineFilters(),
  );
  const [opsHistoricalTimelinePayload, setOpsHistoricalTimelinePayload] =
    useState<CollectionHistoricalTimelineEventsResponse | null>(null);
  const [opsHistoricalTimelineLoading, setOpsHistoricalTimelineLoading] = useState(false);
  const [opsHistoricalTimelineError, setOpsHistoricalTimelineError] = useState<string | null>(null);

  const [duplicateScanClustersFilter, setDuplicateScanClustersFilter] =
    useState<DuplicateScanClassificationFilter>("all");
  const [duplicateScanClustersData, setDuplicateScanClustersData] = useState<DuplicateScanClustersListResponse | null>(
    null,
  );
  const [duplicateScanClustersLoading, setDuplicateScanClustersLoading] = useState(true);
  const [duplicateScanClustersError, setDuplicateScanClustersError] = useState<string | null>(null);

  const [duplicateOwnershipOps, setDuplicateOwnershipOps] = useState<DuplicateOwnershipListResponse | null>(null);
  const [duplicateOwnershipOpsLoading, setDuplicateOwnershipOpsLoading] = useState(true);
  const [duplicateOwnershipOpsError, setDuplicateOwnershipOpsError] = useState<string | null>(null);
  const [duplicateOwnershipDupScanOps, setDuplicateOwnershipDupScanOps] =
    useState<DuplicateScanClassificationFilter>("all");
  const [duplicateOwnershipClassificationOps, setDuplicateOwnershipClassificationOps] = useState<
    DuplicateOwnershipClassification | "all"
  >("all");
  const [runDetectionOps, setRunDetectionOps] = useState<RunDetectionListResponse | null>(null);
  const [runDetectionOpsLoading, setRunDetectionOpsLoading] = useState(true);
  const [runDetectionOpsError, setRunDetectionOpsError] = useState<string | null>(null);
  const [runDetectionStatusOps, setRunDetectionStatusOps] = useState<RunDetectionSeriesStatus | "all">("all");
  const [missingIssueOpsClassification, setMissingIssueOpsClassification] =
    useState<MissingIssueClassification | "all">("all");

  const [variantFamilyClustersFilter, setVariantFamilyClustersFilter] =
    useState<VariantFamilyClassificationFilter>("all");
  const [variantFamilyClustersData, setVariantFamilyClustersData] = useState<VariantFamilyClustersListResponse | null>(
    null,
  );
  const [variantFamilyClustersLoading, setVariantFamilyClustersLoading] = useState(true);
  const [variantFamilyClustersError, setVariantFamilyClustersError] = useState<string | null>(null);
  const [canonicalSuggestionReviewState, setCanonicalSuggestionReviewState] =
    useState<CanonicalIssueSuggestionReviewState | "all">("all");
  const [canonicalSuggestionConfidenceBucket, setCanonicalSuggestionConfidenceBucket] =
    useState<CanonicalIssueSuggestionConfidenceBucket | "all">("all");
  const [canonicalSuggestionType, setCanonicalSuggestionType] =
    useState<CanonicalIssueSuggestionType | "all">("all");
  const [canonicalSuggestionsData, setCanonicalSuggestionsData] = useState<CanonicalIssueSuggestionOpsListResponse | null>(
    null,
  );
  const [canonicalSuggestionsLoading, setCanonicalSuggestionsLoading] = useState(true);
  const [canonicalSuggestionsError, setCanonicalSuggestionsError] = useState<string | null>(null);
  const [relationshipConflictSeverity, setRelationshipConflictSeverity] =
    useState<RelationshipConflictSeverity | "all">("all");
  const [relationshipConflictStatus, setRelationshipConflictStatus] =
    useState<RelationshipConflictStatus | "all">("all");
  const [relationshipConflictType, setRelationshipConflictType] =
    useState<RelationshipConflictType | "all">("all");
  const [relationshipConflictsData, setRelationshipConflictsData] =
    useState<RelationshipConflictListResponse | null>(null);
  const [relationshipConflictsLoading, setRelationshipConflictsLoading] = useState(true);
  const [relationshipConflictsError, setRelationshipConflictsError] = useState<string | null>(null);
  const [relationshipConflictsDetectBusy, setRelationshipConflictsDetectBusy] = useState(false);
  const [relationshipConflictsDetectMessage, setRelationshipConflictsDetectMessage] = useState<string | null>(null);

  const [opsScanPipelineDash, setOpsScanPipelineDash] = useState<ScanPipelineDashboardResponse | null>(null);
  const [opsScanPipelineDashLoading, setOpsScanPipelineDashLoading] = useState(true);
  const [opsScanPipelineDashError, setOpsScanPipelineDashError] = useState<string | null>(null);

  const [opsMarketSalesRefreshTick, setOpsMarketSalesRefreshTick] = useState(0);
  const [opsListingDistribution, setOpsListingDistribution] = useState<ListingOpsStatusDistribution | null>(null);
  const [opsListingDistributionLoading, setOpsListingDistributionLoading] = useState(true);
  const [opsListingDistributionError, setOpsListingDistributionError] = useState<string | null>(null);
  const [opsListingEventsFeed, setOpsListingEventsFeed] = useState<OpsListingLifecycleEventListResponse | null>(null);
  const [opsListingEventsFeedLoading, setOpsListingEventsFeedLoading] = useState(true);
  const [opsListingEventsFeedError, setOpsListingEventsFeedError] = useState<string | null>(null);
  const [opsListingExportRuns, setOpsListingExportRuns] = useState<ListingExportRunListResponse | null>(null);
  const [opsListingExportRunsLoading, setOpsListingExportRunsLoading] = useState(true);
  const [opsListingExportRunsError, setOpsListingExportRunsError] = useState<string | null>(null);
  const [opsListingExportDownloadError, setOpsListingExportDownloadError] = useState<string | null>(null);
  const [opsOperationalReports, setOpsOperationalReports] = useState<OperationalReportRunListResponse | null>(null);
  const [opsOperationalReportsLoading, setOpsOperationalReportsLoading] = useState(true);
  const [opsOperationalReportsError, setOpsOperationalReportsError] = useState<string | null>(null);
  const [opsOperationalOwnerDraft, setOpsOperationalOwnerDraft] = useState("");
  const [opsOperationalOwnerFilter, setOpsOperationalOwnerFilter] = useState<number | undefined>();
  const [opsOperationalDownloadError, setOpsOperationalDownloadError] = useState<string | null>(null);
  const [opsGradingReports, setOpsGradingReports] = useState<GradingOperationalReportRunListResponse | null>(null);
  const [opsGradingReportsLoading, setOpsGradingReportsLoading] = useState(true);
  const [opsGradingReportsError, setOpsGradingReportsError] = useState<string | null>(null);
  const [opsGradingReportsOwnerDraft, setOpsGradingReportsOwnerDraft] = useState("");
  const [opsGradingReportsOwnerFilter, setOpsGradingReportsOwnerFilter] = useState<number | undefined>();
  const [opsGradingReportsDownloadError, setOpsGradingReportsDownloadError] = useState<string | null>(null);
  const [opsGradingCandidates, setOpsGradingCandidates] = useState<GradingCandidateListResponse | null>(null);
  const [opsGradingCandidatesLoading, setOpsGradingCandidatesLoading] = useState(true);
  const [opsGradingCandidatesError, setOpsGradingCandidatesError] = useState<string | null>(null);
  const [opsGradingOwnerDraft, setOpsGradingOwnerDraft] = useState("");
  const [opsGradingOwnerFilter, setOpsGradingOwnerFilter] = useState<number | undefined>();
  const [opsGradingSpreads, setOpsGradingSpreads] = useState<GradingSpreadListResponse | null>(null);
  const [opsGradingSpreadsLoading, setOpsGradingSpreadsLoading] = useState(true);
  const [opsGradingSpreadsError, setOpsGradingSpreadsError] = useState<string | null>(null);
  const [opsGradingRoi, setOpsGradingRoi] = useState<GradingRoiListResponse | null>(null);
  const [opsGradingRoiLoading, setOpsGradingRoiLoading] = useState(true);
  const [opsGradingRoiError, setOpsGradingRoiError] = useState<string | null>(null);
  const [opsGradingSubmission, setOpsGradingSubmission] = useState<GradingSubmissionListResponse | null>(null);
  const [opsGradingSubmissionLoading, setOpsGradingSubmissionLoading] = useState(true);
  const [opsGradingSubmissionError, setOpsGradingSubmissionError] = useState<string | null>(null);
  const [opsGradingRecommendation, setOpsGradingRecommendation] = useState<GradingRecommendationListResponse | null>(
    null,
  );
  const [opsGradingRecommendationLoading, setOpsGradingRecommendationLoading] = useState(true);
  const [opsGradingRecommendationError, setOpsGradingRecommendationError] = useState<string | null>(null);
  const [opsGradingRisk, setOpsGradingRisk] = useState<GradingRiskListResponse | null>(null);
  const [opsGradingRiskLoading, setOpsGradingRiskLoading] = useState(true);
  const [opsGradingRiskError, setOpsGradingRiskError] = useState<string | null>(null);
  const [opsGradingReconciliation, setOpsGradingReconciliation] = useState<GradingReconciliationListResponse | null>(
    null,
  );
  const [opsGradingReconciliationLoading, setOpsGradingReconciliationLoading] = useState(true);
  const [opsGradingReconciliationError, setOpsGradingReconciliationError] = useState<string | null>(null);
  const [opsConventionSummary, setOpsConventionSummary] = useState<ConventionDashboardSummary | null>(null);
  const [opsConventionSummaryLoading, setOpsConventionSummaryLoading] = useState(true);
  const [opsConventionSummaryError, setOpsConventionSummaryError] = useState<string | null>(null);
  const [opsConventionEvents, setOpsConventionEvents] = useState<ConventionEventListResponse | null>(null);
  const [opsConventionEventsLoading, setOpsConventionEventsLoading] = useState(true);
  const [opsConventionEventsError, setOpsConventionEventsError] = useState<string | null>(null);
  const [opsConventionAssignments, setOpsConventionAssignments] = useState<ConventionAssignmentListResponse | null>(null);
  const [opsConventionAssignmentsLoading, setOpsConventionAssignmentsLoading] = useState(true);
  const [opsConventionAssignmentsError, setOpsConventionAssignmentsError] = useState<string | null>(null);
  const [opsConventionMovements, setOpsConventionMovements] = useState<ConventionMovementListResponse | null>(null);
  const [opsConventionMovementsLoading, setOpsConventionMovementsLoading] = useState(true);
  const [opsConventionMovementsError, setOpsConventionMovementsError] = useState<string | null>(null);
  const [opsConventionPriceSnapshots, setOpsConventionPriceSnapshots] = useState<ConventionPriceSnapshotListResponse | null>(null);
  const [opsConventionPriceSnapshotsLoading, setOpsConventionPriceSnapshotsLoading] = useState(true);
  const [opsConventionPriceSnapshotsError, setOpsConventionPriceSnapshotsError] = useState<string | null>(null);
  const [opsConventionSaleSessions, setOpsConventionSaleSessions] = useState<ConventionSaleSessionListResponse | null>(null);
  const [opsConventionSaleSessionsLoading, setOpsConventionSaleSessionsLoading] = useState(true);
  const [opsConventionSaleSessionsError, setOpsConventionSaleSessionsError] = useState<string | null>(null);
  const [opsListingIntelligenceSummary, setOpsListingIntelligenceSummary] = useState<ListingIntelligenceDashboardSummary | null>(null);
  const [opsListingIntelligenceSummaryLoading, setOpsListingIntelligenceSummaryLoading] = useState(true);
  const [opsListingIntelligenceSummaryError, setOpsListingIntelligenceSummaryError] = useState<string | null>(null);
  const [opsListingIntelligenceSnapshots, setOpsListingIntelligenceSnapshots] = useState<ListingIntelligenceSnapshotRead[]>([]);
  const [opsListingIntelligenceSnapshotsLoading, setOpsListingIntelligenceSnapshotsLoading] = useState(true);
  const [opsListingIntelligenceSnapshotsError, setOpsListingIntelligenceSnapshotsError] = useState<string | null>(null);
  const [opsListingIntelligenceChecks, setOpsListingIntelligenceChecks] = useState<ListingCompletenessCheckRead[]>([]);
  const [opsListingIntelligenceChecksLoading, setOpsListingIntelligenceChecksLoading] = useState(true);
  const [opsListingIntelligenceChecksError, setOpsListingIntelligenceChecksError] = useState<string | null>(null);
  const [opsListingIntelligenceEvidence, setOpsListingIntelligenceEvidence] = useState<ListingIntelligenceEvidenceRead[]>([]);
  const [opsListingIntelligenceEvidenceLoading, setOpsListingIntelligenceEvidenceLoading] = useState(true);
  const [opsListingIntelligenceEvidenceError, setOpsListingIntelligenceEvidenceError] = useState<string | null>(null);
  const [opsListingIntelligenceChannelPerf, setOpsListingIntelligenceChannelPerf] = useState<ListingChannelPerformanceSnapshotRead[]>([]);
  const [opsListingIntelligenceChannelPerfLoading, setOpsListingIntelligenceChannelPerfLoading] = useState(true);
  const [opsListingIntelligenceChannelPerfError, setOpsListingIntelligenceChannelPerfError] = useState<string | null>(null);
  const [opsDealerDash, setOpsDealerDash] = useState<DealerDashboardGetResponse | null>(null);
  const [opsDealerDashLoading, setOpsDealerDashLoading] = useState(true);
  const [opsDealerDashError, setOpsDealerDashError] = useState<string | null>(null);
  const [opsDealerOwnerDraft, setOpsDealerOwnerDraft] = useState("");
  const [opsDealerOwnerApplied, setOpsDealerOwnerApplied] = useState<number | undefined>(undefined);
  const [opsDealerAlerts, setOpsDealerAlerts] = useState<DealerDashboardAlertRead[]>([]);
  const [opsDealerFeed, setOpsDealerFeed] = useState<DealerDashboardFeedEventRead[]>([]);
  const [opsDealerMetrics, setOpsDealerMetrics] = useState<DealerDashboardMetricRead[]>([]);
  const [opsStrategyDash, setOpsStrategyDash] = useState<PortfolioStrategyDashboardGetResponse | null>(null);
  const [opsStrategyDashLoading, setOpsStrategyDashLoading] = useState(true);
  const [opsStrategyDashError, setOpsStrategyDashError] = useState<string | null>(null);
  const [opsStrategyAlerts, setOpsStrategyAlerts] = useState<PortfolioStrategyDashboardAlertRead[]>([]);
  const [opsStrategyFeed, setOpsStrategyFeed] = useState<PortfolioStrategyDashboardFeedEventRead[]>([]);
  const [opsStrategyMetrics, setOpsStrategyMetrics] = useState<PortfolioStrategyDashboardMetricRead[]>([]);
  const [opsDealerGradingDash, setOpsDealerGradingDash] = useState<DealerGradingDashboardGetResponse | null>(null);
  const [opsDealerGradingDashLoading, setOpsDealerGradingDashLoading] = useState(true);
  const [opsDealerGradingDashError, setOpsDealerGradingDashError] = useState<string | null>(null);
  const [opsDealerGradingOwnerDraft, setOpsDealerGradingOwnerDraft] = useState("");
  const [opsDealerGradingOwnerApplied, setOpsDealerGradingOwnerApplied] = useState<number | undefined>(undefined);
  const [opsDealerGradingAlerts, setOpsDealerGradingAlerts] = useState<DealerGradingDashboardAlertRead[]>([]);
  const [opsDealerGradingFeed, setOpsDealerGradingFeed] = useState<DealerGradingDashboardFeedEventRead[]>([]);
  const [opsDealerGradingMetrics, setOpsDealerGradingMetrics] = useState<DealerGradingDashboardMetricRead[]>([]);
  const [opsPortfolioOwnerDraft, setOpsPortfolioOwnerDraft] = useState("");
  const [opsPortfolioOwnerApplied, setOpsPortfolioOwnerApplied] = useState<number | undefined>(undefined);
  const loadOpsStrategyDashboard = useCallback(async () => {
    setOpsStrategyDashLoading(true);
    setOpsStrategyDashError(null);
    const scoped = opsPortfolioOwnerApplied === undefined ? {} : { owner_user_id: opsPortfolioOwnerApplied };
    const [dashResult, alertsResult, feedResult, metricsResult] = await Promise.allSettled([
      apiClient.getOpsPortfolioStrategyDashboard(scoped),
      apiClient.listOpsPortfolioStrategyDashboardAlerts({ ...scoped, limit: 60, offset: 0 }),
      apiClient.listOpsPortfolioStrategyDashboardFeed({ ...scoped, limit: 60, offset: 0 }),
      apiClient.listOpsPortfolioStrategyDashboardMetrics({ ...scoped, limit: 120, offset: 0 }),
    ]);
    const dash = dashResult.status === "fulfilled" ? dashResult.value : null;
    const failedParts: string[] = [];
    if (dashResult.status === "rejected") {
      failedParts.push("snapshot");
    }
    if (alertsResult.status === "fulfilled") {
      setOpsStrategyAlerts(alertsResult.value.items);
    } else {
      setOpsStrategyAlerts([]);
      failedParts.push("alerts");
    }
    if (feedResult.status === "fulfilled") {
      setOpsStrategyFeed(feedResult.value.items);
    } else {
      setOpsStrategyFeed([]);
      failedParts.push("feed");
    }
    if (metricsResult.status === "fulfilled") {
      setOpsStrategyMetrics(metricsResult.value.items);
    } else {
      setOpsStrategyMetrics([]);
      failedParts.push("metrics");
    }
    setOpsStrategyDash(dash);
    if (failedParts.length > 0) {
      const primaryMessage =
        dashResult.status === "rejected"
          ? dashResult.reason instanceof ApiError
            ? dashResult.reason.message
            : "Unable to load portfolio strategy dashboard ops payloads."
          : `Strategy ops partially loaded. Missing ${failedParts.join(", ")}.`;
      setOpsStrategyDashError(primaryMessage);
    } else {
      setOpsStrategyDashError(null);
    }
    setOpsStrategyDashLoading(false);
  }, [opsPortfolioOwnerApplied]);
  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsMarketDeterminismLoading(true);
      setOpsMarketDeterminismError(null);
      const scoped = opsPortfolioOwnerApplied === undefined ? {} : { owner_user_id: opsPortfolioOwnerApplied };
      try {
        const [runs, invariants, replayAudits] = await Promise.all([
          apiClient.listOpsMarketDeterminismValidationRuns({ ...scoped, limit: 8, offset: 0 }),
          apiClient.listOpsMarketDeterminismInvariants({ ...scoped, limit: 40, offset: 0 }),
          apiClient.listOpsMarketDeterminismReplayAudits({ ...scoped, limit: 40, offset: 0 }),
        ]);
        if (!ignore) {
          setOpsMarketDeterminismRuns(runs);
          setOpsMarketDeterminismInvariants(invariants.items);
          setOpsMarketDeterminismReplayAudits(replayAudits.items);
          setOpsMarketDeterminismSelectedInvariantId(invariants.items[0]?.id ?? null);
          setOpsMarketDeterminismSelectedReplayId(replayAudits.items[0]?.id ?? null);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketDeterminismRuns(null);
          setOpsMarketDeterminismInvariants([]);
          setOpsMarketDeterminismReplayAudits([]);
          setOpsMarketDeterminismError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load market determinism ops diagnostics.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketDeterminismLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsPortfolioOwnerApplied]);
  const [opsPortfolioList, setOpsPortfolioList] = useState<PortfolioListResponse | null>(null);
  const [opsPortfolioItems, setOpsPortfolioItems] = useState<PortfolioItemListResponse | null>(null);
  const [opsPortfolioExposures, setOpsPortfolioExposures] = useState<PortfolioExposureSnapshotListResponse | null>(null);
  const [opsPortfolioEvidence, setOpsPortfolioEvidence] = useState<PortfolioExposureEvidenceListResponse | null>(null);
  const [opsPortfolioAllocations, setOpsPortfolioAllocations] = useState<PortfolioAllocationSnapshotListResponse | null>(
    null,
  );
  const [opsPortfolioLoading, setOpsPortfolioLoading] = useState(true);
  const [opsPortfolioError, setOpsPortfolioError] = useState<string | null>(null);
  const [opsDuplicateClusters, setOpsDuplicateClusters] = useState<DuplicateClusterListResponse | null>(null);
  const [opsDuplicateClusterItems, setOpsDuplicateClusterItems] = useState<DuplicateClusterItemListResponse | null>(null);
  const [opsDuplicateRecos, setOpsDuplicateRecos] = useState<DuplicateConsolidationRecommendationListResponse | null>(
    null,
  );
  const [opsDuplicateHistory, setOpsDuplicateHistory] = useState<DuplicateHistoryListResponse | null>(null);
  const [opsPortfolioLiquidityList, setOpsPortfolioLiquidityList] = useState<PortfolioLiquiditySnapshotListResponse | null>(null);
  const [opsPortfolioLiquidityDetail, setOpsPortfolioLiquidityDetail] =
    useState<PortfolioLiquiditySnapshotDetailResponse | null>(null);
  const [opsPortfolioLiquidityEvidence, setOpsPortfolioLiquidityEvidence] =
    useState<PortfolioLiquidityEvidenceListResponse | null>(null);
  const [opsPortfolioLiquidityHistory, setOpsPortfolioLiquidityHistory] =
    useState<PortfolioLiquidityHistoryListResponse | null>(null);
  const [opsPortfolioRecommendationList, setOpsPortfolioRecommendationList] =
    useState<PortfolioRecommendationListResponse | null>(null);
  const [opsPortfolioRecommendationDetail, setOpsPortfolioRecommendationDetail] =
    useState<PortfolioRecommendationDetailRead | null>(null);
  const [opsPortfolioRecommendationEvidence, setOpsPortfolioRecommendationEvidence] =
    useState<PortfolioRecommendationEvidenceListResponse | null>(null);
  const [opsPortfolioRecommendationHistory, setOpsPortfolioRecommendationHistory] =
    useState<PortfolioRecommendationHistoryListResponse | null>(null);
  const [opsPortfolioRecommendationLoading, setOpsPortfolioRecommendationLoading] = useState(true);
  const [opsPortfolioRecommendationError, setOpsPortfolioRecommendationError] = useState<string | null>(null);
  const [opsAcquisitionPriorityList, setOpsAcquisitionPriorityList] = useState<AcquisitionPriorityListResponse | null>(null);
  const [opsAcquisitionPriorityDetail, setOpsAcquisitionPriorityDetail] = useState<AcquisitionPriorityDetailRead | null>(null);
  const [opsAcquisitionPriorityEvidence, setOpsAcquisitionPriorityEvidence] =
    useState<AcquisitionPriorityEvidenceListResponse | null>(null);
  const [opsAcquisitionPriorityHistory, setOpsAcquisitionPriorityHistory] =
    useState<AcquisitionPriorityHistoryListResponse | null>(null);
  const [opsAcquisitionPriorityLoading, setOpsAcquisitionPriorityLoading] = useState(true);
  const [opsAcquisitionPriorityError, setOpsAcquisitionPriorityError] = useState<string | null>(null);
  const [opsConcentrationRiskList, setOpsConcentrationRiskList] = useState<ConcentrationRiskListResponse | null>(null);
  const [opsConcentrationRiskDetail, setOpsConcentrationRiskDetail] = useState<ConcentrationRiskDetailRead | null>(null);
  const [opsConcentrationRiskEvidence, setOpsConcentrationRiskEvidence] =
    useState<ConcentrationRiskEvidenceListResponse | null>(null);
  const [opsConcentrationRiskFactors, setOpsConcentrationRiskFactors] =
    useState<ConcentrationRiskFactorListResponse | null>(null);
  const [opsConcentrationRiskHistory, setOpsConcentrationRiskHistory] =
    useState<ConcentrationRiskHistoryListResponse | null>(null);
  const [opsConcentrationRiskLoading, setOpsConcentrationRiskLoading] = useState(true);
  const [opsConcentrationRiskError, setOpsConcentrationRiskError] = useState<string | null>(null);
  const [opsLiquiditySummary, setOpsLiquiditySummary] = useState<LiquidityDashboardSummary | null>(null);
  const [opsLiquiditySummaryLoading, setOpsLiquiditySummaryLoading] = useState(true);
  const [opsLiquiditySummaryError, setOpsLiquiditySummaryError] = useState<string | null>(null);
  const [opsLiquiditySnapshots, setOpsLiquiditySnapshots] = useState<InventoryLiquiditySnapshotRead[]>([]);
  const [opsLiquiditySnapshotsLoading, setOpsLiquiditySnapshotsLoading] = useState(true);
  const [opsLiquiditySnapshotsError, setOpsLiquiditySnapshotsError] = useState<string | null>(null);
  const [opsSalesLedger, setOpsSalesLedger] = useState<SaleRecordRead[]>([]);
  const [opsSalesLedgerLoading, setOpsSalesLedgerLoading] = useState(true);
  const [opsSalesLedgerError, setOpsSalesLedgerError] = useState<string | null>(null);
  const [opsMarketIngestionSummary, setOpsMarketIngestionSummary] = useState<MarketAcquisitionIngestionBatchListResponse | null>(null);
  const [opsMarketIngestionLoading, setOpsMarketIngestionLoading] = useState(true);
  const [opsMarketIngestionError, setOpsMarketIngestionError] = useState<string | null>(null);
  const [opsMarketIngestionSelectedId, setOpsMarketIngestionSelectedId] = useState<number | null>(null);
  const [opsMarketIngestionDetail, setOpsMarketIngestionDetail] = useState<MarketAcquisitionIngestionBatchRead | null>(null);
  const [opsMarketIngestionDetailLoading, setOpsMarketIngestionDetailLoading] = useState(false);
  const [opsMarketIngestionDetailError, setOpsMarketIngestionDetailError] = useState<string | null>(null);
  const [opsMarketIngestionRaw, setOpsMarketIngestionRaw] = useState<MarketAcquisitionRawSourceRead[]>([]);
  const [opsMarketNormSummary, setOpsMarketNormSummary] = useState<MarketNormalizationRunListResponse | null>(null);
  const [opsMarketNormLoading, setOpsMarketNormLoading] = useState(true);
  const [opsMarketNormError, setOpsMarketNormError] = useState<string | null>(null);
  const [opsMarketNormSelectedId, setOpsMarketNormSelectedId] = useState<number | null>(null);
  const [opsMarketNormDetail, setOpsMarketNormDetail] = useState<MarketNormalizationRunDetailRead | null>(null);
  const [opsMarketNormDetailLoading, setOpsMarketNormDetailLoading] = useState(false);
  const [opsMarketNormDetailError, setOpsMarketNormDetailError] = useState<string | null>(null);
  const [opsMarketNormCandidates, setOpsMarketNormCandidates] = useState<MarketAcquisitionNormalizedCandidateRead[]>([]);
  const [opsMarketNormIssues, setOpsMarketNormIssues] = useState<MarketNormalizationIssueRead[]>([]);
  const [opsMarketScoringSummary, setOpsMarketScoringSummary] = useState<MarketAcquisitionScoreSnapshotListResponse | null>(
    null,
  );
  const [opsMarketScoringLoading, setOpsMarketScoringLoading] = useState(true);
  const [opsMarketScoringError, setOpsMarketScoringError] = useState<string | null>(null);
  const [opsMarketScoringSelectedId, setOpsMarketScoringSelectedId] = useState<number | null>(null);
  const [opsMarketScoringScores, setOpsMarketScoringScores] = useState<MarketAcquisitionScoreRead[]>([]);
  const [opsMarketScoringHistory, setOpsMarketScoringHistory] = useState<MarketAcquisitionScoreHistoryRead[]>([]);
  const [opsMarketScoringDetail, setOpsMarketScoringDetail] = useState<MarketAcquisitionScoreDetailRead | null>(null);
  const [opsMarketScoringDetailLoading, setOpsMarketScoringDetailLoading] = useState(false);
  const [opsMarketScoringDetailError, setOpsMarketScoringDetailError] = useState<string | null>(null);
  const [opsMarketSignalSummary, setOpsMarketSignalSummary] = useState<MarketAcquisitionSignalSnapshotListResponse | null>(null);
  const [opsMarketSignalLoading, setOpsMarketSignalLoading] = useState(true);
  const [opsMarketSignalError, setOpsMarketSignalError] = useState<string | null>(null);
  const [opsMarketSignalSelectedId, setOpsMarketSignalSelectedId] = useState<number | null>(null);
  const [opsMarketSignals, setOpsMarketSignals] = useState<MarketAcquisitionSignalRead[]>([]);
  const [opsMarketSignalHistory, setOpsMarketSignalHistory] = useState<MarketAcquisitionSignalHistoryRead[]>([]);
  const [opsMarketSignalDetail, setOpsMarketSignalDetail] = useState<MarketAcquisitionSignalDetailRead | null>(null);
  const [opsMarketSignalEvidence, setOpsMarketSignalEvidence] = useState<MarketAcquisitionSignalEvidenceRead[]>([]);
  const [opsMarketSignalDetailLoading, setOpsMarketSignalDetailLoading] = useState(false);
  const [opsMarketSignalDetailError, setOpsMarketSignalDetailError] = useState<string | null>(null);
  const [opsMarketOpportunitySummary, setOpsMarketOpportunitySummary] =
    useState<MarketAcquisitionOpportunitySnapshotListResponse | null>(null);
  const [opsMarketOpportunityLoading, setOpsMarketOpportunityLoading] = useState(true);
  const [opsMarketOpportunityError, setOpsMarketOpportunityError] = useState<string | null>(null);
  const [opsMarketOpportunitySelectedId, setOpsMarketOpportunitySelectedId] = useState<number | null>(null);
  const [opsMarketOpportunityItems, setOpsMarketOpportunityItems] = useState<MarketAcquisitionOpportunityItemRead[]>([]);
  const [opsMarketOpportunityDetail, setOpsMarketOpportunityDetail] = useState<MarketAcquisitionOpportunityDetailRead | null>(
    null,
  );
  const [opsMarketOpportunityEvidence, setOpsMarketOpportunityEvidence] = useState<MarketAcquisitionOpportunityEvidenceRead[]>(
    [],
  );
  const [opsMarketOpportunityHistory, setOpsMarketOpportunityHistory] = useState<MarketAcquisitionOpportunityHistoryRead[]>(
    [],
  );
  const [opsMarketOpportunityDetailLoading, setOpsMarketOpportunityDetailLoading] = useState(false);
  const [opsMarketOpportunityDetailError, setOpsMarketOpportunityDetailError] = useState<string | null>(null);
  const [opsPortfolioCouplingSummary, setOpsPortfolioCouplingSummary] =
    useState<PortfolioMarketCouplingSnapshotListResponse | null>(null);
  const [opsPortfolioCouplingLoading, setOpsPortfolioCouplingLoading] = useState(true);
  const [opsPortfolioCouplingError, setOpsPortfolioCouplingError] = useState<string | null>(null);
  const [opsPortfolioCouplingSelectedId, setOpsPortfolioCouplingSelectedId] = useState<number | null>(null);
  const [opsPortfolioCouplingDetail, setOpsPortfolioCouplingDetail] = useState<PortfolioMarketCouplingDetailRead | null>(
    null,
  );
  const [opsPortfolioCouplingEdges, setOpsPortfolioCouplingEdges] = useState<PortfolioMarketCouplingEdgeRead[]>([]);
  const [opsPortfolioCouplingHistory, setOpsPortfolioCouplingHistory] = useState<PortfolioMarketCouplingHistoryRead[]>([]);
  const [opsPortfolioCouplingDetailLoading, setOpsPortfolioCouplingDetailLoading] = useState(false);
  const [opsPortfolioCouplingDetailError, setOpsPortfolioCouplingDetailError] = useState<string | null>(null);
  const [opsMarketDeterminismRuns, setOpsMarketDeterminismRuns] =
    useState<MarketDeterminismValidationRunListResponse | null>(null);
  const [opsMarketDeterminismLoading, setOpsMarketDeterminismLoading] = useState(true);
  const [opsMarketDeterminismError, setOpsMarketDeterminismError] = useState<string | null>(null);
  const [opsMarketDeterminismInvariants, setOpsMarketDeterminismInvariants] = useState<MarketDeterminismInvariantRead[]>([]);
  const [opsMarketDeterminismReplayAudits, setOpsMarketDeterminismReplayAudits] = useState<MarketDeterminismReplayAuditRead[]>(
    [],
  );
  const [opsMarketDeterminismSelectedInvariantId, setOpsMarketDeterminismSelectedInvariantId] = useState<number | null>(
    null,
  );
  const [opsMarketDeterminismSelectedReplayId, setOpsMarketDeterminismSelectedReplayId] = useState<number | null>(null);
  const [opsMarketSales, setOpsMarketSales] = useState<MarketSaleSummaryRead[]>([]);
  const [opsMarketSalesLoading, setOpsMarketSalesLoading] = useState(true);
  const [opsMarketSalesError, setOpsMarketSalesError] = useState<string | null>(null);
  const [opsMarketSaleSelectedId, setOpsMarketSaleSelectedId] = useState<number | null>(null);
  const [opsMarketSaleDetail, setOpsMarketSaleDetail] = useState<MarketSaleRead | null>(null);
  const [opsMarketSaleDetailLoading, setOpsMarketSaleDetailLoading] = useState(false);
  const [opsMarketSaleDetailError, setOpsMarketSaleDetailError] = useState<string | null>(null);
  const [opsMarketSaleNormalizationDraft, setOpsMarketSaleNormalizationDraft] =
    useState<MarketSaleNormalizationUpdatePayload>({ mark_reviewed: false });
  const [opsMarketSaleReviewQueueRefreshTick, setOpsMarketSaleReviewQueueRefreshTick] = useState(0);
  const [opsMarketSaleReviewQueue, setOpsMarketSaleReviewQueue] = useState<MarketSaleReviewQueueResponse | null>(null);
  const [opsMarketSaleReviewQueueLoading, setOpsMarketSaleReviewQueueLoading] = useState(true);
  const [opsMarketSaleReviewQueueError, setOpsMarketSaleReviewQueueError] = useState<string | null>(null);
  const [opsMarketSaleReviewQueueSummary, setOpsMarketSaleReviewQueueSummary] =
    useState<MarketSaleReviewQueueSummaryRead | null>(null);
  const [opsMarketSaleReviewClassificationFilter, setOpsMarketSaleReviewClassificationFilter] = useState<
    "" | MarketSaleReviewClassification
  >("");
  const [opsMarketSaleReviewPriorityFilter, setOpsMarketSaleReviewPriorityFilter] = useState<
    "" | MarketSaleReviewPriority
  >("");
  const [opsMarketSaleReviewStatusFilter, setOpsMarketSaleReviewStatusFilter] = useState<
    "" | MarketSaleReviewStatus
  >("");
  const [opsMarketSaleReviewSourceFilter, setOpsMarketSaleReviewSourceFilter] = useState("");
  const [opsMarketSaleReviewSourceTypeFilter, setOpsMarketSaleReviewSourceTypeFilter] = useState("");
  const [opsMarketSaleReviewIssueTypeFilter, setOpsMarketSaleReviewIssueTypeFilter] = useState("");
  const [opsMarketCompEligibility, setOpsMarketCompEligibility] =
    useState<MarketSaleCompEligibilityListResponse | null>(null);
  const [opsMarketCompEligibilityLoading, setOpsMarketCompEligibilityLoading] = useState(true);
  const [opsMarketCompEligibilityError, setOpsMarketCompEligibilityError] = useState<string | null>(null);
  const [opsMarketCompEligibilitySourceFilter, setOpsMarketCompEligibilitySourceFilter] = useState("");
  const [opsMarketCompEligibilityStatusFilter, setOpsMarketCompEligibilityStatusFilter] =
    useState<"" | MarketCompEligibilityStatus>("");
  const [opsMarketCompEligibilityClassificationFilter, setOpsMarketCompEligibilityClassificationFilter] =
    useState<"" | MarketCompEligibilityClassification>("");
  const [opsMarketCompEligibilityGradingCompanyFilter, setOpsMarketCompEligibilityGradingCompanyFilter] =
    useState("");
  const [opsMarketCompEligibilityIsGradedFilter, setOpsMarketCompEligibilityIsGradedFilter] =
    useState<"" | "true" | "false">("");
  const [opsMarketCompEligibilityCurrencyFilter, setOpsMarketCompEligibilityCurrencyFilter] = useState("");
  const [opsMarketCompEligibilitySaleDateFromFilter, setOpsMarketCompEligibilitySaleDateFromFilter] = useState("");
  const [opsMarketCompEligibilitySaleDateToFilter, setOpsMarketCompEligibilitySaleDateToFilter] = useState("");
  const [opsMarketCompEligibilitySelectedId, setOpsMarketCompEligibilitySelectedId] = useState<number | null>(null);
  const [opsMarketCompEligibilityDetail, setOpsMarketCompEligibilityDetail] =
    useState<MarketSaleCompEligibilityRead | null>(null);
  const [opsMarketCompEligibilityDetailLoading, setOpsMarketCompEligibilityDetailLoading] = useState(false);
  const [opsMarketCompEligibilityDetailError, setOpsMarketCompEligibilityDetailError] = useState<string | null>(null);
  const [opsMarketComps, setOpsMarketComps] = useState<MarketComparableListResponse | null>(null);
  const [opsMarketCompsLoading, setOpsMarketCompsLoading] = useState(true);
  const [opsMarketCompsError, setOpsMarketCompsError] = useState<string | null>(null);
  const [opsMarketCompsSourceFilter, setOpsMarketCompsSourceFilter] = useState("");
  const [opsMarketCompsMetadataIdentityKeyFilter, setOpsMarketCompsMetadataIdentityKeyFilter] = useState("");
  const [opsMarketCompsIsGradedFilter, setOpsMarketCompsIsGradedFilter] = useState<"" | "true" | "false">("");
  const [opsMarketCompsGradingCompanyFilter, setOpsMarketCompsGradingCompanyFilter] = useState("");
  const [opsMarketCompsNormalizedGradeFilter, setOpsMarketCompsNormalizedGradeFilter] = useState("");
  const [opsMarketCompsCurrencyFilter, setOpsMarketCompsCurrencyFilter] = useState("");
  const [opsMarketCompsSaleDateFromFilter, setOpsMarketCompsSaleDateFromFilter] = useState("");
  const [opsMarketCompsSaleDateToFilter, setOpsMarketCompsSaleDateToFilter] = useState("");
  const [opsMarketCompsIncludeExcluded, setOpsMarketCompsIncludeExcluded] = useState(true);
  const [opsMarketFmv, setOpsMarketFmv] = useState<MarketFmvSnapshotListResponse | null>(null);
  const [opsMarketFmvLoading, setOpsMarketFmvLoading] = useState(true);
  const [opsMarketFmvError, setOpsMarketFmvError] = useState<string | null>(null);
  const [opsMarketFmvScopeFilter, setOpsMarketFmvScopeFilter] = useState<"" | MarketFmvSnapshotScope>("");
  const [opsMarketFmvConfidenceFilter, setOpsMarketFmvConfidenceFilter] =
    useState<"" | MarketFmvConfidenceBucket>("");
  const [opsMarketFmvLiquidityFilter, setOpsMarketFmvLiquidityFilter] =
    useState<"" | MarketFmvLiquidityBucket>("");
  const [opsMarketFmvStaleFilter, setOpsMarketFmvStaleFilter] = useState<"" | "true" | "false">("");
  const [opsMarketFmvCurrencyFilter, setOpsMarketFmvCurrencyFilter] = useState("");
  const [opsMarketFmvGradingCompanyFilter, setOpsMarketFmvGradingCompanyFilter] = useState("");
  const [opsMarketFmvNormalizedGradeFilter, setOpsMarketFmvNormalizedGradeFilter] = useState("");
  const [opsMarketFmvSelectedId, setOpsMarketFmvSelectedId] = useState<number | null>(null);
  const [opsMarketFmvDetail, setOpsMarketFmvDetail] = useState<MarketFmvSnapshotRead | null>(null);
  const [opsMarketFmvDetailLoading, setOpsMarketFmvDetailLoading] = useState(false);
  const [opsMarketFmvDetailError, setOpsMarketFmvDetailError] = useState<string | null>(null);
  const [opsMarketFmvGenerateBusy, setOpsMarketFmvGenerateBusy] = useState(false);
  const [opsMarketFmvGenerateSummary, setOpsMarketFmvGenerateSummary] = useState<MarketFmvGenerateResponse | null>(null);
  const [opsMarketFmvRefreshTick, setOpsMarketFmvRefreshTick] = useState(0);
  const [opsMarketTrends, setOpsMarketTrends] = useState<MarketTrendSnapshotListResponse | null>(null);
  const [opsMarketTrendsLoading, setOpsMarketTrendsLoading] = useState(true);
  const [opsMarketTrendsError, setOpsMarketTrendsError] = useState<string | null>(null);
  const [opsMarketTrendScopeFilter, setOpsMarketTrendScopeFilter] = useState<"" | MarketTrendSnapshotScope>("");
  const [opsMarketTrendDirectionFilter, setOpsMarketTrendDirectionFilter] =
    useState<"" | MarketTrendDirection>("");
  const [opsMarketTrendStrengthFilter, setOpsMarketTrendStrengthFilter] =
    useState<"" | MarketTrendStrength>("");
  const [opsMarketTrendLiquidityFilter, setOpsMarketTrendLiquidityFilter] =
    useState<"" | MarketTrendLiquidityDirection>("");
  const [opsMarketTrendStaleFilter, setOpsMarketTrendStaleFilter] = useState<"" | "true" | "false">("");
  const [opsMarketTrendCurrencyFilter, setOpsMarketTrendCurrencyFilter] = useState("");
  const [opsMarketTrendGradingCompanyFilter, setOpsMarketTrendGradingCompanyFilter] = useState("");
  const [opsMarketTrendGradeFilter, setOpsMarketTrendGradeFilter] = useState("");
  const [opsMarketTrendWindowFilter, setOpsMarketTrendWindowFilter] = useState<"" | MarketTrendWindow>("");
  const [opsMarketTrendSelectedId, setOpsMarketTrendSelectedId] = useState<number | null>(null);
  const [opsMarketTrendDetail, setOpsMarketTrendDetail] = useState<MarketTrendSnapshotRead | null>(null);
  const [opsMarketTrendDetailLoading, setOpsMarketTrendDetailLoading] = useState(false);
  const [opsMarketTrendDetailError, setOpsMarketTrendDetailError] = useState<string | null>(null);
  const [opsMarketTrendGenerateBusy, setOpsMarketTrendGenerateBusy] = useState(false);
  const [opsMarketTrendGenerateSummary, setOpsMarketTrendGenerateSummary] =
    useState<MarketTrendGenerateResponse | null>(null);
  const [opsMarketTrendsRefreshTick, setOpsMarketTrendsRefreshTick] = useState(0);
  const [opsMarketMatchSuggestionsRefreshTick, setOpsMarketMatchSuggestionsRefreshTick] = useState(0);
  const [opsMarketMatchSuggestions, setOpsMarketMatchSuggestions] =
    useState<MarketSaleMatchSuggestionOpsListResponse | null>(null);
  const [opsMarketMatchSuggestionsLoading, setOpsMarketMatchSuggestionsLoading] = useState(true);
  const [opsMarketMatchSuggestionsError, setOpsMarketMatchSuggestionsError] = useState<string | null>(null);
  const [opsMarketMatchSuggestionSourceFilter, setOpsMarketMatchSuggestionSourceFilter] = useState("");
  const [opsMarketMatchSuggestionConfidenceFilter, setOpsMarketMatchSuggestionConfidenceFilter] =
    useState<"" | MarketSaleMatchSuggestionConfidenceBucket>("");
  const [opsMarketMatchSuggestionReviewFilter, setOpsMarketMatchSuggestionReviewFilter] =
    useState<"" | MarketSaleMatchSuggestionReviewState>("");
  const [opsMarketMatchSuggestionTypeFilter, setOpsMarketMatchSuggestionTypeFilter] =
    useState<"" | MarketSaleMatchSuggestionType>("");
  const [opsMarketMatchSuggestionSelectedId, setOpsMarketMatchSuggestionSelectedId] = useState<number | null>(null);
  const [opsMarketMatchSuggestionBusyId, setOpsMarketMatchSuggestionBusyId] = useState<number | null>(null);

  const [opsScanSessions, setOpsScanSessions] = useState<ScanSessionSummary[]>([]);
  const [opsScanSessionsLoading, setOpsScanSessionsLoading] = useState(true);
  const [opsScanSessionsError, setOpsScanSessionsError] = useState<string | null>(null);
  const [opsScanSessionSelectedId, setOpsScanSessionSelectedId] = useState<number | null>(null);
  const [opsScanSessionDetail, setOpsScanSessionDetail] = useState<ScanSessionDetail | null>(null);
  const [opsScanSessionDetailLoading, setOpsScanSessionDetailLoading] = useState(false);

  const [opsHrStats, setOpsHrStats] = useState<HighResReviewRequestStatsRead | null>(null);
  const [opsHrList, setOpsHrList] = useState<HighResReviewRequestSummary[]>([]);
  const [opsHrLoading, setOpsHrLoading] = useState(true);
  const [opsHrError, setOpsHrError] = useState<string | null>(null);
  const [opsHrStatusFilter, setOpsHrStatusFilter] = useState("");
  const [opsHrPriorityFilter, setOpsHrPriorityFilter] = useState("");
  const [opsHrReasonFilter, setOpsHrReasonFilter] = useState("");
  const [opsHrOwnerUserIdDraft, setOpsHrOwnerUserIdDraft] = useState("");

  const [opsScanQaFleet, setOpsScanQaFleet] = useState<OpsScanQaFleetSummaryRead | null>(null);
  const [opsScanQaFleetLoading, setOpsScanQaFleetLoading] = useState(true);
  const [opsScanQaFleetError, setOpsScanQaFleetError] = useState<string | null>(null);

  const [opsScanPipelineReplays, setOpsScanPipelineReplays] = useState<ScanPipelineReplayRunRead[]>([]);
  const [opsScanPipelineReplaysLoading, setOpsScanPipelineReplaysLoading] = useState(true);
  const [opsScanPipelineReplaysError, setOpsScanPipelineReplaysError] = useState<string | null>(null);
  const [opsScanPipelineReplaySelectedId, setOpsScanPipelineReplaySelectedId] = useState<number | null>(null);
  const [opsScanPipelineReplayDetail, setOpsScanPipelineReplayDetail] = useState<ScanPipelineReplayRunRead | null>(null);
  const [opsScanPipelineReplayDetailLoading, setOpsScanPipelineReplayDetailLoading] = useState(false);

  const [opsRouting, setOpsRouting] = useState<QueueRoutingListResponse | null>(null);
  const [opsRoutingLoading, setOpsRoutingLoading] = useState(true);
  const [opsRoutingError, setOpsRoutingError] = useState<string | null>(null);

  const handleGenerateMarketFmv = useCallback(async () => {
    setOpsMarketFmvGenerateBusy(true);
    setOpsMarketFmvError(null);
    try {
      const response = await apiClient.generateOpsMarketFmvSnapshots();
      setOpsMarketFmvGenerateSummary(response);
      setOpsMarketFmvRefreshTick((cur) => cur + 1);
    } catch (generateErr) {
      setOpsMarketFmvGenerateSummary(null);
      setOpsMarketFmvError(generateErr instanceof ApiError ? generateErr.message : "Unable to generate market FMV snapshots.");
    } finally {
      setOpsMarketFmvGenerateBusy(false);
    }
  }, []);

  const handleGenerateMarketTrends = useCallback(async () => {
    setOpsMarketTrendGenerateBusy(true);
    setOpsMarketTrendsError(null);
    try {
      const response = await apiClient.generateOpsMarketTrends();
      setOpsMarketTrendGenerateSummary(response);
      setOpsMarketTrendsRefreshTick((cur) => cur + 1);
    } catch (generateErr) {
      setOpsMarketTrendGenerateSummary(null);
      setOpsMarketTrendsError(generateErr instanceof ApiError ? generateErr.message : "Unable to generate market trend snapshots.");
    } finally {
      setOpsMarketTrendGenerateBusy(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;

    async function loadDashboardAndAliases() {
      setIsLoading(true);
      setInventoryFmvLoading(true);
      setError(null);
      setInventoryFmvError(null);
      try {
        const [dashboardResponse, aliases, portfolioSummary, fmvCoverage, lowConfidence, stale, noMarketData] = await Promise.all([
          apiClient.getOpsDashboard(),
          apiClient.listMetadataAliases(),
          apiClient.getOpsPortfolioValueSummary(),
          apiClient.getOpsInventoryFmvList({ page: 1, page_size: 25 }),
          apiClient.getOpsInventoryFmvList({ page: 1, page_size: 12, confidence_bucket: "low" }),
          apiClient.getOpsInventoryFmvList({ page: 1, page_size: 12, stale_data: true }),
          apiClient.getOpsInventoryFmvList({ page: 1, page_size: 12, valuation_scope: "no_market_data" }),
        ]);
        if (!ignore) {
          setDashboard(dashboardResponse);
          setMetadataAliases(aliases);
          setPortfolioValueSummary(portfolioSummary);
          setInventoryFmvCoverage(fmvCoverage);
          setInventoryFmvLowConfidence(lowConfidence);
          setInventoryFmvStale(stale);
          setInventoryFmvNoMarketData(noMarketData);
          void apiClient.listRecentCoverLinkDecisionsForOps({ include_inactive: true, limit: 12 }).then(setCoverLinkDecisions);
        }
      } catch (loadError) {
        if (!ignore) {
          setInventoryFmvError(
            loadError instanceof ApiError
              ? loadError.message
              : "Unable to load FMV coverage dashboard.",
          );
          setError(
            loadError instanceof ApiError
              ? loadError.message
              : "Unable to load operations dashboard.",
          );
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
          setInventoryFmvLoading(false);
        }
      }
    }

    void loadDashboardAndAliases();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsScanSessionsLoading(true);
      setOpsScanSessionsError(null);
      try {
        const list = await apiClient.listOpsScanSessions({ limit: 250 });
        if (!ignore) {
          setOpsScanSessions(list.sessions);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsScanSessions([]);
          setOpsScanSessionsError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load ops scan sessions.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsScanSessionsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsScanPipelineDashLoading(true);
      setOpsScanPipelineDashError(null);
      try {
        const dash = await apiClient.getOpsScanPipelineDashboard();
        if (!ignore) {
          setOpsScanPipelineDash(dash);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsScanPipelineDash(null);
          setOpsScanPipelineDashError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load bulk ingest pipeline dashboard.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsScanPipelineDashLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsSalesLedgerLoading(true);
      setOpsSalesLedgerError(null);
      try {
        const list = await apiClient.getOpsSales({ limit: 100 });
        if (!ignore) {
          setOpsSalesLedger(list.items);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsSalesLedger([]);
          setOpsSalesLedgerError(loadErr instanceof ApiError ? loadErr.message : "Unable to load sales ledger.");
        }
      } finally {
        if (!ignore) {
          setOpsSalesLedgerLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsMarketIngestionLoading(true);
      setOpsMarketIngestionError(null);
      try {
        const summary = await apiClient.listOpsMarketIngestionBatches({ limit: 60, offset: 0 });
        if (!ignore) {
          setOpsMarketIngestionSummary(summary);
          setOpsMarketIngestionSelectedId((cur) => cur ?? summary.items[0]?.id ?? null);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketIngestionSummary(null);
          setOpsMarketIngestionSelectedId(null);
          setOpsMarketIngestionError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load market ingestion batches.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketIngestionLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      if (!opsMarketIngestionSelectedId) {
        if (!ignore) {
          setOpsMarketIngestionDetail(null);
          setOpsMarketIngestionRaw([]);
          setOpsMarketIngestionDetailLoading(false);
          setOpsMarketIngestionDetailError(null);
        }
        return;
      }
      setOpsMarketIngestionDetailLoading(true);
      setOpsMarketIngestionDetailError(null);
      try {
        const [detail, raw] = await Promise.all([
          apiClient.getOpsMarketIngestionBatch(opsMarketIngestionSelectedId),
          apiClient.listOpsMarketIngestionRaw({ ingestion_batch_id: opsMarketIngestionSelectedId, limit: 200, offset: 0 }),
        ]);
        if (!ignore) {
          setOpsMarketIngestionDetail(detail);
          setOpsMarketIngestionRaw(raw.items);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketIngestionDetail(null);
          setOpsMarketIngestionRaw([]);
          setOpsMarketIngestionDetailError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load market ingestion detail.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketIngestionDetailLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsMarketIngestionSelectedId]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsMarketNormLoading(true);
      setOpsMarketNormError(null);
      const scoped = opsPortfolioOwnerApplied === undefined ? {} : { owner_user_id: opsPortfolioOwnerApplied };
      try {
        const summary = await apiClient.listOpsMarketNormalizationRuns({ limit: 80, offset: 0, ...scoped });
        if (!ignore) {
          setOpsMarketNormSummary(summary);
          setOpsMarketNormSelectedId((cur) => cur ?? summary.items[0]?.id ?? null);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketNormSummary(null);
          setOpsMarketNormSelectedId(null);
          setOpsMarketNormError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load market normalization runs.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketNormLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsPortfolioOwnerApplied]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      if (!opsMarketNormSelectedId || !opsMarketNormSummary) {
        if (!ignore) {
          setOpsMarketNormDetail(null);
          setOpsMarketNormCandidates([]);
          setOpsMarketNormIssues([]);
          setOpsMarketNormDetailLoading(false);
          setOpsMarketNormDetailError(null);
        }
        return;
      }
      const runRow = opsMarketNormSummary.items.find((item) => item.id === opsMarketNormSelectedId);
      if (!runRow) {
        if (!ignore) {
          setOpsMarketNormDetail(null);
          setOpsMarketNormCandidates([]);
          setOpsMarketNormIssues([]);
          setOpsMarketNormDetailLoading(false);
          setOpsMarketNormDetailError("Selected normalization run is no longer available.");
        }
        return;
      }
      const scoped = opsPortfolioOwnerApplied === undefined ? {} : { owner_user_id: opsPortfolioOwnerApplied };
      const batchId = runRow.ingestion_batch_id;
      setOpsMarketNormDetailLoading(true);
      setOpsMarketNormDetailError(null);
      try {
        const [detail, cands, iss] = await Promise.all([
          apiClient.getOpsMarketNormalizationRun(opsMarketNormSelectedId),
          apiClient.listOpsMarketNormalizationCandidates({
            ...scoped,
            ingestion_batch_id: batchId,
            limit: 100,
            offset: 0,
          }),
          apiClient.listOpsMarketNormalizationIssues({
            ...scoped,
            ingestion_batch_id: batchId,
            limit: 100,
            offset: 0,
          }),
        ]);
        if (!ignore) {
          setOpsMarketNormDetail(detail);
          setOpsMarketNormCandidates(cands.items);
          setOpsMarketNormIssues(iss.items);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketNormDetail(null);
          setOpsMarketNormCandidates([]);
          setOpsMarketNormIssues([]);
          setOpsMarketNormDetailError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load normalization drill-down.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketNormDetailLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsMarketNormSelectedId, opsPortfolioOwnerApplied, opsMarketNormSummary?.items]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsMarketScoringLoading(true);
      setOpsMarketScoringError(null);
      const scoped = opsPortfolioOwnerApplied === undefined ? {} : { owner_user_id: opsPortfolioOwnerApplied };
      try {
        const summary = await apiClient.listOpsMarketScoringSnapshots({ limit: 40, offset: 0, ...scoped });
        if (!ignore) {
          setOpsMarketScoringSummary(summary);
          setOpsMarketScoringSelectedId((cur) => cur ?? summary.items[0]?.id ?? null);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketScoringSummary(null);
          setOpsMarketScoringSelectedId(null);
          setOpsMarketScoringError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load market scoring snapshots.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketScoringLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsPortfolioOwnerApplied]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      if (!opsMarketScoringSelectedId || !opsMarketScoringSummary) {
        if (!ignore) {
          setOpsMarketScoringScores([]);
          setOpsMarketScoringHistory([]);
          setOpsMarketScoringDetail(null);
          setOpsMarketScoringDetailLoading(false);
          setOpsMarketScoringDetailError(null);
        }
        return;
      }
      setOpsMarketScoringDetailLoading(true);
      setOpsMarketScoringDetailError(null);
      const scoped = opsPortfolioOwnerApplied === undefined ? {} : { owner_user_id: opsPortfolioOwnerApplied };
      try {
        const [scores, history] = await Promise.all([
          apiClient.listOpsMarketScoringScores({ ...scoped, limit: 200, offset: 0 }),
          apiClient.listOpsMarketScoringHistory({ ...scoped, limit: 80, offset: 0 }),
        ]);
        const scopedScores = scores.items.filter(
          (row) => row.market_acquisition_score_snapshot_id === opsMarketScoringSelectedId,
        );
        const leadScore = scopedScores[0] ?? null;
        const detail = leadScore ? await apiClient.getOpsMarketScoringScore(leadScore.id) : null;
        if (!ignore) {
          setOpsMarketScoringScores(scopedScores);
          setOpsMarketScoringHistory(history.items.filter((row) => row.snapshot_date === leadScore?.snapshot_date));
          setOpsMarketScoringDetail(detail);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketScoringScores([]);
          setOpsMarketScoringHistory([]);
          setOpsMarketScoringDetail(null);
          setOpsMarketScoringDetailError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load market scoring drill-down.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketScoringDetailLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsMarketScoringSelectedId, opsMarketScoringSummary, opsPortfolioOwnerApplied]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsMarketSignalLoading(true);
      setOpsMarketSignalError(null);
      const scoped = opsPortfolioOwnerApplied === undefined ? {} : { owner_user_id: opsPortfolioOwnerApplied };
      try {
        const summary = await apiClient.listOpsMarketSignalSnapshots({ limit: 40, offset: 0, ...scoped });
        if (!ignore) {
          setOpsMarketSignalSummary(summary);
          setOpsMarketSignalSelectedId((cur) => cur ?? summary.items[0]?.id ?? null);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketSignalSummary(null);
          setOpsMarketSignalSelectedId(null);
          setOpsMarketSignalError(loadErr instanceof ApiError ? loadErr.message : "Unable to load market signal snapshots.");
        }
      } finally {
        if (!ignore) {
          setOpsMarketSignalLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsPortfolioOwnerApplied]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      if (!opsMarketSignalSelectedId || !opsMarketSignalSummary) {
        if (!ignore) {
          setOpsMarketSignals([]);
          setOpsMarketSignalHistory([]);
          setOpsMarketSignalDetail(null);
          setOpsMarketSignalEvidence([]);
          setOpsMarketSignalDetailLoading(false);
          setOpsMarketSignalDetailError(null);
        }
        return;
      }
      setOpsMarketSignalDetailLoading(true);
      setOpsMarketSignalDetailError(null);
      const scoped = opsPortfolioOwnerApplied === undefined ? {} : { owner_user_id: opsPortfolioOwnerApplied };
      try {
        const [signals, history, evidence] = await Promise.all([
          apiClient.listOpsMarketSignals({ ...scoped, limit: 200, offset: 0 }),
          apiClient.listOpsMarketSignalHistory({ ...scoped, limit: 80, offset: 0 }),
          apiClient.listOpsMarketSignalEvidence({ ...scoped, limit: 240, offset: 0 }),
        ]);
        const scopedSignals = signals.items.filter((row) => row.market_acquisition_signal_snapshot_id === opsMarketSignalSelectedId);
        const leadSignal = scopedSignals[0] ?? null;
        const detail = leadSignal ? await apiClient.getOpsMarketSignal(leadSignal.id) : null;
        if (!ignore) {
          setOpsMarketSignals(scopedSignals);
          setOpsMarketSignalHistory(history.items.filter((row) => row.snapshot_date === leadSignal?.snapshot_date));
          setOpsMarketSignalDetail(detail);
          setOpsMarketSignalEvidence(
            evidence.items.filter((row) => !leadSignal || row.market_acquisition_signal_id === leadSignal.id),
          );
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketSignals([]);
          setOpsMarketSignalHistory([]);
          setOpsMarketSignalDetail(null);
          setOpsMarketSignalEvidence([]);
          setOpsMarketSignalDetailError(loadErr instanceof ApiError ? loadErr.message : "Unable to load market signal drill-down.");
        }
      } finally {
        if (!ignore) {
          setOpsMarketSignalDetailLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsMarketSignalSelectedId, opsMarketSignalSummary, opsPortfolioOwnerApplied]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsMarketOpportunityLoading(true);
      setOpsMarketOpportunityError(null);
      const scoped = opsPortfolioOwnerApplied === undefined ? {} : { owner_user_id: opsPortfolioOwnerApplied };
      try {
        const summary = await apiClient.listOpsMarketOpportunitySnapshots({ limit: 40, offset: 0, ...scoped });
        if (!ignore) {
          setOpsMarketOpportunitySummary(summary);
          setOpsMarketOpportunitySelectedId((cur) => cur ?? summary.items[0]?.id ?? null);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketOpportunitySummary(null);
          setOpsMarketOpportunitySelectedId(null);
          setOpsMarketOpportunityError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load market opportunity snapshots.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketOpportunityLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsPortfolioOwnerApplied]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      if (!opsMarketOpportunitySelectedId || !opsMarketOpportunitySummary) {
        if (!ignore) {
          setOpsMarketOpportunityItems([]);
          setOpsMarketOpportunityEvidence([]);
          setOpsMarketOpportunityHistory([]);
          setOpsMarketOpportunityDetail(null);
          setOpsMarketOpportunityDetailLoading(false);
          setOpsMarketOpportunityDetailError(null);
        }
        return;
      }
      setOpsMarketOpportunityDetailLoading(true);
      setOpsMarketOpportunityDetailError(null);
      const scoped = opsPortfolioOwnerApplied === undefined ? {} : { owner_user_id: opsPortfolioOwnerApplied };
      try {
        const [itemsResp, evidence, history, snapDetail] = await Promise.all([
          apiClient.listOpsMarketOpportunityItems({
            ...scoped,
            opportunity_snapshot_id: opsMarketOpportunitySelectedId,
            limit: 200,
            offset: 0,
          }),
          apiClient.listOpsMarketOpportunityEvidence({
            ...scoped,
            opportunity_snapshot_id: opsMarketOpportunitySelectedId,
            limit: 80,
            offset: 0,
          }),
          apiClient.listOpsMarketOpportunityHistory({
            ...scoped,
            opportunity_snapshot_id: opsMarketOpportunitySelectedId,
            limit: 80,
            offset: 0,
          }),
          apiClient.getOpsMarketOpportunitySnapshot(opsMarketOpportunitySelectedId),
        ]);
        const leadSnap = opsMarketOpportunitySummary.items.find((row) => row.id === opsMarketOpportunitySelectedId);
        const snapshotDate = leadSnap?.snapshot_date;
        if (!ignore) {
          setOpsMarketOpportunityItems(itemsResp.items);
          setOpsMarketOpportunityEvidence(evidence.items);
          setOpsMarketOpportunityHistory(
            history.items.filter((row) => !snapshotDate || row.snapshot_date === snapshotDate),
          );
          setOpsMarketOpportunityDetail(snapDetail);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketOpportunityItems([]);
          setOpsMarketOpportunityEvidence([]);
          setOpsMarketOpportunityHistory([]);
          setOpsMarketOpportunityDetail(null);
          setOpsMarketOpportunityDetailError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load market opportunity drill-down.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketOpportunityDetailLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsMarketOpportunitySelectedId, opsMarketOpportunitySummary, opsPortfolioOwnerApplied]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsPortfolioCouplingLoading(true);
      setOpsPortfolioCouplingError(null);
      const scoped = opsPortfolioOwnerApplied === undefined ? {} : { owner_user_id: opsPortfolioOwnerApplied };
      try {
        const summary = await apiClient.listOpsPortfolioMarketCouplingSnapshots({ limit: 40, offset: 0, ...scoped });
        if (!ignore) {
          setOpsPortfolioCouplingSummary(summary);
          setOpsPortfolioCouplingSelectedId((cur) => cur ?? summary.items[0]?.id ?? null);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsPortfolioCouplingSummary(null);
          setOpsPortfolioCouplingSelectedId(null);
          setOpsPortfolioCouplingError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load portfolio-market coupling snapshots.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsPortfolioCouplingLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsPortfolioOwnerApplied]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      if (!opsPortfolioCouplingSelectedId || !opsPortfolioCouplingSummary) {
        if (!ignore) {
          setOpsPortfolioCouplingDetail(null);
          setOpsPortfolioCouplingEdges([]);
          setOpsPortfolioCouplingHistory([]);
          setOpsPortfolioCouplingDetailLoading(false);
          setOpsPortfolioCouplingDetailError(null);
        }
        return;
      }
      setOpsPortfolioCouplingDetailLoading(true);
      setOpsPortfolioCouplingDetailError(null);
      const scoped = opsPortfolioOwnerApplied === undefined ? {} : { owner_user_id: opsPortfolioOwnerApplied };
      try {
        const [detail, edges, history] = await Promise.all([
          apiClient.getOpsPortfolioMarketCouplingSnapshot(opsPortfolioCouplingSelectedId, scoped),
          apiClient.listOpsPortfolioMarketCouplingEdges({
            ...scoped,
            coupling_snapshot_id: opsPortfolioCouplingSelectedId,
            limit: 200,
            offset: 0,
          }),
          apiClient.listOpsPortfolioMarketCouplingHistory({
            ...scoped,
            coupling_snapshot_id: opsPortfolioCouplingSelectedId,
            limit: 40,
            offset: 0,
          }),
        ]);
        if (!ignore) {
          setOpsPortfolioCouplingDetail(detail);
          setOpsPortfolioCouplingEdges(edges.items);
          setOpsPortfolioCouplingHistory(history.items);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsPortfolioCouplingDetail(null);
          setOpsPortfolioCouplingEdges([]);
          setOpsPortfolioCouplingHistory([]);
          setOpsPortfolioCouplingDetailError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load coupling drill-down.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsPortfolioCouplingDetailLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsPortfolioCouplingSelectedId, opsPortfolioCouplingSummary, opsPortfolioOwnerApplied]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsMarketSalesLoading(true);
      setOpsMarketSalesError(null);
      try {
        const list = await apiClient.getOpsMarketSales();
        if (!ignore) {
          setOpsMarketSales(list.items);
          setOpsMarketSaleSelectedId((cur) => cur ?? list.items[0]?.id ?? null);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketSales([]);
          setOpsMarketSaleSelectedId(null);
          setOpsMarketSalesError(loadErr instanceof ApiError ? loadErr.message : "Unable to load market sales.");
        }
      } finally {
        if (!ignore) {
          setOpsMarketSalesLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsMarketSalesRefreshTick]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsListingDistributionLoading(true);
      setOpsListingDistributionError(null);
      try {
        const distribution = await apiClient.getOpsListingStatusDistribution();
        if (!ignore) {
          setOpsListingDistribution(distribution);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsListingDistribution(null);
          setOpsListingDistributionError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load listing distribution.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsListingDistributionLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsListingEventsFeedLoading(true);
      setOpsListingEventsFeedError(null);
      try {
        const feed = await apiClient.getOpsListingLifecycleEvents({ limit: 40, offset: 0 });
        if (!ignore) {
          setOpsListingEventsFeed(feed);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsListingEventsFeed(null);
          setOpsListingEventsFeedError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load listing lifecycle events.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsListingEventsFeedLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsListingIntelligenceSummaryLoading(true);
      setOpsListingIntelligenceSummaryError(null);
      setOpsListingIntelligenceSnapshotsLoading(true);
      setOpsListingIntelligenceSnapshotsError(null);
      setOpsListingIntelligenceChecksLoading(true);
      setOpsListingIntelligenceChecksError(null);
      setOpsListingIntelligenceEvidenceLoading(true);
      setOpsListingIntelligenceEvidenceError(null);
      setOpsListingIntelligenceChannelPerfLoading(true);
      setOpsListingIntelligenceChannelPerfError(null);
      try {
        const [summary, snapshots, checks, evidence, channelPerf] = await Promise.all([
          apiClient.getOpsListingIntelligenceDashboardSummary({}),
          apiClient.getOpsListingIntelligence({ limit: 25, offset: 0 }),
          apiClient.getOpsListingCompletenessChecks({ limit: 25, offset: 0 }),
          apiClient.getOpsListingIntelligenceEvidence({ limit: 25, offset: 0 }),
          apiClient.getOpsListingChannelPerformance({ limit: 25, offset: 0 }),
        ]);
        if (!ignore) {
          setOpsListingIntelligenceSummary(summary);
          setOpsListingIntelligenceSnapshots(snapshots.items);
          setOpsListingIntelligenceChecks(checks.items);
          setOpsListingIntelligenceEvidence(evidence.items);
          setOpsListingIntelligenceChannelPerf(channelPerf.items);
        }
      } catch (loadErr) {
        if (!ignore) {
          const errorMessage =
            loadErr instanceof ApiError ? loadErr.message : "Unable to load listing intelligence operations.";
          setOpsListingIntelligenceSummary(null);
          setOpsListingIntelligenceSummaryError(errorMessage);
          setOpsListingIntelligenceSnapshots([]);
          setOpsListingIntelligenceSnapshotsError(errorMessage);
          setOpsListingIntelligenceChecks([]);
          setOpsListingIntelligenceChecksError(errorMessage);
          setOpsListingIntelligenceEvidence([]);
          setOpsListingIntelligenceEvidenceError(errorMessage);
          setOpsListingIntelligenceChannelPerf([]);
          setOpsListingIntelligenceChannelPerfError(errorMessage);
        }
      } finally {
        if (!ignore) {
          setOpsListingIntelligenceSummaryLoading(false);
          setOpsListingIntelligenceSnapshotsLoading(false);
          setOpsListingIntelligenceChecksLoading(false);
          setOpsListingIntelligenceEvidenceLoading(false);
          setOpsListingIntelligenceChannelPerfLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsDealerDashLoading(true);
      setOpsDealerDashError(null);
      try {
        const scoped = opsDealerOwnerApplied === undefined ? {} : { owner_user_id: opsDealerOwnerApplied };
        const [dash, alerts, feed, metrics] = await Promise.all([
          apiClient.getOpsDealerDashboard(scoped),
          apiClient.listOpsDealerDashboardAlerts({ ...scoped, limit: 50, offset: 0 }),
          apiClient.listOpsDealerDashboardFeed({ ...scoped, limit: 50, offset: 0 }),
          apiClient.listOpsDealerDashboardMetrics({ ...scoped, limit: 100, offset: 0 }),
        ]);
        if (!ignore) {
          setOpsDealerDash(dash);
          setOpsDealerAlerts(alerts.items);
          setOpsDealerFeed(feed.items);
          setOpsDealerMetrics(metrics.items);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsDealerDash(null);
          setOpsDealerAlerts([]);
          setOpsDealerFeed([]);
          setOpsDealerMetrics([]);
          setOpsDealerDashError(loadErr instanceof ApiError ? loadErr.message : "Unable to load dealer dashboard ops payloads.");
        }
      } finally {
        if (!ignore) {
          setOpsDealerDashLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsDealerOwnerApplied]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsDealerGradingDashLoading(true);
      setOpsDealerGradingDashError(null);
      try {
        const scoped = opsDealerGradingOwnerApplied === undefined ? {} : { owner_user_id: opsDealerGradingOwnerApplied };
        const [dash, alerts, feed, metrics] = await Promise.all([
          apiClient.getOpsDealerGradingDashboard(scoped),
          apiClient.listOpsDealerGradingDashboardAlerts({ ...scoped, limit: 50, offset: 0 }),
          apiClient.listOpsDealerGradingDashboardFeed({ ...scoped, limit: 50, offset: 0 }),
          apiClient.listOpsDealerGradingDashboardMetrics({ ...scoped, limit: 100, offset: 0 }),
        ]);
        if (!ignore) {
          setOpsDealerGradingDash(dash);
          setOpsDealerGradingAlerts(alerts.items);
          setOpsDealerGradingFeed(feed.items);
          setOpsDealerGradingMetrics(metrics.items);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsDealerGradingDash(null);
          setOpsDealerGradingAlerts([]);
          setOpsDealerGradingFeed([]);
          setOpsDealerGradingMetrics([]);
          setOpsDealerGradingDashError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load grading dashboard ops telescope.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsDealerGradingDashLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsDealerGradingOwnerApplied]);

  useEffect(() => {
    void loadOpsStrategyDashboard();
  }, [loadOpsStrategyDashboard]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsPortfolioLoading(true);
      setOpsPortfolioError(null);
      setOpsPortfolioRecommendationLoading(true);
      setOpsPortfolioRecommendationError(null);
      setOpsAcquisitionPriorityLoading(true);
      setOpsAcquisitionPriorityError(null);
      setOpsConcentrationRiskLoading(true);
      setOpsConcentrationRiskError(null);
      try {
        const scoped = opsPortfolioOwnerApplied === undefined ? {} : { owner_user_id: opsPortfolioOwnerApplied };
        const dupScoped = {
          ...scoped,
          latest_only: opsPortfolioOwnerApplied !== undefined,
          limit: 200,
          offset: 0,
        };
        const [
          portfolios,
          items,
          exposures,
          evidence,
          allocations,
          dupClusters,
          dupItems,
          dupRecos,
          dupHist,
          liqList,
          liqHist,
          recList,
          recHist,
          acqList,
          acqHist,
          concList,
          concHist,
        ] =
          await Promise.all([
            apiClient.listOpsPortfolios({ ...scoped, limit: 75, offset: 0 }),
            apiClient.listOpsPortfolioItems({ ...scoped, limit: 150, offset: 0 }),
            apiClient.listOpsPortfolioExposures({ ...scoped, latest_batch: true, limit: 250, offset: 0 }),
            apiClient.listOpsPortfolioExposureEvidence({ ...scoped, limit: 200, offset: 0 }),
            apiClient.listOpsPortfolioAllocations({ ...scoped, limit: 75, offset: 0 }),
            apiClient.listOpsDuplicateClusters(dupScoped),
            apiClient.listOpsDuplicateClusterItems(dupScoped),
            apiClient.listOpsDuplicateConsolidationRecommendations(dupScoped),
            apiClient.listOpsDuplicateHistory(dupScoped),
            apiClient.listOpsPortfolioLiquidity(dupScoped),
            apiClient.listOpsPortfolioLiquidityHistory({ ...scoped, limit: 120, offset: 0 }),
            apiClient.listOpsPortfolioRecommendations({ ...scoped, limit: 200, offset: 0 }),
            apiClient.listOpsPortfolioRecommendationHistory({ ...scoped, limit: 200, offset: 0 }),
            apiClient.listOpsAcquisitionPriorities({ ...scoped, limit: 200, offset: 0 }),
            apiClient.listOpsAcquisitionPriorityHistory({ ...scoped, limit: 200, offset: 0 }),
            apiClient.listOpsConcentrationRisk({ ...scoped, limit: 200, offset: 0 }),
            apiClient.listOpsConcentrationRiskHistory({ ...scoped, limit: 200, offset: 0 }),
          ]);
        let liqDetail: PortfolioLiquiditySnapshotDetailResponse | null = null;
        let liqEvidence: PortfolioLiquidityEvidenceListResponse | null = null;
        const firstLiq = liqList.items[0];
        if (firstLiq) {
          liqDetail = await apiClient.getOpsPortfolioLiquiditySnapshot(firstLiq.id, scoped);
          liqEvidence = await apiClient.listOpsPortfolioLiquidityEvidence({
            ...scoped,
            portfolio_liquidity_snapshot_id: firstLiq.id,
            limit: 120,
            offset: 0,
          });
        }
        let recDetail: PortfolioRecommendationDetailRead | null = null;
        let recEvidence: PortfolioRecommendationEvidenceListResponse | null = null;
        const firstRec = recList.items[0];
        if (firstRec) {
          recDetail = await apiClient.getOpsPortfolioRecommendation(firstRec.id, scoped);
          recEvidence = await apiClient.listOpsPortfolioRecommendationEvidence({
            ...scoped,
            recommendation_id: firstRec.id,
            limit: 120,
            offset: 0,
          });
        }
        let acqDetail: AcquisitionPriorityDetailRead | null = null;
        let acqEvidence: AcquisitionPriorityEvidenceListResponse | null = null;
        const firstAcq = acqList.items[0];
        if (firstAcq) {
          acqDetail = await apiClient.getOpsAcquisitionPriority(firstAcq.id, scoped);
          acqEvidence = await apiClient.listOpsAcquisitionPriorityEvidence({
            ...scoped,
            acquisition_priority_snapshot_id: firstAcq.id,
            limit: 120,
            offset: 0,
          });
        }
        let concDetail: ConcentrationRiskDetailRead | null = null;
        let concEvidence: ConcentrationRiskEvidenceListResponse | null = null;
        let concFactors: ConcentrationRiskFactorListResponse | null = null;
        const firstConc = concList.items[0];
        if (firstConc) {
          concDetail = await apiClient.getOpsConcentrationRisk(firstConc.id, scoped);
          concEvidence = await apiClient.listOpsConcentrationRiskEvidence({
            ...scoped,
            concentration_risk_snapshot_id: firstConc.id,
            limit: 120,
            offset: 0,
          });
          concFactors = await apiClient.listOpsConcentrationRiskFactors({
            ...scoped,
            concentration_risk_snapshot_id: firstConc.id,
            limit: 120,
            offset: 0,
          });
        }
        if (!ignore) {
          setOpsPortfolioList(portfolios);
          setOpsPortfolioItems(items);
          setOpsPortfolioExposures(exposures);
          setOpsPortfolioEvidence(evidence);
          setOpsPortfolioAllocations(allocations);
          setOpsDuplicateClusters(dupClusters);
          setOpsDuplicateClusterItems(dupItems);
          setOpsDuplicateRecos(dupRecos);
          setOpsDuplicateHistory(dupHist);
          setOpsPortfolioLiquidityList(liqList);
          setOpsPortfolioLiquidityDetail(liqDetail);
          setOpsPortfolioLiquidityEvidence(liqEvidence);
          setOpsPortfolioLiquidityHistory(liqHist);
          setOpsPortfolioRecommendationList(recList);
          setOpsPortfolioRecommendationDetail(recDetail);
          setOpsPortfolioRecommendationEvidence(recEvidence);
          setOpsPortfolioRecommendationHistory(recHist);
          setOpsAcquisitionPriorityList(acqList);
          setOpsAcquisitionPriorityDetail(acqDetail);
          setOpsAcquisitionPriorityEvidence(acqEvidence);
          setOpsAcquisitionPriorityHistory(acqHist);
          setOpsConcentrationRiskList(concList);
          setOpsConcentrationRiskDetail(concDetail);
          setOpsConcentrationRiskEvidence(concEvidence);
          setOpsConcentrationRiskFactors(concFactors);
          setOpsConcentrationRiskHistory(concHist);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsPortfolioList(null);
          setOpsPortfolioItems(null);
          setOpsPortfolioExposures(null);
          setOpsPortfolioEvidence(null);
          setOpsPortfolioAllocations(null);
          setOpsDuplicateClusters(null);
          setOpsDuplicateClusterItems(null);
          setOpsDuplicateRecos(null);
          setOpsDuplicateHistory(null);
          setOpsPortfolioLiquidityList(null);
          setOpsPortfolioLiquidityDetail(null);
          setOpsPortfolioLiquidityEvidence(null);
          setOpsPortfolioLiquidityHistory(null);
          setOpsPortfolioRecommendationList(null);
          setOpsPortfolioRecommendationDetail(null);
          setOpsPortfolioRecommendationEvidence(null);
          setOpsPortfolioRecommendationHistory(null);
          setOpsAcquisitionPriorityList(null);
          setOpsAcquisitionPriorityDetail(null);
          setOpsAcquisitionPriorityEvidence(null);
          setOpsAcquisitionPriorityHistory(null);
          setOpsConcentrationRiskList(null);
          setOpsConcentrationRiskDetail(null);
          setOpsConcentrationRiskEvidence(null);
          setOpsConcentrationRiskFactors(null);
          setOpsConcentrationRiskHistory(null);
          setOpsPortfolioError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load portfolio registry ops payloads.",
          );
          setOpsPortfolioRecommendationError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load portfolio recommendation ops payloads.",
          );
          setOpsAcquisitionPriorityError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load acquisition priority ops payloads.",
          );
          setOpsConcentrationRiskError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load concentration risk ops payloads.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsPortfolioLoading(false);
          setOpsPortfolioRecommendationLoading(false);
          setOpsAcquisitionPriorityLoading(false);
          setOpsConcentrationRiskLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsPortfolioOwnerApplied]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsConventionSummaryLoading(true);
      setOpsConventionSummaryError(null);
      setOpsConventionEventsLoading(true);
      setOpsConventionEventsError(null);
      setOpsConventionAssignmentsLoading(true);
      setOpsConventionAssignmentsError(null);
      setOpsConventionMovementsLoading(true);
      setOpsConventionMovementsError(null);
      setOpsConventionPriceSnapshotsLoading(true);
      setOpsConventionPriceSnapshotsError(null);
      setOpsConventionSaleSessionsLoading(true);
      setOpsConventionSaleSessionsError(null);
      try {
        const [summary, events, assignments, movements, prices, sessions] = await Promise.all([
          apiClient.getOpsConventionDashboardSummary(),
          apiClient.getOpsConventionEvents({ limit: 25, offset: 0 }),
          apiClient.getOpsConventionAssignments({ limit: 25, offset: 0 }),
          apiClient.getOpsConventionMovements({ limit: 25, offset: 0 }),
          apiClient.getOpsConventionPriceSnapshots({ limit: 25, offset: 0 }),
          apiClient.getOpsConventionSaleSessions({ limit: 25, offset: 0 }),
        ]);
        if (!ignore) {
          setOpsConventionSummary(summary);
          setOpsConventionEvents(events);
          setOpsConventionAssignments(assignments);
          setOpsConventionMovements(movements);
          setOpsConventionPriceSnapshots(prices);
          setOpsConventionSaleSessions(sessions);
        }
      } catch (loadErr) {
        if (!ignore) {
          const errorMessage = loadErr instanceof ApiError ? loadErr.message : "Unable to load convention operations.";
          setOpsConventionSummary(null);
          setOpsConventionSummaryError(errorMessage);
          setOpsConventionEvents(null);
          setOpsConventionEventsError(errorMessage);
          setOpsConventionAssignments(null);
          setOpsConventionAssignmentsError(errorMessage);
          setOpsConventionMovements(null);
          setOpsConventionMovementsError(errorMessage);
          setOpsConventionPriceSnapshots(null);
          setOpsConventionPriceSnapshotsError(errorMessage);
          setOpsConventionSaleSessions(null);
          setOpsConventionSaleSessionsError(errorMessage);
        }
      } finally {
        if (!ignore) {
          setOpsConventionSummaryLoading(false);
          setOpsConventionEventsLoading(false);
          setOpsConventionAssignmentsLoading(false);
          setOpsConventionMovementsLoading(false);
          setOpsConventionPriceSnapshotsLoading(false);
          setOpsConventionSaleSessionsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsLiquiditySummaryLoading(true);
      setOpsLiquiditySummaryError(null);
      try {
        const summary = await apiClient.getOpsLiquidityDashboardSummary();
        if (!ignore) {
          setOpsLiquiditySummary(summary);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsLiquiditySummary(null);
          setOpsLiquiditySummaryError(loadErr instanceof ApiError ? loadErr.message : "Unable to load liquidity summary.");
        }
      } finally {
        if (!ignore) {
          setOpsLiquiditySummaryLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsLiquiditySnapshotsLoading(true);
      setOpsLiquiditySnapshotsError(null);
      try {
        const list = await apiClient.getOpsLiquidity({ limit: 100, offset: 0 });
        if (!ignore) {
          setOpsLiquiditySnapshots(list.items);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsLiquiditySnapshots([]);
          setOpsLiquiditySnapshotsError(loadErr instanceof ApiError ? loadErr.message : "Unable to load liquidity snapshots.");
        }
      } finally {
        if (!ignore) {
          setOpsLiquiditySnapshotsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsListingExportRunsLoading(true);
      setOpsListingExportRunsError(null);
      try {
        const rsp = await apiClient.getOpsListingExportRuns({ limit: 75, offset: 0 });
        if (!ignore) {
          setOpsListingExportRuns(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsListingExportRuns(null);
          setOpsListingExportRunsError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load listing export runs.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsListingExportRunsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsOperationalReportsLoading(true);
      setOpsOperationalReportsError(null);
      try {
        const rsp = await apiClient.getOpsOperationalReports({
          owner_user_id: opsOperationalOwnerFilter,
          limit: 75,
          offset: 0,
        });
        if (!ignore) {
          setOpsOperationalReports(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsOperationalReports(null);
          setOpsOperationalReportsError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load operational reports.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsOperationalReportsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsOperationalOwnerFilter]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsGradingReportsLoading(true);
      setOpsGradingReportsError(null);
      try {
        const rsp = await apiClient.getOpsGradingReports({
          owner_user_id: opsGradingReportsOwnerFilter,
          limit: 75,
          offset: 0,
        });
        if (!ignore) {
          setOpsGradingReports(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsGradingReports(null);
          setOpsGradingReportsError(loadErr instanceof ApiError ? loadErr.message : "Unable to load grading reports.");
        }
      } finally {
        if (!ignore) {
          setOpsGradingReportsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsGradingReportsOwnerFilter]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsGradingCandidatesLoading(true);
      setOpsGradingCandidatesError(null);
      try {
        const rsp = await apiClient.getOpsGradingCandidates({
          owner_user_id: opsGradingOwnerFilter,
          limit: 75,
          offset: 0,
        });
        if (!ignore) {
          setOpsGradingCandidates(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsGradingCandidates(null);
          setOpsGradingCandidatesError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load grading candidates.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsGradingCandidatesLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsGradingOwnerFilter]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsGradingSpreadsLoading(true);
      setOpsGradingSpreadsError(null);
      try {
        const rsp = await apiClient.getOpsGradingSpreads({
          owner_user_id: opsGradingOwnerFilter,
          limit: 75,
          offset: 0,
        });
        if (!ignore) {
          setOpsGradingSpreads(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsGradingSpreads(null);
          setOpsGradingSpreadsError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load grading spreads.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsGradingSpreadsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsGradingOwnerFilter]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsGradingRoiLoading(true);
      setOpsGradingRoiError(null);
      try {
        const rsp = await apiClient.getOpsGradingRoi({
          owner_user_id: opsGradingOwnerFilter,
          limit: 75,
          offset: 0,
        });
        if (!ignore) {
          setOpsGradingRoi(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsGradingRoi(null);
          setOpsGradingRoiError(loadErr instanceof ApiError ? loadErr.message : "Unable to load grading ROI.");
        }
      } finally {
        if (!ignore) {
          setOpsGradingRoiLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsGradingOwnerFilter]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsGradingSubmissionLoading(true);
      setOpsGradingSubmissionError(null);
      try {
        const rsp = await apiClient.listOpsGradingSubmissionBatches({
          owner_user_id: opsGradingOwnerFilter,
          limit: 75,
          offset: 0,
        });
        if (!ignore) {
          setOpsGradingSubmission(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsGradingSubmission(null);
          setOpsGradingSubmissionError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load grading submission batches.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsGradingSubmissionLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsGradingOwnerFilter]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsGradingRecommendationLoading(true);
      setOpsGradingRecommendationError(null);
      try {
        const rsp = await apiClient.listOpsGradingRecommendations({
          owner_user_id: opsGradingOwnerFilter,
          limit: 75,
          offset: 0,
        });
        if (!ignore) {
          setOpsGradingRecommendation(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsGradingRecommendation(null);
          setOpsGradingRecommendationError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load grading recommendations.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsGradingRecommendationLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsGradingOwnerFilter]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsGradingRiskLoading(true);
      setOpsGradingRiskError(null);
      try {
        const rsp = await apiClient.listOpsGradingRisk({
          owner_user_id: opsGradingOwnerFilter,
          limit: 75,
          offset: 0,
        });
        if (!ignore) {
          setOpsGradingRisk(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsGradingRisk(null);
          setOpsGradingRiskError(loadErr instanceof ApiError ? loadErr.message : "Unable to load grading risk.");
        }
      } finally {
        if (!ignore) {
          setOpsGradingRiskLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsGradingOwnerFilter]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsGradingReconciliationLoading(true);
      setOpsGradingReconciliationError(null);
      try {
        const rsp = await apiClient.listOpsGradingReconciliation({
          owner_user_id: opsGradingOwnerFilter,
          limit: 75,
          offset: 0,
        });
        if (!ignore) {
          setOpsGradingReconciliation(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsGradingReconciliation(null);
          setOpsGradingReconciliationError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load grading reconciliation.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsGradingReconciliationLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsGradingOwnerFilter]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsMarketSaleReviewQueueLoading(true);
      setOpsMarketSaleReviewQueueError(null);
      const params = {
        ...(opsMarketSaleReviewClassificationFilter ? { classification: opsMarketSaleReviewClassificationFilter } : {}),
        ...(opsMarketSaleReviewPriorityFilter ? { priority: opsMarketSaleReviewPriorityFilter } : {}),
        ...(opsMarketSaleReviewStatusFilter ? { review_status: opsMarketSaleReviewStatusFilter } : {}),
        ...(opsMarketSaleReviewSourceFilter.trim() ? { source: opsMarketSaleReviewSourceFilter.trim() } : {}),
        ...(opsMarketSaleReviewSourceTypeFilter.trim() ? { source_type: opsMarketSaleReviewSourceTypeFilter.trim() } : {}),
        ...(opsMarketSaleReviewIssueTypeFilter.trim() ? { issue_type: opsMarketSaleReviewIssueTypeFilter.trim() } : {}),
      };
      try {
        const [queue, summary] = await Promise.all([
          apiClient.getOpsMarketSaleReviewQueue(params),
          apiClient.getOpsMarketSaleReviewQueueSummary(params),
        ]);
        if (!ignore) {
          setOpsMarketSaleReviewQueue(queue);
          setOpsMarketSaleReviewQueueSummary(summary);
          setOpsMarketSaleSelectedId((cur) => cur ?? queue.items[0]?.id ?? null);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketSaleReviewQueue(null);
          setOpsMarketSaleReviewQueueSummary(null);
          setOpsMarketSaleReviewQueueError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load market sale review queue.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketSaleReviewQueueLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [
    opsMarketSaleReviewClassificationFilter,
    opsMarketSaleReviewPriorityFilter,
    opsMarketSaleReviewStatusFilter,
    opsMarketSaleReviewSourceFilter,
    opsMarketSaleReviewSourceTypeFilter,
    opsMarketSaleReviewIssueTypeFilter,
    opsMarketSaleReviewQueueRefreshTick,
  ]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsMarketCompEligibilityLoading(true);
      setOpsMarketCompEligibilityError(null);
      const params = {
        ...(opsMarketCompEligibilitySourceFilter.trim() ? { source: opsMarketCompEligibilitySourceFilter.trim() } : {}),
        ...(opsMarketCompEligibilityStatusFilter ? { eligibility_status: opsMarketCompEligibilityStatusFilter } : {}),
        ...(opsMarketCompEligibilityClassificationFilter
          ? { eligibility_classification: opsMarketCompEligibilityClassificationFilter }
          : {}),
        ...(opsMarketCompEligibilityGradingCompanyFilter.trim()
          ? { grading_company: opsMarketCompEligibilityGradingCompanyFilter.trim() }
          : {}),
        ...(opsMarketCompEligibilityIsGradedFilter
          ? { is_graded: opsMarketCompEligibilityIsGradedFilter === "true" }
          : {}),
        ...(opsMarketCompEligibilityCurrencyFilter.trim()
          ? { currency: opsMarketCompEligibilityCurrencyFilter.trim() }
          : {}),
        ...(opsMarketCompEligibilitySaleDateFromFilter.trim()
          ? { sale_date_from: opsMarketCompEligibilitySaleDateFromFilter.trim() }
          : {}),
        ...(opsMarketCompEligibilitySaleDateToFilter.trim()
          ? { sale_date_to: opsMarketCompEligibilitySaleDateToFilter.trim() }
          : {}),
      };
      try {
        const list = await apiClient.getOpsMarketCompEligibility(params);
        if (!ignore) {
          setOpsMarketCompEligibility(list);
          setOpsMarketCompEligibilitySelectedId((cur) =>
            cur != null && list.items.some((row) => row.id === cur) ? cur : list.items[0]?.id ?? null,
          );
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketCompEligibility(null);
          setOpsMarketCompEligibilitySelectedId(null);
          setOpsMarketCompEligibilityError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load market comp eligibility.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketCompEligibilityLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [
    opsMarketCompEligibilitySourceFilter,
    opsMarketCompEligibilityStatusFilter,
    opsMarketCompEligibilityClassificationFilter,
    opsMarketCompEligibilityGradingCompanyFilter,
    opsMarketCompEligibilityIsGradedFilter,
    opsMarketCompEligibilityCurrencyFilter,
    opsMarketCompEligibilitySaleDateFromFilter,
    opsMarketCompEligibilitySaleDateToFilter,
  ]);

  useEffect(() => {
    let ignore = false;
    if (opsMarketCompEligibilitySelectedId == null) {
      setOpsMarketCompEligibilityDetail(null);
      setOpsMarketCompEligibilityDetailError(null);
      setOpsMarketCompEligibilityDetailLoading(false);
      return undefined;
    }
    void (async () => {
      setOpsMarketCompEligibilityDetailLoading(true);
      setOpsMarketCompEligibilityDetailError(null);
      try {
        const detail = await apiClient.getOpsMarketSaleCompEligibility(opsMarketCompEligibilitySelectedId);
        if (!ignore) {
          setOpsMarketCompEligibilityDetail(detail);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketCompEligibilityDetail(null);
          setOpsMarketCompEligibilityDetailError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load market comp eligibility detail.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketCompEligibilityDetailLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsMarketCompEligibilitySelectedId]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsMarketCompsLoading(true);
      setOpsMarketCompsError(null);
      const identityKey = opsMarketCompsMetadataIdentityKeyFilter.trim();
      const params = {
        ...(opsMarketCompsSourceFilter.trim() ? { source: opsMarketCompsSourceFilter.trim() } : {}),
        ...(opsMarketCompsIsGradedFilter ? { is_graded: opsMarketCompsIsGradedFilter === "true" } : {}),
        ...(opsMarketCompsGradingCompanyFilter.trim() ? { grading_company: opsMarketCompsGradingCompanyFilter.trim() } : {}),
        ...(opsMarketCompsNormalizedGradeFilter.trim()
          ? { normalized_grade: opsMarketCompsNormalizedGradeFilter.trim() }
          : {}),
        ...(opsMarketCompsCurrencyFilter.trim() ? { currency: opsMarketCompsCurrencyFilter.trim() } : {}),
        ...(opsMarketCompsSaleDateFromFilter.trim() ? { sale_date_from: opsMarketCompsSaleDateFromFilter.trim() } : {}),
        ...(opsMarketCompsSaleDateToFilter.trim() ? { sale_date_to: opsMarketCompsSaleDateToFilter.trim() } : {}),
        include_excluded: opsMarketCompsIncludeExcluded,
      };
      try {
        const response = identityKey
          ? await apiClient.getOpsMarketCompsByIdentity(identityKey, params)
          : await apiClient.getOpsMarketComps(params);
        if (!ignore) {
          setOpsMarketComps(response);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketComps(null);
          setOpsMarketCompsError(loadErr instanceof ApiError ? loadErr.message : "Unable to load market comps.");
        }
      } finally {
        if (!ignore) {
          setOpsMarketCompsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [
    opsMarketCompsSourceFilter,
    opsMarketCompsMetadataIdentityKeyFilter,
    opsMarketCompsIsGradedFilter,
    opsMarketCompsGradingCompanyFilter,
    opsMarketCompsNormalizedGradeFilter,
    opsMarketCompsCurrencyFilter,
    opsMarketCompsSaleDateFromFilter,
    opsMarketCompsSaleDateToFilter,
    opsMarketCompsIncludeExcluded,
  ]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsMarketFmvLoading(true);
      setOpsMarketFmvError(null);
      const params = {
        ...(opsMarketFmvScopeFilter ? { snapshot_scope: opsMarketFmvScopeFilter } : {}),
        ...(opsMarketFmvConfidenceFilter ? { confidence_bucket: opsMarketFmvConfidenceFilter } : {}),
        ...(opsMarketFmvLiquidityFilter ? { liquidity_bucket: opsMarketFmvLiquidityFilter } : {}),
        ...(opsMarketFmvStaleFilter ? { stale_data: opsMarketFmvStaleFilter === "true" } : {}),
        ...(opsMarketFmvCurrencyFilter.trim() ? { currency: opsMarketFmvCurrencyFilter.trim() } : {}),
        ...(opsMarketFmvGradingCompanyFilter.trim() ? { grading_company: opsMarketFmvGradingCompanyFilter.trim() } : {}),
        ...(opsMarketFmvNormalizedGradeFilter.trim()
          ? { normalized_grade: opsMarketFmvNormalizedGradeFilter.trim() }
          : {}),
      };
      try {
        const list = await apiClient.getOpsMarketFmv(params);
        if (!ignore) {
          setOpsMarketFmv(list);
          setOpsMarketFmvSelectedId((cur) => (cur != null && list.items.some((row) => row.id === cur) ? cur : list.items[0]?.id ?? null));
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketFmv(null);
          setOpsMarketFmvSelectedId(null);
          setOpsMarketFmvError(loadErr instanceof ApiError ? loadErr.message : "Unable to load market FMV snapshots.");
        }
      } finally {
        if (!ignore) {
          setOpsMarketFmvLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [
    opsMarketFmvScopeFilter,
    opsMarketFmvConfidenceFilter,
    opsMarketFmvLiquidityFilter,
    opsMarketFmvStaleFilter,
    opsMarketFmvCurrencyFilter,
    opsMarketFmvGradingCompanyFilter,
    opsMarketFmvNormalizedGradeFilter,
    opsMarketFmvRefreshTick,
  ]);

  useEffect(() => {
    let ignore = false;
    if (opsMarketFmvSelectedId == null) {
      setOpsMarketFmvDetail(null);
      setOpsMarketFmvDetailError(null);
      setOpsMarketFmvDetailLoading(false);
      return undefined;
    }
    void (async () => {
      setOpsMarketFmvDetailLoading(true);
      setOpsMarketFmvDetailError(null);
      try {
        const detail = await apiClient.getOpsMarketFmvSnapshot(opsMarketFmvSelectedId);
        if (!ignore) {
          setOpsMarketFmvDetail(detail);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketFmvDetail(null);
          setOpsMarketFmvDetailError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load market FMV snapshot detail.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketFmvDetailLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsMarketFmvSelectedId]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsMarketTrendsLoading(true);
      setOpsMarketTrendsError(null);
      const params = {
        ...(opsMarketTrendScopeFilter ? { snapshot_scope: opsMarketTrendScopeFilter } : {}),
        ...(opsMarketTrendDirectionFilter ? { trend_direction: opsMarketTrendDirectionFilter } : {}),
        ...(opsMarketTrendStrengthFilter ? { trend_strength: opsMarketTrendStrengthFilter } : {}),
        ...(opsMarketTrendLiquidityFilter ? { liquidity_direction: opsMarketTrendLiquidityFilter } : {}),
        ...(opsMarketTrendStaleFilter ? { stale_data: opsMarketTrendStaleFilter === "true" } : {}),
        ...(opsMarketTrendCurrencyFilter.trim() ? { currency: opsMarketTrendCurrencyFilter.trim() } : {}),
        ...(opsMarketTrendGradingCompanyFilter.trim() ? { grading_company: opsMarketTrendGradingCompanyFilter.trim() } : {}),
        ...(opsMarketTrendGradeFilter.trim() ? { grade: opsMarketTrendGradeFilter.trim() } : {}),
        ...(opsMarketTrendWindowFilter ? { trend_window: opsMarketTrendWindowFilter } : {}),
      };
      try {
        const list = await apiClient.getOpsMarketTrends(params);
        if (!ignore) {
          setOpsMarketTrends(list);
          setOpsMarketTrendSelectedId((cur) => (cur != null && list.items.some((row) => row.id === cur) ? cur : list.items[0]?.id ?? null));
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketTrends(null);
          setOpsMarketTrendSelectedId(null);
          setOpsMarketTrendsError(loadErr instanceof ApiError ? loadErr.message : "Unable to load market trend snapshots.");
        }
      } finally {
        if (!ignore) {
          setOpsMarketTrendsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [
    opsMarketTrendScopeFilter,
    opsMarketTrendDirectionFilter,
    opsMarketTrendStrengthFilter,
    opsMarketTrendLiquidityFilter,
    opsMarketTrendStaleFilter,
    opsMarketTrendCurrencyFilter,
    opsMarketTrendGradingCompanyFilter,
    opsMarketTrendGradeFilter,
    opsMarketTrendWindowFilter,
    opsMarketTrendsRefreshTick,
  ]);

  useEffect(() => {
    let ignore = false;
    if (opsMarketTrendSelectedId == null) {
      setOpsMarketTrendDetail(null);
      setOpsMarketTrendDetailError(null);
      setOpsMarketTrendDetailLoading(false);
      return undefined;
    }
    void (async () => {
      setOpsMarketTrendDetailLoading(true);
      setOpsMarketTrendDetailError(null);
      try {
        const detail = await apiClient.getOpsMarketTrendSnapshot(opsMarketTrendSelectedId);
        if (!ignore) {
          setOpsMarketTrendDetail(detail);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketTrendDetail(null);
          setOpsMarketTrendDetailError(loadErr instanceof ApiError ? loadErr.message : "Unable to load market trend detail.");
        }
      } finally {
        if (!ignore) {
          setOpsMarketTrendDetailLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsMarketTrendSelectedId]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsMarketMatchSuggestionsLoading(true);
      setOpsMarketMatchSuggestionsError(null);
      const params = {
        ...(opsMarketMatchSuggestionSourceFilter.trim()
          ? { source: opsMarketMatchSuggestionSourceFilter.trim() }
          : {}),
        ...(opsMarketMatchSuggestionConfidenceFilter
          ? { confidence_bucket: opsMarketMatchSuggestionConfidenceFilter }
          : {}),
        ...(opsMarketMatchSuggestionReviewFilter ? { review_state: opsMarketMatchSuggestionReviewFilter } : {}),
        ...(opsMarketMatchSuggestionTypeFilter ? { suggestion_type: opsMarketMatchSuggestionTypeFilter } : {}),
      };
      try {
        const list = await apiClient.listOpsMarketMatchSuggestions(params);
        if (!ignore) {
          setOpsMarketMatchSuggestions(list);
          setOpsMarketMatchSuggestionSelectedId((cur) =>
            cur != null && list.suggestions.some((row) => row.id === cur) ? cur : list.suggestions[0]?.id ?? null,
          );
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketMatchSuggestions(null);
          setOpsMarketMatchSuggestionSelectedId(null);
          setOpsMarketMatchSuggestionsError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load market match suggestions.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketMatchSuggestionsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [
    opsMarketMatchSuggestionSourceFilter,
    opsMarketMatchSuggestionConfidenceFilter,
    opsMarketMatchSuggestionReviewFilter,
    opsMarketMatchSuggestionTypeFilter,
    opsMarketMatchSuggestionsRefreshTick,
  ]);

  useEffect(() => {
    let ignore = false;
    if (opsMarketSaleSelectedId == null) {
      setOpsMarketSaleDetail(null);
      setOpsMarketSaleDetailError(null);
      setOpsMarketSaleDetailLoading(false);
      return undefined;
    }
    void (async () => {
      setOpsMarketSaleDetailLoading(true);
      setOpsMarketSaleDetailError(null);
      try {
        const detail = await apiClient.getOpsMarketSale(opsMarketSaleSelectedId);
        if (!ignore) {
          setOpsMarketSaleDetail(detail);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsMarketSaleDetail(null);
          setOpsMarketSaleDetailError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load market sale detail.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsMarketSaleDetailLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsMarketSaleSelectedId, opsMarketSalesRefreshTick, opsMarketSaleReviewQueueRefreshTick]);

  useEffect(() => {
    if (!opsMarketSaleDetail) {
      setOpsMarketSaleNormalizationDraft({ mark_reviewed: false });
      return;
    }
    setOpsMarketSaleNormalizationDraft({
      normalized_title: opsMarketSaleDetail.normalized_title,
      normalized_issue: opsMarketSaleDetail.normalized_issue,
      normalized_publisher: opsMarketSaleDetail.normalized_publisher,
      normalized_variant: opsMarketSaleDetail.normalized_variant,
      normalized_grade: opsMarketSaleDetail.normalized_grade,
      normalized_cert_number: opsMarketSaleDetail.normalized_cert_number,
      normalization_status: opsMarketSaleDetail.normalization_status,
      mark_reviewed: false,
      review_note: "",
    });
  }, [opsMarketSaleDetail]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsScanQaFleetLoading(true);
      setOpsScanQaFleetError(null);
      try {
        const row = await apiClient.getOpsScanQaFleetSummary();
        if (!ignore) {
          setOpsScanQaFleet(row);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsScanQaFleet(null);
          setOpsScanQaFleetError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load scan QA fleet summary.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsScanQaFleetLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsScanPipelineReplaysLoading(true);
      setOpsScanPipelineReplaysError(null);
      try {
        const pack = await apiClient.listOpsScanPipelineReplays({ limit: 75, offset: 0 });
        if (!ignore) {
          setOpsScanPipelineReplays(pack.items);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsScanPipelineReplays([]);
          setOpsScanPipelineReplaysError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load scan pipeline replays.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsScanPipelineReplaysLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    if (opsScanPipelineReplaySelectedId == null) {
      setOpsScanPipelineReplayDetail(null);
      return;
    }
    let ignore = false;
    void (async () => {
      setOpsScanPipelineReplayDetailLoading(true);
      try {
        const replay = await apiClient.getOpsScanPipelineReplay(opsScanPipelineReplaySelectedId);
        if (!ignore) {
          setOpsScanPipelineReplayDetail(replay);
        }
      } catch {
        if (!ignore) {
          setOpsScanPipelineReplayDetail(null);
        }
      } finally {
        if (!ignore) {
          setOpsScanPipelineReplayDetailLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsScanPipelineReplaySelectedId]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsRoutingLoading(true);
      setOpsRoutingError(null);
      try {
        const routing = await apiClient.getOpsScanRoutingRecommendations();
        if (!ignore) {
          setOpsRouting(routing);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsRouting(null);
          setOpsRoutingError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load scan routing recommendations.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsRoutingLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const opsBulkPipelineActiveSessions = useMemo(() => {
    const sessions = opsScanPipelineDash?.active_sessions ?? [];
    return sessions.filter((s) => s.session_type === "bulk_ingest");
  }, [opsScanPipelineDash]);

  const opsBulkPipelineSessionsCompletedWithErrors = useMemo(() => {
    const sessions = opsScanPipelineDash?.recent_sessions ?? [];
    return sessions.filter((s) => s.session_type === "bulk_ingest" && s.status === "completed_with_errors");
  }, [opsScanPipelineDash]);

  const opsMarketSalesSummary = useMemo(() => {
    const normalized = opsMarketSales.filter((row) => row.normalization_status === "normalized").length;
    const partial = opsMarketSales.filter((row) => row.normalization_status === "partially_normalized").length;
    const failed = opsMarketSales.filter((row) => row.normalization_status === "normalization_failed").length;
    const duplicateWarnings = opsMarketSales.filter((row) => row.normalization_issue_count > 0).length;
    return {
      total: opsMarketSales.length,
      normalized,
      partial,
      failed,
      duplicateWarnings,
    };
  }, [opsMarketSales]);

  const refreshMarketSalesAndReviewQueue = useCallback(() => {
    setOpsMarketSalesRefreshTick((value) => value + 1);
    setOpsMarketSaleReviewQueueRefreshTick((value) => value + 1);
  }, []);

  const handleMarketSaleNormalizationSave = useCallback(async () => {
    if (opsMarketSaleSelectedId == null) {
      return;
    }
    try {
      const updated = await apiClient.patchOpsMarketSaleNormalization(opsMarketSaleSelectedId, opsMarketSaleNormalizationDraft);
      setOpsMarketSaleDetail(updated);
      refreshMarketSalesAndReviewQueue();
    } catch (err) {
      setOpsMarketSaleDetailError(err instanceof ApiError ? err.message : "Unable to save market-sale normalization.");
    }
  }, [opsMarketSaleNormalizationDraft, opsMarketSaleSelectedId, refreshMarketSalesAndReviewQueue]);

  const handleMarketSaleIgnore = useCallback(async () => {
    if (opsMarketSaleSelectedId == null) {
      return;
    }
    try {
      const updated = await apiClient.ignoreOpsMarketSale(opsMarketSaleSelectedId, {
        reason: opsMarketSaleNormalizationDraft.review_note ?? undefined,
      });
      setOpsMarketSaleDetail(updated);
      refreshMarketSalesAndReviewQueue();
    } catch (err) {
      setOpsMarketSaleDetailError(err instanceof ApiError ? err.message : "Unable to ignore market-sale record.");
    }
  }, [opsMarketSaleNormalizationDraft.review_note, opsMarketSaleSelectedId, refreshMarketSalesAndReviewQueue]);

  const handleMarketSaleFlagDuplicate = useCallback(async () => {
    if (opsMarketSaleSelectedId == null) {
      return;
    }
    try {
      const updated = await apiClient.flagDuplicateOpsMarketSale(opsMarketSaleSelectedId, {
        reason: opsMarketSaleNormalizationDraft.review_note ?? undefined,
      });
      setOpsMarketSaleDetail(updated);
      refreshMarketSalesAndReviewQueue();
    } catch (err) {
      setOpsMarketSaleDetailError(err instanceof ApiError ? err.message : "Unable to flag duplicate.");
    }
  }, [opsMarketSaleNormalizationDraft.review_note, opsMarketSaleSelectedId, refreshMarketSalesAndReviewQueue]);

  useEffect(() => {
    if (opsScanSessionSelectedId == null) {
      setOpsScanSessionDetail(null);
      return;
    }
    let ignore = false;
    void (async () => {
      setOpsScanSessionDetailLoading(true);
      try {
        const detail = await apiClient.getOpsScanSession(opsScanSessionSelectedId);
        if (!ignore) {
          setOpsScanSessionDetail(detail);
        }
      } catch {
        if (!ignore) {
          setOpsScanSessionDetail(null);
        }
      } finally {
        if (!ignore) {
          setOpsScanSessionDetailLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsScanSessionSelectedId]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsHrLoading(true);
      setOpsHrError(null);
      const trimmedOwner = opsHrOwnerUserIdDraft.trim();
      let ownerUserId: number | undefined;
      if (trimmedOwner) {
        const parsed = Number(trimmedOwner);
        if (!Number.isInteger(parsed) || parsed <= 0) {
          if (!ignore) {
            setOpsHrStats(null);
            setOpsHrList([]);
            setOpsHrError("Owner user id must be a positive integer.");
            setOpsHrLoading(false);
          }
          return;
        }
        ownerUserId = parsed;
      }
      try {
        const [st, lst] = await Promise.all([
          apiClient.getOpsHighResReviewRequestStats(),
          apiClient.listOpsHighResReviewRequests({
            limit: 250,
            ...(ownerUserId !== undefined ? { owner_user_id: ownerUserId } : {}),
            ...(opsHrStatusFilter ? { status: opsHrStatusFilter as HighResReviewRequestStatus } : {}),
            ...(opsHrPriorityFilter ? { priority: opsHrPriorityFilter as HighResReviewRequestPriority } : {}),
            ...(opsHrReasonFilter ? { reason: opsHrReasonFilter as HighResReviewRequestReason } : {}),
          }),
        ]);
        if (!ignore) {
          setOpsHrStats(st);
          setOpsHrList(lst.requests);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpsHrStats(null);
          setOpsHrList([]);
          setOpsHrError(
            loadErr instanceof ApiError
              ? loadErr.message
              : "Unable to load high-resolution review queue.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsHrLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsHrStatusFilter, opsHrPriorityFilter, opsHrReasonFilter, opsHrOwnerUserIdDraft]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setInventoryIntelOpsError(null);
      try {
        const [summaryRollup, healthRollup, breakdown] = await Promise.all([
          apiClient.getOpsInventoryIntelligenceSummary(),
          apiClient.getOpsInventoryIntelligenceHealth(),
          apiClient.getOpsInventoryIntelligenceBreakdown(),
        ]);
        if (!ignore) {
          setInventoryIntelOpsSummary(summaryRollup);
          setInventoryIntelOpsHealth(healthRollup);
          setInventoryIntelOpsBreakdown(breakdown);
        }
      } catch (loadOpsIntelError) {
        if (!ignore) {
          setInventoryIntelOpsSummary(null);
          setInventoryIntelOpsHealth(null);
          setInventoryIntelOpsBreakdown(null);
          setInventoryIntelOpsError(
            loadOpsIntelError instanceof ApiError
              ? loadOpsIntelError.message
              : "Unable to load global inventory intelligence rollup.",
          );
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsInventoryRiskError(null);
      try {
        const response = await apiClient.getOpsInventoryRisks({
          priority: opsInventoryRiskPriority || undefined,
          risk_type: opsInventoryRiskType || undefined,
          open_only: opsInventoryRiskOpenOnly,
        });
        if (!ignore) {
          setOpsInventoryRiskReport(response);
        }
      } catch (loadOpsRiskError) {
        if (!ignore) {
          setOpsInventoryRiskReport(null);
          setOpsInventoryRiskError(
            loadOpsRiskError instanceof ApiError
              ? loadOpsRiskError.message
              : "Unable to load global inventory risks.",
          );
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsInventoryRiskOpenOnly, opsInventoryRiskPriority, opsInventoryRiskType]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsIacError(null);
      try {
        const response = await apiClient.getOpsInventoryActionCenter({
          priority: opsIacPriority || undefined,
          action_category: opsIacCategory || undefined,
        });
        if (!ignore) {
          setOpsIacReport(response);
        }
      } catch (loadOpsIacError) {
        if (!ignore) {
          setOpsIacReport(null);
          setOpsIacError(
            loadOpsIacError instanceof ApiError
              ? loadOpsIacError.message
              : "Unable to load global inventory action center.",
          );
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsIacPriority, opsIacCategory]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsOrderArrivalError(null);
      try {
        const params = {
          classification: opsOrderArrivalClassification || undefined,
        };
        const [listResp, calendarResp] = await Promise.all([
          apiClient.getOpsOrderArrivalIntelligence(params),
          apiClient.getOpsOrderArrivalCalendar(params),
        ]);
        if (!ignore) {
          setOpsOrderArrivalReport(listResp);
          setOpsOrderArrivalCalendar(calendarResp);
        }
      } catch (orderArrivalLoadError) {
        if (!ignore) {
          setOpsOrderArrivalReport(null);
          setOpsOrderArrivalCalendar(null);
          setOpsOrderArrivalError(
            orderArrivalLoadError instanceof ApiError
              ? orderArrivalLoadError.message
              : "Unable to load global order / arrival intelligence.",
          );
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsOrderArrivalClassification]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsPhysicalIntakeError(null);
      try {
        const [sum, lst] = await Promise.all([
          apiClient.getOpsPhysicalIntakeSummary(),
          apiClient.getOpsPhysicalIntake({ intake_state: opsPhysicalIntakeStateFilter || undefined }),
        ]);
        if (!ignore) {
          setOpsPhysicalIntakeSummary(sum);
          setOpsPhysicalIntakeList(lst);
        }
      } catch (physicalIntakeErr) {
        if (!ignore) {
          setOpsPhysicalIntakeSummary(null);
          setOpsPhysicalIntakeList(null);
          setOpsPhysicalIntakeError(
            physicalIntakeErr instanceof ApiError
              ? physicalIntakeErr.message
              : "Unable to load global physical intake overlays.",
          );
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsPhysicalIntakeStateFilter]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsCollectionAnalyticsError(null);
      try {
        const [summary, publishers, quality, composition, timeline] = await Promise.all([
          apiClient.getOpsCollectionAnalyticsSummary(),
          apiClient.getOpsCollectionAnalyticsPublishers(),
          apiClient.getOpsCollectionAnalyticsQuality(),
          apiClient.getOpsCollectionAnalyticsComposition(),
          apiClient.getOpsCollectionAnalyticsTimeline(),
        ]);
        if (!ignore) {
          setOpsCollectionSummary(summary);
          setOpsCollectionPublishers(publishers);
          setOpsCollectionQuality(quality);
          setOpsCollectionComposition(composition);
          setOpsCollectionTimeline(timeline);
        }
      } catch (loadOpsCollectionError) {
        if (!ignore) {
          setOpsCollectionSummary(null);
          setOpsCollectionPublishers(null);
          setOpsCollectionQuality(null);
          setOpsCollectionComposition(null);
          setOpsCollectionTimeline(null);
          setOpsCollectionAnalyticsError(
            loadOpsCollectionError instanceof ApiError
              ? loadOpsCollectionError.message
              : "Unable to load global collection analytics.",
          );
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setOpsHistoricalTimelineLoading(true);
      setOpsHistoricalTimelineError(null);
      try {
        const response = await apiClient.getOpsCollectionHistoricalTimeline({
          event_type: opsHistoricalTimelineApplied.event_type || undefined,
          publisher: opsHistoricalTimelineApplied.publisher.trim() || undefined,
          ownership_state: opsHistoricalTimelineApplied.ownership_state || undefined,
          release_status: opsHistoricalTimelineApplied.release_status || undefined,
          start_date: opsHistoricalTimelineApplied.start_date || undefined,
          end_date: opsHistoricalTimelineApplied.end_date || undefined,
          preorder_only: opsHistoricalTimelineApplied.preorder_only ? true : undefined,
          in_hand_only: opsHistoricalTimelineApplied.in_hand_only ? true : undefined,
          grouping: opsHistoricalTimelineApplied.grouping,
          sort: opsHistoricalTimelineApplied.sort,
          limit: 150,
        });
        if (!ignore) {
          setOpsHistoricalTimelinePayload(response);
        }
      } catch (histErr) {
        if (!ignore) {
          setOpsHistoricalTimelinePayload(null);
          setOpsHistoricalTimelineError(
            histErr instanceof ApiError
              ? histErr.message
              : "Unable to load global historical collection timeline.",
          );
        }
      } finally {
        if (!ignore) {
          setOpsHistoricalTimelineLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [opsHistoricalTimelineApplied]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setDuplicateScanClustersLoading(true);
      setDuplicateScanClustersError(null);
      try {
        const data = await apiClient.listDuplicateScanClustersForOps({
          classification_filter: duplicateScanClustersFilter,
        });
        if (!ignore) {
          setDuplicateScanClustersData(data);
        }
      } catch (intelError) {
        if (!ignore) {
          setDuplicateScanClustersData(null);
          setDuplicateScanClustersError(
            intelError instanceof ApiError
              ? intelError.message
              : "Unable to load duplicate-scan cluster intelligence.",
          );
        }
      } finally {
        if (!ignore) {
          setDuplicateScanClustersLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [duplicateScanClustersFilter]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setDuplicateOwnershipOpsLoading(true);
      setDuplicateOwnershipOpsError(null);
      try {
        const classification =
          duplicateOwnershipClassificationOps === "all" ? undefined : duplicateOwnershipClassificationOps;
        const data = await apiClient.getOpsDuplicateOwnershipList({
          dup_scan_classification: duplicateOwnershipDupScanOps,
          classification,
        });
        if (!ignore) {
          setDuplicateOwnershipOps(data);
        }
      } catch (loadErr) {
        if (!ignore) {
          setDuplicateOwnershipOps(null);
          setDuplicateOwnershipOpsError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load duplicate ownership intelligence.",
          );
        }
      } finally {
        if (!ignore) {
          setDuplicateOwnershipOpsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [duplicateOwnershipClassificationOps, duplicateOwnershipDupScanOps]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setRunDetectionOpsLoading(true);
      setRunDetectionOpsError(null);
      try {
        const seriesStatus = runDetectionStatusOps === "all" ? undefined : runDetectionStatusOps;
        const data = await apiClient.getOpsRunDetectionList({
          series_status: seriesStatus,
        });
        if (!ignore) {
          setRunDetectionOps(data);
        }
      } catch (loadErr) {
        if (!ignore) {
          setRunDetectionOps(null);
          setRunDetectionOpsError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load run detection intelligence.",
          );
        }
      } finally {
        if (!ignore) {
          setRunDetectionOpsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [runDetectionStatusOps]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setVariantFamilyClustersLoading(true);
      setVariantFamilyClustersError(null);
      try {
        const vfData = await apiClient.listVariantFamilyClustersForOps({
          classification_filter: variantFamilyClustersFilter,
        });
        if (!ignore) {
          setVariantFamilyClustersData(vfData);
        }
      } catch (vfIntelErr) {
        if (!ignore) {
          setVariantFamilyClustersData(null);
          setVariantFamilyClustersError(
            vfIntelErr instanceof ApiError
              ? vfIntelErr.message
              : "Unable to load variant-family cluster intelligence.",
          );
        }
      } finally {
        if (!ignore) {
          setVariantFamilyClustersLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [variantFamilyClustersFilter]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setCanonicalSuggestionsLoading(true);
      setCanonicalSuggestionsError(null);
      try {
        const data = await apiClient.listCanonicalIssueSuggestionsForOps({
          review_state: canonicalSuggestionReviewState,
          confidence_bucket: canonicalSuggestionConfidenceBucket,
          suggestion_type: canonicalSuggestionType,
        });
        if (!ignore) {
          setCanonicalSuggestionsData(data);
        }
      } catch (loadError) {
        if (!ignore) {
          setCanonicalSuggestionsData(null);
          setCanonicalSuggestionsError(
            loadError instanceof ApiError ? loadError.message : "Unable to load canonical issue suggestions.",
          );
        }
      } finally {
        if (!ignore) {
          setCanonicalSuggestionsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [canonicalSuggestionConfidenceBucket, canonicalSuggestionReviewState, canonicalSuggestionType]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setRelationshipConflictsLoading(true);
      setRelationshipConflictsError(null);
      try {
        const data = await apiClient.getRelationshipConflictsForOps({
          severity: relationshipConflictSeverity,
          status: relationshipConflictStatus,
          conflict_type: relationshipConflictType,
        });
        if (!ignore) {
          setRelationshipConflictsData(data);
        }
      } catch (loadError) {
        if (!ignore) {
          setRelationshipConflictsData(null);
          setRelationshipConflictsError(
            loadError instanceof ApiError ? loadError.message : "Unable to load relationship conflicts.",
          );
        }
      } finally {
        if (!ignore) {
          setRelationshipConflictsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [relationshipConflictSeverity, relationshipConflictStatus, relationshipConflictType]);

  const handleOcrPipelineRecover = useCallback(async () => {
    setPipelineRecoverBusy(true);
    setPipelineRecoverMessage(null);
    try {
      const res = await apiClient.postOpsOcrPipelineRecover();
      const dash = await apiClient.getOpsDashboard();
      setDashboard(dash);
      setCoverLinkDecisions(await apiClient.listRecentCoverLinkDecisionsForOps({ include_inactive: true, limit: 12 }));
      setPipelineRecoverMessage(
        `Recovery complete: OCR results ${res.ocr_results_recovered}, batch items ${res.batch_items_recovered}, replay items ${res.replay_items_recovered}.`,
      );
    } catch (recoverError) {
      setPipelineRecoverMessage(
        recoverError instanceof ApiError
          ? recoverError.message
          : recoverError instanceof Error
            ? recoverError.message
            : "OCR pipeline recovery failed.",
      );
    } finally {
      setPipelineRecoverBusy(false);
    }
  }, []);

  const handleDetectRelationshipConflicts = useCallback(async () => {
    setRelationshipConflictsDetectBusy(true);
    setRelationshipConflictsDetectMessage(null);
    try {
      const result: RelationshipConflictDetectResponse = await apiClient.detectRelationshipConflictsForOps();
      setRelationshipConflictsDetectMessage(
        `Detected ${result.detected_count} conflicts · open ${result.open_count} · acknowledged ${result.acknowledged_count} · dismissed ${result.dismissed_count} · resolved ${result.resolved_count}.`,
      );
      const refreshed = await apiClient.getRelationshipConflictsForOps({
        severity: relationshipConflictSeverity,
        status: relationshipConflictStatus,
        conflict_type: relationshipConflictType,
      });
      setRelationshipConflictsData(refreshed);
    } catch (error) {
      setRelationshipConflictsDetectMessage(
        error instanceof ApiError ? error.message : "Unable to detect relationship conflicts.",
      );
    } finally {
      setRelationshipConflictsDetectBusy(false);
    }
  }, [relationshipConflictSeverity, relationshipConflictStatus, relationshipConflictType]);

  const handleGenerateMarketMatchSuggestions = useCallback(async (marketSaleRecordId: number) => {
    setOpsMarketMatchSuggestionBusyId(marketSaleRecordId);
    try {
      await apiClient.generateOpsMarketSaleMatchSuggestions(marketSaleRecordId);
      setOpsMarketMatchSuggestionsRefreshTick((tick) => tick + 1);
    } catch (loadError) {
      setOpsMarketMatchSuggestionsError(
        loadError instanceof ApiError ? loadError.message : "Unable to generate market match suggestions.",
      );
    } finally {
      setOpsMarketMatchSuggestionBusyId(null);
    }
  }, []);

  const reviewMarketMatchSuggestion = useCallback(
    async (suggestionId: number, action: "approve" | "reject" | "ignore") => {
      setOpsMarketMatchSuggestionBusyId(suggestionId);
      try {
        if (action === "approve") {
          await apiClient.approveOpsMarketMatchSuggestion(suggestionId);
        } else if (action === "reject") {
          await apiClient.rejectOpsMarketMatchSuggestion(suggestionId);
        } else {
          await apiClient.ignoreOpsMarketMatchSuggestion(suggestionId);
        }
        setOpsMarketMatchSuggestionsRefreshTick((tick) => tick + 1);
      } catch (loadError) {
        setOpsMarketMatchSuggestionsError(
          loadError instanceof ApiError ? loadError.message : "Unable to update market match suggestion.",
        );
      } finally {
        setOpsMarketMatchSuggestionBusyId(null);
      }
    },
    [],
  );

  const opsMarketMatchSelectedSuggestion =
    opsMarketMatchSuggestions?.suggestions.find((row) => row.id === opsMarketMatchSuggestionSelectedId) ?? null;

  const loadCoverRelationshipGraphQuickView = useCallback(async () => {
    setGraphQuickError(null);
    setGraphQuickBusy(true);
    setGraphQuickPayload(null);
    try {
      const id = Number(graphQuickCoverIdDraft.trim());
      if (!Number.isInteger(id) || id < 1) {
        throw new Error("Enter a valid cover image id.");
      }
      const data = await apiClient.getCoverRelationshipGraphForOps(id);
      setGraphQuickPayload(data);
    } catch (quickError) {
      setGraphQuickError(
        quickError instanceof ApiError
          ? quickError.message
          : quickError instanceof Error
            ? quickError.message
            : "Unable to load relationship graph.",
      );
    } finally {
      setGraphQuickBusy(false);
    }
  }, [graphQuickCoverIdDraft]);

  const refreshDuplicateCandidates = useCallback(async () => {
    setDuplicateCandidatesLoading(true);
    setDuplicateCandidatesError(null);
    try {
      const params =
        duplicateReviewFilter === "all" ? {} : { review_status: duplicateReviewFilter };
      const rows = await apiClient.getInventoryDuplicateCandidates(params);
      setDuplicateCandidates(rows);
      setDuplicateNotesDraft(
        Object.fromEntries(rows.map((group) => [group.metadata_identity_key, group.notes ?? ""])),
      );
    } catch (loadError) {
      setDuplicateCandidatesError(
        loadError instanceof ApiError
          ? loadError.message
          : "Unable to load duplicate inventory candidates.",
      );
    } finally {
      setDuplicateCandidatesLoading(false);
    }
  }, [duplicateReviewFilter]);

  const refreshCanonicalSeries = useCallback(async () => {
    setCanonicalSeriesLoading(true);
    setCanonicalSeriesError(null);
    try {
      const earliestMin = parseOptionalYear(canonicalSeriesEarliestYearMin);
      const earliestMax = parseOptionalYear(canonicalSeriesEarliestYearMax);
      const latestMin = parseOptionalYear(canonicalSeriesLatestYearMin);
      const latestMax = parseOptionalYear(canonicalSeriesLatestYearMax);
      const rows = await apiClient.getCanonicalSeriesRegistry({
        publisher: canonicalSeriesPublisherFilter.trim() || undefined,
        title: canonicalSeriesTitleFilter.trim() || undefined,
        earliest_release_year_min: earliestMin,
        earliest_release_year_max: earliestMax,
        latest_release_year_min: latestMin,
        latest_release_year_max: latestMax,
      });
      setCanonicalSeries(rows);
    } catch (loadError) {
      setCanonicalSeriesError(
        loadError instanceof ApiError
          ? loadError.message
          : "Unable to load canonical series registry.",
      );
    } finally {
      setCanonicalSeriesLoading(false);
    }
  }, [
    canonicalSeriesPublisherFilter,
    canonicalSeriesTitleFilter,
    canonicalSeriesEarliestYearMin,
    canonicalSeriesEarliestYearMax,
    canonicalSeriesLatestYearMin,
    canonicalSeriesLatestYearMax,
  ]);

  const refreshCanonicalCreators = useCallback(async () => {
    setCanonicalCreatorsLoading(true);
    setCanonicalCreatorsError(null);
    try {
      const rows = await apiClient.getCanonicalCreatorsRegistry({
        name: canonicalCreatorsBroadFilter.trim() || undefined,
        canonical_name: canonicalCreatorsCanonicalNameFilter.trim() || undefined,
        normalized_name: canonicalCreatorsNormalizedNameFilter.trim() || undefined,
        creator_key: canonicalCreatorsKeyFilter.trim() || undefined,
      });
      setCanonicalCreators(rows);
    } catch (loadError) {
      setCanonicalCreatorsError(
        loadError instanceof ApiError
          ? loadError.message
          : "Unable to load canonical creator registry.",
      );
    } finally {
      setCanonicalCreatorsLoading(false);
    }
  }, [
    canonicalCreatorsBroadFilter,
    canonicalCreatorsCanonicalNameFilter,
    canonicalCreatorsNormalizedNameFilter,
    canonicalCreatorsKeyFilter,
  ]);

  const refreshMetadataAudits = useCallback(async () => {
    setMetadataAuditsLoading(true);
    setMetadataAuditsError(null);
    try {
      const rows = await apiClient.getMetadataAudits({ limit: 20 });
      setMetadataAudits(rows);
    } catch (loadError) {
      setMetadataAuditsError(
        loadError instanceof ApiError ? loadError.message : "Unable to load metadata audit history.",
      );
    } finally {
      setMetadataAuditsLoading(false);
    }
  }, []);

  const refreshOcrBatches = useCallback(async () => {
    setOcrBatchesLoading(true);
    setOcrBatchesError(null);
    try {
      const rows = await apiClient.getOcrBatchesForOps(25);
      setOcrBatches(rows);
    } catch (loadError) {
      setOcrBatches([]);
      setOcrBatchesError(
        loadError instanceof ApiError ? loadError.message : "Unable to load OCR batches.",
      );
    } finally {
      setOcrBatchesLoading(false);
    }
  }, []);

  const refreshOcrReplays = useCallback(async () => {
    setOcrReplaysLoading(true);
    setOcrReplaysError(null);
    try {
      const rows = await apiClient.getOcrReplaysForOps(25);
      setOcrReplays(rows);
    } catch (loadError) {
      setOcrReplays([]);
      setOcrReplaysError(
        loadError instanceof ApiError ? loadError.message : "Unable to load OCR replays.",
      );
    } finally {
      setOcrReplaysLoading(false);
    }
  }, []);

  const refreshRelationshipReplays = useCallback(async () => {
    setRelationshipReplaysLoading(true);
    setRelationshipReplaysError(null);
    try {
      const rows = await apiClient.getRelationshipReplaysForOps(25);
      setRelationshipReplays(rows);
    } catch (loadError) {
      setRelationshipReplays([]);
      setRelationshipReplaysError(
        loadError instanceof ApiError ? loadError.message : "Unable to load relationship replays.",
      );
    } finally {
      setRelationshipReplaysLoading(false);
    }
  }, []);

  const refreshRecentCoverImages = useCallback(async () => {
    setCoverThumbUrls({});
    setCoverThumbErrors({});
    setRecentCoversLoading(true);
    setRecentCoversError(null);
    try {
      const rows = await apiClient.getRecentCoverImagesForOps({
        limit: coverOpsLimit,
        source_type: coverOpsSource === "all" ? undefined : coverOpsSource,
        linkage: coverOpsLinkage === "all" ? undefined : coverOpsLinkage,
        matching_status: coverOpsMatchingStatus === "all" ? undefined : coverOpsMatchingStatus,
      });
      setRecentCoverImages(rows);
    } catch (loadError) {
      setRecentCoverImages([]);
      setRecentCoversError(
        loadError instanceof ApiError ? loadError.message : "Unable to load recent cover images.",
      );
    } finally {
      setRecentCoversLoading(false);
    }
  }, [coverOpsLimit, coverOpsLinkage, coverOpsMatchingStatus, coverOpsSource]);

  const refreshDuplicateCoverGroups = useCallback(async () => {
    setDupCoverThumbUrls({});
    setDupCoverThumbErrors({});
    setDuplicateCoversLoading(true);
    setDuplicateCoversError(null);
    try {
      const rows = await apiClient.getDuplicateCoverImagesForOps({
        limit: dupCoverLimit,
        min_count: dupCoverMinCount,
        source_type: dupCoverSource === "all" ? undefined : dupCoverSource,
        linkage: dupCoverLinkage === "all" ? undefined : dupCoverLinkage,
      });
      setDuplicateCoverGroups(rows);
    } catch (loadError) {
      setDuplicateCoverGroups([]);
      setDuplicateCoversError(
        loadError instanceof ApiError
          ? loadError.message
          : "Unable to load duplicate cover groups.",
      );
    } finally {
      setDuplicateCoversLoading(false);
    }
  }, [dupCoverLimit, dupCoverMinCount, dupCoverSource, dupCoverLinkage]);

  async function opsFleetExport(download: () => Promise<void>): Promise<void> {
    try {
      setError(null);
      await download();
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Export failed.";
      setError(`Ops export: ${message}`);
    }
  }

  const opsExportChipClass =
    "rounded-xl border border-amber-200/35 px-3 py-2 text-xs font-semibold text-amber-50 transition hover:border-amber-200/65 hover:bg-amber-400/10";

  const inventoryFmvPanels: Array<{ title: string; resp: InventoryResponse | null }> = [
    { title: "Low-confidence rows", resp: inventoryFmvLowConfidence },
    { title: "Stale rows", resp: inventoryFmvStale },
    { title: "No market data rows", resp: inventoryFmvNoMarketData },
  ];

  async function handleOpsAssignCoverToInventory(coverImageId: number): Promise<void> {
    const invRaw = (coverOpsAssignInvDraft[coverImageId] ?? "").trim();
    const invNum = Number(invRaw);
    if (!Number.isInteger(invNum) || invNum < 1) {
      setCoverOpsAssignMessage((prev) => ({
        ...prev,
        [coverImageId]: "Enter a valid inventory copy id.",
      }));
      return;
    }
    setCoverOpsAssignBusyId(coverImageId);
    setCoverOpsAssignMessage((prev) => ({ ...prev, [coverImageId]: "" }));
    try {
      await apiClient.assignExistingCoverToInventory(invNum, {
        cover_image_id: coverImageId,
        set_primary: coverOpsAssignPrimary[coverImageId] ?? false,
      });
      setCoverOpsAssignMessage((prev) => ({ ...prev, [coverImageId]: "Assigned." }));
      await refreshRecentCoverImages();
    } catch (assignErr) {
      setCoverOpsAssignMessage((prev) => ({
        ...prev,
        [coverImageId]:
          assignErr instanceof ApiError ? assignErr.message : "Assignment failed.",
      }));
    } finally {
      setCoverOpsAssignBusyId(null);
    }
  }

  async function handleOpsProcessCoverImage(coverImageId: number): Promise<void> {
    setCoverOpsProcessBusyId(coverImageId);
    setCoverOpsProcessMessage((prev) => ({ ...prev, [coverImageId]: "" }));
    try {
      const response = await apiClient.processCoverImageForOps(coverImageId);
      setCoverOpsProcessMessage((prev) => ({
        ...prev,
        [coverImageId]:
          response.status === "already_queued"
            ? "Processing already queued."
            : "Metadata reprocessing queued.",
      }));
      await refreshRecentCoverImages();
    } catch (processErr) {
      setCoverOpsProcessMessage((prev) => ({
        ...prev,
        [coverImageId]:
          processErr instanceof ApiError ? processErr.message : "Unable to queue processing.",
      }));
    } finally {
      setCoverOpsProcessBusyId(null);
    }
  }

  async function handleOpsEvaluateCoverImage(coverImageId: number): Promise<void> {
    setCoverOpsEvaluateBusyId(coverImageId);
    setCoverOpsEvaluateMessage((prev) => ({ ...prev, [coverImageId]: "" }));
    try {
      await apiClient.evaluateCoverImageMatchingReadinessForOps(coverImageId);
      setCoverOpsEvaluateMessage((prev) => ({
        ...prev,
        [coverImageId]: "Matching readiness evaluated.",
      }));
      await Promise.all([refreshRecentCoverImages(), refreshDuplicateCoverGroups()]);
    } catch (evaluateErr) {
      setCoverOpsEvaluateMessage((prev) => ({
        ...prev,
        [coverImageId]:
          evaluateErr instanceof ApiError ? evaluateErr.message : "Unable to evaluate readiness.",
      }));
    } finally {
      setCoverOpsEvaluateBusyId(null);
    }
  }

  async function handleOpsQueueCoverImageOcr(row: OpsRecentCoverImageRow): Promise<void> {
    setCoverOpsOcrBusyId(row.id);
    try {
      const headline = resolveCoverImageOcrHeadline({
        ocr_visibility: row.ocr_visibility,
        latest_ocr_result: row.latest_ocr_result,
      });
      const hasPriorResult = row.latest_ocr_result !== null;
      const replayReason = headline === "failed" ? "ops-retry-after-failure" : "ops-manual-replay";
      await (hasPriorResult
        ? apiClient.replayCoverImageOcrForOps(row.id, { replay_reason: replayReason })
        : apiClient.runCoverImageOcrForOps(row.id));
      await refreshRecentCoverImages();
    } catch (ocrErr) {
      setRecentCoversError(ocrErr instanceof ApiError ? ocrErr.message : "Unable to queue cover OCR.");
    } finally {
      setCoverOpsOcrBusyId(null);
    }
  }

  async function handleOpsGenerateFingerprints(coverImageId: number): Promise<void> {
    setCoverOpsFingerprintBusyId(coverImageId);
    setCoverOpsFingerprintMessage((prev) => ({ ...prev, [coverImageId]: "" }));
    try {
      const response = await apiClient.generateCoverImageFingerprintsForOps(coverImageId);
      setCoverOpsFingerprintMessage((prev) => ({
        ...prev,
        [coverImageId]:
          response.fingerprint_count > 0
            ? `Fingerprints refreshed (${response.fingerprint_count}).`
            : "No fingerprint records generated.",
      }));
      await refreshRecentCoverImages();
    } catch (fingerprintErr) {
      setCoverOpsFingerprintMessage((prev) => ({
        ...prev,
        [coverImageId]:
          fingerprintErr instanceof ApiError
            ? fingerprintErr.message
            : "Unable to generate fingerprints.",
      }));
    } finally {
      setCoverOpsFingerprintBusyId(null);
    }
  }

  async function handleOpsAnalyzeOcrQuality(coverImageId: number): Promise<void> {
    setCoverOpsQualityBusyId(coverImageId);
    setCoverOpsQualityMessage((prev) => ({ ...prev, [coverImageId]: "" }));
    try {
      const response = await apiClient.analyzeCoverImageOcrQualityForOps(coverImageId);
      setCoverOpsQualityMessage((prev) => ({
        ...prev,
        [coverImageId]:
          response.analysis_count > 0
            ? `OCR quality refreshed (${response.analysis_count}).`
            : "No OCR quality records generated.",
      }));
      await refreshRecentCoverImages();
    } catch (qualityErr) {
      setCoverOpsQualityMessage((prev) => ({
        ...prev,
        [coverImageId]:
          qualityErr instanceof ApiError ? qualityErr.message : "Unable to analyze OCR quality.",
      }));
    } finally {
      setCoverOpsQualityBusyId(null);
    }
  }

  async function handleCreateOcrBatch(): Promise<void> {
    const coverIds = ocrBatchCoverIdsDraft
      .split(/[,\s]+/)
      .map((value) => Number(value.trim()))
      .filter((value) => Number.isInteger(value) && value > 0);
    if (coverIds.length === 0) {
      setOcrBatchesError("Enter at least one valid cover image id.");
      return;
    }
    setOcrBatchBusyAction("create");
    setOcrBatchMessage(null);
    setOcrBatchesError(null);
    try {
      const batch = await apiClient.createOcrBatchForOps({ cover_image_ids: coverIds });
      setOcrBatchMessage(`Created OCR batch ${batch.batch_key} with ${batch.total_items} item(s).`);
      setOcrBatchCoverIdsDraft("");
      await refreshOcrBatches();
    } catch (actionError) {
      setOcrBatchesError(
        actionError instanceof ApiError ? actionError.message : "Unable to create OCR batch.",
      );
    } finally {
      setOcrBatchBusyAction(null);
    }
  }

  async function handleOcrBatchAction(
    batchId: number,
    action: "enqueue" | "retry-failed" | "cancel",
  ): Promise<void> {
    setOcrBatchBusyAction(`${action}:${batchId}`);
    setOcrBatchMessage(null);
    setOcrBatchesError(null);
    try {
      const response =
        action === "enqueue"
          ? await apiClient.enqueueOcrBatchForOps(batchId)
          : action === "retry-failed"
            ? await apiClient.retryFailedOcrBatchItemsForOps(batchId)
            : await apiClient.cancelOcrBatchForOps(batchId);
      setOcrBatchMessage(
        action === "enqueue"
          ? `Queued OCR batch ${response.batch_key}.`
          : action === "retry-failed"
            ? `Retried failed items for ${response.batch_key}.`
            : `Cancelled OCR batch ${response.batch_key}.`,
      );
      await refreshOcrBatches();
    } catch (actionError) {
      setOcrBatchesError(
        actionError instanceof ApiError ? actionError.message : "Unable to update OCR batch.",
      );
    } finally {
      setOcrBatchBusyAction(null);
    }
  }

  async function handleCreateOcrReplay(): Promise<void> {
    const coverIds = ocrReplayCoverIdsDraft
      .split(/[,\s]+/)
      .map((value) => Number(value.trim()))
      .filter((value) => Number.isInteger(value) && value > 0);
    if (coverIds.length === 0) {
      setOcrReplaysError("Enter at least one valid cover image id.");
      return;
    }
    setOcrReplayBusyAction("create");
    setOcrReplayMessage(null);
    setOcrReplaysError(null);
    try {
      const replay = await apiClient.createOcrReplayForOps({
        replay_type: ocrReplayTypeDraft,
        cover_image_ids: coverIds,
      });
      setOcrReplayMessage(
        `Created ${replay.replay_type.replace(/_/g, " ")} replay #${replay.id} with ${replay.total_items} item(s).`,
      );
      setOcrReplayCoverIdsDraft("");
      await refreshOcrReplays();
    } catch (actionError) {
      setOcrReplaysError(
        actionError instanceof ApiError ? actionError.message : "Unable to create OCR replay.",
      );
    } finally {
      setOcrReplayBusyAction(null);
    }
  }

  async function handleOcrReplayAction(
    replayId: number,
    action: "start" | "cancel",
  ): Promise<void> {
    setOcrReplayBusyAction(`${action}:${replayId}`);
    setOcrReplayMessage(null);
    setOcrReplaysError(null);
    try {
      const replay =
        action === "start"
          ? await apiClient.startOcrReplayForOps(replayId)
          : await apiClient.cancelOcrReplayForOps(replayId);
      setOcrReplayMessage(
        action === "start"
          ? `Started OCR replay #${replay.id}.`
          : `Cancelled OCR replay #${replay.id}.`,
      );
      await refreshOcrReplays();
    } catch (actionError) {
      setOcrReplaysError(
        actionError instanceof ApiError ? actionError.message : "Unable to update OCR replay.",
      );
    } finally {
      setOcrReplayBusyAction(null);
    }
  }

  async function handleCreateRelationshipReplay(): Promise<void> {
    const coverIds = relationshipReplayCoverIdsDraft
      .split(/[,\s]+/)
      .map((value) => Number(value.trim()))
      .filter((value) => Number.isInteger(value) && value > 0);
    setRelationshipReplayBusyAction("create");
    setRelationshipReplayMessage(null);
    setRelationshipReplaysError(null);
    try {
      const replay = await apiClient.createRelationshipReplayForOps({
        replay_type: relationshipReplayTypeDraft,
        cover_image_ids: coverIds,
      });
      setRelationshipReplayMessage(
        `Created ${replay.replay_type.replace(/_/g, " ")} relationship replay #${replay.id} with ${replay.total_items} item(s).`,
      );
      setRelationshipReplayCoverIdsDraft("");
      await refreshRelationshipReplays();
    } catch (actionError) {
      setRelationshipReplaysError(
        actionError instanceof ApiError ? actionError.message : "Unable to create relationship replay.",
      );
    } finally {
      setRelationshipReplayBusyAction(null);
    }
  }

  async function handleRelationshipReplayAction(
    replayId: number,
    action: "start" | "cancel",
  ): Promise<void> {
    setRelationshipReplayBusyAction(`${action}:${replayId}`);
    setRelationshipReplayMessage(null);
    setRelationshipReplaysError(null);
    try {
      const replay =
        action === "start"
          ? await apiClient.startRelationshipReplayForOps(replayId)
          : await apiClient.cancelRelationshipReplayForOps(replayId);
      setRelationshipReplayMessage(
        action === "start"
          ? `Started relationship replay #${replay.id}.`
          : `Cancelled relationship replay #${replay.id}.`,
      );
      await refreshRelationshipReplays();
    } catch (actionError) {
      setRelationshipReplaysError(
        actionError instanceof ApiError ? actionError.message : "Unable to update relationship replay.",
      );
    } finally {
      setRelationshipReplayBusyAction(null);
    }
  }

  useEffect(() => {
    void refreshDuplicateCandidates();
  }, [refreshDuplicateCandidates]);

  useEffect(() => {
    void refreshCanonicalSeries();
  }, [refreshCanonicalSeries]);

  useEffect(() => {
    void refreshCanonicalCreators();
  }, [refreshCanonicalCreators]);

  useEffect(() => {
    void refreshMetadataAudits();
  }, [refreshMetadataAudits]);

  useEffect(() => {
    void refreshOcrBatches();
  }, [refreshOcrBatches]);

  useEffect(() => {
    void refreshOcrReplays();
  }, [refreshOcrReplays]);

  useEffect(() => {
    void refreshRelationshipReplays();
  }, [refreshRelationshipReplays]);

  useEffect(() => {
    void refreshRecentCoverImages();
  }, [refreshRecentCoverImages]);

  useEffect(() => {
    void refreshDuplicateCoverGroups();
  }, [refreshDuplicateCoverGroups]);

  useEffect(() => {
    let cancelled = false;
    const objectUrls: string[] = [];

    if (recentCoversLoading) {
      return () => {
        cancelled = true;
        objectUrls.forEach((url) => URL.revokeObjectURL(url));
      };
    }

    if (recentCoverImages.length === 0) {
      setCoverThumbUrls({});
      setCoverThumbErrors({});
      return () => {
        cancelled = true;
      };
    }

    async function loadThumbnails() {
      const nextUrls: Record<number, string> = {};
      const nextErrs: Record<number, boolean> = {};
      await Promise.all(
        recentCoverImages.map(async (row) => {
          try {
            const blob = await apiClient.fetchCoverImageBlob(
              row.thumbnail_fetch_path ?? row.fetch_path,
            );
            if (cancelled) return;
            const url = URL.createObjectURL(blob);
            objectUrls.push(url);
            nextUrls[row.id] = url;
          } catch {
            if (!cancelled) {
              nextErrs[row.id] = true;
            }
          }
        }),
      );
      if (!cancelled) {
        setCoverThumbUrls(nextUrls);
        setCoverThumbErrors(nextErrs);
      }
    }

    void loadThumbnails();

    return () => {
      cancelled = true;
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [recentCoverImages, recentCoversLoading]);

  useEffect(() => {
    let cancelled = false;
    const objectUrls: string[] = [];

    if (duplicateCoversLoading) {
      return () => {
        cancelled = true;
        objectUrls.forEach((url) => URL.revokeObjectURL(url));
      };
    }

    const idToPath = new Map<number, string>();
    for (const group of duplicateCoverGroups) {
      for (const cover of group.covers) {
        idToPath.set(cover.id, cover.thumbnail_fetch_path ?? cover.fetch_path);
      }
    }

    if (idToPath.size === 0) {
      setDupCoverThumbUrls({});
      setDupCoverThumbErrors({});
      return () => {
        cancelled = true;
      };
    }

    async function loadDupThumbnails(): Promise<void> {
      const nextUrls: Record<number, string> = {};
      const nextErrs: Record<number, boolean> = {};
      await Promise.all(
        [...idToPath.entries()].map(async ([coverId, fetchPath]) => {
          try {
            const blob = await apiClient.fetchCoverImageBlob(fetchPath);
            if (cancelled) {
              return;
            }
            const url = URL.createObjectURL(blob);
            objectUrls.push(url);
            nextUrls[coverId] = url;
          } catch {
            if (!cancelled) {
              nextErrs[coverId] = true;
            }
          }
        }),
      );
      if (!cancelled) {
        setDupCoverThumbUrls(nextUrls);
        setDupCoverThumbErrors(nextErrs);
      }
    }

    void loadDupThumbnails();

    return () => {
      cancelled = true;
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [duplicateCoverGroups, duplicateCoversLoading]);

  async function persistDuplicateDecision(
    group: OpsInventoryDuplicateCandidateGroup,
    reviewStatus: "confirmed_duplicate" | "not_duplicate",
  ): Promise<void> {
    setBusyDuplicateIdentityKey(group.metadata_identity_key);
    setDuplicateCandidatesError(null);
    try {
      const draft = duplicateNotesDraft[group.metadata_identity_key] ?? "";
      const trimmedDraft = draft.trim();

      const payload: DuplicateCandidateReviewDecisionPayload = {
        metadata_identity_key: group.metadata_identity_key,
        review_status: reviewStatus,
      };

      if (trimmedDraft.length > 0) {
        payload.notes = trimmedDraft;
      }

      await apiClient.postDuplicateCandidateReviewDecision(payload);
      await refreshDuplicateCandidates();
    } catch (actionError) {
      setDuplicateCandidatesError(
        actionError instanceof ApiError
          ? actionError.message
          : "Unable to save duplicate review decision.",
      );
    } finally {
      setBusyDuplicateIdentityKey(null);
    }
  }

  async function saveDuplicateCandidateNotes(metadataIdentityKey: string): Promise<void> {
    setBusyDuplicateIdentityKey(metadataIdentityKey);
    setDuplicateCandidatesError(null);
    try {
      const draftValue = duplicateNotesDraft[metadataIdentityKey] ?? "";
      const trimmed = draftValue.trim();
      await apiClient.patchDuplicateCandidateReviewNotes({
        metadata_identity_key: metadataIdentityKey,
        notes: trimmed.length > 0 ? trimmed : null,
      });
      await refreshDuplicateCandidates();
    } catch (actionError) {
      setDuplicateCandidatesError(
        actionError instanceof ApiError
          ? actionError.message
          : "Unable to save duplicate review notes.",
      );
    } finally {
      setBusyDuplicateIdentityKey(null);
    }
  }

  async function enqueueDraftReenrichment(): Promise<void> {
    const importId = Number(reenrichDraftImportId.trim());
    if (!Number.isInteger(importId) || importId < 1) {
      setError("Enter a valid draft import id before queueing re-enrichment.");
      return;
    }
    setReenrichBusyKey("draft");
    setError(null);
    setReenrichMessage(null);
    try {
      const response = await apiClient.enqueueImportReenrichment(
        importId,
        reenrichReason.trim() || undefined,
      );
      setReenrichMessage(`Queued ${response.entity_type} #${response.entity_id} as job ${response.job_id}.`);
      await refreshMetadataAudits();
    } catch (actionError) {
      setError(
        actionError instanceof ApiError
          ? actionError.message
          : "Unable to queue draft metadata re-enrichment.",
      );
    } finally {
      setReenrichBusyKey(null);
    }
  }

  async function enqueueInventoryReenrichment(): Promise<void> {
    const inventoryCopyId = Number(reenrichInventoryCopyId.trim());
    if (!Number.isInteger(inventoryCopyId) || inventoryCopyId < 1) {
      setError("Enter a valid inventory copy id before queueing re-enrichment.");
      return;
    }
    setReenrichBusyKey("inventory");
    setError(null);
    setReenrichMessage(null);
    try {
      const response = await apiClient.enqueueInventoryReenrichment(
        inventoryCopyId,
        reenrichReason.trim() || undefined,
      );
      setReenrichMessage(`Queued ${response.entity_type} #${response.entity_id} as job ${response.job_id}.`);
      await refreshMetadataAudits();
    } catch (actionError) {
      setError(
        actionError instanceof ApiError
          ? actionError.message
          : "Unable to queue inventory metadata re-enrichment.",
      );
    } finally {
      setReenrichBusyKey(null);
    }
  }

  if (isLoading) {
    return (
      <AppShell>
        <LoadingState
          title="Loading operations dashboard"
          description="Refreshing Gmail syncs, parse jobs, imports, queue health, and operational events."
        />
      </AppShell>
    );
  }

  const filteredAliases = metadataAliases.filter((alias) =>
    aliasTypeFilter === "all" ? true : alias.alias_type === aliasTypeFilter,
  );
  const filteredRecentCoverImages = recentCoverImages.filter(
    (row) =>
      ocrQualityFilterPasses(row, coverOpsQualitySeverityFilter, coverOpsQualityTypeFilter) &&
      matchCandidateFilterPasses(row, coverOpsMatchConfidenceFilter, coverOpsMatchTypeFilter),
  );

  return (
    <AppShell>
      <PageHeader
        eyebrow="Operations"
        title="Ingestion Monitoring"
        description="Lightweight operational visibility for Gmail ingestion, parser activity, queue health, and import lifecycle state."
      />

      <details className="mt-6 rounded-3xl border border-amber-400/40 bg-amber-400/10 p-4 shadow-xl shadow-black/25 [&>summary::-webkit-details-marker]:hidden">
        <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-amber-50">Fleet exports (deterministic snapshots)</h2>
              <p className="mt-1 max-w-3xl text-[11px] text-amber-100/85">
                Ops-only CSV/JSON. Rows include deterministic{" "}
                <span className="font-semibold">owner identifiers</span> where the schema requires multi-tenant context.
              </p>
            </div>
            <span className="rounded-full border border-amber-200/50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-100">
              Ops / multi-tenant
            </span>
          </div>
        </summary>
        <div className="mt-5 flex flex-wrap gap-2 border-t border-amber-200/20 pt-4">
          <button
            type="button"
            className={opsExportChipClass}
            onClick={() => void opsFleetExport(() => apiClient.downloadOpsReportsInventoryCsvAll())}
          >
            Ops inventory CSV
          </button>
          <button
            type="button"
            className={opsExportChipClass}
            onClick={() => void opsFleetExport(() => apiClient.downloadOpsReportsInventoryJsonAll())}
          >
            Ops inventory JSON
          </button>
          <button
            type="button"
            className={opsExportChipClass}
            onClick={() => void opsFleetExport(() => apiClient.downloadOpsReportsActionCenterCsv())}
          >
            Ops action center CSV
          </button>
          <button
            type="button"
            className={opsExportChipClass}
            onClick={() => void opsFleetExport(() => apiClient.downloadOpsReportsOrderArrivalCsv())}
          >
            Ops order / arrival CSV
          </button>
          <button
            type="button"
            className={opsExportChipClass}
            onClick={() => void opsFleetExport(() => apiClient.downloadOpsReportsRunDetectionCsv())}
          >
            Ops missing issues CSV
          </button>
          <button
            type="button"
            className={opsExportChipClass}
            onClick={() => void opsFleetExport(() => apiClient.downloadOpsReportsTimelineCsv())}
          >
            Ops timeline CSV
          </button>
          <button
            type="button"
            className={opsExportChipClass}
            onClick={() => void opsFleetExport(() => apiClient.downloadOpsReportsCollectionSummaryJson())}
          >
            Ops collection summary JSON
          </button>
        </div>
      </details>

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      {inventoryFmvError ? (
        <div className="mt-6">
          <StatusBanner tone="warning">{inventoryFmvError}</StatusBanner>
        </div>
      ) : null}

      {!inventoryFmvLoading ? (
        <section className="mt-6 rounded-3xl border border-cyan-400/30 bg-cyan-950/20 p-5 shadow-xl shadow-black/25">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-cyan-50">Inventory FMV coverage</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Deterministic market valuation attached to inventory copies. Currencies stay separated, preorder rows stay
                informational, and cancelled rows are excluded from active value.
              </p>
            </div>
            <span className="rounded-full border border-cyan-300/40 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/90">
              Ops / FMV
            </span>
          </div>
          {portfolioValueSummary?.items.length ? (
            <div className="mt-5 space-y-6">
              {portfolioValueSummary.items.map((bucket) => (
                <div key={bucket.currency_code} className="rounded-2xl border border-white/10 bg-slate-950/55 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">{bucket.currency_code}</p>
                      <p className="mt-1 text-sm text-slate-300">Separated currency bucket</p>
                    </div>
                    <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                      Active value {formatCurrencyWithCode(bucket.total_active_market_value, bucket.currency_code)}
                    </div>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <StatCard label="Raw" value={formatCurrencyWithCode(bucket.raw_market_value, bucket.currency_code)} />
                    <StatCard label="Graded" value={formatCurrencyWithCode(bucket.graded_market_value, bucket.currency_code)} />
                    <StatCard
                      label="Preorder informational"
                      value={formatCurrencyWithCode(bucket.preorder_informational_value, bucket.currency_code)}
                    />
                    <StatCard
                      label="Low-confidence"
                      value={formatCurrencyWithCode(bucket.low_confidence_value, bucket.currency_code)}
                    />
                    <StatCard label="Stale value" value={formatCurrencyWithCode(bucket.stale_value, bucket.currency_code)} />
                    <StatCard label="No market data" value={String(bucket.no_market_data_count)} />
                    <StatCard label="Cancelled excluded" value={String(bucket.cancelled_excluded_count)} />
                    <StatCard
                      label="Duplicate exposure"
                      value={formatCurrencyWithCode(bucket.duplicate_value_exposure, bucket.currency_code)}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-400">No portfolio FMV summary returned.</p>
          )}
          <div className="mt-6 grid gap-4 xl:grid-cols-3">
            {inventoryFmvPanels.map(({ title, resp }) => (
              <article key={title} className="rounded-2xl border border-white/10 bg-slate-950/55 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-white">{title}</h3>
                    <p className="text-xs text-slate-500">{resp?.total ?? 0} rows shown</p>
                  </div>
                  <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-300">
                    FMV
                  </span>
                </div>
                <div className="mt-3 space-y-2">
                  {resp?.items.slice(0, 8).map((item) => (
                    <Link
                      key={item.inventory_copy_id}
                      to={`/inventory/${item.inventory_copy_id}`}
                      className="block rounded-xl border border-white/10 bg-slate-900/70 p-3 transition hover:border-cyan-300/35 hover:bg-slate-900"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-medium text-white">{item.title}</p>
                          <p className="text-xs text-slate-400">{item.publisher} #{item.issue_number}</p>
                        </div>
                        <div className="text-right text-xs text-slate-400">
                          <p>{item.valuation_scope?.replace(/_/g, " ")}</p>
                          <p className="mt-1 text-slate-300">
                            {item.current_market_fmv
                              ? formatCurrencyWithCode(item.current_market_fmv, item.fmv_currency_code ?? "USD")
                              : "—"}
                          </p>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <details className="mt-6 rounded-3xl border border-cyan-400/40 bg-cyan-950/20 p-5 shadow-xl shadow-black/25 [&>summary::-webkit-details-marker]:hidden">
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-cyan-50">Bulk ingest operations</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Consolidated fleet counters for scan sessions, persisted QA, open routing recommendations, high-resolution
                queues, physical intake projections, pipeline replays that reported item changes, and bulk-ingest scanner
                presets. Read-only aggregates — no OCR enqueue and no metadata mutation from these reads.
              </p>
              <p className="mt-2 max-w-3xl text-[11px] text-cyan-100/85">
                Collapsed by default to avoid repeating the QA / replay / routing drawers below — expand when you want the
                single-pane headline rollup before drilling into ledger tables.
              </p>
            </div>
            <span className="rounded-full border border-cyan-300/40 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/90">
              Ops / ingest
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-cyan-200/20 pt-4">
          {opsScanPipelineDashLoading ? (
            <p className="text-sm text-slate-400">Loading bulk ingest dashboard…</p>
          ) : opsScanPipelineDashError ? (
            <StatusBanner tone="error">{opsScanPipelineDashError}</StatusBanner>
          ) : opsScanPipelineDash ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6">
                <StatCard label="Active sessions" value={String(opsScanPipelineDash.summary.active_sessions)} />
                <StatCard
                  label="Sessions · completed w/ errors"
                  value={String(opsScanPipelineDash.summary.sessions_completed_with_errors)}
                />
                <StatCard label="Σ session failed items" value={String(opsScanPipelineDash.summary.failed_items)} />
                <StatCard label="Review-required items" value={String(opsScanPipelineDash.summary.review_required_items)} />
                <StatCard label="QA persisted · needs rescan" value={String(opsScanPipelineDash.summary.qa_needs_rescan)} />
                <StatCard
                  label="QA persisted · corrupt / unreadable"
                  value={String(opsScanPipelineDash.summary.qa_corrupt_or_unreadable)}
                />
                <StatCard
                  label="Open routing · recommend OCR"
                  value={String(opsScanPipelineDash.summary.routing_recommend_ocr)}
                />
                <StatCard
                  label="Open routing · high-res review"
                  value={String(opsScanPipelineDash.summary.routing_recommend_high_res_review)}
                />
                <StatCard label="High-res queue · pending" value={String(opsScanPipelineDash.summary.high_res_pending)} />
                <StatCard
                  label="Physical intake · received pending scan"
                  value={String(opsScanPipelineDash.summary.physical_intake_received_pending_scan)}
                />
                <StatCard
                  label="Replay runs w/ changes"
                  value={String(opsScanPipelineDash.summary.replay_runs_with_changes)}
                />
              </div>

              <div className="mt-8 grid gap-6 xl:grid-cols-2">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Bulk ingest · active / paused (preview)
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    First page from the pipeline dashboard; see{" "}
                    <span className="text-slate-300">Scan sessions (fleet)</span> for the full ledger.
                  </p>
                  <div className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Session</th>
                          <th className="p-3 font-medium">Owner</th>
                          <th className="p-3 font-medium">Status</th>
                          <th className="p-3 font-medium">Fails / total</th>
                          <th className="p-3 font-medium">Updated</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10 text-slate-200">
                        {opsBulkPipelineActiveSessions.length === 0 ? (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={5}>
                              No active bulk-ingest sessions in the preview window.
                            </td>
                          </tr>
                        ) : (
                          opsBulkPipelineActiveSessions.slice(0, 12).map((row) => (
                            <tr key={row.id}>
                              <td className="p-3 font-mono text-[11px] text-white">#{row.id}</td>
                              <td className="p-3 font-mono text-[11px]">#{row.owner_user_id}</td>
                              <td className="p-3 capitalize">{row.status.replace(/_/g, " ")}</td>
                              <td className="p-3">
                                {row.failed_items}/{row.total_items}
                              </td>
                              <td className="p-3 text-slate-400">{formatDateTime(row.updated_at)}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Bulk ingest · completed with errors (preview)
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Surfaced from recent terminal sessions; cross-check QA &amp; routing panels below.
                  </p>
                  <div className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Session</th>
                          <th className="p-3 font-medium">Owner</th>
                          <th className="p-3 font-medium">Fails / total</th>
                          <th className="p-3 font-medium">Preset</th>
                          <th className="p-3 font-medium">Updated</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10 text-slate-200">
                        {opsBulkPipelineSessionsCompletedWithErrors.length === 0 ? (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={5}>
                              No recent bulk-ingest sessions completed with errors in the preview window.
                            </td>
                          </tr>
                        ) : (
                          opsBulkPipelineSessionsCompletedWithErrors.slice(0, 12).map((row) => (
                            <tr key={row.id}>
                              <td className="p-3 font-mono text-[11px] text-white">#{row.id}</td>
                              <td className="p-3 font-mono text-[11px]">#{row.owner_user_id}</td>
                              <td className="p-3">
                                {row.failed_items}/{row.total_items}
                              </td>
                              <td className="p-3 text-slate-300">{row.scanner_profile ?? "—"}</td>
                              <td className="p-3 text-slate-400">{formatDateTime(row.updated_at)}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <div className="mt-8">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  Scanner presets · fleet usage (bulk ingest)
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Counts grouped by linked profile id / frozen preset label on scan sessions with items.
                </p>
                {opsScanPipelineDash.summary.most_used_scanner_profiles.length === 0 ? (
                  <p className="mt-3 text-sm text-slate-500">No labelled bulk-ingest presets recorded yet.</p>
                ) : (
                  <div className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Preset</th>
                          <th className="p-3 font-medium">Profile id</th>
                          <th className="p-3 font-medium">Sessions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10 text-slate-200">
                        {opsScanPipelineDash.summary.most_used_scanner_profiles.map((row, idx) => (
                          <tr key={`${row.scanner_profile_id ?? "nl"}-${row.profile_label}-${idx}`}>
                            <td className="p-3 text-slate-100">{row.profile_label}</td>
                            <td className="p-3 font-mono text-[11px]">
                              {row.scanner_profile_id != null ? `#${row.scanner_profile_id}` : "—"}
                            </td>
                            <td className="p-3">{row.scan_session_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">No pipeline dashboard payload.</p>
          )}
        </div>
      </details>

      <nav
        id="market-ops-quicknav"
        aria-label="Market workspace navigation"
        className="mt-6 flex flex-wrap gap-2 rounded-2xl border border-emerald-500/25 bg-slate-950/45 p-4 text-[11px] text-slate-200"
      >
        <span className="font-semibold uppercase tracking-[0.12em] text-emerald-100/90">Market ops shortcuts</span>
        {[
          ["Dealer dashboard", "#dealer-dashboard-ops"],
          ["Grading dashboard", "#dealer-grading-dashboard-ops"],
          ["Strategy dashboard", "#portfolio-strategy-dashboard-ops"],
          ["P39 checksum & trace", "#market-intelligence-p39-trace"],
          ["P39 feed", "#market-feed"],
          ["Market scoring", "#market-scoring-ops"],
          ["Market signals", "#market-signal-ops"],
          ["Market opportunities", "#market-opportunity-ops"],
          ["Portfolio-market coupling", "#market-portfolio-coupling-ops"],
          ["Market normalization", "#market-normalization-ops"],
          ["Market ingestion", "#market-ingestion-ops"],
          ["Portfolio registry", "#portfolio-registry-ops"],
          ["Duplicate consolidation", "#duplicate-consolidation-ops"],
          ["Portfolio liquidity", "#portfolio-liquidity-ops"],
          ["Portfolio recommendations", "#portfolio-recommendation-ops"],
          ["Acquisition priorities", "#acquisition-priority-ops"],
          ["Concentration risk", "#concentration-risk-ops"],
          ["Grading reports", "#grading-reporting-ops"],
          ["Operational reports", "#operational-reporting-ops"],
          ["Grading candidates", "#grading-candidate-ops"],
          ["Grading spreads", "#grading-spread-ops"],
          ["Grading recommendations", "#grading-recommendation-ops"],
          ["Grading risk", "#grading-risk-ops"],
          ["Listing intelligence", "#listing-intelligence-ops"],
          ["Convention", "#convention-ops"],
          ["Liquidity", "#liquidity-ops"],
          ["Realized sales", "#sales-ledger-ops"],
          ["Market sale evidence", "#ops-market-sales-anchor"],
          ["Listings registry", "#listing-registry-ops"],
          ["Listing exports", "#listing-export-ops"],
          ["Review queue", "#market-sale-review-queue"],
          ["Comp readiness", "#market-comp-eligibility"],
          ["Grouped comps", "#market-comps"],
          ["FMV snapshots", "#market-fmv"],
          ["Trends", "#market-trends"],
          ["Match suggestions", "#market-match-suggestions"],
        ].map(([label, hash]) => (
          <a key={hash} className="rounded-full border border-white/15 px-2 py-1 hover:border-emerald-300/55" href={hash}>
            {label}
          </a>
        ))}
      </nav>

      <details
        id="listing-registry-ops"
        open
        className="mt-4 rounded-3xl border border-amber-400/35 bg-amber-950/10 p-5 shadow-xl shadow-black/15 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Listing registry explorer</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Deterministic status distribution plus the newest lifecycle spine rows — read-only bookkeeping for manual,
                exporter, convention, Shopify, Whatnot lanes. Mutations remain owner-initiated endpoints only.
              </p>
            </div>
            <span className="rounded-full border border-amber-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-100/90">
              Ops / listings
            </span>
          </div>
        </summary>
        <div className="mt-5 space-y-4 border-t border-amber-200/15 pt-4">
          {opsListingDistributionLoading ? (
            <p className="text-sm text-slate-400">Loading listing status counts…</p>
          ) : opsListingDistributionError ? (
            <StatusBanner tone="error">{opsListingDistributionError}</StatusBanner>
          ) : opsListingDistribution ? (
            <div className="flex flex-wrap gap-2">
              {opsListingDistribution.rows.map((row) => (
                <span
                  key={row.status}
                  className="rounded-full border border-white/15 bg-slate-950/55 px-3 py-1 text-[11px] text-slate-100"
                >
                  <span className="font-semibold text-amber-100">{row.status}</span>
                  <span className="ml-2 font-mono text-slate-300">×{row.count}</span>
                </span>
              ))}
              {opsListingDistribution.rows.length === 0 ? (
                <span className="text-sm text-slate-500">No listings persisted yet.</span>
              ) : null}
            </div>
          ) : null}

          {opsListingEventsFeedLoading ? (
            <p className="text-sm text-slate-400">Loading listing audit feed…</p>
          ) : opsListingEventsFeedError ? (
            <StatusBanner tone="error">{opsListingEventsFeedError}</StatusBanner>
          ) : opsListingEventsFeed ? (
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Listing</th>
                    <th className="p-3 font-medium">Event</th>
                    <th className="p-3 font-medium">Statuses</th>
                    <th className="p-3 font-medium">Recorded</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsListingEventsFeed.items.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={4}>
                        No lifecycle events recorded yet.
                      </td>
                    </tr>
                  ) : (
                    opsListingEventsFeed.items.map((evt) => (
                      <tr key={evt.id}>
                        <td className="p-3 font-mono text-[11px]">#{evt.listing_id}</td>
                        <td className="p-3">{evt.event_type.replace(/_/g, " ")}</td>
                        <td className="p-3 text-slate-400">
                          {(evt.prior_status ?? "—")} → {(evt.new_status ?? "—")}
                        </td>
                        <td className="p-3 text-slate-400">{formatDateTime(evt.created_at)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </details>

      <details
        id="dealer-dashboard-ops"
        open
        className="mt-6 rounded-3xl border border-lime-500/35 bg-slate-950/80 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Dealer dashboard ops telescope</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Mirrors owner `/dealer-dashboard*` payloads with deterministic snapshot rows plus append-safe alerts/feeds scoped by optional `owner_user_id`.
              </p>
            </div>
            <span className="rounded-full border border-lime-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-lime-100/90">
              Ops / dealer
            </span>
          </div>
        </summary>
        <div className="mt-5 space-y-4 border-t border-lime-200/15 pt-4">
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
              Owner user id
              <input
                value={opsDealerOwnerDraft}
                onChange={(e) => setOpsDealerOwnerDraft(e.target.value)}
                className="mt-2 w-52 rounded-xl border border-white/15 bg-slate-950/70 px-3 py-2 text-sm text-white"
                placeholder="Blank = aggregate"
              />
            </label>
            <button
              type="button"
              className="rounded-xl border border-lime-400/45 px-3 py-2 text-xs font-semibold text-lime-100"
              onClick={() => {
                const trimmed = opsDealerOwnerDraft.trim();
                if (!trimmed) {
                  setOpsDealerOwnerApplied(undefined);
                  return;
                }
                const n = Number(trimmed);
                setOpsDealerOwnerApplied(Number.isFinite(n) && n > 0 ? Math.floor(n) : undefined);
              }}
            >
              Apply scope
            </button>
          </div>

          {opsDealerDashLoading ? (
            <p className="text-sm text-slate-400">Loading dealer snapshots…</p>
          ) : opsDealerDashError ? (
            <StatusBanner tone="error">{opsDealerDashError}</StatusBanner>
          ) : opsDealerDash?.snapshot ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5 text-xs">
              <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-3">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Snapshot date</p>
                <p className="mt-2 text-sm text-white">{opsDealerDash.snapshot.snapshot_date}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-3">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Owner user</p>
                <p className="mt-2 font-mono text-sm text-white">#{opsDealerDash.snapshot.owner_user_id}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-3">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Liquidity hi / low</p>
                <p className="mt-2 text-sm text-white">
                  {opsDealerDash.snapshot.liquidity_high_count} · {opsDealerDash.snapshot.liquidity_low_count}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-3">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Exports 30d</p>
                <p className="mt-2 text-sm text-white">
                  {opsDealerDash.snapshot.export_run_count_30d} runs · {opsDealerDash.snapshot.failed_export_count_30d} degraded
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-3">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Checksum</p>
                <p className="mt-2 break-all font-mono text-[11px] text-slate-300">{abbrevExportChecksum(opsDealerDash.snapshot.checksum)}</p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">No dealer snapshots materialized.</p>
          )}

          <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
            <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Alerts · recent slice</p>
            <table className="mt-3 w-full border-collapse text-left text-xs">
              <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th className="p-3 font-medium">When</th>
                  <th className="p-3 font-medium">Severity</th>
                  <th className="p-3 font-medium">Type</th>
                  <th className="p-3 font-medium">Evidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10 text-slate-200">
                {opsDealerAlerts.length === 0 ? (
                  <tr>
                    <td className="p-4 text-slate-500" colSpan={4}>
                      No alerts in this scope.
                    </td>
                  </tr>
                ) : (
                  opsDealerAlerts.map((alertRow) => (
                    <tr key={alertRow.id}>
                      <td className="whitespace-nowrap p-3 text-slate-500">{formatDateTime(alertRow.created_at)}</td>
                      <td className="p-3 font-semibold">{alertRow.severity}</td>
                      <td className="p-3">{alertRow.alert_type}</td>
                      <td className="p-3 text-slate-400">{alertRow.message}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
            <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Operational feed</p>
            <table className="mt-3 w-full border-collapse text-left text-xs">
              <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th className="p-3 font-medium">When</th>
                  <th className="p-3 font-medium">Type</th>
                  <th className="p-3 font-medium">Summary</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10 text-slate-200">
                {opsDealerFeed.length === 0 ? (
                  <tr>
                    <td className="p-4 text-slate-500" colSpan={3}>
                      Append-only deterministic feed waits for dealer snapshot generation.
                    </td>
                  </tr>
                ) : (
                  opsDealerFeed.map((evt) => (
                    <tr key={evt.id}>
                      <td className="whitespace-nowrap p-3 text-slate-500">{formatDateTime(evt.created_at)}</td>
                      <td className="p-3">{evt.event_type}</td>
                      <td className="p-3 text-slate-400">{evt.summary}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
            <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Derived metrics ledger</p>
            <table className="mt-3 w-full border-collapse text-left text-xs">
              <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th className="p-3 font-medium">Metric key</th>
                  <th className="p-3 font-medium">Decimal</th>
                  <th className="p-3 font-medium">Text</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10 text-slate-200">
                {opsDealerMetrics.length === 0 ? (
                  <tr>
                    <td className="p-4 text-slate-500" colSpan={3}>
                      Metrics hydrate when dealer snapshots persist.
                    </td>
                  </tr>
                ) : (
                  opsDealerMetrics.map((metricRow) => (
                    <tr key={metricRow.id}>
                      <td className="p-3 font-mono text-[11px] text-slate-300">{metricRow.metric_key}</td>
                      <td className="p-3 text-slate-400">{metricRow.metric_value_decimal ?? "—"}</td>
                      <td className="p-3 text-slate-400">{metricRow.metric_value_text ?? "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </details>

      <details
        id="dealer-grading-dashboard-ops"
        open
        className="mt-6 rounded-3xl border border-cyan-500/35 bg-slate-950/80 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Dealer grading dashboard ops telescope</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Mirrors owner `/dealer-grading-dashboard*` payloads with deterministic grading snapshots, observational alerts,
                append-safe feed rows, and derived grading KPI metrics under optional `owner_user_id` scope.
              </p>
            </div>
            <span className="rounded-full border border-cyan-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/90">
              Ops / grading
            </span>
          </div>
        </summary>
        <div className="mt-5 space-y-4 border-t border-cyan-200/15 pt-4">
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
              Owner user id
              <input
                value={opsDealerGradingOwnerDraft}
                onChange={(e) => setOpsDealerGradingOwnerDraft(e.target.value)}
                className="mt-2 w-52 rounded-xl border border-white/15 bg-slate-950/70 px-3 py-2 text-sm text-white"
                placeholder="Blank = aggregate"
              />
            </label>
            <button
              type="button"
              className="rounded-xl border border-cyan-400/45 px-3 py-2 text-xs font-semibold text-cyan-100"
              onClick={() => {
                const trimmed = opsDealerGradingOwnerDraft.trim();
                if (!trimmed) {
                  setOpsDealerGradingOwnerApplied(undefined);
                  return;
                }
                const n = Number(trimmed);
                setOpsDealerGradingOwnerApplied(Number.isFinite(n) && n > 0 ? Math.floor(n) : undefined);
              }}
            >
              Apply scope
            </button>
          </div>

          {opsDealerGradingDashLoading ? (
            <p className="text-sm text-slate-400">Loading grading dashboard snapshots…</p>
          ) : opsDealerGradingDashError ? (
            <StatusBanner tone="error">{opsDealerGradingDashError}</StatusBanner>
          ) : opsDealerGradingDash?.snapshot ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5 text-xs">
              <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-3">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Snapshot date</p>
                <p className="mt-2 text-sm text-white">{opsDealerGradingDash.snapshot.snapshot_date}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-3">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Owner user</p>
                <p className="mt-2 font-mono text-sm text-white">#{opsDealerGradingDash.snapshot.owner_user_id}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-3">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Candidates active / graded</p>
                <p className="mt-2 text-sm text-white">
                  {opsDealerGradingDash.snapshot.active_candidate_count} · {opsDealerGradingDash.snapshot.graded_candidate_count}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-3">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Risk / confidence flags</p>
                <p className="mt-2 text-sm text-white">
                  {opsDealerGradingDash.snapshot.high_risk_candidate_count} high risk ·{" "}
                  {opsDealerGradingDash.snapshot.low_confidence_candidate_count} low confidence
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-3">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Checksum</p>
                <p className="mt-2 break-all font-mono text-[11px] text-slate-300">
                  {abbrevExportChecksum(opsDealerGradingDash.snapshot.checksum)}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">No grading snapshots materialized.</p>
          )}

          <div className="grid gap-4 xl:grid-cols-2">
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Alerts</p>
              <table className="mt-3 w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">When</th>
                    <th className="p-3 font-medium">Severity</th>
                    <th className="p-3 font-medium">Type</th>
                    <th className="p-3 font-medium">Evidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsDealerGradingAlerts.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={4}>
                        No grading alerts in this scope.
                      </td>
                    </tr>
                  ) : (
                    opsDealerGradingAlerts.map((row) => (
                      <tr key={row.id}>
                        <td className="whitespace-nowrap p-3 text-slate-500">{formatDateTime(row.created_at)}</td>
                        <td className="p-3 font-semibold">{row.severity}</td>
                        <td className="p-3">{row.alert_type}</td>
                        <td className="p-3 text-slate-400">{row.message}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Feed</p>
              <table className="mt-3 w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">When</th>
                    <th className="p-3 font-medium">Type</th>
                    <th className="p-3 font-medium">Summary</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsDealerGradingFeed.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={3}>
                        Append-only grading feed waits for grading snapshot generation.
                      </td>
                    </tr>
                  ) : (
                    opsDealerGradingFeed.map((row) => (
                      <tr key={row.id}>
                        <td className="whitespace-nowrap p-3 text-slate-500">{formatDateTime(row.created_at)}</td>
                        <td className="p-3">{row.event_type}</td>
                        <td className="p-3 text-slate-400">{row.summary}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
            <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
              Metrics / grading KPIs
            </p>
            <table className="mt-3 w-full border-collapse text-left text-xs">
              <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th className="p-3 font-medium">Metric key</th>
                  <th className="p-3 font-medium">Decimal</th>
                  <th className="p-3 font-medium">Text</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10 text-slate-200">
                {opsDealerGradingMetrics.length === 0 ? (
                  <tr>
                    <td className="p-4 text-slate-500" colSpan={3}>
                      Metrics hydrate when grading snapshots persist.
                    </td>
                  </tr>
                ) : (
                  opsDealerGradingMetrics.map((row) => (
                    <tr key={row.id}>
                      <td className="p-3 font-mono text-[11px] text-slate-300">{row.metric_key}</td>
                      <td className="p-3 text-slate-400">{row.metric_value_decimal ?? "—"}</td>
                      <td className="p-3 text-slate-400">{row.metric_value_text ?? "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </details>

      <details
        id="portfolio-registry-ops"
        open
        className="mt-6 rounded-3xl border border-amber-500/35 bg-slate-950/80 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Portfolio registry ops</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Read-only portfolio, exposure snapshots, deterministic evidence joins, allocation rollups, and checksum fields.
                Scoped with optional owner filter; aligns with `/ops/portfolios*`.
              </p>
            </div>
            <span className="rounded-full border border-amber-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-100/90">
              Ops / portfolio
            </span>
          </div>
        </summary>
        <div className="mt-5 space-y-4 border-t border-amber-200/15 pt-4">
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
              Owner user id
              <input
                value={opsPortfolioOwnerDraft}
                onChange={(e) => setOpsPortfolioOwnerDraft(e.target.value)}
                className="mt-2 w-52 rounded-xl border border-white/15 bg-slate-950/70 px-3 py-2 text-sm text-white"
                placeholder="Blank = all owners"
              />
            </label>
            <button
              type="button"
              className="rounded-xl border border-amber-400/45 px-3 py-2 text-xs font-semibold text-amber-50"
              onClick={() => {
                const trimmed = opsPortfolioOwnerDraft.trim();
                if (!trimmed) {
                  setOpsPortfolioOwnerApplied(undefined);
                  return;
                }
                const n = Number(trimmed);
                setOpsPortfolioOwnerApplied(Number.isFinite(n) && n > 0 ? Math.floor(n) : undefined);
              }}
            >
              Apply scope
            </button>
          </div>

          {opsPortfolioLoading ? (
            <p className="text-sm text-slate-400">Loading portfolio ops telescope…</p>
          ) : opsPortfolioError ? (
            <StatusBanner tone="error">{opsPortfolioError}</StatusBanner>
          ) : (
            <div className="grid gap-4 xl:grid-cols-2">
              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Portfolios ({opsPortfolioList?.total_items ?? 0})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Id</th>
                      <th className="p-3 font-medium">Owner</th>
                      <th className="p-3 font-medium">Name</th>
                      <th className="p-3 font-medium">Type</th>
                      <th className="p-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsPortfolioList?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={5}>
                          No portfolios in this scope yet.
                        </td>
                      </tr>
                    ) : (
                      opsPortfolioList?.items.map((row) => (
                        <tr key={row.id}>
                          <td className="p-3 font-mono text-[11px]">{row.id}</td>
                          <td className="p-3 font-mono text-[11px]">{row.owner_user_id}</td>
                          <td className="p-3">{row.name}</td>
                          <td className="p-3 text-slate-400">{row.portfolio_type}</td>
                          <td className="p-3">{row.status}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Portfolio items ({opsPortfolioItems?.total_items ?? 0})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Id</th>
                      <th className="p-3 font-medium">Portfolio</th>
                      <th className="p-3 font-medium">Inventory</th>
                      <th className="p-3 font-medium">Role</th>
                      <th className="p-3 font-medium">Removed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsPortfolioItems?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={5}>
                          Portfolio membership rows hydrate after owners create portfolios/items.
                        </td>
                      </tr>
                    ) : (
                      opsPortfolioItems?.items.map((row) => (
                        <tr key={row.id}>
                          <td className="p-3 font-mono text-[11px]">{row.id}</td>
                          <td className="p-3 font-mono text-[11px]">{row.portfolio_id}</td>
                          <td className="p-3 font-mono text-[11px]">{row.inventory_item_id}</td>
                          <td className="p-3">{row.allocation_role}</td>
                          <td className="p-3 text-slate-400">{row.removed_at ? formatDateTime(row.removed_at) : "active"}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Exposure snapshots ({opsPortfolioExposures?.total_items ?? 0})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Type</th>
                      <th className="p-3 font-medium">Key</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">Batch</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsPortfolioExposures?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={5}>
                          Generate exposures from owner dashboard refresh or API to fill this grid.
                        </td>
                      </tr>
                    ) : (
                      opsPortfolioExposures?.items.slice(0, 40).map((row) => (
                        <tr key={row.id}>
                          <td className="p-3">{row.exposure_type}</td>
                          <td className="p-3 font-mono text-[10px] text-slate-400">{row.exposure_key}</td>
                          <td className="p-3">{row.exposure_status}</td>
                          <td className="p-3 font-mono text-[10px] text-slate-400">
                            {abbrevExportChecksum(row.generation_batch_checksum)}
                          </td>
                          <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Allocation snapshots ({opsPortfolioAllocations?.total_items ?? 0})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Date</th>
                      <th className="p-3 font-medium">Items</th>
                      <th className="p-3 font-medium">Graded/Raw</th>
                      <th className="p-3 font-medium">Liquidity Hi/Lo</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsPortfolioAllocations?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={5}>
                          Allocation snapshots show descriptive posture counts only.
                        </td>
                      </tr>
                    ) : (
                      opsPortfolioAllocations?.items.slice(0, 25).map((row) => (
                        <tr key={row.id}>
                          <td className="p-3 whitespace-nowrap">{row.snapshot_date}</td>
                          <td className="p-3">{row.total_item_count}</td>
                          <td className="p-3">
                            {row.graded_item_count} · {row.raw_item_count}
                          </td>
                          <td className="p-3">
                            {row.high_liquidity_count} · {row.low_liquidity_count}
                          </td>
                          <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45 xl:col-span-2">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Exposure evidence rows ({opsPortfolioEvidence?.total_items ?? 0})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">When</th>
                      <th className="p-3 font-medium">Snapshot</th>
                      <th className="p-3 font-medium">Type</th>
                      <th className="p-3 font-medium">Payload</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsPortfolioEvidence?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={4}>
                          Evidence materializes alongside exposure snapshots.
                        </td>
                      </tr>
                    ) : (
                      opsPortfolioEvidence?.items.slice(0, 35).map((row) => (
                        <tr key={row.id}>
                          <td className="whitespace-nowrap p-3 text-slate-500">{formatDateTime(row.created_at)}</td>
                          <td className="p-3 font-mono text-[11px]">{row.portfolio_exposure_snapshot_id}</td>
                          <td className="p-3">{row.evidence_type}</td>
                          <td className="p-3 text-[10px] text-slate-400">
                            {JSON.stringify(row.evidence_value_json).slice(0, 160)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </details>

      <details
        id="duplicate-consolidation-ops"
        open
        className="mt-6 rounded-3xl border border-rose-500/35 bg-slate-950/80 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Duplicate consolidation ops</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Mirrors `/ops/duplicate-*` deterministic duplicate clusters, per-copy strength tiers, consolidation
                recommendations (observational), and append-only history fingerprints. Shares owner scope controls with portfolio
                registry above.
              </p>
            </div>
            <span className="rounded-full border border-rose-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-rose-100/90">
              Ops / duplicates
            </span>
          </div>
        </summary>
        <div className="mt-5 space-y-4 border-t border-rose-200/15 pt-4">
          {opsPortfolioLoading ? (
            <p className="text-sm text-slate-400">Hydrating duplicate telescope…</p>
          ) : opsPortfolioError ? (
            <StatusBanner tone="error">{opsPortfolioError}</StatusBanner>
          ) : (
            <div className="grid gap-4 xl:grid-cols-2">
              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45 xl:col-span-2">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Duplicate clusters ({opsDuplicateClusters?.items.length ?? 0}) · batch{" "}
                  {abbrevExportChecksum(opsDuplicateClusters?.generation_batch_checksum ?? "")}
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Type</th>
                      <th className="p-3 font-medium">Issue</th>
                      <th className="p-3 font-medium">Liquidity</th>
                      <th className="p-3 font-medium">Dup status</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsDuplicateClusters?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={5}>
                          Generate duplicate snapshots from dashboard or `/duplicate-clusters/generate`.
                        </td>
                      </tr>
                    ) : (
                      opsDuplicateClusters?.items.slice(0, 40).map((row) => (
                        <tr key={row.id}>
                          <td className="p-3">{row.cluster_type}</td>
                          <td className="p-3 font-mono text-[11px] text-slate-400">{String(row.canonical_comic_issue_id ?? "—")}</td>
                          <td className="p-3">{row.liquidity_profile}</td>
                          <td className="p-3">{row.duplication_status}</td>
                          <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45 xl:col-span-2">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Duplicate cluster items ({opsDuplicateClusterItems?.items.length ?? 0})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Inventory</th>
                      <th className="p-3 font-medium">Cluster</th>
                      <th className="p-3 font-medium">Grading</th>
                      <th className="p-3 font-medium">Strength</th>
                      <th className="p-3 font-medium">Priority</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsDuplicateClusterItems?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={5}>
                          Rows appear after clustering runs persist.
                        </td>
                      </tr>
                    ) : (
                      opsDuplicateClusterItems?.items.slice(0, 35).map((row) => (
                        <tr key={row.id}>
                          <td className="p-3 font-mono text-[11px]">{row.inventory_item_id}</td>
                          <td className="p-3 font-mono text-[11px]">{row.duplicate_cluster_id}</td>
                          <td className="p-3">{row.grading_status}</td>
                          <td className="p-3">{row.estimated_strength_score ?? "—"}</td>
                          <td className="p-3">{row.recommendation_priority}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45 xl:col-span-2">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Consolidation recommendations ({opsDuplicateRecos?.items.length ?? 0})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Action</th>
                      <th className="p-3 font-medium">Confidence</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">Cluster</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsDuplicateRecos?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={5}>
                          Recommendation rows hydrate per duplicate cluster snapshot.
                        </td>
                      </tr>
                    ) : (
                      opsDuplicateRecos?.items.slice(0, 35).map((row) => (
                        <tr key={row.id}>
                          <td className="p-3">{row.recommendation_action}</td>
                          <td className="p-3">{row.confidence_level}</td>
                          <td className="p-3">{row.recommendation_status}</td>
                          <td className="p-3 font-mono text-[11px]">{row.duplicate_cluster_id}</td>
                          <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45 xl:col-span-2">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Duplicate history ({opsDuplicateHistory?.items.length ?? 0})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Cluster key</th>
                      <th className="p-3 font-medium">Items</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">Batch</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsDuplicateHistory?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={4}>
                          History increments with each deterministic generation batch.
                        </td>
                      </tr>
                    ) : (
                      opsDuplicateHistory?.items.slice(0, 35).map((row) => (
                        <tr key={row.id}>
                          <td className="p-3 font-mono text-[10px] text-slate-400">{row.cluster_key}</td>
                          <td className="p-3">{row.total_item_count}</td>
                          <td className="p-3">{row.duplication_status}</td>
                          <td className="p-3 font-mono text-[10px] text-slate-400">
                            {abbrevExportChecksum(row.generation_batch_checksum)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </details>

      <details
        id="portfolio-liquidity-ops"
        open
        className="mt-6 rounded-3xl border border-teal-500/40 bg-teal-950/15 p-5 shadow-xl shadow-teal-950/30 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Portfolio liquidity operations</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Read-only `/ops/portfolio-liquidity*` mirrors. Deterministic capital-allocation rollups (buckets, scores, dead
                capital estimate, balance status) generated from liquidity engine rows, FMV, sales, listings, allocations, and
                convention activity — no auto-liquidation and no FMV mutation.
              </p>
            </div>
            <span className="rounded-full border border-teal-300/40 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-teal-100/95">
              Ops / liquidity
            </span>
          </div>
        </summary>
        <div className="mt-5 space-y-4 border-t border-teal-200/15 pt-4">
          {opsPortfolioLoading ? (
            <p className="text-sm text-slate-400">Loading portfolio liquidity snapshots…</p>
          ) : opsPortfolioError ? (
            <StatusBanner tone="error">{opsPortfolioError}</StatusBanner>
          ) : (
            <div className="grid gap-4 xl:grid-cols-2">
              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45 xl:col-span-2">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Liquidity snapshots ({opsPortfolioLiquidityList?.total ?? 0}) · uses same owner scope as portfolio registry
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Id</th>
                      <th className="p-3 font-medium">Owner</th>
                      <th className="p-3 font-medium">Scope</th>
                      <th className="p-3 font-medium">Date</th>
                      <th className="p-3 font-medium">Liquid FMV</th>
                      <th className="p-3 font-medium">Illiquid FMV</th>
                      <th className="p-3 font-medium">Efficiency</th>
                      <th className="p-3 font-medium">Drag</th>
                      <th className="p-3 font-medium">Concentration</th>
                      <th className="p-3 font-medium">Dead $</th>
                      <th className="p-3 font-medium">Balance</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsPortfolioLiquidityList?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={12}>
                          No snapshots yet. Owners run `POST /portfolio-liquidity/generate` from the dashboard.
                        </td>
                      </tr>
                    ) : (
                      opsPortfolioLiquidityList!.items.slice(0, 30).map((row) => (
                        <tr key={row.id}>
                          <td className="whitespace-nowrap p-3 font-mono text-[11px]">{row.id}</td>
                          <td className="p-3">{row.owner_user_id}</td>
                          <td className="max-w-[9rem] truncate p-3 font-mono text-[10px] text-slate-400">{row.generation_scope_key}</td>
                          <td className="whitespace-nowrap p-3 text-slate-400">{formatDate(row.snapshot_date)}</td>
                          <td className="whitespace-nowrap p-3">{formatCurrency(row.liquid_portfolio_value)}</td>
                          <td className="whitespace-nowrap p-3">{formatCurrency(row.illiquid_portfolio_value)}</td>
                          <td className="p-3">{row.liquidity_efficiency_score ?? "—"}</td>
                          <td className="p-3">{row.liquidity_drag_score ?? "—"}</td>
                          <td className="p-3">{row.concentration_risk_score ?? "—"}</td>
                          <td className="whitespace-nowrap p-3">{formatCurrency(row.dead_capital_estimate)}</td>
                          <td className="whitespace-nowrap p-3 text-teal-100">{row.liquidity_balance_status}</td>
                          <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45 xl:col-span-2">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Bucket distribution (latest row in scoped list snapshot #{opsPortfolioLiquidityDetail?.snapshot.id ?? "—"})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Bucket</th>
                      <th className="p-3 font-medium">Items</th>
                      <th className="p-3 font-medium">FMV</th>
                      <th className="p-3 font-medium">Weighted LQ</th>
                      <th className="p-3 font-medium">% portfolio</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {!opsPortfolioLiquidityDetail?.buckets?.length ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={5}>
                          Hydrated from the newest snapshot matching the scoped list (needs at least one snapshot).
                        </td>
                      </tr>
                    ) : (
                      [...opsPortfolioLiquidityDetail.buckets]
                        .sort((a, b) => a.liquidity_bucket.localeCompare(b.liquidity_bucket))
                        .map((b) => (
                          <tr key={b.id}>
                            <td className="p-3 font-semibold text-teal-100">{b.liquidity_bucket}</td>
                            <td className="p-3">{b.item_count}</td>
                            <td className="whitespace-nowrap p-3">{formatCurrency(b.total_fmv)}</td>
                            <td className="whitespace-nowrap p-3">{formatCurrency(b.weighted_liquidity_value)}</td>
                            <td className="p-3">{b.percentage_of_portfolio ?? "—"}</td>
                          </tr>
                        ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45 xl:col-span-2">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Evidence spine ({opsPortfolioLiquidityEvidence?.total ?? 0})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Recorded</th>
                      <th className="p-3 font-medium">Snapshot</th>
                      <th className="p-3 font-medium">Type</th>
                      <th className="p-3 font-medium">Payload</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsPortfolioLiquidityEvidence?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={4}>
                          Rows attach when liquidity snapshots regenerate (first scoped snapshot preview).
                        </td>
                      </tr>
                    ) : (
                      opsPortfolioLiquidityEvidence!.items.slice(0, 30).map((ev) => (
                        <tr key={ev.id}>
                          <td className="whitespace-nowrap p-3 text-slate-500">{formatDateTime(ev.created_at)}</td>
                          <td className="p-3 font-mono text-[11px]">{ev.portfolio_liquidity_snapshot_id}</td>
                          <td className="p-3">{ev.evidence_type}</td>
                          <td className="p-3 text-[10px] text-slate-400">
                            {JSON.stringify(ev.evidence_value_json).slice(0, 200)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45 xl:col-span-2">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Append-only history ({opsPortfolioLiquidityHistory?.total ?? 0})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Date</th>
                      <th className="p-3 font-medium">Owner</th>
                      <th className="p-3 font-medium">Scope</th>
                      <th className="p-3 font-medium">Efficiency</th>
                      <th className="p-3 font-medium">Drag</th>
                      <th className="p-3 font-medium">Concentration</th>
                      <th className="p-3 font-medium">Dead $</th>
                      <th className="p-3 font-medium">Balance</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsPortfolioLiquidityHistory?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={9}>
                          History rows append once per new checksum for a generation tuple.
                        </td>
                      </tr>
                    ) : (
                      opsPortfolioLiquidityHistory!.items.slice(0, 35).map((h) => (
                        <tr key={h.id}>
                          <td className="whitespace-nowrap p-3 text-slate-400">{formatDate(h.snapshot_date)}</td>
                          <td className="p-3">{h.owner_user_id}</td>
                          <td className="max-w-[8rem] truncate p-3 font-mono text-[10px] text-slate-500">{h.generation_scope_key}</td>
                          <td className="p-3">{h.liquidity_efficiency_score ?? "—"}</td>
                          <td className="p-3">{h.liquidity_drag_score ?? "—"}</td>
                          <td className="p-3">{h.concentration_risk_score ?? "—"}</td>
                          <td className="whitespace-nowrap p-3">{formatCurrency(h.dead_capital_estimate)}</td>
                          <td className="p-3 text-teal-100">{h.liquidity_balance_status}</td>
                          <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(h.checksum)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </details>

      <details
        id="portfolio-strategy-dashboard-ops"
        open
        className="mt-6 rounded-3xl border border-emerald-400/35 bg-emerald-950/15 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Portfolio strategy dashboard operations</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Read-only `/ops/portfolio-strategy-dashboard*` mirrors. Strategic KPIs, metrics, alerts, and feed events
                built from the latest portfolio, duplicate, liquidity, recommendation, concentration, and acquisition layers.
              </p>
            </div>
            <span className="rounded-full border border-emerald-300/40 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-100/95">
              Ops / strategy
            </span>
          </div>
        </summary>
        <div className="mt-5 space-y-4 border-t border-emerald-200/15 pt-4">
          {opsStrategyDashLoading ? (
            <p className="text-sm text-slate-400">Loading portfolio strategy dashboard…</p>
          ) : (
            <>
              {opsStrategyDashError ? <StatusBanner tone={opsStrategyDash?.snapshot ? "warning" : "error"}>{opsStrategyDashError}</StatusBanner> : null}
              {!opsStrategyDash?.snapshot ? (
                <p className="mt-3 text-sm text-slate-500">No strategy snapshots materialized for this scope.</p>
              ) : null}
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <StatCard label="Portfolios" value={String(opsStrategyDash?.snapshot?.portfolio_count ?? 0)} />
                <StatCard label="Total value" value={formatCurrency(opsStrategyDash?.snapshot?.total_portfolio_value ?? null)} />
                <StatCard label="Cost basis" value={formatCurrency(opsStrategyDash?.snapshot?.total_cost_basis ?? null)} />
                <StatCard label="Dead capital" value={formatCurrency(opsStrategyDash?.snapshot?.dead_capital_estimate ?? null)} />
                <StatCard label="Diversification" value={opsStrategyDash?.snapshot?.diversification_score ?? "—"} />
              </div>

              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Strategy metrics ({opsStrategyMetrics.length})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Metric</th>
                      <th className="p-3 font-medium">Value</th>
                      <th className="p-3 font-medium">Text</th>
                      <th className="p-3 font-medium">Metadata</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsStrategyMetrics.length === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={4}>
                          No strategy metrics captured for this owner scope yet.
                        </td>
                      </tr>
                    ) : (
                      opsStrategyMetrics.map((row) => (
                        <tr key={row.id}>
                          <td className="p-3 text-slate-300">{row.metric_key}</td>
                          <td className="p-3 text-slate-300">{row.metric_value_decimal ?? "—"}</td>
                          <td className="p-3 text-slate-300">{row.metric_value_text ?? "—"}</td>
                          <td className="p-3 text-[10px] text-slate-400">
                            {row.metric_metadata_json ? JSON.stringify(row.metric_metadata_json).slice(0, 220) : "—"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                  <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                    Strategic alerts ({opsStrategyAlerts.length})
                  </p>
                  <table className="mt-3 w-full border-collapse text-left text-xs">
                    <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                      <tr>
                        <th className="p-3 font-medium">Severity</th>
                        <th className="p-3 font-medium">Type</th>
                        <th className="p-3 font-medium">Owner</th>
                        <th className="p-3 font-medium">Source</th>
                        <th className="p-3 font-medium">Message</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10 text-slate-200">
                      {opsStrategyAlerts.length === 0 ? (
                        <tr>
                          <td className="p-4 text-slate-500" colSpan={5}>
                            No strategy alerts recorded for this scope.
                          </td>
                        </tr>
                      ) : (
                        opsStrategyAlerts.map((row) => (
                          <tr key={row.alert_replay_key}>
                            <td className="p-3">{row.severity}</td>
                            <td className="p-3">{row.alert_type}</td>
                            <td className="p-3 font-mono text-[11px]">@{row.owner_user_id}</td>
                            <td className="p-3 text-[10px] text-slate-500">
                              portfolio {row.source_portfolio_id ?? "—"} · inv {row.source_inventory_item_id ?? "—"} · snap{" "}
                              {row.source_snapshot_id ?? "—"}
                            </td>
                            <td className="p-3 text-slate-300">{row.message}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                  <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                    Strategic feed ({opsStrategyFeed.length})
                  </p>
                  <table className="mt-3 w-full border-collapse text-left text-xs">
                    <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                      <tr>
                        <th className="p-3 font-medium">Created</th>
                        <th className="p-3 font-medium">Event</th>
                        <th className="p-3 font-medium">Owner</th>
                        <th className="p-3 font-medium">Summary</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10 text-slate-200">
                      {opsStrategyFeed.length === 0 ? (
                        <tr>
                          <td className="p-4 text-slate-500" colSpan={4}>
                            No strategic feed events recorded for this scope.
                          </td>
                        </tr>
                      ) : (
                        opsStrategyFeed.map((row) => (
                          <tr key={row.deterministic_key}>
                            <td className="whitespace-nowrap p-3 text-slate-400">{formatDateTime(row.created_at)}</td>
                            <td className="p-3">{row.event_type}</td>
                            <td className="p-3 font-mono text-[11px]">@{row.owner_user_id}</td>
                            <td className="p-3 text-slate-300">{row.summary}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </details>

      <details
        id="acquisition-priority-ops"
        open
        className="mt-6 rounded-3xl border border-sky-400/35 bg-sky-950/15 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Acquisition intelligence operations</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Read-only `/ops/acquisition-priorities*` mirrors. Deterministic acquisition rows showing category, priority,
                diversification gain, liquidity gain, confidence, risk, and replay-safe checksums.
              </p>
            </div>
            <span className="rounded-full border border-sky-300/40 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-sky-100/95">
              Ops / acquisition
            </span>
          </div>
        </summary>
        <div className="mt-5 space-y-4 border-t border-sky-200/15 pt-4">
          {opsAcquisitionPriorityLoading ? (
            <p className="text-sm text-slate-400">Loading acquisition priorities…</p>
          ) : opsAcquisitionPriorityError ? (
            <StatusBanner tone="error">{opsAcquisitionPriorityError}</StatusBanner>
          ) : (
            <>
              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Acquisition table ({opsAcquisitionPriorityList?.total ?? 0})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Category</th>
                      <th className="p-3 font-medium">Priority</th>
                      <th className="p-3 font-medium">Owner</th>
                      <th className="p-3 font-medium">Issue</th>
                      <th className="p-3 font-medium">Diversification</th>
                      <th className="p-3 font-medium">Liquidity</th>
                      <th className="p-3 font-medium">Confidence</th>
                      <th className="p-3 font-medium">Risk</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsAcquisitionPriorityList?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={9}>
                          No acquisition-priority rows for this scope yet.
                        </td>
                      </tr>
                    ) : (
                      opsAcquisitionPriorityList!.items.slice(0, 30).map((row) => (
                        <tr key={row.id}>
                          <td className="p-3 text-slate-300">{row.acquisition_category}</td>
                          <td className="p-3">
                            <div className="font-semibold text-white">{row.acquisition_priority}</div>
                            <div className="text-[10px] text-slate-500">{row.recommendation_strength}</div>
                          </td>
                          <td className="p-3 font-mono text-[11px] text-slate-300">@{row.owner_user_id}</td>
                          <td className="p-3 text-slate-300">issue {row.canonical_comic_issue_id ?? "—"}</td>
                          <td className="p-3 text-slate-300">{row.diversification_impact ?? "—"}</td>
                          <td className="p-3 text-slate-300">{row.liquidity_impact ?? "—"}</td>
                          <td className="p-3 text-slate-300">{row.confidence_level}</td>
                          <td className="p-3 text-slate-300">{row.risk_level}</td>
                          <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {opsAcquisitionPriorityDetail ? (
                <div className="grid gap-4 xl:grid-cols-3">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4 xl:col-span-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Selected acquisition row</p>
                    <p className="mt-2 text-sm text-slate-100">
                      {opsAcquisitionPriorityDetail.snapshot.acquisition_category} ·{" "}
                      {opsAcquisitionPriorityDetail.snapshot.acquisition_priority} · confidence{" "}
                      {opsAcquisitionPriorityDetail.snapshot.confidence_level} · risk{" "}
                      {opsAcquisitionPriorityDetail.snapshot.risk_level}
                    </p>
                    <p className="mt-1 text-[11px] text-slate-300">
                      {opsAcquisitionPriorityDetail.snapshot.rationale_summary}
                    </p>
                  </div>
                  <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45 xl:col-span-2">
                    <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                      Evidence list ({opsAcquisitionPriorityEvidence?.total ?? 0})
                    </p>
                    <table className="mt-3 w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Type</th>
                          <th className="p-3 font-medium">Source</th>
                          <th className="p-3 font-medium">Payload</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10 text-slate-200">
                        {(opsAcquisitionPriorityEvidence?.items.length ?? 0) === 0 ? (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={3}>
                              Evidence rows attach to each acquisition snapshot.
                            </td>
                          </tr>
                        ) : (
                          opsAcquisitionPriorityEvidence!.items.slice(0, 20).map((row) => (
                            <tr key={row.id}>
                              <td className="p-3">{row.evidence_type}</td>
                              <td className="p-3 font-mono text-[10px] text-slate-400">
                                {row.source_table ?? "—"} #{row.source_id ?? "—"}
                              </td>
                              <td className="p-3 text-[10px] text-slate-400">{JSON.stringify(row.evidence_value_json).slice(0, 200)}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                  <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                    <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                      Scenarios / history
                    </p>
                    <div className="mt-3 space-y-4">
                      <table className="w-full border-collapse text-left text-xs">
                        <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                          <tr>
                            <th className="p-3 font-medium">Scenario</th>
                            <th className="p-3 font-medium">Liquidity</th>
                            <th className="p-3 font-medium">Diversification</th>
                            <th className="p-3 font-medium">Efficiency</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/10 text-slate-200">
                          {opsAcquisitionPriorityDetail.scenarios.map((scenario) => (
                            <tr key={scenario.id}>
                              <td className="p-3">{scenario.scenario_name}</td>
                              <td className="p-3">{scenario.projected_liquidity_impact ?? "—"}</td>
                              <td className="p-3">{scenario.projected_diversification_impact ?? "—"}</td>
                              <td className="p-3">{scenario.projected_portfolio_efficiency ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <table className="w-full border-collapse text-left text-xs">
                        <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                          <tr>
                            <th className="p-3 font-medium">Date</th>
                            <th className="p-3 font-medium">Category</th>
                            <th className="p-3 font-medium">Priority</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/10 text-slate-200">
                          {opsAcquisitionPriorityHistory?.items.slice(0, 15).length ? (
                            opsAcquisitionPriorityHistory!.items.slice(0, 15).map((row) => (
                              <tr key={row.id}>
                                <td className="p-3 text-slate-400">{formatDate(row.snapshot_date)}</td>
                                <td className="p-3">{row.acquisition_category}</td>
                                <td className="p-3">{row.acquisition_priority}</td>
                              </tr>
                            ))
                          ) : (
                            <tr>
                              <td className="p-4 text-slate-500" colSpan={3}>
                                History appends only when a new checksum appears for the same issue/category tuple.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </details>

      <details
        id="concentration-risk-ops"
        open
        className="mt-6 rounded-3xl border border-fuchsia-400/35 bg-fuchsia-950/15 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Concentration risk operations</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Read-only `/ops/concentration-risk*` mirrors. Deterministic concentration snapshots with explicit scores,
                evidence, factor weights, and append-safe history.
              </p>
            </div>
            <span className="rounded-full border border-fuchsia-300/40 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-fuchsia-100/95">
              Ops / concentration
            </span>
          </div>
        </summary>
        <div className="mt-5 space-y-4 border-t border-fuchsia-200/15 pt-4">
          {opsConcentrationRiskLoading ? (
            <p className="text-sm text-slate-400">Loading concentration risk…</p>
          ) : opsConcentrationRiskError ? (
            <StatusBanner tone="error">{opsConcentrationRiskError}</StatusBanner>
          ) : (
            <>
              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Concentration table ({opsConcentrationRiskList?.total ?? 0})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Type</th>
                      <th className="p-3 font-medium">Key</th>
                      <th className="p-3 font-medium">Owner</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">Score</th>
                      <th className="p-3 font-medium">Diversification</th>
                      <th className="p-3 font-medium">Liquidity weighted</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsConcentrationRiskList?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={8}>
                          No concentration-risk rows for this scope yet.
                        </td>
                      </tr>
                    ) : (
                      opsConcentrationRiskList!.items.slice(0, 30).map((row) => (
                        <tr key={row.id}>
                          <td className="p-3 text-slate-300">{row.concentration_type}</td>
                          <td className="p-3 text-slate-300">{row.concentration_key}</td>
                          <td className="p-3 font-mono text-[11px] text-slate-300">@{row.owner_user_id}</td>
                          <td className="p-3">{row.exposure_status}</td>
                          <td className="p-3 text-slate-300">{row.concentration_score ?? "—"}</td>
                          <td className="p-3 text-slate-300">{row.diversification_score ?? "—"}</td>
                          <td className="p-3 text-slate-300">{row.liquidity_weighted_concentration ?? "—"}</td>
                          <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {opsConcentrationRiskDetail ? (
                <div className="grid gap-4 xl:grid-cols-3">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4 xl:col-span-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Selected concentration snapshot</p>
                    <p className="mt-2 text-sm text-slate-100">
                      {opsConcentrationRiskDetail.snapshot.concentration_type} · {opsConcentrationRiskDetail.snapshot.concentration_key}
                      {" · "}{opsConcentrationRiskDetail.snapshot.exposure_status}
                    </p>
                    <p className="mt-1 text-[11px] text-slate-300">
                      Score {opsConcentrationRiskDetail.snapshot.concentration_score ?? "—"} · diversification{" "}
                      {opsConcentrationRiskDetail.snapshot.diversification_score ?? "—"} · liquidity weighted{" "}
                      {opsConcentrationRiskDetail.snapshot.liquidity_weighted_concentration ?? "—"}
                    </p>
                  </div>
                  <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45 xl:col-span-2">
                    <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                      Evidence list ({opsConcentrationRiskEvidence?.total ?? 0})
                    </p>
                    <table className="mt-3 w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Type</th>
                          <th className="p-3 font-medium">Source</th>
                          <th className="p-3 font-medium">Payload</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10 text-slate-200">
                        {(opsConcentrationRiskEvidence?.items.length ?? 0) === 0 ? (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={3}>
                              Evidence rows attach to each concentration snapshot.
                            </td>
                          </tr>
                        ) : (
                          opsConcentrationRiskEvidence!.items.slice(0, 20).map((row) => (
                            <tr key={row.id}>
                              <td className="p-3">{row.evidence_type}</td>
                              <td className="p-3 font-mono text-[10px] text-slate-400">
                                {row.source_table ?? "—"} #{row.source_id ?? "—"}
                              </td>
                              <td className="p-3 text-[10px] text-slate-400">{JSON.stringify(row.evidence_value_json).slice(0, 200)}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                  <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                    <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                      Factors / history
                    </p>
                    <div className="mt-3 space-y-4">
                      <table className="w-full border-collapse text-left text-xs">
                        <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                          <tr>
                            <th className="p-3 font-medium">Factor</th>
                            <th className="p-3 font-medium">Score</th>
                            <th className="p-3 font-medium">Weight</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/10 text-slate-200">
                          {opsConcentrationRiskFactors?.items.slice(0, 10).length ? (
                            opsConcentrationRiskFactors!.items.slice(0, 10).map((row) => (
                              <tr key={row.id}>
                                <td className="p-3">{row.factor_key}</td>
                                <td className="p-3">{row.factor_score ?? "—"}</td>
                                <td className="p-3">{row.weighting ?? "—"}</td>
                              </tr>
                            ))
                          ) : (
                            <tr>
                              <td className="p-4 text-slate-500" colSpan={3}>
                                Factor rows are persisted with explicit weights.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                      <table className="w-full border-collapse text-left text-xs">
                        <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                          <tr>
                            <th className="p-3 font-medium">Date</th>
                            <th className="p-3 font-medium">Status</th>
                            <th className="p-3 font-medium">Score</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/10 text-slate-200">
                          {opsConcentrationRiskHistory?.items.slice(0, 15).length ? (
                            opsConcentrationRiskHistory!.items.slice(0, 15).map((row) => (
                              <tr key={row.id}>
                                <td className="p-3 text-slate-400">{formatDate(row.snapshot_date)}</td>
                                <td className="p-3">{row.exposure_status}</td>
                                <td className="p-3">{row.concentration_score ?? "—"}</td>
                              </tr>
                            ))
                          ) : (
                            <tr>
                              <td className="p-4 text-slate-500" colSpan={3}>
                                History appends only when a new checksum appears for the same concentration key.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </details>

      <details
        id="portfolio-recommendation-ops"
        open
        className="mt-6 rounded-3xl border border-amber-400/35 bg-amber-950/15 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Portfolio recommendation operations</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Read-only `/ops/portfolio-recommendations*` mirrors. Deterministic hold/sell intelligence rows with action,
                strength, confidence, risk, capital-release estimates, and replay-safe checksums.
              </p>
            </div>
            <span className="rounded-full border border-amber-300/40 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-100/95">
              Ops / recommendations
            </span>
          </div>
        </summary>
        <div className="mt-5 space-y-4 border-t border-amber-200/15 pt-4">
          {opsPortfolioRecommendationLoading ? (
            <p className="text-sm text-slate-400">Loading portfolio recommendations…</p>
          ) : opsPortfolioRecommendationError ? (
            <StatusBanner tone="error">{opsPortfolioRecommendationError}</StatusBanner>
          ) : (
            <>
              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Recommendation table ({opsPortfolioRecommendationList?.total ?? 0})
                </p>
                <table className="mt-3 w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Action</th>
                      <th className="p-3 font-medium">Owner</th>
                      <th className="p-3 font-medium">Inventory</th>
                      <th className="p-3 font-medium">Strength</th>
                      <th className="p-3 font-medium">Confidence</th>
                      <th className="p-3 font-medium">Risk</th>
                      <th className="p-3 font-medium">Capital release</th>
                      <th className="p-3 font-medium">Liquidity impact</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {(opsPortfolioRecommendationList?.items.length ?? 0) === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={9}>
                          No portfolio recommendation rows for this scope yet.
                        </td>
                      </tr>
                    ) : (
                      opsPortfolioRecommendationList!.items.slice(0, 30).map((row) => (
                        <tr key={row.id}>
                          <td className="p-3">
                            <div className="font-semibold text-white">{row.recommendation_action}</div>
                            <div className="text-[10px] text-slate-500">{row.recommendation_status}</div>
                          </td>
                          <td className="p-3 font-mono text-[11px] text-slate-300">@{row.owner_user_id}</td>
                          <td className="p-3 text-slate-300">
                            inv {row.inventory_item_id ?? "—"}
                            <span className="block text-[10px] text-slate-500">portfolio {row.portfolio_id ?? "—"}</span>
                          </td>
                          <td className="p-3 text-slate-300">{row.recommendation_strength}</td>
                          <td className="p-3 text-slate-300">{row.confidence_level}</td>
                          <td className="p-3 text-slate-300">{row.risk_level}</td>
                          <td className="p-3 text-slate-300">{row.estimated_capital_release ?? "—"}</td>
                          <td className="p-3 text-slate-300">{row.estimated_liquidity_impact ?? "—"}</td>
                          <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {opsPortfolioRecommendationDetail ? (
                <div className="grid gap-4 xl:grid-cols-3">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4 xl:col-span-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Selected recommendation</p>
                    <p className="mt-2 text-sm text-slate-100">
                      {opsPortfolioRecommendationDetail.recommendation.recommendation_action} ·{" "}
                      {opsPortfolioRecommendationDetail.recommendation.recommendation_strength} · confidence{" "}
                      {opsPortfolioRecommendationDetail.recommendation.confidence_level} · risk{" "}
                      {opsPortfolioRecommendationDetail.recommendation.risk_level}
                    </p>
                    <p className="mt-1 text-[11px] text-slate-300">
                      {opsPortfolioRecommendationDetail.recommendation.rationale_summary}
                    </p>
                  </div>
                  <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45 xl:col-span-2">
                    <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                      Evidence spine ({opsPortfolioRecommendationEvidence?.total ?? 0})
                    </p>
                    <table className="mt-3 w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Type</th>
                          <th className="p-3 font-medium">Source</th>
                          <th className="p-3 font-medium">Payload</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10 text-slate-200">
                        {(opsPortfolioRecommendationEvidence?.items.length ?? 0) === 0 ? (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={3}>
                              Evidence rows attach to each recommendation snapshot.
                            </td>
                          </tr>
                        ) : (
                          opsPortfolioRecommendationEvidence!.items.slice(0, 20).map((ev) => (
                            <tr key={ev.id}>
                              <td className="p-3">{ev.evidence_type}</td>
                              <td className="p-3 font-mono text-[10px] text-slate-400">
                                {ev.source_table ?? "—"} #{ev.source_id ?? "—"}
                              </td>
                              <td className="p-3 text-[10px] text-slate-400">
                                {JSON.stringify(ev.evidence_value_json).slice(0, 200)}
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                  <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                    <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                      Scenarios / history
                    </p>
                    <div className="mt-3 space-y-4">
                      <table className="w-full border-collapse text-left text-xs">
                        <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                          <tr>
                            <th className="p-3 font-medium">Scenario</th>
                            <th className="p-3 font-medium">Capital release</th>
                            <th className="p-3 font-medium">Liquidity gain</th>
                            <th className="p-3 font-medium">Impact</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/10 text-slate-200">
                          {opsPortfolioRecommendationDetail.scenarios.map((scenario) => (
                            <tr key={scenario.id}>
                              <td className="p-3">{scenario.scenario_name}</td>
                              <td className="p-3">{scenario.projected_capital_release ?? "—"}</td>
                              <td className="p-3">{scenario.projected_liquidity_gain ?? "—"}</td>
                              <td className="p-3">{scenario.projected_portfolio_impact ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <table className="w-full border-collapse text-left text-xs">
                        <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                          <tr>
                            <th className="p-3 font-medium">Date</th>
                            <th className="p-3 font-medium">Action</th>
                            <th className="p-3 font-medium">Strength</th>
                            <th className="p-3 font-medium">Risk</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/10 text-slate-200">
                          {opsPortfolioRecommendationHistory?.items.slice(0, 15).length ? (
                            opsPortfolioRecommendationHistory!.items.slice(0, 15).map((row) => (
                              <tr key={row.id}>
                                <td className="p-3 text-slate-400">{formatDate(row.snapshot_date)}</td>
                                <td className="p-3">{row.recommendation_action}</td>
                                <td className="p-3">{row.recommendation_strength}</td>
                                <td className="p-3">{row.risk_level}</td>
                              </tr>
                            ))
                          ) : (
                            <tr>
                              <td className="p-4 text-slate-500" colSpan={4}>
                                History appends only when a new checksum appears for the same generation tuple.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </details>

      <details
        id="grading-reporting-ops"
        className="mt-6 rounded-3xl border border-indigo-400/35 bg-indigo-950/15 p-5 shadow-xl shadow-black/15 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Grading reporting</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Append-safe P37 closeout CSV registry for grading candidates, economics, submissions, reconciliation,
                recommendations, risk, dashboard summaries, and grader performance. Downloads stay read-only and scoped.
              </p>
            </div>
            <span className="rounded-full border border-indigo-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-indigo-100/90">
              Ops / grading reports
            </span>
          </div>
        </summary>
        <div className="mt-4">
          <div className="mb-4 flex flex-wrap items-end gap-2">
            <label className="flex flex-col text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
              Owner user id
              <input
                value={opsGradingReportsOwnerDraft}
                onChange={(e) => setOpsGradingReportsOwnerDraft(e.target.value)}
                className="mt-2 w-52 rounded-xl border border-white/15 bg-slate-950/70 px-3 py-2 text-sm text-white"
                placeholder="Blank = all owners"
              />
            </label>
            <button
              type="button"
              className="rounded-xl border border-indigo-400/45 px-3 py-2 text-xs font-semibold text-indigo-100"
              onClick={() => {
                const trimmed = opsGradingReportsOwnerDraft.trim();
                if (!trimmed) {
                  setOpsGradingReportsOwnerFilter(undefined);
                  return;
                }
                const n = Number(trimmed);
                setOpsGradingReportsOwnerFilter(Number.isFinite(n) && n > 0 ? Math.floor(n) : undefined);
              }}
            >
              Apply scope
            </button>
          </div>
          {opsGradingReportsDownloadError ? (
            <div className="mb-3">
              <StatusBanner tone="error">{opsGradingReportsDownloadError}</StatusBanner>
            </div>
          ) : null}
          {opsGradingReportsLoading ? (
            <p className="text-sm text-slate-400">Loading grading report runs…</p>
          ) : opsGradingReportsError ? (
            <StatusBanner tone="error">{opsGradingReportsError}</StatusBanner>
          ) : opsGradingReports ? (
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Run</th>
                    <th className="p-3 font-medium">Owner</th>
                    <th className="p-3 font-medium">Report type</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">CSV rows</th>
                    <th className="p-3 font-medium">Checksum</th>
                    <th className="p-3 font-medium">Replay</th>
                    <th className="p-3 font-medium">Created</th>
                    <th className="p-3 font-medium">Download</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsGradingReports.items.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={9}>
                        No grading report runs recorded for this scope.
                      </td>
                    </tr>
                  ) : (
                    opsGradingReports.items.map((run) => (
                      <tr key={run.id}>
                        <td className="p-3 font-mono text-[11px] text-slate-300">#{run.id}</td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">@{run.owner_user_id}</td>
                        <td className="p-3 text-slate-300">{run.report_type.replace(/_/g, " ")}</td>
                        <td className="p-3">
                          <div>{run.status}</div>
                          {run.failure_reason ? (
                            <div className="mt-1 max-w-[14rem] truncate text-[10px] text-rose-300" title={run.failure_reason}>
                              {run.failure_reason}
                            </div>
                          ) : null}
                        </td>
                        <td className="p-3 text-slate-400">{run.csv_row_count}</td>
                        <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(run.checksum)}</td>
                        <td className="p-3 font-mono text-[10px] text-slate-500">{run.replay_key ?? "—"}</td>
                        <td className="p-3 text-slate-400">{formatDateTime(run.created_at)}</td>
                        <td className="p-3">
                          <button
                            type="button"
                            disabled={run.status !== "COMPLETED"}
                            className="rounded-full border border-indigo-300/45 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-100 disabled:cursor-not-allowed disabled:opacity-40"
                            onClick={() => {
                              void (async () => {
                                setOpsGradingReportsDownloadError(null);
                                try {
                                  await apiClient.downloadOpsGradingReportCsv(run.id);
                                } catch (err) {
                                  setOpsGradingReportsDownloadError(
                                    err instanceof ApiError ? err.message : "Unable to download grading report CSV.",
                                  );
                                }
                              })();
                            }}
                          >
                            CSV
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Grading reporting registry unavailable.</p>
          )}
        </div>
      </details>

      <details
        id="operational-reporting-ops"
        className="mt-6 rounded-3xl border border-violet-400/35 bg-violet-950/15 p-5 shadow-xl shadow-black/15 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Operational reporting</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Append-only CSV run history with deterministic checksums and replay keys. Downloads are read-only; no
                source-table mutation. Optional owner scope limits the run list.
              </p>
            </div>
            <span className="rounded-full border border-violet-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-100/90">
              Ops / reports
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-violet-200/15 pt-4">
          <div className="mb-4 flex flex-wrap items-end gap-2">
            <label className="flex flex-col text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
              Owner user id
              <input
                value={opsOperationalOwnerDraft}
                onChange={(e) => setOpsOperationalOwnerDraft(e.target.value)}
                className="mt-2 w-52 rounded-xl border border-white/15 bg-slate-950/70 px-3 py-2 text-sm text-white"
                placeholder="Blank = all owners"
              />
            </label>
            <button
              type="button"
              className="rounded-xl border border-violet-400/45 px-3 py-2 text-xs font-semibold text-violet-100"
              onClick={() => {
                const trimmed = opsOperationalOwnerDraft.trim();
                if (!trimmed) {
                  setOpsOperationalOwnerFilter(undefined);
                  return;
                }
                const n = Number(trimmed);
                setOpsOperationalOwnerFilter(Number.isFinite(n) && n > 0 ? Math.floor(n) : undefined);
              }}
            >
              Apply scope
            </button>
          </div>
          {opsOperationalDownloadError ? (
            <div className="mb-3">
              <StatusBanner tone="error">{opsOperationalDownloadError}</StatusBanner>
            </div>
          ) : null}
          {opsOperationalReportsLoading ? (
            <p className="text-sm text-slate-400">Loading operational report runs…</p>
          ) : opsOperationalReportsError ? (
            <StatusBanner tone="error">{opsOperationalReportsError}</StatusBanner>
          ) : opsOperationalReports ? (
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Run</th>
                    <th className="p-3 font-medium">Owner</th>
                    <th className="p-3 font-medium">Report type</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">CSV rows</th>
                    <th className="p-3 font-medium">Checksum</th>
                    <th className="p-3 font-medium">Replay</th>
                    <th className="p-3 font-medium">Created</th>
                    <th className="p-3 font-medium">Download</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsOperationalReports.items.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={9}>
                        No report runs recorded for this scope.
                      </td>
                    </tr>
                  ) : (
                    opsOperationalReports.items.map((run) => (
                      <tr key={run.id}>
                        <td className="p-3 font-mono text-[11px] text-slate-300">#{run.id}</td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">@{run.owner_user_id}</td>
                        <td className="p-3 text-slate-300">{run.report_type.replace(/_/g, " ")}</td>
                        <td className="p-3">
                          <div>{run.status}</div>
                          {run.failure_reason ? (
                            <div
                              className="mt-1 max-w-[14rem] truncate text-[10px] text-rose-300"
                              title={run.failure_reason}
                            >
                              {run.failure_reason}
                            </div>
                          ) : null}
                        </td>
                        <td className="p-3">{run.csv_row_count}</td>
                        <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(run.checksum)}</td>
                        <td className="max-w-[10rem] truncate p-3 font-mono text-[10px] text-slate-400" title={run.replay_key ?? undefined}>
                          {run.replay_key ?? "—"}
                        </td>
                        <td className="p-3 text-slate-400">{formatDateTime(run.created_at)}</td>
                        <td className="p-3">
                          <button
                            type="button"
                            className="rounded-full border border-violet-400/35 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-violet-100 transition hover:border-violet-300/60 hover:bg-violet-500/10 disabled:opacity-40"
                            disabled={run.status !== "COMPLETED"}
                            onClick={() => {
                              void (async () => {
                                setOpsOperationalDownloadError(null);
                                try {
                                  await apiClient.downloadOpsOperationalReportCsv(run.id);
                                } catch (err) {
                                  setOpsOperationalDownloadError(
                                    err instanceof ApiError ? err.message : "Unable to download report CSV.",
                                  );
                                }
                              })();
                            }}
                          >
                            CSV
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </details>

      <details
        id="grading-candidate-ops"
        className="mt-6 rounded-3xl border border-amber-400/35 bg-amber-950/15 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Grading candidate registry</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Read-only cross-owner view into grading intentions, deterministic economics placeholders, ROI fields
                captured by owners, replay keys, lineage evidence, lifecycle events, and snapshot checksums. No inventory
                mutation from this telescope.
              </p>
            </div>
            <span className="rounded-full border border-amber-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-100/90">
              Ops / grading
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-amber-200/15 pt-4">
          <div className="mb-4 flex flex-wrap items-end gap-2">
            <label className="flex flex-col text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
              Owner user id
              <input
                value={opsGradingOwnerDraft}
                onChange={(e) => setOpsGradingOwnerDraft(e.target.value)}
                className="mt-2 w-52 rounded-xl border border-white/15 bg-slate-950/70 px-3 py-2 text-sm text-white"
                placeholder="Blank = all owners"
              />
            </label>
            <button
              type="button"
              className="rounded-xl border border-amber-400/45 px-3 py-2 text-xs font-semibold text-amber-100"
              onClick={() => {
                const trimmed = opsGradingOwnerDraft.trim();
                if (!trimmed) {
                  setOpsGradingOwnerFilter(undefined);
                  return;
                }
                const n = Number(trimmed);
                setOpsGradingOwnerFilter(Number.isFinite(n) && n > 0 ? Math.floor(n) : undefined);
              }}
            >
              Apply scope
            </button>
          </div>
          {opsGradingCandidatesLoading ? (
            <p className="text-sm text-slate-400">Loading grading candidates…</p>
          ) : opsGradingCandidatesError ? (
            <StatusBanner tone="error">{opsGradingCandidatesError}</StatusBanner>
          ) : opsGradingCandidates ? (
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Run</th>
                    <th className="p-3 font-medium">Owner</th>
                    <th className="p-3 font-medium">Inventory</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">Target</th>
                    <th className="p-3 font-medium">Priority</th>
                    <th className="p-3 font-medium">ROI est.</th>
                    <th className="p-3 font-medium">Evidence</th>
                    <th className="p-3 font-medium">Checksum</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsGradingCandidates.items.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={9}>
                        No grading candidates for this scope.
                      </td>
                    </tr>
                  ) : (
                    opsGradingCandidates.items.map((row) => (
                      <tr key={row.id}>
                        <td className="p-3 font-mono text-[11px] text-slate-300">#{row.id}</td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">@{row.owner_user_id}</td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">inv {row.inventory_item_id}</td>
                        <td className="p-3">{row.status}</td>
                        <td className="p-3">
                          {row.target_grader}
                          {row.target_grade ? <span className="block text-[10px] text-slate-500">{row.target_grade}</span> : null}
                        </td>
                        <td className="p-3">{row.candidate_priority}</td>
                        <td className="p-3 text-slate-400">{row.estimated_roi ?? "—"}</td>
                        <td className="p-3">{row.evidence_count}</td>
                        <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.latest_snapshot_checksum)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </details>

      <details
        id="grading-spread-ops"
        className="mt-6 rounded-3xl border border-violet-400/35 bg-violet-950/15 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Grading spread engine</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Read-only spread economics for raw FMV, graded FMV, liquidity modifiers, and deterministic upside
                checks. This lane explains grading economics without prediction or recommendation logic.
              </p>
            </div>
            <span className="rounded-full border border-violet-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-100/90">
              Ops / spread
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-violet-200/15 pt-4">
          <div className="mb-4 flex flex-wrap items-end gap-2">
            <label className="flex flex-col text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
              Owner user id
              <input
                value={opsGradingOwnerDraft}
                onChange={(e) => setOpsGradingOwnerDraft(e.target.value)}
                className="mt-2 w-52 rounded-xl border border-white/15 bg-slate-950/70 px-3 py-2 text-sm text-white"
                placeholder="Blank = all owners"
              />
            </label>
            <button
              type="button"
              className="rounded-xl border border-violet-400/45 px-3 py-2 text-xs font-semibold text-violet-100"
              onClick={() => {
                const trimmed = opsGradingOwnerDraft.trim();
                if (!trimmed) {
                  setOpsGradingOwnerFilter(undefined);
                  return;
                }
                const n = Number(trimmed);
                setOpsGradingOwnerFilter(Number.isFinite(n) && n > 0 ? Math.floor(n) : undefined);
              }}
            >
              Apply scope
            </button>
          </div>
          {opsGradingSpreadsLoading ? (
            <p className="text-sm text-slate-400">Loading grading spreads…</p>
          ) : opsGradingSpreadsError ? (
            <StatusBanner tone="error">{opsGradingSpreadsError}</StatusBanner>
          ) : opsGradingSpreads ? (
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Spread</th>
                    <th className="p-3 font-medium">Owner</th>
                    <th className="p-3 font-medium">Inventory</th>
                    <th className="p-3 font-medium">Target</th>
                    <th className="p-3 font-medium">Raw / Graded</th>
                    <th className="p-3 font-medium">Spread %</th>
                    <th className="p-3 font-medium">Liquidity</th>
                    <th className="p-3 font-medium">Confidence</th>
                    <th className="p-3 font-medium">Checksum</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsGradingSpreads.items.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={9}>
                        No grading spreads for this scope.
                      </td>
                    </tr>
                  ) : (
                    opsGradingSpreads.items.map((row) => (
                      <tr key={row.id}>
                        <td className="p-3">
                          <div className="font-semibold text-white">{row.spread_status}</div>
                          <div className="text-[10px] text-slate-500">#{row.id}</div>
                        </td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">@{row.owner_user_id ?? "—"}</td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">inv {row.inventory_item_id ?? "—"}</td>
                        <td className="p-3">
                          {row.target_grader}
                          {row.target_grade ? <span className="block text-[10px] text-slate-500">{row.target_grade}</span> : null}
                        </td>
                        <td className="p-3 text-slate-400">
                          {row.raw_fmv_amount ?? "—"} / {row.graded_fmv_amount ?? "—"}
                          <span className="block text-[10px] text-slate-500">
                            {row.estimated_net_upside ?? "—"} net
                          </span>
                        </td>
                        <td className="p-3 text-slate-300">{row.estimated_spread_pct ?? "—"}</td>
                        <td className="p-3">
                          <div>{row.liquidity_modifier}</div>
                          <div className="text-[10px] text-slate-500">{row.liquidity_adjusted_upside ?? "—"}</div>
                        </td>
                        <td className="p-3">{row.confidence_level}</td>
                        <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </details>

      <details
        id="grading-roi-ops"
        className="mt-6 rounded-3xl border border-emerald-400/35 bg-emerald-950/15 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Grading ROI engine</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Read-only ROI economics for grading fees, shipping, insurance, liquidity adjustment, and break-even
                checks. The same owner scope filter applies to this section.
              </p>
            </div>
            <span className="rounded-full border border-emerald-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-100/90">
              Ops / ROI
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-emerald-200/15 pt-4">
          {opsGradingRoiLoading ? (
            <p className="text-sm text-slate-400">Loading grading ROI…</p>
          ) : opsGradingRoiError ? (
            <StatusBanner tone="error">{opsGradingRoiError}</StatusBanner>
          ) : opsGradingRoi ? (
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">ROI</th>
                    <th className="p-3 font-medium">Owner</th>
                    <th className="p-3 font-medium">Inventory</th>
                    <th className="p-3 font-medium">Target</th>
                    <th className="p-3 font-medium">Costs</th>
                    <th className="p-3 font-medium">Net profit</th>
                    <th className="p-3 font-medium">ROI %</th>
                    <th className="p-3 font-medium">Liquidity-adjusted</th>
                    <th className="p-3 font-medium">Confidence</th>
                    <th className="p-3 font-medium">Checksum</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsGradingRoi.items.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={10}>
                        No grading ROI snapshots for this scope.
                      </td>
                    </tr>
                  ) : (
                    opsGradingRoi.items.map((row) => (
                      <tr key={row.id}>
                        <td className="p-3">
                          <div className="font-semibold text-white">{row.roi_status}</div>
                          <div className="text-[10px] text-slate-500">#{row.id}</div>
                        </td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">@{row.owner_user_id ?? "—"}</td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">inv {row.inventory_item_id ?? "—"}</td>
                        <td className="p-3">
                          {row.target_grader}
                          {row.target_grade ? <span className="block text-[10px] text-slate-500">{row.target_grade}</span> : null}
                        </td>
                        <td className="p-3 text-slate-400">
                          {row.grading_fee_amount ?? "—"} / {row.shipping_cost_amount ?? "—"} / {row.insurance_cost_amount ?? "—"}
                          <span className="block text-[10px] text-slate-500">
                            total {row.estimated_total_cost ?? "—"} · BE {row.break_even_grade ?? "—"}
                          </span>
                        </td>
                        <td className="p-3 text-slate-300">{row.estimated_net_profit ?? "—"}</td>
                        <td className="p-3 text-slate-300">{row.estimated_roi_pct ?? "—"}</td>
                        <td className="p-3">
                          <div>{row.liquidity_adjusted_roi ?? "—"}</div>
                          <div className="text-[10px] text-slate-500">{row.estimated_spread_amount ?? "—"} spread</div>
                        </td>
                        <td className="p-3">{row.confidence_level}</td>
                        <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </details>

      <details
        id="grading-submission-ops"
        className="mt-6 rounded-3xl border border-sky-400/35 bg-sky-950/15 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Grading submission batches</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Deterministic batch lifecycle reads for submission groups, shipment state, and turnaround estimates.
                No grader APIs or live carrier tracking.
              </p>
            </div>
            <span className="rounded-full border border-sky-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-sky-100/90">
              Ops / submissions
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-sky-200/15 pt-4">
          {opsGradingSubmissionLoading ? (
            <p className="text-sm text-slate-400">Loading grading submission batches…</p>
          ) : opsGradingSubmissionError ? (
            <StatusBanner tone="error">{opsGradingSubmissionError}</StatusBanner>
          ) : opsGradingSubmission ? (
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Batch</th>
                    <th className="p-3 font-medium">Owner</th>
                    <th className="p-3 font-medium">Grader</th>
                    <th className="p-3 font-medium">Items</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">Estimated cost</th>
                    <th className="p-3 font-medium">Shipment</th>
                    <th className="p-3 font-medium">Lifecycle</th>
                    <th className="p-3 font-medium">Turnaround</th>
                    <th className="p-3 font-medium">Checksum</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsGradingSubmission.items.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={10}>
                        No grading submission batches for this scope.
                      </td>
                    </tr>
                  ) : (
                    opsGradingSubmission.items.map((row) => (
                      <tr key={row.id}>
                        <td className="p-3">
                          <div className="font-semibold text-white">{row.batch_name}</div>
                          <div className="text-[10px] text-slate-500">#{row.id}</div>
                        </td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">@{row.owner_user_id}</td>
                        <td className="p-3 text-slate-300">{row.target_grader}</td>
                        <td className="p-3 text-slate-300">{row.item_count}</td>
                        <td className="p-3">
                          <div className="font-semibold text-white">{row.status}</div>
                          <div className="text-[10px] text-slate-500">
                            {row.shipped_date ?? "—"} / {row.completed_date ?? "—"}
                          </div>
                        </td>
                        <td className="p-3 text-slate-300">
                          {row.estimated_total_cost ?? "—"}
                          <span className="block text-[10px] text-slate-500">
                            actual {row.actual_total_cost ?? "—"}
                          </span>
                        </td>
                        <td className="p-3 text-slate-300">
                          {row.shipped_date ?? "—"}
                          <span className="block text-[10px] text-slate-500">
                            return {row.return_shipped_date ?? "—"}
                          </span>
                        </td>
                        <td className="p-3 text-slate-300">
                          submission {row.submission_date ?? "—"}
                          <span className="block text-[10px] text-slate-500">
                            received {row.grader_received_date ?? "—"} · grading {row.grading_started_date ?? "—"}
                          </span>
                        </td>
                        <td className="p-3 text-slate-300">{row.estimated_turnaround_days ?? "—"}</td>
                        <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </details>

      <details
        id="grading-recommendation-ops"
        className="mt-6 rounded-3xl border border-fuchsia-400/35 bg-fuchsia-950/15 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Grading recommendations</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Deterministic decision-support rows showing recommended action, preferred grader, ROI, confidence,
                risk, and replay-safe checksums.
              </p>
            </div>
            <span className="rounded-full border border-fuchsia-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-fuchsia-100/90">
              Ops / recommendations
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-fuchsia-200/15 pt-4">
          {opsGradingRecommendationLoading ? (
            <p className="text-sm text-slate-400">Loading grading recommendations…</p>
          ) : opsGradingRecommendationError ? (
            <StatusBanner tone="error">{opsGradingRecommendationError}</StatusBanner>
          ) : opsGradingRecommendation ? (
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Recommendation</th>
                    <th className="p-3 font-medium">Owner</th>
                    <th className="p-3 font-medium">Inventory</th>
                    <th className="p-3 font-medium">Grader</th>
                    <th className="p-3 font-medium">Expected ROI</th>
                    <th className="p-3 font-medium">Liquidity-adjusted ROI</th>
                    <th className="p-3 font-medium">Confidence</th>
                    <th className="p-3 font-medium">Risk</th>
                    <th className="p-3 font-medium">Checksum</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsGradingRecommendation.items.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={9}>
                        No grading recommendations for this scope.
                      </td>
                    </tr>
                  ) : (
                    opsGradingRecommendation.items.map((row) => (
                      <tr key={row.id}>
                        <td className="p-3">
                          <div className="font-semibold text-white">{row.recommended_action}</div>
                          <div className="text-[10px] text-slate-500">
                            {row.recommendation_strength} · #{row.id}
                          </div>
                        </td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">@{row.owner_user_id}</td>
                        <td className="p-3 text-slate-300">
                          inv {row.inventory_item_id ?? "—"}
                          <span className="block text-[10px] text-slate-500">candidate {row.grading_candidate_id ?? "—"}</span>
                        </td>
                        <td className="p-3">
                          {row.recommended_grader ?? "—"}
                          <span className="block text-[10px] text-slate-500">{row.recommended_grade_target ?? "—"}</span>
                        </td>
                        <td className="p-3 text-slate-300">
                          {row.expected_roi ?? "—"}
                          <span className="block text-[10px] text-slate-500">
                            profit {row.estimated_net_profit ?? "—"} · cost {row.estimated_total_cost ?? "—"}
                          </span>
                        </td>
                        <td className="p-3 text-slate-300">{row.liquidity_adjusted_roi ?? "—"}</td>
                        <td className="p-3 text-slate-300">
                          {row.confidence_score}
                          <span className="block text-[10px] text-slate-500">{row.recommendation_status}</span>
                        </td>
                        <td className="p-3 text-slate-300">
                          {row.risk_level}
                          <span className="block text-[10px] text-slate-500">{row.evidence_count} evidence</span>
                        </td>
                        <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </details>

      <details
        id="grading-risk-ops"
        className="mt-6 rounded-3xl border border-rose-400/35 bg-rose-950/15 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Grading risk and confidence</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Deterministic risk snapshots, confidence bands, and risk-adjusted ROI signals layered onto grading
                recommendations without changing recommendation actions.
              </p>
            </div>
            <span className="rounded-full border border-rose-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-rose-100/90">
              Ops / risk
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-rose-200/15 pt-4">
          {opsGradingRiskLoading ? (
            <p className="text-sm text-slate-400">Loading grading risk snapshots…</p>
          ) : opsGradingRiskError ? (
            <StatusBanner tone="error">{opsGradingRiskError}</StatusBanner>
          ) : opsGradingRisk ? (
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Snapshot</th>
                    <th className="p-3 font-medium">Owner</th>
                    <th className="p-3 font-medium">Inventory</th>
                    <th className="p-3 font-medium">Risk / confidence</th>
                    <th className="p-3 font-medium">Risk-adjusted ROI</th>
                    <th className="p-3 font-medium">Volatility indicators</th>
                    <th className="p-3 font-medium">Evidence</th>
                    <th className="p-3 font-medium">Checksum</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsGradingRisk.items.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={8}>
                        No grading risk snapshots for this scope.
                      </td>
                    </tr>
                  ) : (
                    opsGradingRisk.items.map((row) => (
                      <tr key={row.id}>
                        <td className="p-3">
                          <div className="font-semibold text-white">#{row.id}</div>
                          <div className="text-[10px] text-slate-500">rec {row.recommendation_id ?? "—"}</div>
                        </td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">@{row.owner_user_id}</td>
                        <td className="p-3 text-slate-300">
                          inv {row.inventory_item_id ?? "—"}
                          <span className="block text-[10px] text-slate-500">candidate {row.grading_candidate_id ?? "—"}</span>
                        </td>
                        <td className="p-3 text-slate-300">
                          {row.overall_risk_level}
                          <span className="block text-[10px] text-slate-500">{row.overall_confidence_level}</span>
                        </td>
                        <td className="p-3 text-slate-300">
                          {row.risk_adjusted_roi ?? "—"}
                          <span className="block text-[10px] text-slate-500">weight {row.confidence_weight ?? "—"}</span>
                        </td>
                        <td className="p-3 text-slate-300">
                          liq {row.liquidity_risk_score} · spread {row.spread_volatility_score}
                          <span className="block text-[10px] text-slate-500">
                            roi {row.roi_volatility_score} · grader {row.grader_variability_score}
                          </span>
                        </td>
                        <td className="p-3 text-slate-300">
                          {row.evidence_count} rows
                          <span className="block text-[10px] text-slate-500">strength {row.evidence_strength_score}</span>
                        </td>
                        <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </details>

      <details
        id="grading-reconciliation-ops"
        className="mt-6 rounded-3xl border border-cyan-400/35 bg-cyan-950/15 p-5 shadow-xl shadow-black/18 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Grading reconciliation</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Read-only expected-vs-actual grade and ROI delta rows with deterministic confidence and checksum
                lineage.
              </p>
            </div>
            <span className="rounded-full border border-cyan-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/90">
              Ops / reconciliation
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-cyan-200/15 pt-4">
          {opsGradingReconciliationLoading ? (
            <p className="text-sm text-slate-400">Loading grading reconciliation…</p>
          ) : opsGradingReconciliationError ? (
            <StatusBanner tone="error">{opsGradingReconciliationError}</StatusBanner>
          ) : opsGradingReconciliation ? (
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Record</th>
                    <th className="p-3 font-medium">Owner</th>
                    <th className="p-3 font-medium">Inventory</th>
                    <th className="p-3 font-medium">Grader</th>
                    <th className="p-3 font-medium">Expected</th>
                    <th className="p-3 font-medium">Actual</th>
                    <th className="p-3 font-medium">ROI delta</th>
                    <th className="p-3 font-medium">Confidence</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">Checksum</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsGradingReconciliation.items.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={10}>
                        No grading reconciliation records for this scope.
                      </td>
                    </tr>
                  ) : (
                    opsGradingReconciliation.items.map((row) => (
                      <tr key={row.id}>
                        <td className="p-3">
                          <div className="font-semibold text-white">#{row.id}</div>
                          <div className="text-[10px] text-slate-500">{row.grading_accuracy_status}</div>
                        </td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">@{row.owner_user_id}</td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">inv {row.inventory_item_id}</td>
                        <td className="p-3 text-slate-300">{row.target_grader}</td>
                        <td className="p-3 text-slate-300">
                          {row.expected_grade ?? "—"}
                          <span className="block text-[10px] text-slate-500">ROI {row.expected_roi ?? "—"}</span>
                        </td>
                        <td className="p-3 text-slate-300">
                          {row.final_grade ?? "—"}
                          <span className="block text-[10px] text-slate-500">ROI {row.realized_roi ?? "—"}</span>
                        </td>
                        <td className="p-3 text-slate-300">{row.roi_delta ?? "—"}</td>
                        <td className="p-3 text-slate-300">{row.confidence_level}</td>
                        <td className="p-3 text-slate-300">
                          {row.reconciliation_status}
                          <span className="block text-[10px] text-slate-500">{row.grading_accuracy_status}</span>
                        </td>
                        <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </details>

      {opsListingIntelligenceSummaryLoading ||
      opsListingIntelligenceSummaryError ||
      opsListingIntelligenceSummary ||
      opsListingIntelligenceSnapshotsLoading ||
      opsListingIntelligenceSnapshotsError ||
      opsListingIntelligenceSnapshots.length > 0 ||
      opsListingIntelligenceChecksLoading ||
      opsListingIntelligenceChecksError ||
      opsListingIntelligenceChecks.length > 0 ||
      opsListingIntelligenceEvidenceLoading ||
      opsListingIntelligenceEvidenceError ||
      opsListingIntelligenceEvidence.length > 0 ||
      opsListingIntelligenceChannelPerfLoading ||
      opsListingIntelligenceChannelPerfError ||
      opsListingIntelligenceChannelPerf.length > 0 ? (
        <details
          id="listing-intelligence-ops"
          open
          className="mt-6 rounded-3xl border border-fuchsia-400/35 bg-fuchsia-950/10 p-5 shadow-xl shadow-black/15 [&>summary::-webkit-details-marker]:hidden"
        >
          <summary className="cursor-pointer list-none">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-white">Listing intelligence explorer</h2>
                <p className="mt-1 max-w-3xl text-xs text-slate-400">
                  Deterministic listing quality, export-readiness, and channel-performance snapshots with evidence and
                  completeness checks. Read-only operational intelligence only.
                </p>
              </div>
              <span className="rounded-full border border-fuchsia-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-fuchsia-100/90">
                Ops / intelligence
              </span>
            </div>
          </summary>
          <div className="mt-5 space-y-4 border-t border-fuchsia-200/15 pt-4">
            {opsListingIntelligenceSummaryLoading ? (
              <p className="text-sm text-slate-400">Loading listing intelligence summary…</p>
            ) : opsListingIntelligenceSummaryError ? (
              <StatusBanner tone="error">{opsListingIntelligenceSummaryError}</StatusBanner>
            ) : opsListingIntelligenceSummary ? (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <StatCard label="Strong listings" value={String(opsListingIntelligenceSummary.strong_listing_count)} />
                <StatCard
                  label="Incomplete listings"
                  value={String(opsListingIntelligenceSummary.incomplete_listing_count)}
                />
                <StatCard
                  label="Average completeness"
                  value={opsListingIntelligenceSummary.average_completeness_score ?? "—"}
                />
                <StatCard label="Export-ready" value={String(opsListingIntelligenceSummary.export_ready_count)} />
                <StatCard label="Stale-risk" value={String(opsListingIntelligenceSummary.stale_risk_count)} />
              </div>
            ) : null}

            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Snapshot</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">Score</th>
                    <th className="p-3 font-medium">Evidence</th>
                    <th className="p-3 font-medium">Warnings</th>
                    <th className="p-3 font-medium">Checksum</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsListingIntelligenceSnapshotsLoading ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={6}>
                        Loading intelligence snapshots…
                      </td>
                    </tr>
                  ) : opsListingIntelligenceSnapshotsError ? (
                    <tr>
                      <td className="p-4" colSpan={6}>
                        <StatusBanner tone="error">{opsListingIntelligenceSnapshotsError}</StatusBanner>
                      </td>
                    </tr>
                  ) : opsListingIntelligenceSnapshots.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={6}>
                        No intelligence snapshots recorded yet.
                      </td>
                    </tr>
                  ) : (
                    opsListingIntelligenceSnapshots.map((row) => (
                      <tr key={row.id}>
                        <td className="p-3 font-mono text-[11px] text-slate-300">#{row.listing_id}</td>
                        <td className="p-3">{row.intelligence_status}</td>
                        <td className="p-3 text-slate-300">{row.completeness_score}</td>
                        <td className="p-3 text-slate-300">{row.evidence_count}</td>
                        <td className="p-3 text-slate-400">
                          {row.warning_flags_json.length > 0 ? row.warning_flags_json.join(", ") : "—"}
                        </td>
                        <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Listing</th>
                    <th className="p-3 font-medium">Check</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">Severity</th>
                    <th className="p-3 font-medium">Message</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsListingIntelligenceChecksLoading ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={5}>
                        Loading completeness checks…
                      </td>
                    </tr>
                  ) : opsListingIntelligenceChecksError ? (
                    <tr>
                      <td className="p-4" colSpan={5}>
                        <StatusBanner tone="error">{opsListingIntelligenceChecksError}</StatusBanner>
                      </td>
                    </tr>
                  ) : opsListingIntelligenceChecks.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={5}>
                        No completeness checks recorded yet.
                      </td>
                    </tr>
                  ) : (
                    opsListingIntelligenceChecks.slice(0, 12).map((row) => (
                      <tr key={row.id}>
                        <td className="p-3 font-mono text-[11px] text-slate-300">#{row.listing_id}</td>
                        <td className="p-3">{row.check_key.replace(/_/g, " ")}</td>
                        <td className="p-3">{row.status}</td>
                        <td className="p-3 text-slate-400">{row.severity}</td>
                        <td className="p-3 text-slate-400">{row.message}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Listing</th>
                      <th className="p-3 font-medium">Evidence</th>
                      <th className="p-3 font-medium">Type</th>
                      <th className="p-3 font-medium">Key</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsListingIntelligenceEvidenceLoading ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={4}>
                          Loading evidence rows…
                        </td>
                      </tr>
                    ) : opsListingIntelligenceEvidenceError ? (
                      <tr>
                        <td className="p-4" colSpan={4}>
                          <StatusBanner tone="error">{opsListingIntelligenceEvidenceError}</StatusBanner>
                        </td>
                      </tr>
                    ) : opsListingIntelligenceEvidence.length === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={4}>
                          No evidence rows recorded yet.
                        </td>
                      </tr>
                    ) : (
                      opsListingIntelligenceEvidence.slice(0, 10).map((row) => (
                        <tr key={row.id}>
                          <td className="p-3 font-mono text-[11px] text-slate-300">#{row.source_listing_id ?? "—"}</td>
                          <td className="p-3 text-slate-300">#{row.id}</td>
                          <td className="p-3">{row.evidence_type}</td>
                          <td className="p-3 text-slate-400">{row.evidence_key}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Channel</th>
                      <th className="p-3 font-medium">Listings</th>
                      <th className="p-3 font-medium">Sold</th>
                      <th className="p-3 font-medium">Exported</th>
                      <th className="p-3 font-medium">Sales</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsListingIntelligenceChannelPerfLoading ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={6}>
                          Loading channel performance…
                        </td>
                      </tr>
                    ) : opsListingIntelligenceChannelPerfError ? (
                      <tr>
                        <td className="p-4" colSpan={6}>
                          <StatusBanner tone="error">{opsListingIntelligenceChannelPerfError}</StatusBanner>
                        </td>
                      </tr>
                    ) : opsListingIntelligenceChannelPerf.length === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={6}>
                          No channel performance snapshots recorded yet.
                        </td>
                      </tr>
                    ) : (
                      opsListingIntelligenceChannelPerf.slice(0, 10).map((row) => (
                        <tr key={row.id}>
                          <td className="p-3">{row.channel}</td>
                          <td className="p-3">{row.total_listings}</td>
                          <td className="p-3">{row.sold_listings}</td>
                          <td className="p-3">{row.exported_count}</td>
                          <td className="p-3">{row.sales_count}</td>
                          <td className="p-3 font-mono text-[10px] text-slate-400">
                            {abbrevExportChecksum(row.checksum)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </details>
      ) : null}

      <details
        id="listing-export-ops"
        open
        className="mt-6 rounded-3xl border border-cyan-400/35 bg-cyan-950/10 p-5 shadow-xl shadow-black/15 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Marketplace listing exports</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Read-only audit of deterministic CSV artifacts. Rows include owner scope, counters, replay keys, checksums,
                and stable skip reasons — no inventory decrements or live marketplace posting occurs on this ledger.
              </p>
            </div>
            <span className="rounded-full border border-cyan-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/90">
              Ops / exports
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-cyan-200/15 pt-4">
          {opsListingExportDownloadError ? (
            <div className="mb-3">
              <StatusBanner tone="error">{opsListingExportDownloadError}</StatusBanner>
            </div>
          ) : null}
          {opsListingExportRunsLoading ? (
            <p className="text-sm text-slate-400">Loading listing export runs…</p>
          ) : opsListingExportRunsError ? (
            <StatusBanner tone="error">{opsListingExportRunsError}</StatusBanner>
          ) : opsListingExportRuns ? (
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Run</th>
                    <th className="p-3 font-medium">Owner</th>
                    <th className="p-3 font-medium">Channel</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">Exported</th>
                    <th className="p-3 font-medium">Skipped</th>
                    <th className="p-3 font-medium">Checksum</th>
                    <th className="p-3 font-medium">Created</th>
                    <th className="p-3 font-medium">Completed</th>
                    <th className="p-3 font-medium">Artifacts</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsListingExportRuns.items.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={10}>
                        No export attempts recorded yet.
                      </td>
                    </tr>
                  ) : (
                    opsListingExportRuns.items.map((run) => (
                      <tr key={run.id}>
                        <td className="p-3 font-mono text-[11px] text-slate-300">#{run.id}</td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">@{run.owner_user_id}</td>
                        <td className="p-3">{run.channel}</td>
                        <td className="p-3">{run.status}</td>
                        <td className="p-3">{run.exported_listing_count}</td>
                        <td className="p-3">{run.skipped_listing_count}</td>
                        <td className="p-3 font-mono text-[10px] text-slate-400">{abbrevExportChecksum(run.checksum)}</td>
                        <td className="p-3 text-slate-400">{formatDateTime(run.created_at)}</td>
                        <td className="p-3 text-slate-400">{run.completed_at ? formatDateTime(run.completed_at) : "—"}</td>
                        <td className="p-3">
                          <button
                            type="button"
                            className="rounded-full border border-cyan-400/35 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-100 transition hover:border-cyan-300/60 hover:bg-cyan-500/10 disabled:opacity-40"
                            disabled={run.status !== "COMPLETED"}
                            onClick={() => {
                              void (async () => {
                                setOpsListingExportDownloadError(null);
                                try {
                                  await apiClient.downloadOpsListingExportCsv(run.id);
                                } catch (err) {
                                  setOpsListingExportDownloadError(
                                    err instanceof ApiError ? err.message : "Unable to download export CSV.",
                                  );
                                }
                              })();
                            }}
                          >
                            CSV
                          </button>
                          <div className="mt-2 text-[10px] text-slate-500">
                            Replay:
                            <span className="ml-1 font-mono text-slate-400">{run.replay_key ?? "—"}</span>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </details>

      <section
        id="convention-ops"
        className="mt-6 rounded-3xl border border-violet-400/35 bg-violet-950/12 p-5 shadow-xl shadow-black/15"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Convention / show operations</h2>
            <p className="mt-1 max-w-3xl text-xs text-slate-400">
              Read-only operator view of convention events, assignments, movement history, temporary pricing, and sale
              sessions. The surface is descriptive only and preserves append-only operational history.
            </p>
          </div>
          <span className="rounded-full border border-violet-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-100/90">
            Ops / convention
          </span>
        </div>
        <div className="mt-5 border-t border-violet-200/15 pt-4">
          {opsConventionSummaryLoading ? (
            <p className="text-sm text-slate-400">Loading convention summary…</p>
          ) : opsConventionSummaryError ? (
            <StatusBanner tone="error">{opsConventionSummaryError}</StatusBanner>
          ) : opsConventionSummary ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <StatCard label="Active conventions" value={String(opsConventionSummary.active_convention_count)} />
                <StatCard label="Assigned inventory" value={String(opsConventionSummary.assigned_inventory_count)} />
                <StatCard label="Wall books" value={String(opsConventionSummary.wall_book_count)} />
                <StatCard label="Showcases" value={String(opsConventionSummary.showcase_count)} />
                <StatCard label="Active sale sessions" value={String(opsConventionSummary.active_sale_session_count)} />
              </div>
              <div className="mt-4 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Event</th>
                      <th className="p-3 font-medium">Type</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">Window</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsConventionSummary.recent_events.length === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={4}>
                          No convention events recorded yet.
                        </td>
                      </tr>
                    ) : (
                      opsConventionSummary.recent_events.slice(0, 5).map((event) => (
                        <tr key={event.id}>
                          <td className="p-3 text-slate-200">{event.name}</td>
                          <td className="p-3 text-slate-300">{event.event_type.replace(/_/g, " ")}</td>
                          <td className="p-3 text-slate-300">{event.status}</td>
                          <td className="p-3 text-slate-300">
                            {formatDate(event.start_date)} - {formatDate(event.end_date)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
          <div className="mt-5 grid gap-4 xl:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Assignments</p>
              {opsConventionAssignmentsLoading ? (
                <p className="mt-3 text-sm text-slate-400">Loading convention assignments…</p>
              ) : opsConventionAssignmentsError ? (
                <div className="mt-3">
                  <StatusBanner tone="error">{opsConventionAssignmentsError}</StatusBanner>
                </div>
              ) : (
                <div className="mt-3 overflow-auto rounded-xl border border-white/10 bg-slate-900/55">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                      <tr>
                        <th className="p-3 font-medium">Event</th>
                        <th className="p-3 font-medium">Inventory</th>
                        <th className="p-3 font-medium">Type</th>
                        <th className="p-3 font-medium">Location</th>
                        <th className="p-3 font-medium">Price</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10 text-slate-200">
                      {opsConventionAssignments?.items.length ? (
                        opsConventionAssignments.items.slice(0, 6).map((assignment) => (
                          <tr key={assignment.id}>
                            <td className="p-3 font-mono text-[11px]">#{assignment.convention_event_id}</td>
                            <td className="p-3 font-mono text-[11px]">#{assignment.inventory_item_id}</td>
                            <td className="p-3 text-slate-300">{assignment.assignment_type}</td>
                            <td className="p-3 text-slate-300">{assignment.display_location ?? "—"}</td>
                            <td className="p-3 text-slate-300">
                              {assignment.local_price_amount ? `${assignment.local_price_currency ?? ""} ${assignment.local_price_amount}` : "—"}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td className="p-4 text-slate-500" colSpan={5}>
                            No convention assignments recorded yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Movement history</p>
              {opsConventionMovementsLoading ? (
                <p className="mt-3 text-sm text-slate-400">Loading movement history…</p>
              ) : opsConventionMovementsError ? (
                <div className="mt-3">
                  <StatusBanner tone="error">{opsConventionMovementsError}</StatusBanner>
                </div>
              ) : (
                <div className="mt-3 overflow-auto rounded-xl border border-white/10 bg-slate-900/55">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                      <tr>
                        <th className="p-3 font-medium">Event</th>
                        <th className="p-3 font-medium">Inventory</th>
                        <th className="p-3 font-medium">Type</th>
                        <th className="p-3 font-medium">From</th>
                        <th className="p-3 font-medium">To</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10 text-slate-200">
                      {opsConventionMovements?.items.length ? (
                        opsConventionMovements.items.slice(0, 6).map((movement) => (
                          <tr key={movement.id}>
                            <td className="p-3 font-mono text-[11px]">#{movement.convention_event_id}</td>
                            <td className="p-3 font-mono text-[11px]">#{movement.inventory_item_id}</td>
                            <td className="p-3 text-slate-300">{movement.movement_type}</td>
                            <td className="p-3 text-slate-300">{movement.from_location ?? "—"}</td>
                            <td className="p-3 text-slate-300">{movement.to_location ?? "—"}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td className="p-4 text-slate-500" colSpan={5}>
                            No movement history recorded yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Temporary pricing</p>
              {opsConventionPriceSnapshotsLoading ? (
                <p className="mt-3 text-sm text-slate-400">Loading convention pricing…</p>
              ) : opsConventionPriceSnapshotsError ? (
                <div className="mt-3">
                  <StatusBanner tone="error">{opsConventionPriceSnapshotsError}</StatusBanner>
                </div>
              ) : (
                <div className="mt-3 overflow-auto rounded-xl border border-white/10 bg-slate-900/55">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                      <tr>
                        <th className="p-3 font-medium">Event</th>
                        <th className="p-3 font-medium">Inventory</th>
                        <th className="p-3 font-medium">Price</th>
                        <th className="p-3 font-medium">Source</th>
                        <th className="p-3 font-medium">Created</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10 text-slate-200">
                      {opsConventionPriceSnapshots?.items.length ? (
                        opsConventionPriceSnapshots.items.slice(0, 6).map((price) => (
                          <tr key={price.id}>
                            <td className="p-3 font-mono text-[11px]">#{price.convention_event_id}</td>
                            <td className="p-3 font-mono text-[11px]">#{price.inventory_item_id}</td>
                            <td className="p-3 text-slate-300">
                              {price.currency} {price.price_amount}
                            </td>
                            <td className="p-3 text-slate-300">{price.pricing_source}</td>
                            <td className="p-3 text-slate-400">{formatDateTime(price.created_at)}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td className="p-4 text-slate-500" colSpan={5}>
                            No convention price snapshots recorded yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Active sessions</p>
              {opsConventionSaleSessionsLoading ? (
                <p className="mt-3 text-sm text-slate-400">Loading sale sessions…</p>
              ) : opsConventionSaleSessionsError ? (
                <div className="mt-3">
                  <StatusBanner tone="error">{opsConventionSaleSessionsError}</StatusBanner>
                </div>
              ) : (
                <div className="mt-3 overflow-auto rounded-xl border border-white/10 bg-slate-900/55">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                      <tr>
                        <th className="p-3 font-medium">Session</th>
                        <th className="p-3 font-medium">Event</th>
                        <th className="p-3 font-medium">Status</th>
                        <th className="p-3 font-medium">Opened</th>
                        <th className="p-3 font-medium">Closed</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10 text-slate-200">
                      {opsConventionSaleSessions?.items.length ? (
                        opsConventionSaleSessions.items.slice(0, 6).map((sessionRow) => (
                          <tr key={sessionRow.id}>
                            <td className="p-3 font-mono text-[11px]">#{sessionRow.id}</td>
                            <td className="p-3 font-mono text-[11px]">#{sessionRow.convention_event_id}</td>
                            <td className="p-3 text-slate-300">{sessionRow.status}</td>
                            <td className="p-3 text-slate-400">{formatDateTime(sessionRow.opened_at)}</td>
                            <td className="p-3 text-slate-400">{sessionRow.closed_at ? formatDateTime(sessionRow.closed_at) : "—"}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td className="p-4 text-slate-500" colSpan={5}>
                            No convention sale sessions recorded yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      <section
        id="liquidity-ops"
        className="mt-6 rounded-3xl border border-sky-400/35 bg-sky-950/12 p-5 shadow-xl shadow-black/15"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Inventory liquidity engine</h2>
            <p className="mt-1 max-w-3xl text-xs text-slate-400">
              Deterministic liquidity snapshots derived from listing velocity, stale thresholds, and actual sales. The
              panel is read-only and explains every result through persisted evidence rows.
            </p>
          </div>
          <span className="rounded-full border border-sky-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-sky-100/90">
            Ops / liquidity
          </span>
        </div>
        <div className="mt-5 border-t border-sky-200/15 pt-4">
          {opsLiquiditySummaryLoading ? (
            <p className="text-sm text-slate-400">Loading liquidity summary…</p>
          ) : opsLiquiditySummaryError ? (
            <StatusBanner tone="error">{opsLiquiditySummaryError}</StatusBanner>
          ) : opsLiquiditySummary ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="High liquidity snapshots" value={String(opsLiquiditySummary.high_liquidity_count)} />
                <StatCard label="Stale inventory snapshots" value={String(opsLiquiditySummary.stale_inventory_count)} />
                <StatCard
                  label="Median days to sale"
                  value={opsLiquiditySummary.median_days_to_sale ? `${opsLiquiditySummary.median_days_to_sale} days` : "—"}
                />
                <StatCard label="Sell-through %" value={`${opsLiquiditySummary.sell_through_pct}%`} />
              </div>
              <div className="mt-4 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Event</th>
                      <th className="p-3 font-medium">Threshold</th>
                      <th className="p-3 font-medium">Days active</th>
                      <th className="p-3 font-medium">Listing</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsLiquiditySummary.recent_stale_events.length === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={4}>
                          No stale events recorded yet.
                        </td>
                      </tr>
                    ) : (
                      opsLiquiditySummary.recent_stale_events.slice(0, 6).map((evt) => (
                        <tr key={evt.id}>
                          <td className="p-3 text-slate-200">{evt.event_type.replace(/_/g, " ")}</td>
                          <td className="p-3 text-slate-300">{evt.threshold_days}+ days</td>
                          <td className="p-3 text-slate-300">{evt.days_active} days</td>
                          <td className="p-3 font-mono text-[11px] text-slate-300">#{evt.listing_id}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
          <div className="mt-5">
            {opsLiquiditySnapshotsLoading ? (
              <p className="text-sm text-slate-400">Loading liquidity snapshots…</p>
            ) : opsLiquiditySnapshotsError ? (
              <StatusBanner tone="error">{opsLiquiditySnapshotsError}</StatusBanner>
            ) : (
              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Snapshot</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">Channel</th>
                      <th className="p-3 font-medium">Sell-through</th>
                      <th className="p-3 font-medium">Stale</th>
                      <th className="p-3 font-medium">Relist</th>
                      <th className="p-3 font-medium">Confidence</th>
                      <th className="p-3 font-medium">Evidence</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsLiquiditySnapshots.length === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={9}>
                          No liquidity snapshots recorded yet.
                        </td>
                      </tr>
                    ) : (
                      opsLiquiditySnapshots.map((snapshot) => (
                        <tr key={snapshot.id}>
                          <td className="p-3 font-mono text-[11px] text-slate-300">#{snapshot.id}</td>
                          <td className="p-3 text-slate-200">{snapshot.liquidity_status}</td>
                          <td className="p-3 text-slate-200">{snapshot.channel ?? "—"}</td>
                          <td className="p-3 text-slate-300">{snapshot.sell_through_rate_pct}%</td>
                          <td className="p-3 text-slate-300">{snapshot.stale_listing_rate_pct}%</td>
                          <td className="p-3 text-slate-300">{snapshot.relist_rate_pct}%</td>
                          <td className="p-3 text-slate-300">{snapshot.liquidity_confidence}</td>
                          <td className="p-3 text-slate-300">{snapshot.evidence_count}</td>
                          <td className="p-3 font-mono text-[10px] text-slate-400">{snapshot.checksum.slice(0, 10)}…</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </section>

      <section
        id="sales-ledger-ops"
        className="mt-6 rounded-3xl border border-emerald-400/35 bg-emerald-950/12 p-5 shadow-xl shadow-black/15"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Realized sales ledger</h2>
            <p className="mt-1 max-w-3xl text-xs text-slate-400">
              Append-only realized sale truth with deterministic money math, linked listing transitions, and no inventory
              decrements. This is the economic ledger used for ops review and downstream profitability analysis.
            </p>
          </div>
          <span className="rounded-full border border-emerald-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-100/90">
            Ops / realized sales
          </span>
        </div>
        <div className="mt-5 border-t border-emerald-200/15 pt-4">
          {opsSalesLedgerLoading ? (
            <p className="text-sm text-slate-400">Loading realized sales…</p>
          ) : opsSalesLedgerError ? (
            <StatusBanner tone="error">{opsSalesLedgerError}</StatusBanner>
          ) : (
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Sale</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">Channel</th>
                    <th className="p-3 font-medium">Gross</th>
                    <th className="p-3 font-medium">Net</th>
                    <th className="p-3 font-medium">Profit</th>
                    <th className="p-3 font-medium">Sale date</th>
                    <th className="p-3 font-medium">Linked listing</th>
                    <th className="p-3 font-medium">Events</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsSalesLedger.length === 0 ? (
                    <tr>
                      <td className="p-4 text-slate-500" colSpan={9}>
                        No realized sales recorded yet.
                      </td>
                    </tr>
                  ) : (
                    opsSalesLedger.map((sale) => (
                      <tr key={sale.id}>
                        <td className="p-3 font-mono text-[11px] text-slate-300">#{sale.id}</td>
                        <td className="p-3 text-slate-200">{sale.status}</td>
                        <td className="p-3 text-slate-200">{sale.channel.replace(/_/g, " ")}</td>
                        <td className="p-3 text-slate-300">{formatCurrency(sale.gross_sale_amount)}</td>
                        <td className="p-3 text-slate-300">{formatCurrency(sale.net_proceeds_amount)}</td>
                        <td className="p-3 text-slate-300">{formatCurrency(sale.realized_profit_amount)}</td>
                        <td className="p-3 text-slate-400">{formatDate(sale.sale_date)}</td>
                        <td className="p-3 text-slate-400">{sale.listing_id ? `#${sale.listing_id}` : "—"}</td>
                        <td className="p-3 text-slate-400">{sale.event_count}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <MarketIntelligenceOpsDiagnostics ownerUserId={opsPortfolioOwnerApplied} />
      <MarketIntelligenceFeedPanel ownerUserId={opsPortfolioOwnerApplied} mode="ops" />

      <section
        id="market-determinism-ops"
        className="mt-6 rounded-3xl border border-violet-400/35 bg-violet-950/12 p-5 shadow-xl shadow-black/20"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Market determinism integrity</h2>
            <p className="mt-1 max-w-3xl text-xs text-slate-400">
              Append-only validation runs, invariant findings, replay audits, and checksum lineage across the P39 stack.
            </p>
          </div>
          <span className="rounded-full border border-violet-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-100/90">
            Ops / determinism
          </span>
        </div>
        <div className="mt-5 border-t border-violet-200/15 pt-4">
          {opsMarketDeterminismLoading ? (
            <p className="text-sm text-slate-400">Loading market determinism runs…</p>
          ) : opsMarketDeterminismError ? (
            <StatusBanner tone="error">{opsMarketDeterminismError}</StatusBanner>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5">
                <StatCard
                  label="Validation runs"
                  value={String(opsMarketDeterminismRuns?.pagination.total_count ?? 0)}
                />
                <StatCard
                  label="Invariant findings"
                  value={String(opsMarketDeterminismInvariants.filter((row) => row.invariant_status !== "PASS").length)}
                />
                <StatCard
                  label="Replay failures"
                  value={String(opsMarketDeterminismReplayAudits.filter((row) => row.replay_status === "FAIL").length)}
                />
                <StatCard
                  label="Latest checksum"
                  value={abbrevExportChecksum(opsMarketDeterminismRuns?.items[0]?.validation_checksum ?? null)}
                />
                <StatCard
                  label="Latest status"
                  value={opsMarketDeterminismRuns?.items[0]?.validation_status ?? "—"}
                />
              </div>

              {opsMarketDeterminismRuns?.items[0] &&
              (opsMarketDeterminismRuns.items[0].checksum_mismatch_count > 0 ||
                opsMarketDeterminismRuns.items[0].invariant_failure_count > 0 ||
                opsMarketDeterminismRuns.items[0].replay_failure_count > 0) ? (
                <div className="mt-4">
                  <StatusBanner tone="warning">
                    Latest run recorded {opsMarketDeterminismRuns.items[0].checksum_mismatch_count} checksum mismatches,{" "}
                    {opsMarketDeterminismRuns.items[0].invariant_failure_count} invariant failures, and{" "}
                    {opsMarketDeterminismRuns.items[0].replay_failure_count} replay failures.
                  </StatusBanner>
                </div>
              ) : null}

              <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr,1fr]">
                <div className="space-y-4">
                  <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Run</th>
                          <th className="p-3 font-medium">Status</th>
                          <th className="p-3 font-medium">Date</th>
                          <th className="p-3 font-medium">Checksum</th>
                          <th className="p-3 font-medium">Failures</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10 text-slate-200">
                        {opsMarketDeterminismRuns?.items.length ? (
                          opsMarketDeterminismRuns.items.map((row) => (
                            <tr key={row.id}>
                              <td className="p-3 font-mono text-[11px] text-slate-300">#{row.id}</td>
                              <td className="p-3">
                                <span
                                  className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${determinismTone(
                                    row.validation_status,
                                  )}`}
                                >
                                  {row.validation_status}
                                </span>
                              </td>
                              <td className="p-3 text-slate-300">{row.snapshot_date}</td>
                              <td className="p-3 font-mono text-[10px] text-slate-400">
                                {abbrevExportChecksum(row.validation_checksum)}
                              </td>
                              <td className="p-3 text-slate-300">
                                {row.checksum_mismatch_count + row.invariant_failure_count + row.replay_failure_count}
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={5}>
                              No determinism runs recorded for this scope yet.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>

                  <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Invariant</th>
                          <th className="p-3 font-medium">Layer</th>
                          <th className="p-3 font-medium">Status</th>
                          <th className="p-3 font-medium">Run</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10 text-slate-200">
                        {opsMarketDeterminismInvariants.length ? (
                          opsMarketDeterminismInvariants.map((row) => (
                            <tr
                              key={row.id}
                              className="cursor-pointer hover:bg-white/5"
                              onClick={() => setOpsMarketDeterminismSelectedInvariantId(row.id)}
                            >
                              <td className="p-3 text-slate-200">{row.invariant_code.replace(/_/g, " ")}</td>
                              <td className="p-3 text-slate-300">{row.layer_name}</td>
                              <td className="p-3">
                                <span
                                  className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${determinismTone(
                                    row.invariant_status,
                                  )}`}
                                >
                                  {row.invariant_status}
                                </span>
                              </td>
                              <td className="p-3 font-mono text-[11px] text-slate-400">
                                #{row.market_determinism_validation_run_id}
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={4}>
                              No invariant rows available.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Replay audit</th>
                          <th className="p-3 font-medium">Status</th>
                          <th className="p-3 font-medium">Original</th>
                          <th className="p-3 font-medium">Replay</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10 text-slate-200">
                        {opsMarketDeterminismReplayAudits.length ? (
                          opsMarketDeterminismReplayAudits.map((row) => (
                            <tr
                              key={row.id}
                              className="cursor-pointer hover:bg-white/5"
                              onClick={() => setOpsMarketDeterminismSelectedReplayId(row.id)}
                            >
                              <td className="p-3 text-slate-200">{row.artifact_type.replace(/_/g, " ")}</td>
                              <td className="p-3">
                                <span
                                  className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${determinismTone(
                                    row.replay_status,
                                  )}`}
                                >
                                  {row.replay_status}
                                </span>
                              </td>
                              <td className="p-3 font-mono text-[10px] text-slate-400">
                                {abbrevExportChecksum(row.original_checksum)}
                              </td>
                              <td className="p-3 font-mono text-[10px] text-slate-400">
                                {abbrevExportChecksum(row.replay_checksum)}
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={4}>
                              No replay audit rows available.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>

                  {opsMarketDeterminismInvariants.find((row) => row.id === opsMarketDeterminismSelectedInvariantId) ? (
                    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Selected invariant</p>
                      <pre className="mt-3 overflow-auto whitespace-pre-wrap break-all text-[11px] text-slate-300">
                        {JSON.stringify(
                          opsMarketDeterminismInvariants.find((row) => row.id === opsMarketDeterminismSelectedInvariantId),
                          null,
                          2,
                        )}
                      </pre>
                    </div>
                  ) : null}

                  {opsMarketDeterminismReplayAudits.find((row) => row.id === opsMarketDeterminismSelectedReplayId) ? (
                    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Selected replay audit</p>
                      <pre className="mt-3 overflow-auto whitespace-pre-wrap break-all text-[11px] text-slate-300">
                        {JSON.stringify(
                          opsMarketDeterminismReplayAudits.find((row) => row.id === opsMarketDeterminismSelectedReplayId),
                          null,
                          2,
                        )}
                      </pre>
                    </div>
                  ) : null}
                </div>
              </div>
            </>
          )}
        </div>
      </section>

      <details
        id="market-ingestion-ops"
        className="mt-6 rounded-3xl border border-cyan-400/35 bg-cyan-950/12 p-5 shadow-xl shadow-black/20 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Market ingestion foundation</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Deterministic external acquisition intake batches with preserved raw payload rows, replay-safe checksums,
                append-only events, and no normalization or scoring yet.
              </p>
            </div>
            <span className="rounded-full border border-cyan-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/90">
              Ops / ingestion
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-cyan-200/15 pt-4">
          {opsMarketIngestionLoading ? (
            <p className="text-sm text-slate-400">Loading market ingestion batches…</p>
          ) : opsMarketIngestionError ? (
            <StatusBanner tone="error">{opsMarketIngestionError}</StatusBanner>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5">
                <StatCard label="Batches" value={String(opsMarketIngestionSummary?.pagination.total_count ?? 0)} />
                <StatCard label="Completed" value={String(opsMarketIngestionSummary?.status_counts.COMPLETED ?? 0)} />
                <StatCard label="Failed" value={String(opsMarketIngestionSummary?.status_counts.FAILED ?? 0)} />
                <StatCard
                  label="Pending / processing"
                  value={String((opsMarketIngestionSummary?.status_counts.PENDING ?? 0) + (opsMarketIngestionSummary?.status_counts.PROCESSING ?? 0))}
                />
                <StatCard
                  label="Last ingestion"
                  value={opsMarketIngestionSummary?.last_ingestion_at ? formatDateTime(opsMarketIngestionSummary.last_ingestion_at) : "—"}
                />
              </div>

              <div className="mt-6 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Inspect</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">Owner</th>
                      <th className="p-3 font-medium">Source</th>
                      <th className="p-3 font-medium">Records</th>
                      <th className="p-3 font-medium">Failures</th>
                      <th className="p-3 font-medium">Checksum</th>
                      <th className="p-3 font-medium">Timeline</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsMarketIngestionSummary?.items.length ? (
                      opsMarketIngestionSummary.items.map((row) => {
                        const isSelected = opsMarketIngestionSelectedId === row.id;
                        return (
                          <tr key={row.id}>
                            <td className="p-3 align-top">
                              <button
                                type="button"
                                className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                                  isSelected
                                    ? "border-cyan-300/70 bg-cyan-400/20 text-cyan-50"
                                    : "border-white/15 text-slate-200 hover:border-cyan-300/35"
                                }`}
                                onClick={() => setOpsMarketIngestionSelectedId((cur) => (cur === row.id ? null : row.id))}
                              >
                                {isSelected ? "Hide" : "View"}
                              </button>
                            </td>
                            <td className="p-3 align-top">{row.ingestion_status}</td>
                            <td className="p-3 align-top font-mono text-[11px] text-slate-400">
                              {row.owner_user_id ? `@${row.owner_user_id}` : "global"}
                            </td>
                            <td className="p-3 align-top">
                              <div>{row.batch_source_type}</div>
                              <div className="mt-1 text-[11px] text-slate-500">{row.batch_file_name ?? "No file name"}</div>
                            </td>
                            <td className="p-3 align-top">
                              <div>{row.successful_records}/{row.total_records}</div>
                              <div className="mt-1 text-[11px] text-slate-500">accepted / total</div>
                            </td>
                            <td className="p-3 align-top">{row.failed_records}</td>
                            <td className="p-3 align-top font-mono text-[10px] text-slate-400">
                              {abbrevExportChecksum(row.batch_checksum)}
                            </td>
                            <td className="p-3 align-top text-[11px] text-slate-400">
                              <div>created {formatDateTime(row.created_at)}</div>
                              <div className="mt-1">completed {row.completed_at ? formatDateTime(row.completed_at) : "—"}</div>
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={8}>
                          No market-ingestion batches recorded yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {opsMarketIngestionDetailLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading selected ingestion batch…</p>
              ) : opsMarketIngestionDetailError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{opsMarketIngestionDetailError}</StatusBanner>
                </div>
              ) : opsMarketIngestionDetail ? (
                <div className="mt-5 grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Ingestion timeline</p>
                    <div className="mt-3 space-y-2 text-xs text-slate-200">
                      {opsMarketIngestionDetail.events.map((event) => (
                        <div key={event.id} className="rounded-xl border border-white/10 px-3 py-2">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="font-semibold text-white">{event.event_type}</p>
                            <span className="text-[10px] text-slate-500">{formatDateTime(event.created_at)}</span>
                          </div>
                          <p className="mt-1 text-[10px] text-slate-400">
                            {JSON.stringify(event.metadata_json).slice(0, 240)}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Raw source preview</p>
                    <div className="mt-3 space-y-2 text-xs text-slate-200">
                      {opsMarketIngestionRaw.length === 0 ? (
                        <p className="text-slate-500">No raw rows captured for the selected batch.</p>
                      ) : (
                        opsMarketIngestionRaw.slice(0, 8).map((row) => (
                          <div key={row.id} className="rounded-xl border border-white/10 px-3 py-2">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="font-semibold text-white">{row.processing_status}</p>
                              <span className="font-mono text-[10px] text-slate-500">{abbrevExportChecksum(row.raw_hash)}</span>
                            </div>
                            <p className="mt-1 text-[10px] text-slate-400">
                              {row.error_message ?? JSON.stringify(row.raw_record_json).slice(0, 220)}
                            </p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </details>

      <details
        id="market-scoring-ops"
        className="mt-6 rounded-3xl border border-fuchsia-400/35 bg-fuchsia-950/12 p-5 shadow-xl shadow-black/20 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Market acquisition scoring engine</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Deterministic acquisition ranking built on normalized market candidates plus read-only P38 context.
                Use this view for snapshot distribution, top scored rows, evidence payloads, and append-safe history.
              </p>
            </div>
            <span className="rounded-full border border-fuchsia-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-fuchsia-100/90">
              Ops / P39-03
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-fuchsia-200/15 pt-4">
          {opsMarketScoringLoading ? (
            <p className="text-sm text-slate-400">Loading market scoring snapshots…</p>
          ) : opsMarketScoringError ? (
            <StatusBanner tone="error">{opsMarketScoringError}</StatusBanner>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <StatCard label="Snapshots tracked" value={String(opsMarketScoringSummary?.pagination.total_count ?? 0)} />
                <StatCard label="Top bucket: STRONG_BUY" value={String(opsMarketScoringSummary?.items[0]?.strong_buy_count ?? 0)} />
                <StatCard label="Top bucket: BUY" value={String(opsMarketScoringSummary?.items[0]?.buy_count ?? 0)} />
                <StatCard label="Avg score" value={opsMarketScoringSummary?.items[0]?.avg_score ?? "—"} />
                <StatCard label="Avg liquidity" value={opsMarketScoringSummary?.items[0]?.avg_liquidity_score ?? "—"} />
              </div>

              <div className="mt-6 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Inspect</th>
                      <th className="p-3 font-medium">Owner</th>
                      <th className="p-3 font-medium">Snapshot date</th>
                      <th className="p-3 font-medium">Rows</th>
                      <th className="p-3 font-medium">Distribution</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsMarketScoringSummary?.items.length ? (
                      opsMarketScoringSummary.items.map((row) => {
                        const isSelected = opsMarketScoringSelectedId === row.id;
                        return (
                          <tr key={row.id}>
                            <td className="p-3 align-top">
                              <button
                                type="button"
                                className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                                  isSelected
                                    ? "border-fuchsia-300/70 bg-fuchsia-400/20 text-fuchsia-50"
                                    : "border-white/15 text-slate-200 hover:border-fuchsia-300/35"
                                }`}
                                onClick={() => setOpsMarketScoringSelectedId((cur) => (cur === row.id ? null : row.id))}
                              >
                                {isSelected ? "Hide" : "View"}
                              </button>
                            </td>
                            <td className="p-3 align-top font-mono text-[11px] text-slate-400">@{row.owner_user_id}</td>
                            <td className="p-3 align-top">{formatDate(row.snapshot_date)}</td>
                            <td className="p-3 align-top">{row.total_candidates_scored}</td>
                            <td className="p-3 align-top">
                              <div>SB {row.strong_buy_count} / B {row.buy_count}</div>
                              <div className="mt-1 text-[11px] text-slate-500">W {row.watch_count} / I {row.ignore_count}</div>
                            </td>
                            <td className="p-3 align-top font-mono text-[10px] text-slate-400">
                              {abbrevExportChecksum(row.checksum)}
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={6}>
                          No market-scoring snapshots recorded yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {opsMarketScoringDetailLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading scoring drill-down…</p>
              ) : opsMarketScoringDetailError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{opsMarketScoringDetailError}</StatusBanner>
                </div>
              ) : opsMarketScoringSelectedId ? (
                <div className="mt-5 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Top scored rows</p>
                    <div className="mt-3 space-y-2 text-xs text-slate-200">
                      {opsMarketScoringScores.length === 0 ? (
                        <p className="text-slate-500">No score rows loaded for the selected snapshot.</p>
                      ) : (
                        opsMarketScoringScores.slice(0, 10).map((row) => (
                          <div key={row.id} className="rounded-xl border border-white/10 px-3 py-2">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="font-semibold text-white">
                                Candidate #{row.normalized_candidate_id} · {row.recommendation_label}
                              </p>
                              <span className="text-[10px] text-slate-500">{row.final_rank_score ?? "—"}</span>
                            </div>
                            <p className="mt-1 text-[10px] text-slate-400">
                              Fit {row.portfolio_fit_score ?? "—"} · liquidity {row.liquidity_score ?? "—"} · grading{" "}
                              {row.grading_upside_score ?? "—"} · risk {row.risk_penalty_score ?? "—"}
                            </p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Lead evidence payload</p>
                    <div className="mt-3 space-y-2 text-xs text-slate-200">
                      {!opsMarketScoringDetail ? (
                        <p className="text-slate-500">No lead score selected for evidence drill-down.</p>
                      ) : (
                        opsMarketScoringDetail.evidence.map((row) => (
                          <div key={row.id} className="rounded-xl border border-white/10 px-3 py-2">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="font-semibold text-white">{row.evidence_type}</p>
                              <span className="text-[10px] text-slate-500">{formatDateTime(row.created_at)}</span>
                            </div>
                            <p className="mt-1 text-[10px] text-slate-400">{JSON.stringify(row.evidence_value_json).slice(0, 240)}</p>
                          </div>
                        ))
                      )}
                    </div>
                    <div className="mt-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Recent append-safe history</p>
                      <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-200">
                        {opsMarketScoringHistory.length === 0 ? (
                          <span className="text-slate-500">No matching history rows for the selected snapshot date.</span>
                        ) : (
                          opsMarketScoringHistory.slice(0, 12).map((row) => (
                            <span key={row.id} className="rounded-full border border-white/10 px-2 py-1 font-mono text-[10px] text-fuchsia-100">
                              #{row.normalized_candidate_id} {row.recommendation_label} {row.acquisition_score ?? "—"}
                            </span>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </details>

      <details
        id="market-signal-ops"
        className="mt-6 rounded-3xl border border-amber-400/35 bg-amber-950/12 p-5 shadow-xl shadow-black/20 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Market acquisition signal classification</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Deterministic interpretation layer over persisted acquisition scores. Use this view for dense signal tables,
                score traceability, evidence, and checksum verification without recalculating the scoring engine.
              </p>
            </div>
            <span className="rounded-full border border-amber-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-100/90">
              Ops / P39-04
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-amber-200/15 pt-4">
          {opsMarketSignalLoading ? (
            <p className="text-sm text-slate-400">Loading market signal snapshots…</p>
          ) : opsMarketSignalError ? (
            <StatusBanner tone="error">{opsMarketSignalError}</StatusBanner>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <StatCard label="Snapshots tracked" value={String(opsMarketSignalSummary?.pagination.total_count ?? 0)} />
                <StatCard label="Value dislocation" value={String(opsMarketSignalSummary?.items[0]?.value_dislocation_count ?? 0)} />
                <StatCard
                  label="Liquidity opportunity"
                  value={String(opsMarketSignalSummary?.items[0]?.liquidity_opportunity_count ?? 0)}
                />
                <StatCard label="Portfolio gap fill" value={String(opsMarketSignalSummary?.items[0]?.portfolio_gap_fill_count ?? 0)} />
                <StatCard label="High risk asset" value={String(opsMarketSignalSummary?.items[0]?.high_risk_asset_count ?? 0)} />
              </div>

              <div className="mt-6 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Inspect</th>
                      <th className="p-3 font-medium">Owner</th>
                      <th className="p-3 font-medium">Snapshot date</th>
                      <th className="p-3 font-medium">Signals</th>
                      <th className="p-3 font-medium">Strength mix</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsMarketSignalSummary?.items.length ? (
                      opsMarketSignalSummary.items.map((row) => {
                        const isSelected = opsMarketSignalSelectedId === row.id;
                        return (
                          <tr key={row.id}>
                            <td className="p-3 align-top">
                              <button
                                type="button"
                                className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                                  isSelected
                                    ? "border-amber-300/70 bg-amber-400/20 text-amber-50"
                                    : "border-white/15 text-slate-200 hover:border-amber-300/35"
                                }`}
                                onClick={() => setOpsMarketSignalSelectedId((cur) => (cur === row.id ? null : row.id))}
                              >
                                {isSelected ? "Hide" : "View"}
                              </button>
                            </td>
                            <td className="p-3 align-top font-mono text-[11px] text-slate-400">@{row.owner_user_id}</td>
                            <td className="p-3 align-top">{formatDate(row.snapshot_date)}</td>
                            <td className="p-3 align-top">{row.total_signals}</td>
                            <td className="p-3 align-top">
                              <div>E {row.elite_signal_count} / H {row.high_signal_count}</div>
                              <div className="mt-1 text-[11px] text-slate-500">M {row.medium_signal_count} / L {row.low_signal_count}</div>
                            </td>
                            <td className="p-3 align-top font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.checksum)}</td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={6}>
                          No market-signal snapshots recorded yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {opsMarketSignalDetailLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading signal drill-down…</p>
              ) : opsMarketSignalDetailError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{opsMarketSignalDetailError}</StatusBanner>
                </div>
              ) : opsMarketSignalSelectedId ? (
                <div className="mt-5 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Signal table</p>
                    <div className="mt-3 space-y-2 text-xs text-slate-200">
                      {opsMarketSignals.length === 0 ? (
                        <p className="text-slate-500">No signals loaded for the selected snapshot.</p>
                      ) : (
                        opsMarketSignals.slice(0, 12).map((row) => (
                          <div key={row.id} className="rounded-xl border border-white/10 px-3 py-2">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="font-semibold text-white">
                                Score #{row.scored_candidate_id} · {row.signal_type}
                              </p>
                              <span className="text-[10px] text-slate-500">
                                {row.signal_strength} · {row.signal_score ?? "—"}
                              </span>
                            </div>
                            <p className="mt-1 text-[10px] text-slate-400">
                              Confidence {row.confidence_level} · risk {row.risk_level} · checksum{" "}
                              {abbrevExportChecksum(row.checksum)}
                            </p>
                          </div>
                        ))
                      )}
                    </div>
                    <div className="mt-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Signal breakdown by type</p>
                      <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-200">
                        {Object.entries(
                          opsMarketSignals.reduce<Record<string, number>>((acc, row) => {
                            acc[row.signal_type] = (acc[row.signal_type] ?? 0) + 1;
                            return acc;
                          }, {}),
                        ).map(([key, count]) => (
                          <span key={key} className="rounded-full border border-white/10 px-2 py-1 font-mono text-[10px] text-amber-100">
                            {key}: {count}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Signal-to-score traceability</p>
                    <div className="mt-3 space-y-2 text-xs text-slate-200">
                      {!opsMarketSignalDetail ? (
                        <p className="text-slate-500">No lead signal selected for traceability.</p>
                      ) : (
                        <>
                          <div className="rounded-xl border border-white/10 px-3 py-2">
                            <p className="font-semibold text-white">{opsMarketSignalDetail.signal.signal_type}</p>
                            <p className="mt-1 text-[10px] text-slate-400">
                              Source score #{opsMarketSignalDetail.signal.scored_candidate_id} · strength{" "}
                              {opsMarketSignalDetail.signal.signal_strength} · signal score{" "}
                              {opsMarketSignalDetail.signal.signal_score ?? "—"}
                            </p>
                          </div>
                          {opsMarketSignalEvidence.map((row) => (
                            <div key={row.id} className="rounded-xl border border-white/10 px-3 py-2">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p className="font-semibold text-white">{row.evidence_type}</p>
                                <span className="text-[10px] text-slate-500">{formatDateTime(row.created_at)}</span>
                              </div>
                              <p className="mt-1 text-[10px] text-slate-400">{JSON.stringify(row.evidence_value_json).slice(0, 240)}</p>
                            </div>
                          ))}
                        </>
                      )}
                    </div>
                    <div className="mt-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Checksum verification panel</p>
                      <div className="mt-2 space-y-2 text-[11px] text-slate-200">
                        <div className="rounded-xl border border-white/10 px-3 py-2">
                          Snapshot checksum:{" "}
                          <span className="font-mono text-[10px] text-amber-100">
                            {opsMarketSignalSummary?.items.find((row) => row.id === opsMarketSignalSelectedId)?.checksum ?? "—"}
                          </span>
                        </div>
                        <div className="rounded-xl border border-white/10 px-3 py-2">
                          Lead signal checksum:{" "}
                          <span className="font-mono text-[10px] text-amber-100">
                            {opsMarketSignalDetail?.signal.checksum ?? "—"}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {opsMarketSignalHistory.slice(0, 12).map((row) => (
                            <span key={row.id} className="rounded-full border border-white/10 px-2 py-1 font-mono text-[10px] text-amber-100">
                              #{row.scored_candidate_id} {row.signal_type}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </details>

      <details
        id="market-opportunity-ops"
        className="mt-6 rounded-3xl border border-lime-400/35 bg-lime-950/12 p-5 shadow-xl shadow-black/20 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Market acquisition opportunity snapshots</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Read-only aggregation layer over deterministic signals — inspect classifications, liquidity and
                diversification estimates, weighted items, layered evidence, and checksum stability without touching
                scoring or signal tables.
              </p>
            </div>
            <span className="rounded-full border border-lime-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-lime-100/90">
              Ops / P39-05
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-lime-200/15 pt-4">
          {opsMarketOpportunityLoading ? (
            <p className="text-sm text-slate-400">Loading opportunity snapshots…</p>
          ) : opsMarketOpportunityError ? (
            <StatusBanner tone="error">{opsMarketOpportunityError}</StatusBanner>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <StatCard label="Snapshots tracked" value={String(opsMarketOpportunitySummary?.pagination.total_count ?? 0)} />
                <StatCard
                  label="Classification"
                  value={String(opsMarketOpportunitySummary?.items[0]?.opportunity_classification ?? "—")}
                />
                <StatCard label="Liquidity opps." value={String(opsMarketOpportunitySummary?.items[0]?.liquidity_opportunity_count ?? 0)} />
                <StatCard label="Portfolio gap fill" value={String(opsMarketOpportunitySummary?.items[0]?.portfolio_gap_fill_count ?? 0)} />
                <StatCard label="Concentration reduc." value={String(opsMarketOpportunitySummary?.items[0]?.concentration_reduction_count ?? 0)} />
              </div>
              <div className="mt-6 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Inspect</th>
                      <th className="p-3 font-medium">Owner</th>
                      <th className="p-3 font-medium">Classification</th>
                      <th className="p-3 font-medium">Signals</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsMarketOpportunitySummary?.items.length ? (
                      opsMarketOpportunitySummary.items.map((row) => {
                        const isSel = opsMarketOpportunitySelectedId === row.id;
                        return (
                          <tr key={row.id}>
                            <td className="p-3 align-top">
                              <button
                                type="button"
                                className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                                  isSel
                                    ? "border-lime-300/70 bg-lime-400/20 text-lime-50"
                                    : "border-white/15 text-slate-200 hover:border-lime-300/35"
                                }`}
                                onClick={() => setOpsMarketOpportunitySelectedId((cur) => (cur === row.id ? null : row.id))}
                              >
                                {isSel ? "Hide" : "View"}
                              </button>
                            </td>
                            <td className="p-3 align-top font-mono text-[11px] text-slate-400">@{row.owner_user_id}</td>
                            <td className="p-3 align-top">{row.opportunity_classification}</td>
                            <td className="p-3 align-top">{row.total_signals}</td>
                            <td className="p-3 align-top font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.snapshot_checksum)}</td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={5}>
                          No opportunity snapshots recorded yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              {opsMarketOpportunityDetailLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading snapshot drill-down…</p>
              ) : opsMarketOpportunityDetailError ? (
                <StatusBanner tone="error">{opsMarketOpportunityDetailError}</StatusBanner>
              ) : opsMarketOpportunitySelectedId && opsMarketOpportunityDetail ? (
                <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                  <div className="grid gap-3 md:grid-cols-3">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Signal breakdown</p>
                      <div className="mt-2 text-xs text-slate-200 space-y-1">
                        <div>VALUE_DISLOCATION {opsMarketOpportunityDetail.snapshot.value_dislocation_count}</div>
                        <div>LIQUIDITY_OPPORTUNITY {opsMarketOpportunityDetail.snapshot.liquidity_opportunity_count}</div>
                        <div>PORTFOLIO_GAP_FILL {opsMarketOpportunityDetail.snapshot.portfolio_gap_fill_count}</div>
                        <div>CONCENTRATION_REDUCTION {opsMarketOpportunityDetail.snapshot.concentration_reduction_count}</div>
                      </div>
                    </div>
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Portfolio impact est.</p>
                      <div className="mt-2 text-xs text-slate-200 space-y-1">
                        <div>Gap coverage index {opsMarketOpportunityDetail.snapshot.estimated_portfolio_gap_coverage}</div>
                        <div>Liquidity gain {opsMarketOpportunityDetail.snapshot.estimated_liquidity_gain}</div>
                        <div>Diversification {opsMarketOpportunityDetail.snapshot.estimated_diversification_gain}</div>
                        <div>Risk adjustment {opsMarketOpportunityDetail.snapshot.estimated_risk_adjustment}</div>
                      </div>
                    </div>
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Checksum verification</p>
                      <div className="mt-2 rounded-xl border border-white/10 px-3 py-2 font-mono text-[10px] text-lime-100">
                        {opsMarketOpportunityDetail.snapshot.snapshot_checksum}
                      </div>
                    </div>
                  </div>
                  <div className="mt-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Weighted opportunity items</p>
                    <div className="mt-2 max-h-52 overflow-auto text-xs text-slate-200 space-y-1">
                      {opsMarketOpportunityItems.slice(0, 24).map((it) => (
                        <div key={it.id}>
                          Cand #{it.candidate_id} · {it.signal_type} · strength {it.signal_strength} · weight {it.contribution_weight}
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Evidence panel</p>
                      <div className="mt-2 space-y-2 text-[11px] text-slate-300">
                        {opsMarketOpportunityEvidence.map((ev) => (
                          <div key={ev.id} className="rounded-lg border border-white/10 px-2 py-1">
                            <span className="font-semibold text-lime-200">{ev.evidence_type}</span>
                            <span className="ml-2 text-slate-500">{JSON.stringify(ev.evidence_value_json).slice(0, 220)}…</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Append-safe history rows</p>
                      <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-200">
                        {opsMarketOpportunityHistory.map((h) => (
                          <span key={h.id} className="rounded-full border border-white/10 px-2 py-1 font-mono text-[10px]">
                            #{h.id} Δcand {h.total_candidates}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </details>

      <details
        id="market-portfolio-coupling-ops"
        className="mt-6 rounded-3xl border border-sky-400/35 bg-sky-950/12 p-5 shadow-xl shadow-black/20 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Portfolio-market coupling</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Deterministic relational edges bridging opportunity aggregates (P39-05) and portfolio registry reads
                (P38). All surfaces remain read-only; upstream signals, scoring, and normalization artifacts are never
                updated from this lane.
              </p>
            </div>
            <span className="rounded-full border border-sky-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-sky-100/90">
              Ops / P39-06
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-sky-200/15 pt-4">
          {opsPortfolioCouplingLoading ? (
            <p className="text-sm text-slate-400">Loading coupling snapshots…</p>
          ) : opsPortfolioCouplingError ? (
            <StatusBanner tone="error">{opsPortfolioCouplingError}</StatusBanner>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <StatCard label="Snapshots tracked" value={String(opsPortfolioCouplingSummary?.pagination.total_count ?? 0)} />
                <StatCard
                  label="Alignment score"
                  value={String(opsPortfolioCouplingSummary?.items[0]?.portfolio_market_alignment_score ?? "—")}
                />
                <StatCard
                  label="High-fit items"
                  value={String(opsPortfolioCouplingSummary?.items[0]?.high_fit_market_items ?? "—")}
                />
                <StatCard label="Liquidity coupling" value={String(opsPortfolioCouplingSummary?.items[0]?.liquidity_gap_alignment_score ?? "—")} />
                <StatCard
                  label="Normalization coverage"
                  value={String(opsPortfolioCouplingSummary?.items[0]?.normalization_coverage_ratio ?? "—")}
                />
              </div>
              <div className="mt-6 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Inspect</th>
                      <th className="p-3 font-medium">Owner</th>
                      <th className="p-3 font-medium">Opportunity snap</th>
                      <th className="p-3 font-medium">Alignment</th>
                      <th className="p-3 font-medium">Checksum</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsPortfolioCouplingSummary?.items.length ? (
                      opsPortfolioCouplingSummary.items.map((row) => {
                        const isSel = opsPortfolioCouplingSelectedId === row.id;
                        return (
                          <tr key={row.id}>
                            <td className="p-3 align-top">
                              <button
                                type="button"
                                className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                                  isSel
                                    ? "border-sky-300/70 bg-sky-400/20 text-sky-50"
                                    : "border-white/15 text-slate-200 hover:border-sky-300/35"
                                }`}
                                onClick={() =>
                                  setOpsPortfolioCouplingSelectedId((cur) => (cur === row.id ? null : row.id))
                                }
                              >
                                {isSel ? "Hide" : "View"}
                              </button>
                            </td>
                            <td className="p-3 align-top font-mono text-[11px] text-slate-400">@{row.owner_user_id}</td>
                            <td className="p-3 align-top font-mono text-[11px]">#{row.market_acquisition_opportunity_snapshot_id}</td>
                            <td className="p-3 align-top">{row.portfolio_market_alignment_score ?? "—"}</td>
                            <td className="p-3 align-top font-mono text-[10px] text-slate-400">
                              {abbrevExportChecksum(row.snapshot_checksum)}
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={5}>
                          No coupling snapshots recorded yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              {opsPortfolioCouplingDetailLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading coupling drill-down…</p>
              ) : opsPortfolioCouplingDetailError ? (
                <StatusBanner tone="error">{opsPortfolioCouplingDetailError}</StatusBanner>
              ) : opsPortfolioCouplingDetail ? (
                <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/40 p-4 space-y-4">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Alignment breakdown</p>
                    <div className="mt-2 grid gap-2 text-[11px] text-slate-200 sm:grid-cols-3">
                      <div className="rounded-xl border border-white/10 px-3 py-2">
                        Liquidity alignment
                        <p className="mt-1 text-sm font-semibold text-white">
                          {opsPortfolioCouplingDetail.snapshot.liquidity_gap_alignment_score ?? "—"}
                        </p>
                      </div>
                      <div className="rounded-xl border border-white/10 px-3 py-2">
                        Diversification gap alignment
                        <p className="mt-1 text-sm font-semibold text-white">
                          {opsPortfolioCouplingDetail.snapshot.diversification_gap_alignment_score ?? "—"}
                        </p>
                      </div>
                      <div className="rounded-xl border border-white/10 px-3 py-2">
                        Concentration offset
                        <p className="mt-1 text-sm font-semibold text-white">
                          {opsPortfolioCouplingDetail.snapshot.concentration_offset_score ?? "—"}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="overflow-auto rounded-2xl border border-white/10">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Candidate</th>
                          <th className="p-3 font-medium">Portfolio item</th>
                          <th className="p-3 font-medium">Type</th>
                          <th className="p-3 font-medium">Strength</th>
                          <th className="p-3 font-medium">Score</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10 text-slate-200">
                        {opsPortfolioCouplingEdges.length ? (
                          opsPortfolioCouplingEdges.map((e) => (
                            <tr key={e.id}>
                              <td className="p-3 font-mono text-[11px]">#{e.market_candidate_id}</td>
                              <td className="p-3 font-mono text-[11px]">{e.portfolio_item_id ?? "—"}</td>
                              <td className="p-3">{e.coupling_type}</td>
                              <td className="p-3">{e.coupling_strength}</td>
                              <td className="p-3">{e.coupling_score}</td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td className="p-3 text-slate-500" colSpan={5}>
                              No coupling edges recorded.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                  <div className="grid gap-3 md:grid-cols-3 text-[11px] text-slate-200">
                    <div className="rounded-xl border border-white/10 px-3 py-2">
                      <p className="font-semibold text-slate-400">Portfolio vs market mapping</p>
                      <p className="mt-1">
                        Opportunities {opsPortfolioCouplingDetail.snapshot.market_opportunity_count} · aligned{" "}
                        {opsPortfolioCouplingDetail.snapshot.aligned_opportunity_count} · misaligned{" "}
                        {opsPortfolioCouplingDetail.snapshot.misaligned_opportunity_count}
                      </p>
                    </div>
                    <div className="rounded-xl border border-white/10 px-3 py-2">
                      <p className="font-semibold text-slate-400">Conflict analysis</p>
                      <p className="mt-1">
                        CONCENTRATION_CONFLICT edges:{" "}
                        {opsPortfolioCouplingEdges.filter((e) => e.coupling_type === "CONCENTRATION_CONFLICT").length}
                      </p>
                    </div>
                    <div className="rounded-xl border border-white/10 px-3 py-2">
                      <p className="font-semibold text-slate-400">Coverage ratios</p>
                      <p className="mt-1">
                        Signal {opsPortfolioCouplingDetail.snapshot.signal_coverage_ratio ?? "—"} · scoring{" "}
                        {opsPortfolioCouplingDetail.snapshot.scoring_coverage_ratio ?? "—"} · normalization{" "}
                        {opsPortfolioCouplingDetail.snapshot.normalization_coverage_ratio ?? "—"}
                      </p>
                    </div>
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Checksum validation</p>
                    <div className="mt-2 space-y-2 text-[11px] text-slate-200">
                      <div className="rounded-xl border border-white/10 px-3 py-2 font-mono text-[10px] text-sky-100">
                        {opsPortfolioCouplingDetail.snapshot.snapshot_checksum}
                      </div>
                      <div className="rounded-xl border border-white/10 px-3 py-2 font-mono text-[10px] text-slate-400">
                        {opsPortfolioCouplingHistory.map((h) => abbrevExportChecksum(h.snapshot_checksum)).join(" · ") || "—"}
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </details>

      <details
        id="market-normalization-ops"
        className="mt-6 rounded-3xl border border-violet-400/35 bg-violet-950/12 p-5 shadow-xl shadow-black/20 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Market acquisition normalization engine</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Deterministic canonicalization pipeline (titles, aliases, deterministic condition bands). Read-only —
                ingestion rows are never mutated. Use this drill-down for run timelines, canonical keys, and recorded
                issues.
              </p>
            </div>
            <span className="rounded-full border border-violet-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-100/90">
              Ops / P39-02
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-violet-200/15 pt-4">
          {opsMarketNormLoading ? (
            <p className="text-sm text-slate-400">Loading normalization runs…</p>
          ) : opsMarketNormError ? (
            <StatusBanner tone="error">{opsMarketNormError}</StatusBanner>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <StatCard label="Runs tracked" value={String(opsMarketNormSummary?.pagination.total_count ?? 0)} />
                <StatCard label="Run status: completed" value={String(opsMarketNormSummary?.status_counts.COMPLETED ?? 0)} />
                <StatCard label="Run status: failed" value={String(opsMarketNormSummary?.status_counts.FAILED ?? 0)} />
                <StatCard label="Normalization row success %" value={`${opsMarketNormSummary?.health.canonical_full_success_rate_pct ?? "—"}${opsMarketNormSummary?.health.canonical_full_success_rate_pct != null ? "%" : ""}`} />
                <StatCard
                  label="Issue rows sampled"
                  value={String(Object.values(opsMarketNormSummary?.health.issue_type_counts ?? {}).reduce((a, b) => a + b, 0))}
                />
              </div>
              <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Issue breakdown</p>
                <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-200">
                  {Object.keys(opsMarketNormSummary?.health.issue_type_counts ?? {}).length === 0 ? (
                    <span className="text-slate-500">No issues recorded for the sampled scope.</span>
                  ) : (
                    Object.entries(opsMarketNormSummary?.health.issue_type_counts ?? {}).map(([k, v]) => (
                      <span key={k} className="rounded-full border border-white/10 px-2 py-1 font-mono text-[10px] text-slate-100">
                        {k}: {String(v)}
                      </span>
                    ))
                  )}
                </div>
                <div className="mt-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Failure signals</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-200">
                    {Object.entries(opsMarketNormSummary?.health.normalization_flag_counts ?? {}).map(([k, v]) => (
                      <span key={k} className="rounded-full border border-white/10 px-2 py-1 font-mono text-[10px] text-violet-100">
                        {k}: {String(v)}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-6 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Inspect</th>
                      <th className="p-3 font-medium">Batch</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">Totals</th>
                      <th className="p-3 font-medium">Checksum</th>
                      <th className="p-3 font-medium">Timeline</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsMarketNormSummary?.items.length ? (
                      opsMarketNormSummary.items.map((row) => {
                        const isSel = opsMarketNormSelectedId === row.id;
                        return (
                          <tr key={row.id}>
                            <td className="p-3 align-top">
                              <button
                                type="button"
                                className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                                  isSel
                                    ? "border-violet-300/70 bg-violet-400/20 text-violet-50"
                                    : "border-white/15 text-slate-200 hover:border-violet-300/35"
                                }`}
                                onClick={() => setOpsMarketNormSelectedId((cur) => (cur === row.id ? null : row.id))}
                              >
                                {isSel ? "Hide" : "View"}
                              </button>
                            </td>
                            <td className="p-3 align-top font-mono text-[11px]">#{row.ingestion_batch_id}</td>
                            <td className="p-3 align-top">{row.run_status}</td>
                            <td className="p-3 align-top">
                              <div>
                                ✓ {row.successful_records} • ~ {row.partial_records} • ✗ {row.failed_records}
                              </div>
                              <div className="mt-1 text-[10px] text-slate-500">success / partial / failed</div>
                            </td>
                            <td className="p-3 align-top font-mono text-[10px] text-slate-400">{abbrevExportChecksum(row.run_checksum)}</td>
                            <td className="p-3 align-top text-[11px] text-slate-400">
                              started {row.started_at ? formatDateTime(row.started_at) : "—"}
                              <div className="mt-1">completed {row.completed_at ? formatDateTime(row.completed_at) : "—"}</div>
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={6}>
                          No normalization runs recorded for the selected ops scope yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {opsMarketNormDetailLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading selected normalization drill-down…</p>
              ) : opsMarketNormDetailError ? (
                <div className="mt-4">
                  <StatusBanner tone="warning">{opsMarketNormDetailError}</StatusBanner>
                </div>
              ) : opsMarketNormDetail ? (
                <div className="mt-5 grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Run timeline</p>
                    <div className="mt-3 max-h-[320px] space-y-2 overflow-auto text-xs text-slate-200">
                      {opsMarketNormDetail.events.map((evt) => (
                        <div key={evt.id} className="rounded-xl border border-white/10 px-3 py-2">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="font-semibold text-white">{evt.event_type}</p>
                            <span className="text-[10px] text-slate-500">{formatDateTime(evt.created_at)}</span>
                          </div>
                          <p className="mt-1 text-[10px] text-slate-400">{JSON.stringify(evt.metadata_json).slice(0, 220)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Canonical key coverage</p>
                    <div className="mt-3 max-h-[220px] overflow-auto">
                      <table className="w-full border-collapse text-left text-[11px]">
                        <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                          <tr>
                            <th className="py-2 pr-2 font-medium">Candidate</th>
                            <th className="py-2 pr-2 font-medium">Status</th>
                            <th className="py-2 pr-2 font-medium">Canonical key</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/10 text-slate-200">
                          {(opsMarketNormCandidates ?? []).slice(0, 25).map((c) => (
                            <tr key={c.id}>
                              <td className="py-2 pr-2 font-mono text-[10px]">#{c.ingestion_candidate_id}</td>
                              <td className="py-2 pr-2">{c.normalization_status}</td>
                              <td className="py-2 pr-2 font-mono text-[10px] text-emerald-200/90">
                                {abbrevExportChecksum(c.canonical_key)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <p className="mt-5 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Issues for selected batch scope
                    </p>
                    <div className="mt-3 max-h-[240px] overflow-auto">
                      <table className="w-full border-collapse text-left text-[11px]">
                        <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                          <tr>
                            <th className="py-2 pr-2 font-medium">Candidate</th>
                            <th className="py-2 pr-2 font-medium">Type</th>
                            <th className="py-2 pr-2 font-medium">Severity</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/10 text-slate-200">
                          {(opsMarketNormIssues ?? []).slice(0, 40).map((iss) => (
                            <tr key={iss.id}>
                              <td className="py-2 pr-2 font-mono text-[10px]">#{iss.ingestion_candidate_id}</td>
                              <td className="py-2 pr-2">{iss.issue_type}</td>
                              <td className="py-2 pr-2">{iss.severity}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </details>

      <details
        id="ops-market-sales-anchor"
        className="mt-6 rounded-3xl border border-emerald-400/35 bg-emerald-950/12 p-5 shadow-xl shadow-black/20 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Market sales foundation</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Deterministic market-sale rows with preserved raw payload history, ordered image evidence, and surfaced
                normalization issues. The panel is read-only except for the explicit ops upsert flow used for future imports.
              </p>
            </div>
            <span className="rounded-full border border-emerald-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-100/90">
              Ops / sales foundation
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-emerald-200/15 pt-4">
          {opsMarketSalesLoading ? (
            <p className="text-sm text-slate-400">Loading market sales…</p>
          ) : opsMarketSalesError ? (
            <StatusBanner tone="error">{opsMarketSalesError}</StatusBanner>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5">
                <StatCard label="Records" value={String(opsMarketSalesSummary.total)} />
                <StatCard label="Normalized" value={String(opsMarketSalesSummary.normalized)} />
                <StatCard label="Partially normalized" value={String(opsMarketSalesSummary.partial)} />
                <StatCard label="Normalization failed" value={String(opsMarketSalesSummary.failed)} />
                <StatCard label="Duplicate warnings" value={String(opsMarketSalesSummary.duplicateWarnings)} />
              </div>

              <div className="mt-6 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Inspect</th>
                      <th className="p-3 font-medium">Source</th>
                      <th className="p-3 font-medium">Title / issue</th>
                      <th className="p-3 font-medium">Sale</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">Issues</th>
                      <th className="p-3 font-medium">Updated</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsMarketSales.length === 0 ? (
                      <tr>
                        <td className="p-4 text-slate-500" colSpan={7}>
                          No market-sale records have been imported yet.
                        </td>
                      </tr>
                    ) : (
                      opsMarketSales.map((row) => {
                        const isSelected = opsMarketSaleSelectedId === row.id;
                        return (
                          <tr key={row.id}>
                            <td className="p-3 align-top">
                              <button
                                type="button"
                                className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                                  isSelected
                                    ? "border-emerald-300/70 bg-emerald-400/20 text-emerald-50"
                                    : "border-white/15 text-slate-200 hover:border-emerald-300/35"
                                }`}
                                onClick={() => setOpsMarketSaleSelectedId((cur) => (cur === row.id ? null : row.id))}
                              >
                                {isSelected ? "Hide" : "View"}
                              </button>
                            </td>
                            <td className="p-3 align-top">
                              <div className="text-slate-100">{row.source_name}</div>
                              <div className="mt-1 text-[11px] text-slate-500">{row.source_type}</div>
                            </td>
                            <td className="p-3 align-top">
                              <div className="font-medium text-slate-100">{row.normalized_title ?? row.raw_title}</div>
                              <div className="mt-1 text-[11px] text-slate-400">
                                Issue {row.normalized_issue ?? row.raw_issue}
                                {row.source_listing_id ? ` · ${row.source_listing_id}` : ""}
                              </div>
                            </td>
                            <td className="p-3 align-top">
                              <div>
                                {row.total_price ?? row.sale_price ?? "—"} {row.currency_code}
                              </div>
                              <div className="mt-1 text-[11px] text-slate-500">
                                {row.sale_date ?? "No sale date"}
                              </div>
                            </td>
                            <td className="p-3 align-top">
                              <span
                                className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${marketSaleStatusTone(
                                  row.normalization_status,
                                )}`}
                              >
                                {row.normalization_status.replace(/_/g, " ")}
                              </span>
                            </td>
                            <td className="p-3 align-top">
                              <span className="rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-100">
                                {row.normalization_issue_count}
                              </span>
                            </td>
                            <td className="p-3 text-slate-400 align-top">{formatDateTime(row.updated_at)}</td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              {opsMarketSaleDetailLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading selected market-sale detail…</p>
              ) : opsMarketSaleDetailError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{opsMarketSaleDetailError}</StatusBanner>
                </div>
              ) : opsMarketSaleDetail ? (
                <div className="mt-5 grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Selected record
                    </p>
                    <div className="mt-3 grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2 text-xs text-slate-300">
                        <div><span className="text-slate-500">Source:</span> {opsMarketSaleDetail.source_name}</div>
                        <div><span className="text-slate-500">Source type:</span> {opsMarketSaleDetail.source_type}</div>
                        <div><span className="text-slate-500">Listing id:</span> {opsMarketSaleDetail.source_listing_id ?? "—"}</div>
                        <div><span className="text-slate-500">Snapshot id:</span> {opsMarketSaleDetail.source_snapshot_id ?? "—"}</div>
                        <div><span className="text-slate-500">Sale date:</span> {opsMarketSaleDetail.sale_date ?? "—"}</div>
                        <div><span className="text-slate-500">Total / shipping:</span> {opsMarketSaleDetail.total_price ?? "—"} / {opsMarketSaleDetail.shipping_price ?? "—"} {opsMarketSaleDetail.currency_code}</div>
                        <div><span className="text-slate-500">Graded:</span> {opsMarketSaleDetail.is_graded ? "Yes" : "No"}</div>
                        <div><span className="text-slate-500">Grading company:</span> {opsMarketSaleDetail.grading_company ?? "—"}</div>
                        <div><span className="text-slate-500">Signed:</span> {opsMarketSaleDetail.is_signed ? "Yes" : "No"}</div>
                        <div><span className="text-slate-500">Seller / buyer:</span> {opsMarketSaleDetail.seller_name ?? "—"} / {opsMarketSaleDetail.buyer_name ?? "—"}</div>
                      </div>
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Raw payload history
                        </p>
                        <pre className="mt-2 max-h-56 overflow-auto rounded-xl border border-white/10 bg-slate-950/70 p-3 text-[11px] leading-5 text-slate-300">
                          {JSON.stringify(opsMarketSaleDetail.source_metadata_json, null, 2)}
                        </pre>
                      </div>
                    </div>
                    <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                            Normalization editor
                          </p>
                          <p className="mt-1 text-xs text-slate-400">
                            Manual updates only. Raw fields and issue history stay intact.
                          </p>
                        </div>
                        <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketSaleReviewPriorityTone(
                          opsMarketSaleDetail.review_status === "ignored"
                            ? "info"
                            : opsMarketSaleDetail.review_status === "duplicate_flagged"
                              ? "high"
                              : "low",
                        )}`}>
                          {marketSaleReviewStatusLabel(opsMarketSaleDetail.review_status)}
                        </span>
                      </div>
                      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                        <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                          Normalized title
                          <input
                            value={opsMarketSaleNormalizationDraft.normalized_title ?? ""}
                            onChange={(event) =>
                              setOpsMarketSaleNormalizationDraft((draft) => ({
                                ...draft,
                                normalized_title: event.target.value,
                              }))
                            }
                            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
                          />
                        </label>
                        <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                          Normalized issue
                          <input
                            value={opsMarketSaleNormalizationDraft.normalized_issue ?? ""}
                            onChange={(event) =>
                              setOpsMarketSaleNormalizationDraft((draft) => ({
                                ...draft,
                                normalized_issue: event.target.value,
                              }))
                            }
                            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
                          />
                        </label>
                        <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                          Normalized publisher
                          <input
                            value={opsMarketSaleNormalizationDraft.normalized_publisher ?? ""}
                            onChange={(event) =>
                              setOpsMarketSaleNormalizationDraft((draft) => ({
                                ...draft,
                                normalized_publisher: event.target.value,
                              }))
                            }
                            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
                          />
                        </label>
                        <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                          Normalized variant
                          <input
                            value={opsMarketSaleNormalizationDraft.normalized_variant ?? ""}
                            onChange={(event) =>
                              setOpsMarketSaleNormalizationDraft((draft) => ({
                                ...draft,
                                normalized_variant: event.target.value,
                              }))
                            }
                            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
                          />
                        </label>
                        <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                          Normalized grade
                          <input
                            value={opsMarketSaleNormalizationDraft.normalized_grade ?? ""}
                            onChange={(event) =>
                              setOpsMarketSaleNormalizationDraft((draft) => ({
                                ...draft,
                                normalized_grade: event.target.value,
                              }))
                            }
                            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
                          />
                        </label>
                        <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                          Normalized cert
                          <input
                            value={opsMarketSaleNormalizationDraft.normalized_cert_number ?? ""}
                            onChange={(event) =>
                              setOpsMarketSaleNormalizationDraft((draft) => ({
                                ...draft,
                                normalized_cert_number: event.target.value,
                              }))
                            }
                            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
                          />
                        </label>
                        <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                          Normalization status
                          <select
                            value={opsMarketSaleNormalizationDraft.normalization_status ?? ""}
                            onChange={(event) =>
                              setOpsMarketSaleNormalizationDraft((draft) => ({
                                ...draft,
                                normalization_status: (event.target.value as MarketSaleNormalizationUpdatePayload["normalization_status"]) || undefined,
                              }))
                            }
                            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
                          >
                            <option value="">Keep current</option>
                            <option value="raw">Raw</option>
                            <option value="partially_normalized">Partially normalized</option>
                            <option value="normalized">Normalized</option>
                            <option value="normalization_failed">Normalization failed</option>
                          </select>
                        </label>
                        <label className="flex flex-col gap-1 text-[11px] text-slate-400 md:col-span-2 xl:col-span-3">
                          Review note
                          <textarea
                            value={opsMarketSaleNormalizationDraft.review_note ?? ""}
                            onChange={(event) =>
                              setOpsMarketSaleNormalizationDraft((draft) => ({
                                ...draft,
                                review_note: event.target.value,
                              }))
                            }
                            rows={3}
                            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
                          />
                        </label>
                        <label className="flex items-center gap-2 text-xs text-slate-300 md:col-span-2 xl:col-span-3">
                          <input
                            type="checkbox"
                            checked={opsMarketSaleNormalizationDraft.mark_reviewed ?? false}
                            onChange={(event) =>
                              setOpsMarketSaleNormalizationDraft((draft) => ({
                                ...draft,
                                mark_reviewed: event.target.checked,
                              }))
                            }
                          />
                          Mark reviewed
                        </label>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="rounded-full border border-emerald-300/40 bg-emerald-500/15 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-100"
                          onClick={() => void handleMarketSaleNormalizationSave()}
                        >
                          Save normalization
                        </button>
                        <button
                          type="button"
                          className="rounded-full border border-slate-300/30 bg-slate-500/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-100"
                          onClick={() => void handleMarketSaleIgnore()}
                        >
                          Ignore record
                        </button>
                        <button
                          type="button"
                          className="rounded-full border border-amber-300/40 bg-amber-500/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-100"
                          onClick={() => void handleMarketSaleFlagDuplicate()}
                        >
                          Flag duplicate
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Normalization issues
                      </p>
                      {opsMarketSaleDetail.normalization_issues.length === 0 ? (
                        <p className="mt-3 text-sm text-slate-500">No issues recorded for this record.</p>
                      ) : (
                        <div className="mt-3 space-y-2">
                          {opsMarketSaleDetail.normalization_issues.map((issue) => (
                            <div
                              key={issue.id}
                              className={`rounded-xl border px-3 py-2 text-xs ${marketSaleIssueTone(issue.severity)}`}
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-semibold uppercase tracking-[0.12em]">{issue.issue_type.replace(/_/g, " ")}</span>
                                <span className="text-[10px] uppercase tracking-[0.16em]">{issue.severity}</span>
                              </div>
                              <pre className="mt-2 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-slate-100/90">
                                {JSON.stringify(issue.details_json, null, 2)}
                              </pre>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Review history
                      </p>
                      {opsMarketSaleDetail.review_actions.length === 0 ? (
                        <p className="mt-3 text-sm text-slate-500">No review actions recorded yet.</p>
                      ) : (
                        <div className="mt-3 space-y-2">
                          {opsMarketSaleDetail.review_actions.map((action) => (
                            <div key={action.id} className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-slate-300">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-semibold uppercase tracking-[0.12em] text-slate-100">
                                  {action.action_type.replace(/_/g, " ")}
                                </span>
                                <span className="text-[10px] text-slate-500">{formatDateTime(action.created_at)}</span>
                              </div>
                              {action.details_json && Object.keys(action.details_json).length > 0 ? (
                                <pre className="mt-2 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-slate-400">
                                  {JSON.stringify(action.details_json, null, 2)}
                                </pre>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Image evidence
                      </p>
                      {opsMarketSaleDetail.images.length === 0 ? (
                        <p className="mt-3 text-sm text-slate-500">No images recorded for this record.</p>
                      ) : (
                        <div className="mt-3 space-y-2">
                          {opsMarketSaleDetail.images.map((image) => (
                            <div key={image.id} className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-slate-300">
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-semibold text-slate-100">Image #{image.display_order}</span>
                                <span className="text-[11px] text-slate-500">{image.image_sha256 ?? "no hash"}</span>
                              </div>
                              <div className="mt-1 break-all text-slate-400">{image.image_url ?? "No URL recorded"}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </details>

      <details
        id="market-sale-review-queue"
        className="mt-6 rounded-3xl border border-cyan-400/35 bg-cyan-950/10 p-5 shadow-xl shadow-black/20 [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Market sale review queue</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Deterministic triage only. No FMV, no fuzzy normalization, no automatic canonical linking, and no raw
                field mutation. Use the table to select a record and the editor above to make explicit human updates.
              </p>
            </div>
            <span className="rounded-full border border-cyan-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/90">
              Ops / review-only
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-cyan-200/15 pt-4">
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex min-w-[12rem] flex-col gap-1 text-[11px] text-slate-400">
              <span className="font-semibold uppercase tracking-[0.1em]">Classification</span>
              <select
                value={opsMarketSaleReviewClassificationFilter}
                onChange={(event) => setOpsMarketSaleReviewClassificationFilter(event.target.value as "" | MarketSaleReviewClassification)}
                className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
              >
                <option value="">Any</option>
                {OPS_MARKET_SALE_REVIEW_CLASSIFICATIONS.map((classification) => (
                  <option key={classification} value={classification}>
                    {marketSaleReviewClassificationLabel(classification)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
              <span className="font-semibold uppercase tracking-[0.1em]">Priority</span>
              <select
                value={opsMarketSaleReviewPriorityFilter}
                onChange={(event) => setOpsMarketSaleReviewPriorityFilter(event.target.value as "" | MarketSaleReviewPriority)}
                className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
              >
                <option value="">Any</option>
                {OPS_MARKET_SALE_REVIEW_PRIORITIES.map((priority) => (
                  <option key={priority} value={priority}>
                    {priority}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
              <span className="font-semibold uppercase tracking-[0.1em]">Review status</span>
              <select
                value={opsMarketSaleReviewStatusFilter}
                onChange={(event) => setOpsMarketSaleReviewStatusFilter(event.target.value as "" | MarketSaleReviewStatus)}
                className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
              >
                <option value="">Any</option>
                <option value="pending">Pending</option>
                <option value="reviewed">Reviewed</option>
                <option value="ignored">Ignored</option>
                <option value="duplicate_flagged">Duplicate flagged</option>
              </select>
            </label>
            <label className="flex min-w-[11rem] flex-col gap-1 text-[11px] text-slate-400">
              <span className="font-semibold uppercase tracking-[0.1em]">Source</span>
              <input
                value={opsMarketSaleReviewSourceFilter}
                onChange={(event) => setOpsMarketSaleReviewSourceFilter(event.target.value)}
                className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-cyan-300/40"
                placeholder="Source name or type"
              />
            </label>
            <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
              <span className="font-semibold uppercase tracking-[0.1em]">Source type</span>
              <input
                value={opsMarketSaleReviewSourceTypeFilter}
                onChange={(event) => setOpsMarketSaleReviewSourceTypeFilter(event.target.value)}
                className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-cyan-300/40"
                placeholder="marketplace"
              />
            </label>
            <label className="flex min-w-[11rem] flex-col gap-1 text-[11px] text-slate-400">
              <span className="font-semibold uppercase tracking-[0.1em]">Issue type</span>
              <input
                value={opsMarketSaleReviewIssueTypeFilter}
                onChange={(event) => setOpsMarketSaleReviewIssueTypeFilter(event.target.value)}
                className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-cyan-300/40"
                placeholder="missing_issue_number"
              />
            </label>
          </div>

          {opsMarketSaleReviewQueueSummary ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              <StatCard label="Queue total" value={String(opsMarketSaleReviewQueueSummary.total)} />
              {OPS_MARKET_SALE_REVIEW_PRIORITIES.map((priority) => (
                <StatCard
                  key={priority}
                  label={`Priority ${priority}`}
                  value={String(opsMarketSaleReviewQueueSummary.by_priority[priority] ?? 0)}
                />
              ))}
            </div>
          ) : null}
          {opsMarketSaleReviewQueueSummary ? (
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {OPS_MARKET_SALE_REVIEW_CLASSIFICATIONS.map((classification) => (
                <StatCard
                  key={classification}
                  label={marketSaleReviewClassificationLabel(classification)}
                  value={String(opsMarketSaleReviewQueueSummary?.by_classification[classification] ?? 0)}
                />
              ))}
            </div>
          ) : null}

          {opsMarketSaleReviewQueueLoading ? (
            <p className="mt-4 text-sm text-slate-400">Loading market sale review queue…</p>
          ) : opsMarketSaleReviewQueueError ? (
            <div className="mt-4">
              <StatusBanner tone="error">{opsMarketSaleReviewQueueError}</StatusBanner>
            </div>
          ) : opsMarketSaleReviewQueue?.items.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No market-sale records matched the active review filters.</p>
          ) : (
            <div className="mt-5 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Inspect</th>
                    <th className="p-3 font-medium">Source</th>
                    <th className="p-3 font-medium">Title / issue</th>
                    <th className="p-3 font-medium">Classification</th>
                    <th className="p-3 font-medium">Priority</th>
                    <th className="p-3 font-medium">Review</th>
                    <th className="p-3 font-medium">Issues</th>
                    <th className="p-3 font-medium">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsMarketSaleReviewQueue?.items.map((row) => {
                    const isSelected = opsMarketSaleSelectedId === row.id;
                    return (
                      <tr key={row.id}>
                        <td className="p-3 align-top">
                          <button
                            type="button"
                            className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                              isSelected
                                ? "border-cyan-300/70 bg-cyan-400/20 text-cyan-50"
                                : "border-white/15 text-slate-200 hover:border-cyan-300/35"
                            }`}
                            onClick={() => setOpsMarketSaleSelectedId((cur) => (cur === row.id ? null : row.id))}
                          >
                            {isSelected ? "Hide" : "View"}
                          </button>
                        </td>
                        <td className="p-3 align-top">
                          <div className="text-slate-100">{row.source_name}</div>
                          <div className="mt-1 text-[11px] text-slate-500">{row.source_type}</div>
                        </td>
                        <td className="p-3 align-top">
                          <div className="font-medium text-slate-100">{row.normalized_title ?? row.raw_title}</div>
                          <div className="mt-1 text-[11px] text-slate-400">
                            Issue {row.normalized_issue ?? row.raw_issue}
                            {row.source_listing_id ? ` · ${row.source_listing_id}` : ""}
                          </div>
                        </td>
                        <td className="p-3 align-top">
                          <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketSaleReviewPriorityTone(row.queue_priority)}`}>
                            {marketSaleReviewClassificationLabel(row.queue_classification)}
                          </span>
                        </td>
                        <td className="p-3 align-top">
                          <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketSaleReviewPriorityTone(row.queue_priority)}`}>
                            {row.queue_priority}
                          </span>
                        </td>
                        <td className="p-3 align-top">
                          <span className="rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-100">
                            {marketSaleReviewStatusLabel(row.review_status)}
                          </span>
                        </td>
                        <td className="p-3 align-top">
                          <span className="rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-100">
                            {row.issue_types.length}
                          </span>
                        </td>
                        <td className="p-3 text-slate-400 align-top">{formatDateTime(row.updated_at)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </details>

      <section
        id="market-comp-eligibility"
        className="mt-6 rounded-3xl border border-emerald-400/25 bg-emerald-950/10 p-5 shadow-xl shadow-black/20"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Market comp eligibility</h2>
            <p className="mt-1 max-w-3xl text-xs text-slate-400">
              Deterministic comp-readiness only. No FMV, no averaging, no fuzzy matching, and no automatic canonical
              linking. Use this panel to inspect whether a market sale is eligible, needs review, or is ineligible for
              future comp analysis.
            </p>
          </div>
          <span className="rounded-full border border-emerald-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-100/90">
            Ops / read-only eligibility
          </span>
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-3">
          <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Status</span>
            <select
              value={opsMarketCompEligibilityStatusFilter}
              onChange={(event) => setOpsMarketCompEligibilityStatusFilter(event.target.value as "" | MarketCompEligibilityStatus)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
            >
              <option value="">Any</option>
              {OPS_MARKET_COMP_ELIGIBILITY_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {marketCompEligibilityStatusLabel(status)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex min-w-[12rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Classification</span>
            <select
              value={opsMarketCompEligibilityClassificationFilter}
              onChange={(event) =>
                setOpsMarketCompEligibilityClassificationFilter(
                  event.target.value as "" | MarketCompEligibilityClassification,
                )
              }
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
            >
              <option value="">Any</option>
              {OPS_MARKET_COMP_ELIGIBILITY_CLASSIFICATIONS.map((classification) => (
                <option key={classification} value={classification}>
                  {marketCompEligibilityClassificationLabel(classification)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex min-w-[11rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Source</span>
            <input
              value={opsMarketCompEligibilitySourceFilter}
              onChange={(event) => setOpsMarketCompEligibilitySourceFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
              placeholder="Source name or type"
            />
          </label>
          <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Graded</span>
            <select
              value={opsMarketCompEligibilityIsGradedFilter}
              onChange={(event) => setOpsMarketCompEligibilityIsGradedFilter(event.target.value as "" | "true" | "false")}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
            >
              <option value="">Any</option>
              <option value="true">Graded</option>
              <option value="false">Raw</option>
            </select>
          </label>
          <label className="flex min-w-[11rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Grading company</span>
            <input
              value={opsMarketCompEligibilityGradingCompanyFilter}
              onChange={(event) => setOpsMarketCompEligibilityGradingCompanyFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
              placeholder="CGC"
            />
          </label>
          <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Currency</span>
            <input
              value={opsMarketCompEligibilityCurrencyFilter}
              onChange={(event) => setOpsMarketCompEligibilityCurrencyFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
              placeholder="USD"
            />
          </label>
          <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Sale date from</span>
            <input
              type="date"
              value={opsMarketCompEligibilitySaleDateFromFilter}
              onChange={(event) => setOpsMarketCompEligibilitySaleDateFromFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
            />
          </label>
          <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Sale date to</span>
            <input
              type="date"
              value={opsMarketCompEligibilitySaleDateToFilter}
              onChange={(event) => setOpsMarketCompEligibilitySaleDateToFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
            />
          </label>
        </div>

        {opsMarketCompEligibility ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total" value={String(opsMarketCompEligibility.total)} />
            <StatCard label="Eligible" value={String(opsMarketCompEligibility.by_eligibility_status.eligible ?? 0)} />
            <StatCard label="Needs review" value={String(opsMarketCompEligibility.by_eligibility_status.needs_review ?? 0)} />
            <StatCard label="Ineligible" value={String(opsMarketCompEligibility.by_eligibility_status.ineligible ?? 0)} />
          </div>
        ) : null}

        {opsMarketCompEligibility ? (
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Eligible raw"
              value={String(opsMarketCompEligibility.by_eligibility_classification.eligible_raw_comp ?? 0)}
            />
            <StatCard
              label="Eligible graded"
              value={String(opsMarketCompEligibility.by_eligibility_classification.eligible_graded_comp ?? 0)}
            />
            <StatCard
              label="Needs review before comp"
              value={String(opsMarketCompEligibility.by_eligibility_classification.needs_review_before_comp ?? 0)}
            />
            <StatCard
              label="Duplicate listings"
              value={String(opsMarketCompEligibility.by_eligibility_classification.ineligible_duplicate_listing ?? 0)}
            />
          </div>
        ) : null}

        {opsMarketCompEligibilityLoading ? (
          <p className="mt-4 text-sm text-slate-400">Loading market comp eligibility…</p>
        ) : opsMarketCompEligibilityError ? (
          <div className="mt-4">
            <StatusBanner tone="error">{opsMarketCompEligibilityError}</StatusBanner>
          </div>
        ) : opsMarketCompEligibility?.items.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">No market-sale records matched the active eligibility filters.</p>
        ) : opsMarketCompEligibility ? (
          <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(340px,0.9fr)]">
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Inspect</th>
                    <th className="p-3 font-medium">Source</th>
                    <th className="p-3 font-medium">Sale</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">Class</th>
                    <th className="p-3 font-medium">Canonical match</th>
                    <th className="p-3 font-medium">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsMarketCompEligibility.items.map((row) => {
                    const isSelected = opsMarketCompEligibilitySelectedId === row.id;
                    return (
                      <tr key={row.id}>
                        <td className="p-3 align-top">
                          <button
                            type="button"
                            className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                              isSelected
                                ? "border-emerald-300/70 bg-emerald-400/20 text-emerald-50"
                                : "border-white/15 text-slate-200 hover:border-emerald-300/35"
                            }`}
                            onClick={() => setOpsMarketCompEligibilitySelectedId((cur) => (cur === row.id ? null : row.id))}
                          >
                            {isSelected ? "Hide" : "View"}
                          </button>
                        </td>
                        <td className="p-3 align-top">
                          <div className="text-slate-100">{row.source_name}</div>
                          <div className="mt-1 text-[11px] text-slate-500">{row.source_type}</div>
                        </td>
                        <td className="p-3 align-top">
                          <div className="font-medium text-slate-100">{row.normalized_title ?? row.raw_title}</div>
                          <div className="mt-1 text-[11px] text-slate-400">
                            Issue {row.normalized_issue ?? row.raw_issue}
                            {row.source_listing_id ? ` · ${row.source_listing_id}` : ""}
                          </div>
                          <div className="mt-1 text-[11px] text-slate-500">
                            {row.total_price ?? row.sale_price ?? "—"} {row.currency_code}
                          </div>
                        </td>
                        <td className="p-3 align-top">
                          <span
                            className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketCompEligibilityStatusTone(
                              row.eligibility_status,
                            )}`}
                          >
                            {marketCompEligibilityStatusLabel(row.eligibility_status)}
                          </span>
                        </td>
                        <td className="p-3 align-top">
                          <span className="rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-100">
                            {marketCompEligibilityClassificationLabel(row.eligibility_classification)}
                          </span>
                        </td>
                        <td className="p-3 align-top">
                          <div className="text-slate-100">{marketSaleMatchSuggestionLabel(row.canonical_match_state)}</div>
                          <div className="mt-1 text-[11px] text-slate-500">
                            {row.canonical_match_confidence_bucket ?? "—"}
                            {row.canonical_match_review_state ? ` · ${row.canonical_match_review_state}` : ""}
                          </div>
                        </td>
                        <td className="p-3 text-slate-400 align-top">{formatDateTime(row.updated_at)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              {opsMarketCompEligibilityDetailLoading ? (
                <p className="text-sm text-slate-400">Loading comp eligibility evidence…</p>
              ) : opsMarketCompEligibilityDetailError ? (
                <StatusBanner tone="error">{opsMarketCompEligibilityDetailError}</StatusBanner>
              ) : opsMarketCompEligibilityDetail ? (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-100">
                        Sale #{opsMarketCompEligibilityDetail.id}
                      </p>
                      <p className="mt-1 text-sm text-slate-100">
                        {opsMarketCompEligibilityDetail.normalized_title ?? opsMarketCompEligibilityDetail.raw_title}
                      </p>
                      <p className="mt-1 text-xs text-slate-400">
                        {opsMarketCompEligibilityDetail.eligibility_classification.replace(/_/g, " ")}
                      </p>
                    </div>
                    <span
                      className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketCompEligibilityStatusTone(
                        opsMarketCompEligibilityDetail.eligibility_status,
                      )}`}
                    >
                      {marketCompEligibilityStatusLabel(opsMarketCompEligibilityDetail.eligibility_status)}
                    </span>
                  </div>
                  <div className="mt-4 grid gap-2 text-xs text-slate-300">
                    <div>
                      Source: {opsMarketCompEligibilityDetail.source_name} ({opsMarketCompEligibilityDetail.source_type})
                    </div>
                    <div>
                      Sale: {opsMarketCompEligibilityDetail.total_price ?? opsMarketCompEligibilityDetail.sale_price ?? "—"}{" "}
                      {opsMarketCompEligibilityDetail.currency_code}
                    </div>
                    <div>
                      Graded: {opsMarketCompEligibilityDetail.is_graded ? "Yes" : "No"}
                      {opsMarketCompEligibilityDetail.grading_company
                        ? ` · ${opsMarketCompEligibilityDetail.grading_company}`
                        : ""}
                    </div>
                    <div>Normalization: {opsMarketCompEligibilityDetail.normalization_status}</div>
                    <div>
                      Canonical match: {opsMarketCompEligibilityDetail.canonical_match_state}
                      {opsMarketCompEligibilityDetail.canonical_match_review_state
                        ? ` · ${opsMarketCompEligibilityDetail.canonical_match_review_state}`
                        : ""}
                    </div>
                    {opsMarketCompEligibilityDetail.eligibility_reasons.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {opsMarketCompEligibilityDetail.eligibility_reasons.map((reason) => (
                          <span
                            key={reason}
                            className="rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-200"
                          >
                            {reason.replace(/_/g, " ")}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Evidence</p>
                    <pre className="mt-2 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-slate-300">
                      {JSON.stringify(opsMarketCompEligibilityDetail.eligibility_evidence_json, null, 2)}
                    </pre>
                  </div>

                  <div className="mt-4 grid gap-3">
                    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                        Normalization issues
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {opsMarketCompEligibilityDetail.normalization_issues.length} issue
                        {opsMarketCompEligibilityDetail.normalization_issues.length === 1 ? "" : "s"}
                      </p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                        Canonical match suggestions
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {opsMarketCompEligibilityDetail.match_suggestions.length} suggestion
                        {opsMarketCompEligibilityDetail.match_suggestions.length === 1 ? "" : "s"}
                      </p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Review actions</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {opsMarketCompEligibilityDetail.review_actions.length} action
                        {opsMarketCompEligibilityDetail.review_actions.length === 1 ? "" : "s"}
                      </p>
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-500">Select a sale to inspect its comp eligibility evidence.</p>
              )}
            </div>
          </div>
        ) : null}
      </section>

      <section
        id="market-comps"
        className="mt-6 rounded-3xl border border-emerald-400/25 bg-emerald-950/10 p-5 shadow-xl shadow-black/20"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Comparable sales explorer</h2>
            <p className="mt-1 max-w-3xl text-xs text-slate-400">
              Deterministic grouped comps only. This explorer surfaces the exact sales records behind comparable-sale
              analysis, including excluded reasons and quality signals, without predictive pricing or metadata mutation.
            </p>
          </div>
          <span className="rounded-full border border-emerald-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-100/90">
            Read-only comp analysis
          </span>
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-3">
          <label className="flex min-w-[11rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Source</span>
            <input
              value={opsMarketCompsSourceFilter}
              onChange={(event) => setOpsMarketCompsSourceFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
              placeholder="Source name or type"
            />
          </label>
          <label className="flex min-w-[14rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Identity key</span>
            <input
              value={opsMarketCompsMetadataIdentityKeyFilter}
              onChange={(event) => setOpsMarketCompsMetadataIdentityKeyFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
              placeholder="Image|Invincible|1|Cover A"
            />
          </label>
          <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Graded</span>
            <select
              value={opsMarketCompsIsGradedFilter}
              onChange={(event) => setOpsMarketCompsIsGradedFilter(event.target.value as "" | "true" | "false")}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
            >
              <option value="">Any</option>
              <option value="true">Graded</option>
              <option value="false">Raw</option>
            </select>
          </label>
          <label className="flex min-w-[11rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Grading company</span>
            <input
              value={opsMarketCompsGradingCompanyFilter}
              onChange={(event) => setOpsMarketCompsGradingCompanyFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
              placeholder="CGC"
            />
          </label>
          <label className="flex min-w-[11rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Normalized grade</span>
            <input
              value={opsMarketCompsNormalizedGradeFilter}
              onChange={(event) => setOpsMarketCompsNormalizedGradeFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
              placeholder="9.8"
            />
          </label>
          <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Currency</span>
            <input
              value={opsMarketCompsCurrencyFilter}
              onChange={(event) => setOpsMarketCompsCurrencyFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
              placeholder="USD"
            />
          </label>
          <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Sale date from</span>
            <input
              type="date"
              value={opsMarketCompsSaleDateFromFilter}
              onChange={(event) => setOpsMarketCompsSaleDateFromFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
            />
          </label>
          <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Sale date to</span>
            <input
              type="date"
              value={opsMarketCompsSaleDateToFilter}
              onChange={(event) => setOpsMarketCompsSaleDateToFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-emerald-300/40"
            />
          </label>
          <label className="flex min-w-[11rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Excluded comps</span>
            <select
              value={opsMarketCompsIncludeExcluded ? "true" : "false"}
              onChange={(event) => setOpsMarketCompsIncludeExcluded(event.target.value === "true")}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
            >
              <option value="true">Show excluded</option>
              <option value="false">Show included only</option>
            </select>
          </label>
        </div>

        {opsMarketComps ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Groups" value={String(opsMarketComps.total_groups)} />
            <StatCard label="Records" value={String(opsMarketComps.total_comps)} />
            <StatCard label="Included" value={String(opsMarketComps.by_classification.included_comp ?? 0)} />
            <StatCard label="Excluded" value={String(opsMarketComps.total_comps - (opsMarketComps.by_classification.included_comp ?? 0))} />
          </div>
        ) : null}

        {opsMarketCompsLoading ? (
          <p className="mt-4 text-sm text-slate-400">Loading comparable sales…</p>
        ) : opsMarketCompsError ? (
          <div className="mt-4">
            <StatusBanner tone="error">{opsMarketCompsError}</StatusBanner>
          </div>
        ) : opsMarketComps?.items.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">No comparable sales matched the active filters.</p>
        ) : opsMarketComps ? (
          <div className="mt-5 space-y-4">
            {opsMarketComps.items.map((group) => (
              <details key={group.group_key} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4" open>
                <summary className="cursor-pointer list-none">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.16em] text-emerald-200/70">Comp group</p>
                      <h3 className="mt-1 text-base font-semibold text-white">{group.group_label}</h3>
                      <p className="mt-1 text-xs text-slate-400">
                        {group.included_count} included · {group.excluded_count} excluded · {group.quality_signals.sale_recency_bucket}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${compQualityTone(group.quality_signals.sale_recency_bucket)}`}>
                        {group.quality_signals.sale_recency_bucket}
                      </span>
                      <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${compQualityTone(group.quality_signals.price_spread_bucket)}`}>
                        {group.quality_signals.price_spread_bucket}
                      </span>
                      <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${compQualityTone(group.quality_signals.volatility_signal)}`}>
                        {group.quality_signals.volatility_signal}
                      </span>
                    </div>
                  </div>
                </summary>
                <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.9fr)]">
                  <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-900/50">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Sale</th>
                          <th className="p-3 font-medium">Source</th>
                          <th className="p-3 font-medium">Scope</th>
                          <th className="p-3 font-medium">Price</th>
                          <th className="p-3 font-medium">Reason</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10 text-slate-200">
                        {[...group.included_comps, ...(opsMarketCompsIncludeExcluded ? group.excluded_comps : [])].map((comp) => (
                          <tr key={comp.id}>
                            <td className="p-3 align-top">
                              <div className="font-medium text-slate-100">{comp.normalized_title ?? comp.raw_title}</div>
                              <div className="mt-1 text-[11px] text-slate-400">
                                Issue {comp.normalized_issue ?? comp.raw_issue}
                                {comp.sale_date ? ` · ${formatDate(comp.sale_date)}` : ""}
                              </div>
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketComparableTone(comp.comp_classification)}`}>
                                  {marketComparableClassificationLabel(comp.comp_classification)}
                                </span>
                                <span className="inline-flex rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-200">
                                  {comp.eligibility_classification.replace(/_/g, " ")}
                                </span>
                              </div>
                            </td>
                            <td className="p-3 align-top">
                              <div className="text-slate-100">{comp.source_name}</div>
                              <div className="mt-1 text-[11px] text-slate-500">{comp.source_type}</div>
                            </td>
                            <td className="p-3 align-top text-slate-300">
                              <div>{comp.comp_scope.replace(/_/g, " ")}</div>
                              <div className="mt-1 text-[11px] text-slate-500">
                                {comp.grading_company ?? "raw"}{comp.normalized_grade ? ` · ${comp.normalized_grade}` : ""}
                              </div>
                            </td>
                            <td className="p-3 align-top text-slate-200">
                              {formatCurrency(comp.total_price ?? comp.sale_price ?? null)}
                            </td>
                            <td className="p-3 align-top text-slate-400">
                              <div className="text-xs text-slate-300">{comp.comp_reason}</div>
                              <div className="mt-1 text-[11px] text-slate-500">
                                {String((comp.comp_evidence_json as { canonical_match_state?: string }).canonical_match_state ?? "—")}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Quality signals</p>
                    <div className="mt-3 grid gap-2 text-xs text-slate-300">
                      <div>Recency: {group.quality_signals.sale_recency_days ?? "—"} days</div>
                      <div>Source diversity: {group.quality_signals.source_diversity_count}</div>
                      <div>Price spread: {group.quality_signals.price_spread}</div>
                      <div>Grade consistency: {group.quality_signals.grade_consistency_bucket}</div>
                      <div>Duplicate risk: {group.quality_signals.duplicate_risk_bucket}</div>
                      <div>Volatility: {group.quality_signals.volatility_signal}</div>
                      <div>Stale warning: {group.quality_signals.stale_data_warning ? "Yes" : "No"}</div>
                    </div>
                    {!opsMarketCompsIncludeExcluded ? (
                      <p className="mt-3 text-[11px] text-slate-500">
                        Excluded comps are hidden by the active filter.
                      </p>
                    ) : null}
                  </div>
                </div>
              </details>
            ))}
          </div>
        ) : null}
      </section>

      <section
        id="market-fmv"
        className="mt-6 rounded-3xl border border-cyan-400/25 bg-cyan-950/10 p-5 shadow-xl shadow-black/20"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Market FMV snapshots</h2>
            <p className="mt-1 max-w-3xl text-xs text-slate-400">
              Deterministic FMV snapshots only. Generate currency-specific market valuations from eligible comps without
              updating inventory, metadata, or manual FMV history.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="rounded-full border border-cyan-300/35 px-3 py-1.5 text-[11px] font-semibold text-cyan-100 transition hover:border-cyan-200/60 hover:bg-cyan-500/10 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={() => void handleGenerateMarketFmv()}
              disabled={opsMarketFmvGenerateBusy}
            >
              {opsMarketFmvGenerateBusy ? "Generating…" : "Generate FMV snapshots"}
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-3">
          <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Scope</span>
            <select
              value={opsMarketFmvScopeFilter}
              onChange={(event) => setOpsMarketFmvScopeFilter(event.target.value as "" | MarketFmvSnapshotScope)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
            >
              <option value="">Any</option>
              {OPS_MARKET_FMV_SCOPES.map((scope) => (
                <option key={scope} value={scope}>
                  {marketFmvScopeLabel(scope)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Confidence</span>
            <select
              value={opsMarketFmvConfidenceFilter}
              onChange={(event) => setOpsMarketFmvConfidenceFilter(event.target.value as "" | MarketFmvConfidenceBucket)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
            >
              <option value="">Any</option>
              <option value="very_high">Very high</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="very_low">Very low</option>
            </select>
          </label>
          <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Liquidity</span>
            <select
              value={opsMarketFmvLiquidityFilter}
              onChange={(event) => setOpsMarketFmvLiquidityFilter(event.target.value as "" | MarketFmvLiquidityBucket)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
            >
              <option value="">Any</option>
              <option value="very_high">Very high</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="very_low">Very low</option>
            </select>
          </label>
          <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Stale</span>
            <select
              value={opsMarketFmvStaleFilter}
              onChange={(event) => setOpsMarketFmvStaleFilter(event.target.value as "" | "true" | "false")}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
            >
              <option value="">Any</option>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </label>
          <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Currency</span>
            <input
              value={opsMarketFmvCurrencyFilter}
              onChange={(event) => setOpsMarketFmvCurrencyFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-cyan-300/40"
              placeholder="USD"
            />
          </label>
          <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Grading company</span>
            <input
              value={opsMarketFmvGradingCompanyFilter}
              onChange={(event) => setOpsMarketFmvGradingCompanyFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-cyan-300/40"
              placeholder="CGC"
            />
          </label>
          <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Grade</span>
            <input
              value={opsMarketFmvNormalizedGradeFilter}
              onChange={(event) => setOpsMarketFmvNormalizedGradeFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-cyan-300/40"
              placeholder="9.8"
            />
          </label>
        </div>

        {opsMarketFmvGenerateSummary ? (
          <div className="mt-4">
            <StatusBanner tone="success">
              Generated {opsMarketFmvGenerateSummary.snapshot_count} deterministic FMV snapshot
              {opsMarketFmvGenerateSummary.snapshot_count === 1 ? "" : "s"}.
            </StatusBanner>
          </div>
        ) : null}
        {opsMarketFmvError ? (
          <div className="mt-4">
            <StatusBanner tone="error">{opsMarketFmvError}</StatusBanner>
          </div>
        ) : null}

        {opsMarketFmv ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total snapshots" value={String(opsMarketFmv.total)} />
            <StatCard
              label="High confidence"
              value={String((opsMarketFmv.by_confidence_bucket.very_high ?? 0) + (opsMarketFmv.by_confidence_bucket.high ?? 0))}
            />
            <StatCard
              label="Low liquidity"
              value={String((opsMarketFmv.by_liquidity_bucket.low ?? 0) + (opsMarketFmv.by_liquidity_bucket.very_low ?? 0))}
            />
            <StatCard label="Stale snapshots" value={String(opsMarketFmv.stale_count)} />
          </div>
        ) : null}

        {opsMarketFmvLoading ? (
          <p className="mt-4 text-sm text-slate-400">Loading market FMV snapshots…</p>
        ) : opsMarketFmv?.items.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">No FMV snapshots matched the active filters.</p>
        ) : opsMarketFmv ? (
          <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(340px,0.9fr)]">
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Inspect</th>
                    <th className="p-3 font-medium">Scope / method</th>
                    <th className="p-3 font-medium">Identity</th>
                    <th className="p-3 font-medium">FMV</th>
                    <th className="p-3 font-medium">Comps</th>
                    <th className="p-3 font-medium">Confidence</th>
                    <th className="p-3 font-medium">Liquidity</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsMarketFmv.items.map((row) => {
                    const isSelected = opsMarketFmvSelectedId === row.id;
                    return (
                      <tr key={row.id}>
                        <td className="p-3 align-top">
                          <button
                            type="button"
                            className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                              isSelected
                                ? "border-cyan-300/70 bg-cyan-400/20 text-cyan-50"
                                : "border-white/15 text-slate-200 hover:border-cyan-300/35"
                            }`}
                            onClick={() => setOpsMarketFmvSelectedId((cur) => (cur === row.id ? null : row.id))}
                          >
                            {isSelected ? "Hide" : "View"}
                          </button>
                        </td>
                        <td className="p-3 align-top">
                          <div className="font-medium text-slate-100">{marketFmvScopeLabel(row.snapshot_scope)}</div>
                          <div className="mt-1 text-[11px] text-slate-400">{row.valuation_method.replace(/_/g, " ")}</div>
                          <div className="mt-1 text-[11px] text-slate-500">{row.snapshot_date}</div>
                        </td>
                        <td className="p-3 align-top">
                          <div className="text-slate-100">{row.metadata_identity_key ?? `Issue #${row.canonical_issue_id ?? "—"}`}</div>
                          <div className="mt-1 text-[11px] text-slate-500">
                            {row.currency_code}
                            {row.grading_company ? ` · ${row.grading_company}` : ""}
                            {row.normalized_grade ? ` · ${row.normalized_grade}` : ""}
                          </div>
                        </td>
                        <td className="p-3 align-top font-medium text-white">{formatCurrency(row.estimated_fmv)}</td>
                        <td className="p-3 align-top text-slate-300">
                          {row.comp_count}
                          {row.stale_data ? <div className="mt-1 text-[11px] text-amber-200">stale</div> : null}
                        </td>
                        <td className="p-3 align-top">
                          <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketFmvBucketTone(row.confidence_bucket)}`}>
                            {row.confidence_bucket.replace(/_/g, " ")}
                          </span>
                        </td>
                        <td className="p-3 align-top">
                          <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketFmvBucketTone(row.liquidity_bucket)}`}>
                            {row.liquidity_bucket.replace(/_/g, " ")}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              {opsMarketFmvDetailLoading ? (
                <p className="text-sm text-slate-400">Loading market FMV comp references…</p>
              ) : opsMarketFmvDetailError ? (
                <StatusBanner tone="error">{opsMarketFmvDetailError}</StatusBanner>
              ) : opsMarketFmvDetail ? (
                <>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-cyan-100">
                      Snapshot #{opsMarketFmvDetail.id}
                    </p>
                    <p className="mt-1 text-sm text-slate-100">
                      {marketFmvScopeLabel(opsMarketFmvDetail.snapshot_scope)} · {opsMarketFmvDetail.valuation_method.replace(/_/g, " ")}
                    </p>
                    <p className="mt-1 text-xs text-slate-400">
                      {opsMarketFmvDetail.metadata_identity_key ?? `Issue #${opsMarketFmvDetail.canonical_issue_id ?? "—"}`}
                    </p>
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">FMV</p>
                      <p className="mt-2 text-sm text-slate-100">{formatCurrency(opsMarketFmvDetail.estimated_fmv)}</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Comp count</p>
                      <p className="mt-2 text-sm text-slate-100">{opsMarketFmvDetail.comp_count}</p>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-2">
                    <div className="flex flex-wrap gap-2">
                      <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketFmvBucketTone(opsMarketFmvDetail.confidence_bucket)}`}>
                        confidence {opsMarketFmvDetail.confidence_bucket.replace(/_/g, " ")}
                      </span>
                      <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketFmvBucketTone(opsMarketFmvDetail.liquidity_bucket)}`}>
                        liquidity {opsMarketFmvDetail.liquidity_bucket.replace(/_/g, " ")}
                      </span>
                      <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketFmvBucketTone(opsMarketFmvDetail.volatility_bucket)}`}>
                        volatility {opsMarketFmvDetail.volatility_bucket.replace(/_/g, " ")}
                      </span>
                    </div>
                  </div>

                  <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Comp references</p>
                    <div className="mt-3 space-y-2">
                      {opsMarketFmvDetail.comp_references.map((ref) => (
                        <div key={ref.id} className="rounded-xl border border-white/10 bg-slate-950/60 p-3 text-xs text-slate-300">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className="font-medium text-slate-100">
                                {ref.market_sale_record?.normalized_title ?? ref.market_sale_record?.raw_title ?? `Sale #${ref.market_sale_record_id}`}
                              </div>
                              <div className="mt-1 text-[11px] text-slate-400">
                                {ref.market_sale_record?.sale_date ?? "Unknown date"} ·{" "}
                                {ref.market_sale_record?.total_price ?? ref.market_sale_record?.sale_price ?? "—"}{" "}
                                {ref.market_sale_record?.currency_code ?? ""}
                              </div>
                            </div>
                            <span className="text-[11px] text-slate-500">
                              {ref.excluded_reason ? ref.excluded_reason.replace(/_/g, " ") : `w=${ref.weighting_factor.toFixed(2)}`}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-500">Select a snapshot to inspect the comp reference drawer.</p>
              )}
            </div>
          </div>
        ) : null}
      </section>

    <section
      id="market-trends"
      className="mt-6 rounded-3xl border border-violet-400/25 bg-violet-950/10 p-5 shadow-xl shadow-black/20"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Market trend snapshots</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Deterministic trend movement only. Generate windowed signals from FMV history, comp cadence, and volatility
            spread without forecasting, recommendation labels, or inventory mutation.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="rounded-full border border-violet-300/35 px-3 py-1.5 text-[11px] font-semibold text-violet-100 transition hover:border-violet-200/60 hover:bg-violet-500/10 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => void handleGenerateMarketTrends()}
            disabled={opsMarketTrendGenerateBusy}
          >
            {opsMarketTrendGenerateBusy ? "Generating…" : "Generate trend snapshots"}
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
          <span className="font-semibold uppercase tracking-[0.1em]">Scope</span>
          <select
            value={opsMarketTrendScopeFilter}
            onChange={(event) => setOpsMarketTrendScopeFilter(event.target.value as "" | MarketTrendSnapshotScope)}
            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
          >
            <option value="">Any</option>
            {OPS_MARKET_FMV_SCOPES.map((scope) => (
              <option key={scope} value={scope}>
                {marketFmvScopeLabel(scope)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
          <span className="font-semibold uppercase tracking-[0.1em]">Trend</span>
          <select
            value={opsMarketTrendDirectionFilter}
            onChange={(event) => setOpsMarketTrendDirectionFilter(event.target.value as "" | MarketTrendDirection)}
            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
          >
            <option value="">Any</option>
            <option value="rising">Rising</option>
            <option value="stable">Stable</option>
            <option value="falling">Falling</option>
            <option value="volatile">Volatile</option>
          </select>
        </label>
        <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
          <span className="font-semibold uppercase tracking-[0.1em]">Strength</span>
          <select
            value={opsMarketTrendStrengthFilter}
            onChange={(event) => setOpsMarketTrendStrengthFilter(event.target.value as "" | MarketTrendStrength)}
            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
          >
            <option value="">Any</option>
            <option value="very_high">Very high</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
            <option value="very_low">Very low</option>
          </select>
        </label>
        <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
          <span className="font-semibold uppercase tracking-[0.1em]">Liquidity</span>
          <select
            value={opsMarketTrendLiquidityFilter}
            onChange={(event) =>
              setOpsMarketTrendLiquidityFilter(event.target.value as "" | MarketTrendLiquidityDirection)
            }
            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
          >
            <option value="">Any</option>
            <option value="improving">Improving</option>
            <option value="stable">Stable</option>
            <option value="weakening">Weakening</option>
          </select>
        </label>
        <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
          <span className="font-semibold uppercase tracking-[0.1em]">Stale</span>
          <select
            value={opsMarketTrendStaleFilter}
            onChange={(event) => setOpsMarketTrendStaleFilter(event.target.value as "" | "true" | "false")}
            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
          >
            <option value="">Any</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>
        <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
          <span className="font-semibold uppercase tracking-[0.1em]">Window</span>
          <select
            value={opsMarketTrendWindowFilter}
            onChange={(event) => setOpsMarketTrendWindowFilter(event.target.value as "" | MarketTrendWindow)}
            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
          >
            <option value="">Any</option>
            <option value="seven_day">Seven day</option>
            <option value="thirty_day">Thirty day</option>
            <option value="ninety_day">Ninety day</option>
            <option value="one_year">One year</option>
          </select>
        </label>
        <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
          <span className="font-semibold uppercase tracking-[0.1em]">Currency</span>
          <input
            value={opsMarketTrendCurrencyFilter}
            onChange={(event) => setOpsMarketTrendCurrencyFilter(event.target.value)}
            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-violet-300/40"
            placeholder="USD"
          />
        </label>
        <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
          <span className="font-semibold uppercase tracking-[0.1em]">Grading company</span>
          <input
            value={opsMarketTrendGradingCompanyFilter}
            onChange={(event) => setOpsMarketTrendGradingCompanyFilter(event.target.value)}
            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-violet-300/40"
            placeholder="CGC"
          />
        </label>
        <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
          <span className="font-semibold uppercase tracking-[0.1em]">Grade</span>
          <input
            value={opsMarketTrendGradeFilter}
            onChange={(event) => setOpsMarketTrendGradeFilter(event.target.value)}
            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-violet-300/40"
            placeholder="9.8"
          />
        </label>
      </div>

      {opsMarketTrendGenerateSummary ? (
        <div className="mt-4">
          <StatusBanner tone="success">
            Generated {opsMarketTrendGenerateSummary.snapshot_count} deterministic trend snapshot
            {opsMarketTrendGenerateSummary.snapshot_count === 1 ? "" : "s"}.
          </StatusBanner>
        </div>
      ) : null}
      {opsMarketTrendsError ? (
        <div className="mt-4">
          <StatusBanner tone="error">{opsMarketTrendsError}</StatusBanner>
        </div>
      ) : null}

      {opsMarketTrends ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Total snapshots" value={String(opsMarketTrends.total)} />
          <StatCard label="Rising" value={String(opsMarketTrends.by_trend_direction.rising ?? 0)} />
          <StatCard label="Volatile" value={String(opsMarketTrends.by_trend_direction.volatile ?? 0)} />
          <StatCard label="Stale trends" value={String(opsMarketTrends.stale_count)} />
        </div>
      ) : null}

      {opsMarketTrendsLoading ? (
        <p className="mt-4 text-sm text-slate-400">Loading market trend snapshots…</p>
      ) : opsMarketTrends?.items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">No trend snapshots matched the active filters.</p>
      ) : opsMarketTrends ? (
        <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(340px,0.9fr)]">
          <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
            <table className="w-full border-collapse text-left text-xs">
              <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th className="p-3 font-medium">Inspect</th>
                  <th className="p-3 font-medium">Window / scope</th>
                  <th className="p-3 font-medium">Identity</th>
                  <th className="p-3 font-medium">Direction</th>
                  <th className="p-3 font-medium">Movement</th>
                  <th className="p-3 font-medium">Liquidity</th>
                  <th className="p-3 font-medium">Volatility</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10 text-slate-200">
                {opsMarketTrends.items.map((row) => {
                  const isSelected = opsMarketTrendSelectedId === row.id;
                  return (
                    <tr key={row.id}>
                      <td className="p-3 align-top">
                        <button
                          type="button"
                          className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                            isSelected
                              ? "border-violet-300/70 bg-violet-400/20 text-violet-50"
                              : "border-white/15 text-slate-200 hover:border-violet-300/35"
                          }`}
                          onClick={() => setOpsMarketTrendSelectedId((cur) => (cur === row.id ? null : row.id))}
                        >
                          {isSelected ? "Hide" : "View"}
                        </button>
                      </td>
                      <td className="p-3 align-top">
                        <div className="font-medium text-slate-100">{marketTrendLabel(row.trend_window)}</div>
                        <div className="mt-1 text-[11px] text-slate-400">{marketFmvScopeLabel(row.snapshot_scope)}</div>
                        <div className="mt-1 text-[11px] text-slate-500">
                          {row.currency_code}
                          {row.grading_company ? ` · ${row.grading_company}` : ""}
                          {row.normalized_grade ? ` · ${row.normalized_grade}` : ""}
                        </div>
                      </td>
                      <td className="p-3 align-top">
                        <div className="text-slate-100">{row.metadata_identity_key ?? `Issue #${row.canonical_issue_id ?? "—"}`}</div>
                      </td>
                      <td className="p-3 align-top">
                        <span
                          className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketTrendTone(
                            row.trend_direction,
                          )}`}
                        >
                          {marketTrendLabel(row.trend_direction)}
                        </span>
                        <div className="mt-1 text-[11px] text-slate-400">{marketTrendLabel(row.trend_strength)}</div>
                      </td>
                      <td className="p-3 align-top text-slate-200">{Number(row.percent_change).toFixed(2)}%</td>
                      <td className="p-3 align-top">
                        <span
                          className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketTrendTone(
                            row.liquidity_direction,
                          )}`}
                        >
                          {marketTrendLabel(row.liquidity_direction)}
                        </span>
                        {row.stale_data ? <div className="mt-1 text-[11px] text-amber-200">stale</div> : null}
                      </td>
                      <td className="p-3 align-top text-slate-200">{row.volatility_score.toFixed(2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            {opsMarketTrendDetailLoading ? (
              <p className="text-sm text-slate-400">Loading market trend evidence…</p>
            ) : opsMarketTrendDetailError ? (
              <StatusBanner tone="error">{opsMarketTrendDetailError}</StatusBanner>
            ) : opsMarketTrendDetail ? (
              <>
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-violet-100">
                    Snapshot #{opsMarketTrendDetail.id}
                  </p>
                  <p className="mt-1 text-sm text-slate-100">
                    {marketTrendLabel(opsMarketTrendDetail.trend_window)} · {marketTrendLabel(opsMarketTrendDetail.trend_direction)} ·{" "}
                    {marketTrendLabel(opsMarketTrendDetail.trend_strength)}
                  </p>
                  <p className="mt-2 text-sm text-slate-400">
                    {opsMarketTrendDetail.percent_change}% movement across {opsMarketTrendDetail.comp_count} comps.
                  </p>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-3">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Liquidity</p>
                    <p className="mt-2 text-sm text-slate-100">{marketTrendLabel(opsMarketTrendDetail.liquidity_direction)}</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-3">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Volatility score</p>
                    <p className="mt-2 text-sm text-slate-100">{opsMarketTrendDetail.volatility_score.toFixed(2)}</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-3">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Stale</p>
                    <p className="mt-2 text-sm text-slate-100">{opsMarketTrendDetail.stale_data ? "Yes" : "No"}</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-3">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Percent change</p>
                    <p className="mt-2 text-sm text-slate-100">{opsMarketTrendDetail.percent_change}%</p>
                  </div>
                </div>
                <div className="mt-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Evidence drawer</p>
                  <div className="mt-3 space-y-2">
                    {opsMarketTrendDetail.evidence_items.slice(0, 6).map((evidence) => (
                      <div key={evidence.id} className="rounded-2xl border border-white/10 bg-slate-900/60 p-3 text-sm text-slate-300">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="font-medium text-slate-100">{marketTrendLabel(evidence.evidence_type)}</div>
                            <div className="mt-1 text-[11px] text-slate-400">
                              {evidence.market_fmv_snapshot?.snapshot_date ?? evidence.market_sale_record?.sale_date ?? "Unknown"}
                            </div>
                          </div>
                          <span className="text-[11px] text-slate-500">
                            {evidence.market_sale_record?.total_price ??
                              evidence.market_sale_record?.sale_price ??
                              evidence.market_fmv_snapshot?.estimated_fmv ??
                              "—"}
                          </span>
                        </div>
                        <div className="mt-2 text-[11px] text-slate-400">
                          {Object.entries(evidence.evidence_json)
                            .slice(0, 3)
                            .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : String(value)}`)
                            .join(" · ")}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-500">Select a trend row to inspect its evidence drawer.</p>
            )}
          </div>
        </div>
      ) : null}
    </section>

      <section
        id="market-match-suggestions"
        className="mt-6 rounded-3xl border border-violet-400/25 bg-violet-950/10 p-5 shadow-xl shadow-black/20"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Market match suggestions</h2>
            <p className="mt-1 max-w-3xl text-xs text-slate-400">
              Deterministic, review-only suggestions between normalized market sale records and canonical issue or
              inventory context. No automatic canonical linking, no FMV, and no inventory mutation.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="rounded-full border border-violet-300/35 px-3 py-1.5 text-[11px] font-semibold text-violet-100 transition hover:border-violet-200/60 hover:bg-violet-500/10 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={() =>
                opsMarketSaleSelectedId == null ? undefined : void handleGenerateMarketMatchSuggestions(opsMarketSaleSelectedId)
              }
              disabled={opsMarketSaleSelectedId == null || opsMarketMatchSuggestionBusyId != null}
            >
              {opsMarketSaleSelectedId == null
                ? "Select a sale to generate"
                : `Generate for sale #${opsMarketSaleSelectedId}`}
            </button>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <label className="flex min-w-[12rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Source</span>
            <input
              value={opsMarketMatchSuggestionSourceFilter}
              onChange={(event) => setOpsMarketMatchSuggestionSourceFilter(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-violet-300/40"
              placeholder="Source name or type"
            />
          </label>
          <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Confidence</span>
            <select
              value={opsMarketMatchSuggestionConfidenceFilter}
              onChange={(event) =>
                setOpsMarketMatchSuggestionConfidenceFilter(
                  event.target.value as "" | MarketSaleMatchSuggestionConfidenceBucket,
                )
              }
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
            >
              <option value="">All</option>
              <option value="very_high">Very high</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="very_low">Very low</option>
            </select>
          </label>
          <label className="flex min-w-[10rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Review state</span>
            <select
              value={opsMarketMatchSuggestionReviewFilter}
              onChange={(event) =>
                setOpsMarketMatchSuggestionReviewFilter(event.target.value as "" | MarketSaleMatchSuggestionReviewState)
              }
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
            >
              <option value="">All</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="ignored">Ignored</option>
            </select>
          </label>
          <label className="flex min-w-[13rem] flex-col gap-1 text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-[0.1em]">Suggestion type</span>
            <select
              value={opsMarketMatchSuggestionTypeFilter}
              onChange={(event) =>
                setOpsMarketMatchSuggestionTypeFilter(event.target.value as "" | MarketSaleMatchSuggestionType)
              }
              className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
            >
              <option value="">All</option>
              {OPS_MARKET_MATCH_SUGGESTION_TYPES.map((type) => (
                <option key={type} value={type}>
                  {marketSaleMatchSuggestionLabel(type)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {opsMarketMatchSuggestionsError ? (
          <div className="mt-4">
            <StatusBanner tone="error">{opsMarketMatchSuggestionsError}</StatusBanner>
          </div>
        ) : null}
        {opsMarketMatchSuggestionsLoading ? (
          <p className="mt-4 text-sm text-slate-400">Loading market match suggestions…</p>
        ) : opsMarketMatchSuggestions?.suggestions.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">No market match suggestions for the active filters.</p>
        ) : opsMarketMatchSuggestions ? (
          <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]">
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3 font-medium">Inspect</th>
                    <th className="p-3 font-medium">Sale</th>
                    <th className="p-3 font-medium">Target</th>
                    <th className="p-3 font-medium">Type</th>
                    <th className="p-3 font-medium">Confidence</th>
                    <th className="p-3 font-medium">Review</th>
                    <th className="p-3 font-medium">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {opsMarketMatchSuggestions.suggestions.map((row) => {
                    const isSelected = opsMarketMatchSuggestionSelectedId === row.id;
                    return (
                      <tr key={row.id}>
                        <td className="p-3 align-top">
                          <button
                            type="button"
                            className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                              isSelected
                                ? "border-violet-300/70 bg-violet-400/20 text-violet-50"
                                : "border-white/15 text-slate-200 hover:border-violet-300/35"
                            }`}
                            onClick={() => setOpsMarketMatchSuggestionSelectedId((cur) => (cur === row.id ? null : row.id))}
                          >
                            {isSelected ? "Hide" : "View"}
                          </button>
                        </td>
                        <td className="p-3 align-top">
                          <div className="text-slate-100">{row.source_name}</div>
                          <div className="mt-1 text-[11px] text-slate-500">
                            {row.source_type}
                            {row.source_listing_id ? ` · ${row.source_listing_id}` : ""}
                          </div>
                        </td>
                        <td className="p-3 align-top">
                          <div className="font-medium text-slate-100">{row.normalized_title ?? row.raw_title}</div>
                          <div className="mt-1 text-[11px] text-slate-400">
                            Issue {row.normalized_issue ?? row.raw_issue}
                            {row.normalized_publisher ? ` · ${row.normalized_publisher}` : ""}
                          </div>
                        </td>
                        <td className="p-3 align-top">
                          <span className="rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-100">
                            {marketSaleMatchSuggestionLabel(row.suggestion_type)}
                          </span>
                        </td>
                        <td className="p-3 align-top">
                          <span
                            className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketSaleMatchSuggestionTone(
                              row.confidence_bucket,
                            )}`}
                          >
                            {row.confidence_bucket} · {row.deterministic_score.toFixed(2)}
                          </span>
                        </td>
                        <td className="p-3 align-top">
                          <span className="rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-100">
                            {marketSaleMatchSuggestionLabel(row.review_state)}
                          </span>
                        </td>
                        <td className="p-3 text-slate-400 align-top">{formatDateTime(row.updated_at)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              {opsMarketMatchSelectedSuggestion ? (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-violet-100">
                        Suggestion #{opsMarketMatchSelectedSuggestion.id}
                      </p>
                      <p className="mt-1 text-sm text-slate-100">
                        Sale #{opsMarketMatchSelectedSuggestion.market_sale_record_id}
                        {opsMarketMatchSelectedSuggestion.suggested_identity_key
                          ? ` · ${opsMarketMatchSelectedSuggestion.suggested_identity_key}`
                          : ""}
                      </p>
                      <p className="mt-1 text-xs text-slate-400">
                        Canonical refs: issue {opsMarketMatchSelectedSuggestion.canonical_issue_id ?? "—"} · series{" "}
                        {opsMarketMatchSelectedSuggestion.canonical_series_id ?? "—"} · publisher{" "}
                        {opsMarketMatchSelectedSuggestion.canonical_publisher_id ?? "—"}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="rounded-full border border-violet-300/35 px-3 py-1.5 text-[11px] font-semibold text-violet-100 transition hover:border-violet-200/60 hover:bg-violet-500/10 disabled:cursor-not-allowed disabled:opacity-50"
                      onClick={() =>
                        void handleGenerateMarketMatchSuggestions(opsMarketMatchSelectedSuggestion.market_sale_record_id)
                      }
                      disabled={opsMarketMatchSuggestionBusyId != null}
                    >
                      Regenerate sale
                    </button>
                  </div>
                  <div className="mt-4 grid gap-2 text-xs text-slate-300">
                    <div>Source: {opsMarketMatchSelectedSuggestion.source_name} ({opsMarketMatchSelectedSuggestion.source_type})</div>
                    <div>Listing type: {opsMarketMatchSelectedSuggestion.listing_type}</div>
                    <div>
                      Normalization: {opsMarketMatchSelectedSuggestion.normalization_status} · issues{" "}
                      {opsMarketMatchSelectedSuggestion.normalization_issue_count}
                    </div>
                    <div>
                      Review state: {opsMarketMatchSelectedSuggestion.review_state}
                      {opsMarketMatchSelectedSuggestion.reviewed_by_user_id != null
                        ? ` · reviewer #${opsMarketMatchSelectedSuggestion.reviewed_by_user_id}`
                        : ""}
                    </div>
                  </div>
                  <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Evidence</p>
                    <pre className="mt-2 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-slate-300">
                      {JSON.stringify(opsMarketMatchSelectedSuggestion.evidence_json, null, 2)}
                    </pre>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void reviewMarketMatchSuggestion(opsMarketMatchSelectedSuggestion.id, "approve")}
                      disabled={opsMarketMatchSuggestionBusyId === opsMarketMatchSelectedSuggestion.id}
                      className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-[11px] font-semibold text-emerald-100 disabled:opacity-40"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => void reviewMarketMatchSuggestion(opsMarketMatchSelectedSuggestion.id, "reject")}
                      disabled={opsMarketMatchSuggestionBusyId === opsMarketMatchSelectedSuggestion.id}
                      className="rounded-lg border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-[11px] font-semibold text-rose-100 disabled:opacity-40"
                    >
                      Reject
                    </button>
                    <button
                      type="button"
                      onClick={() => void reviewMarketMatchSuggestion(opsMarketMatchSelectedSuggestion.id, "ignore")}
                      disabled={opsMarketMatchSuggestionBusyId === opsMarketMatchSelectedSuggestion.id}
                      className="rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-[11px] font-semibold text-slate-100 disabled:opacity-40"
                    >
                      Ignore
                    </button>
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-500">Select a suggestion to inspect its evidence and review actions.</p>
              )}
            </div>
          </div>
        ) : null}
      </section>

      <details className="mt-6 rounded-3xl border border-teal-400/35 bg-teal-950/15 p-5 shadow-xl shadow-black/20 [&>summary::-webkit-details-marker]:hidden">
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Scan sessions (fleet)</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Deterministic ingest session ledger across owners. Inspect a session for OCR/review/skipped counters and
                duplicate filename/hash rollups — read-only scaffolding with no scanner drivers or automatic metadata edits.
              </p>
            </div>
            <span className="rounded-full border border-teal-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-teal-100/90">
              Ops / read-only stats
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-teal-200/15 pt-4">
          {opsScanSessionsLoading ? (
            <p className="text-sm text-slate-400">Loading scan sessions...</p>
          ) : opsScanSessionsError ? (
            <StatusBanner tone="error">{opsScanSessionsError}</StatusBanner>
          ) : opsScanSessions.length === 0 ? (
            <p className="text-sm text-slate-500">No scan sessions recorded yet.</p>
          ) : (
            <>
              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/50">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Inspect</th>
                      <th className="p-3 font-medium">Session</th>
                      <th className="p-3 font-medium">Owner</th>
                      <th className="p-3 font-medium">Kind</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">Totals</th>
                      <th className="p-3 font-medium">Failed</th>
                      <th className="p-3 font-medium">Skipped</th>
                      <th className="p-3 font-medium">Updated</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-200">
                    {opsScanSessions.map((row) => (
                      <tr key={row.id} className="border-t border-white/10">
                        <td className="p-3">
                          <button
                            type="button"
                            className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                              opsScanSessionSelectedId === row.id
                                ? "border-teal-300/70 bg-teal-400/20 text-teal-50"
                                : "border-white/15 text-slate-200 hover:border-teal-300/35"
                            }`}
                            onClick={() =>
                              setOpsScanSessionSelectedId((cur) => (cur === row.id ? null : row.id))
                            }
                          >
                            {opsScanSessionSelectedId === row.id ? "Hide" : "View"}
                          </button>
                        </td>
                        <td className="p-3 font-mono text-[11px] text-white">#{row.id}</td>
                        <td className="p-3 font-mono text-[11px]">#{row.owner_user_id}</td>
                        <td className="p-3 capitalize">{row.session_type.replace(/_/g, " ")}</td>
                        <td className="p-3 capitalize">{row.status.replace(/_/g, " ")}</td>
                        <td className="p-3">
                          {row.processed_items}/{row.total_items}
                        </td>
                        <td className="p-3">{row.failed_items}</td>
                        <td className="p-3">{row.skipped_items}</td>
                        <td className="p-3 text-slate-400">{formatDateTime(row.updated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <OpsScanSessionInspectionPanel
                selectedId={opsScanSessionSelectedId}
                loading={opsScanSessionDetailLoading}
                detail={opsScanSessionDetail}
              />
            </>
          )}
        </div>
      </details>

      <details className="mt-6 rounded-3xl border border-violet-400/35 bg-violet-950/10 p-5 shadow-xl shadow-black/20 [&>summary::-webkit-details-marker]:hidden">
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Scan QA (fleet)</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Persists only after owners run &quot;Run QA snapshot&quot; on a session. Classification + routing aggregates also
                appear in the condensed <span className="font-semibold text-slate-200">Bulk ingest operations</span> header — expand here for ledger-level breakdowns without duplicating OCR actions elsewhere.
              </p>
            </div>
            <span className="rounded-full border border-violet-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-100/90">
              Ops / persisted ledger
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-violet-200/15 pt-4">
          {opsScanQaFleetLoading ? (
            <p className="text-sm text-slate-400">Loading scan QA aggregates…</p>
          ) : opsScanQaFleetError ? (
            <StatusBanner tone="error">{opsScanQaFleetError}</StatusBanner>
          ) : opsScanQaFleet ? (
            <>
              <p className="text-xs text-slate-400">
                Totals reflect stored <span className="font-mono text-slate-200">scan_qa_result</span> rows (empty until sessions
                run QA).
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {Object.entries(opsScanQaFleet.totals_by_classification).map(([k, v]) => (
                  <StatCard key={k} label={k.replace(/_/g, " ")} value={String(v)} />
                ))}
              </div>
              <p className="mt-6 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Routing recommendations</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(opsScanQaFleet.totals_by_routing).map(([k, v]) => (
                  <StatCard key={k} label={k.replace(/_/g, " ")} value={String(v)} />
                ))}
              </div>
              <p className="mt-6 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                Failure &amp; rescan visibility
              </p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {Object.entries(opsScanQaFleet.failure_and_rescan).map(([k, v]) => (
                  <StatCard key={k} label={k.replace(/_/g, " ")} value={String(v)} />
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">No scan QA fleet data.</p>
          )}
        </div>
      </details>

      <details className="mt-6 rounded-3xl border border-fuchsia-400/35 bg-fuchsia-950/10 p-5 shadow-xl shadow-black/20 [&>summary::-webkit-details-marker]:hidden">
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Scan pipeline replays</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Owners create and start deterministic replays outside this panel — here we only read-back booked comparisons (ingest, QA vs
                persistence, hypothetical routing deltas, OCR job visibility snapshots, high-res review rows). No automatic OCR enqueue,
                destructive cleanup, or metadata writes from replay itself.
              </p>
            </div>
            <span className="rounded-full border border-fuchsia-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-fuchsia-100/90">
              Ops / recovery visibility
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-fuchsia-200/15 pt-4">
          {opsScanPipelineReplaysLoading ? (
            <p className="text-sm text-slate-400">Loading replay ledger…</p>
          ) : opsScanPipelineReplaysError ? (
            <StatusBanner tone="error">{opsScanPipelineReplaysError}</StatusBanner>
          ) : opsScanPipelineReplays.length === 0 ? (
            <p className="text-sm text-slate-500">No replay runs booked yet.</p>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                <StatCard label="Listed replays" value={String(opsScanPipelineReplays.length)} />
                <StatCard
                  label="Σ changed rows"
                  value={String(opsScanPipelineReplays.reduce((acc, r) => acc + r.changed_items, 0))}
                />
                <StatCard
                  label="Σ unchanged rows"
                  value={String(opsScanPipelineReplays.reduce((acc, r) => acc + r.unchanged_items, 0))}
                />
                <StatCard
                  label="Σ failed rows"
                  value={String(opsScanPipelineReplays.reduce((acc, r) => acc + r.failed_items, 0))}
                />
                <StatCard
                  label="Σ cancelled stubs"
                  value={String(opsScanPipelineReplays.reduce((acc, r) => acc + r.cancelled_items, 0))}
                />
              </div>

              <div className="mt-5 overflow-auto rounded-2xl border border-white/10">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3"></th>
                      <th className="p-3">Replay</th>
                      <th className="p-3">Session</th>
                      <th className="p-3">Owner</th>
                      <th className="p-3">Status</th>
                      <th className="p-3">Changed / unchanged</th>
                      <th className="p-3">Failed / cancelled</th>
                      <th className="p-3">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsScanPipelineReplays.map((row) => {
                      const isOpen = opsScanPipelineReplaySelectedId === row.id;
                      return (
                        <tr key={row.id}>
                          <td className="p-3 align-top">
                            <button
                              type="button"
                              className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                                isOpen ? "border-fuchsia-300/70 bg-fuchsia-400/20 text-fuchsia-50" : "border-white/15 text-slate-200 hover:border-fuchsia-300/35"
                              }`}
                              onClick={() =>
                                setOpsScanPipelineReplaySelectedId((cur) => (cur === row.id ? null : row.id))
                              }
                            >
                              {isOpen ? "Hide items" : "Diff detail"}
                            </button>
                          </td>
                          <td className="p-3 font-mono text-[11px] text-white align-top">#{row.id}</td>
                          <td className="p-3 font-mono text-[11px] align-top">
                            #{row.scan_session_id}
                          </td>
                          <td className="p-3 font-mono text-[11px] align-top">
                            #{row.owner_user_id}
                          </td>
                          <td className="p-3 align-top">
                            <span
                              className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${scanPipelineReplayStatusTone(row.status)}`}
                            >
                              {row.status.replace(/_/g, " ")}
                            </span>
                          </td>
                          <td className="p-3 align-top">
                            {row.changed_items} · {row.unchanged_items}
                          </td>
                          <td className="p-3 align-top">
                            {row.failed_items} · {row.cancelled_items}
                          </td>
                          <td className="p-3 text-slate-400 align-top">{formatDateTime(row.created_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {opsScanPipelineReplaySelectedId == null ? null : opsScanPipelineReplayDetailLoading ? (
                <p className="mt-4 text-sm text-slate-400">Hydrating replay item ledger…</p>
              ) : opsScanPipelineReplayDetail ? (
                <div className="mt-4 space-y-3 rounded-2xl border border-white/10 bg-black/25 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Item states &amp; diff categories (#{opsScanPipelineReplayDetail.id})
                  </p>
                  <p className="text-xs text-slate-400">
                    Scopes:&nbsp;
                    <span className="font-mono text-slate-200">{opsScanPipelineReplayDetail.scopes_json.join(", ")}</span>
                  </p>
                  {(() => {
                    const tally: Record<string, number> = {};
                    for (const it of opsScanPipelineReplayDetail.items) {
                      for (const c of it.diff_categories) tally[c] = (tally[c] ?? 0) + 1;
                    }
                    const keys = Object.keys(tally).sort();
                    if (keys.length === 0)
                      return <p className="text-xs text-slate-400">No diff categories recorded.</p>;
                    return (
                      <div className="flex flex-wrap gap-2">
                        {keys.map((k) => (
                          <span
                            key={k}
                            className="rounded-xl border border-fuchsia-400/25 bg-fuchsia-500/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-fuchsia-100"
                          >
                            {k}: {tally[k]}
                          </span>
                        ))}
                      </div>
                    );
                  })()}
                  <div className="max-h-80 overflow-auto rounded-xl border border-white/10 bg-slate-950/40">
                    <table className="w-full border-collapse text-left text-[11px]">
                      <thead className="sticky top-0 bg-slate-950/95 text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-2">Item</th>
                          <th className="p-2">Result</th>
                          <th className="p-2">Diff categories</th>
                          <th className="p-2">Last error</th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-200">
                        {opsScanPipelineReplayDetail.items.slice(0, 750).map((it) => (
                          <tr key={it.id} className="border-t border-white/5 align-top">
                            <td className="p-2 font-mono">#{it.scan_session_item_id}</td>
                            <td className="p-2">{it.result_state.replace(/_/g, " ")}</td>
                            <td className="p-2 font-mono text-[10px] text-slate-300">
                              {it.diff_categories.length === 0 ? "—" : it.diff_categories.join(", ")}
                            </td>
                            <td className="p-2 text-rose-200/95">{it.last_error ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <StatusBanner tone="error">Replay detail unavailable.</StatusBanner>
              )}
            </>
          )}
        </div>
      </details>

      <details className="mt-6 rounded-3xl border border-cyan-400/35 bg-cyan-950/10 p-5 shadow-xl shadow-black/20 [&>summary::-webkit-details-marker]:hidden">
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Queue routing dashboard</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Deterministic recommendations only. The dashboard shows unresolved rows and the stored routing mix across
                scan sessions and linked covers.
              </p>
            </div>
            <span className="rounded-full border border-cyan-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/90">
              Ops / routing ledger
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-cyan-200/15 pt-4">
          {opsRoutingLoading ? (
            <p className="text-sm text-slate-400">Loading routing recommendations…</p>
          ) : opsRoutingError ? (
            <StatusBanner tone="error">{opsRoutingError}</StatusBanner>
          ) : opsRouting ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {Object.entries(opsRouting.totals_by_recommendation).map(([k, v]) => (
                  <StatCard key={k} label={k.replace(/_/g, " ")} value={String(v)} />
                ))}
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {Object.entries(opsRouting.totals_by_status).map(([k, v]) => (
                  <StatCard key={k} label={k.replace(/_/g, " ")} value={String(v)} />
                ))}
                <StatCard label="Unresolved" value={String(opsRouting.unresolved_count)} />
              </div>
              <div className="mt-5 overflow-auto rounded-2xl border border-white/10">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3">Rec id</th>
                      <th className="p-3">Recommendation</th>
                      <th className="p-3">Status</th>
                      <th className="p-3">Session item</th>
                      <th className="p-3">Cover</th>
                      <th className="p-3">Reasons</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {opsRouting.items.filter((row) => row.routing_status === "open").slice(0, 25).map((row) => {
                      const reasons = Array.isArray(row.evidence_json?.reasons)
                        ? (row.evidence_json.reasons as string[])
                        : [];
                      return (
                        <tr key={row.id ?? `${row.scan_session_item_id}-${row.cover_image_id}`} className="align-top">
                          <td className="p-3 font-mono">{row.id ?? "—"}</td>
                          <td className="p-3 capitalize">{row.recommendation_type.replace(/_/g, " ")}</td>
                          <td className="p-3 capitalize">{row.routing_status.replace(/_/g, " ")}</td>
                          <td className="p-3 font-mono">{row.scan_session_item_id ?? "—"}</td>
                          <td className="p-3 font-mono">{row.cover_image_id ? `#${row.cover_image_id}` : "—"}</td>
                          <td className="max-w-[18rem] p-3 text-slate-400">{reasons.slice(0, 4).join(" · ") || "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {opsRouting.unresolved_count === 0 ? (
                <p className="mt-3 text-xs text-slate-500">No unresolved routing recommendations.</p>
              ) : null}
            </>
          ) : (
            <p className="text-sm text-slate-500">No routing recommendations loaded.</p>
          )}
        </div>
      </details>

      <details className="mt-6 rounded-3xl border border-amber-400/35 bg-amber-950/10 p-5 shadow-xl shadow-black/20 [&>summary::-webkit-details-marker]:hidden">
        <summary className="cursor-pointer list-none">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">High-resolution review queue</h2>
              <p className="mt-1 max-w-3xl text-xs text-slate-400">
                Ledger of owner-escalated cover rescans scoped to inventory copies (no primary-cover replacement; attach path
                is owner-only ingestion). Operators can inspect counts across the fleet or filter rows for triage —
                escalation creation remains owner-scoped inventory UI.
              </p>
            </div>
            <span className="rounded-full border border-amber-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-100/90">
              Ops visibility
            </span>
          </div>
        </summary>
        <div className="mt-5 border-t border-amber-200/15 pt-4">
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex min-w-[7rem] flex-col gap-1 text-[11px] text-slate-400">
              <span className="font-semibold uppercase tracking-[0.1em]">Status</span>
              <select
                value={opsHrStatusFilter}
                onChange={(e) => setOpsHrStatusFilter(e.target.value)}
                className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
              >
                <option value="">Any</option>
                {OPS_HIGH_RES_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex min-w-[7rem] flex-col gap-1 text-[11px] text-slate-400">
              <span className="font-semibold uppercase tracking-[0.1em]">Priority</span>
              <select
                value={opsHrPriorityFilter}
                onChange={(e) => setOpsHrPriorityFilter(e.target.value)}
                className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
              >
                <option value="">Any</option>
                {OPS_HIGH_RES_PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex min-w-[11rem] flex-col gap-1 text-[11px] text-slate-400">
              <span className="font-semibold uppercase tracking-[0.1em]">Reason</span>
              <select
                value={opsHrReasonFilter}
                onChange={(e) => setOpsHrReasonFilter(e.target.value)}
                className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-100"
              >
                <option value="">Any</option>
                {OPS_HIGH_RES_REASONS.map((r) => (
                  <option key={r} value={r}>
                    {r.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex min-w-[10rem] flex-1 flex-col gap-1 text-[11px] text-slate-400">
              <span className="font-semibold uppercase tracking-[0.1em]">Owner user id</span>
              <input
                type="text"
                inputMode="numeric"
                placeholder="Fleet-wide when empty"
                value={opsHrOwnerUserIdDraft}
                onChange={(e) => setOpsHrOwnerUserIdDraft(e.target.value)}
                className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none placeholder:text-slate-500 focus:border-amber-300/40"
              />
            </label>
          </div>

          {opsHrStats ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {OPS_HIGH_RES_STATUSES.map((status) => (
                <StatCard
                  key={status}
                  label={status.replace(/_/g, " ")}
                  value={String(opsHrStats.by_status[status] ?? 0)}
                />
              ))}
            </div>
          ) : null}

          {opsHrLoading ? (
            <p className="mt-4 text-sm text-slate-400">Loading high-resolution review requests…</p>
          ) : opsHrError ? (
            <div className="mt-4">
              <StatusBanner tone="error">{opsHrError}</StatusBanner>
            </div>
          ) : opsHrList.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No requests matched the active filters.</p>
          ) : (
            <>
              <p className="mt-4 text-xs text-slate-400">
                Showing{" "}
                <span className="font-semibold text-slate-200">{opsHrList.length}</span> request
                {opsHrList.length === 1 ? "" : "s"} for the current filters.
              </p>
              <div className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-950/50">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Request</th>
                      <th className="p-3 font-medium">Owner</th>
                      <th className="p-3 font-medium">Inventory copy</th>
                      <th className="p-3 font-medium">Reason</th>
                      <th className="p-3 font-medium">Pri</th>
                      <th className="p-3 font-medium">Status</th>
                      <th className="p-3 font-medium">HR cover</th>
                      <th className="p-3 font-medium">Updated</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-200">
                    {opsHrList.map((row) => (
                      <tr key={row.id} className="border-t border-white/10">
                        <td className="p-3 font-mono text-[11px] text-white">#{row.id}</td>
                        <td className="p-3 font-mono text-[11px]">#{row.owner_user_id}</td>
                        <td className="p-3">
                          <Link
                            to={`/inventory/${row.inventory_copy_id}`}
                            className="font-mono font-semibold text-cyan-200 underline-offset-4 hover:underline"
                          >
                            #{row.inventory_copy_id}
                          </Link>
                          {typeof row.attach_scan_session_id === "number" ? (
                            <p className="mt-1 text-[10px] text-slate-500">
                              attach session #{row.attach_scan_session_id}
                            </p>
                          ) : null}
                        </td>
                        <td className="p-3 capitalize">{row.request_reason.replace(/_/g, " ")}</td>
                        <td className="p-3 uppercase">{row.priority}</td>
                        <td className="p-3 capitalize">{row.status.replace(/_/g, " ")}</td>
                        <td className="p-3 font-mono text-[11px] text-slate-300">
                          {row.high_res_cover_image_id != null ? `#${row.high_res_cover_image_id}` : "—"}
                        </td>
                        <td className="p-3 text-slate-400">{formatDateTime(row.updated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </details>

      {dashboard ? (
        <>
          <section className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Recent Gmail Sync Jobs"
              value={String(dashboard.recent_gmail_sync_jobs.length)}
            />
            <StatCard
              label="Recent AI Parse Jobs"
              value={String(dashboard.recent_ai_parse_jobs.length)}
            />
            <StatCard
              label="Parser Failures"
              value={String(dashboard.parser_failures.length)}
            />
            <StatCard
              label="Duplicate Skips"
              value={String(dashboard.duplicate_skip_events.length)}
            />
          </section>

          <details
            className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20"
            open
          >
            <summary className="cursor-pointer list-none text-sm font-semibold text-white">
              Reconciliation summary
            </summary>
            <p className="mt-2 text-sm text-slate-400">
              Read-only health counts for the P32 matching and relationship review surfaces.
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              <StatCard
                label="Open conflicts"
                value={String(dashboard.reconciliation_summary.open_conflicts)}
              />
              <StatCard
                label="Pending canonical suggestions"
                value={String(dashboard.reconciliation_summary.pending_canonical_suggestions)}
              />
              <StatCard
                label="High-confidence unreviewed matches"
                value={String(
                  dashboard.reconciliation_summary.high_confidence_unreviewed_match_candidates,
                )}
              />
              <StatCard
                label="Confirmed duplicate scans"
                value={String(dashboard.reconciliation_summary.confirmed_duplicate_scans)}
              />
              <StatCard
                label="Probable variant families"
                value={String(dashboard.reconciliation_summary.probable_variant_families)}
              />
              <StatCard
                label="Replay changes (7d)"
                value={String(dashboard.reconciliation_summary.recent_relationship_replay_changes)}
              />
            </div>
          </details>

          <details className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
            <summary className="cursor-pointer list-none text-sm font-semibold text-white">
              Global inventory risks
            </summary>
            <p className="mt-2 text-sm text-slate-400">
              Deterministic attention surface across all inventory copies. Read-only signals only: no pricing,
              speculation, automated fixes, or metadata mutation.
            </p>
            <div className="mt-4 flex flex-wrap gap-4">
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Priority
                <select
                  className="rounded-2xl border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  value={opsInventoryRiskPriority}
                  onChange={(event) =>
                    setOpsInventoryRiskPriority(event.target.value as "" | InventoryRiskPriority)
                  }
                >
                  <option value="">All</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                  <option value="info">Info</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Risk type
                <select
                  className="rounded-2xl border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  value={opsInventoryRiskType}
                  onChange={(event) => setOpsInventoryRiskType(event.target.value as "" | InventoryRiskType)}
                >
                  <option value="">All</option>
                  <option value="needs_conflict_review">Conflict review</option>
                  <option value="needs_canonical_review">Canonical review</option>
                  <option value="needs_scan">Needs scan</option>
                  <option value="needs_ocr_retry">OCR retry</option>
                  <option value="needs_cover_processing_review">Cover processing review</option>
                  <option value="preorder_missing_release_date">Preorder missing release date</option>
                  <option value="released_not_received">Released not received</option>
                  <option value="duplicate_uncertainty">Duplicate uncertainty</option>
                  <option value="run_gap_detected">Run gap detected</option>
                  <option value="low_quality_scan">Low quality scan</option>
                  <option value="high_confidence_match_unreviewed">High confidence match</option>
                </select>
              </label>
              <label className="flex items-center gap-3 rounded-2xl border border-white/15 bg-slate-950/80 px-3 py-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={opsInventoryRiskOpenOnly}
                  onChange={(event) => setOpsInventoryRiskOpenOnly(event.target.checked)}
                />
                Open only
              </label>
            </div>
            {opsInventoryRiskError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{opsInventoryRiskError}</StatusBanner>
              </div>
            ) : null}
            {opsInventoryRiskReport ? (
              <>
                <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                  <StatCard label="Critical copies" value={String(opsInventoryRiskReport.summary.critical_copies)} />
                  <StatCard label="High copies" value={String(opsInventoryRiskReport.summary.high_copies)} />
                  <StatCard label="Medium copies" value={String(opsInventoryRiskReport.summary.medium_copies)} />
                  <StatCard label="Low copies" value={String(opsInventoryRiskReport.summary.low_copies)} />
                  <StatCard label="Risk items" value={String(opsInventoryRiskReport.summary.total_risk_items)} />
                  <StatCard label="Copies with risk" value={String(opsInventoryRiskReport.summary.copies_with_risk)} />
                </div>
                <div className="mt-5 overflow-x-auto rounded-2xl border border-white/10">
                  <table className="min-w-full divide-y divide-white/10 text-left text-sm text-slate-200">
                    <thead className="bg-white/5 text-[11px] uppercase tracking-[0.14em] text-slate-400">
                      <tr>
                        <th className="px-4 py-3">Copy</th>
                        <th className="px-4 py-3">Priority</th>
                        <th className="px-4 py-3">Risk</th>
                        <th className="px-4 py-3">Evidence</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {opsInventoryRiskReport.risks.slice(0, 25).map((risk) => (
                        <tr key={risk.risk_key}>
                          <td className="px-4 py-3">
                            <Link to={`/inventory/${risk.inventory_copy_id}`} className="font-medium text-white hover:text-cyan-200">
                              {risk.publisher} · {risk.title} #{risk.issue_number}
                            </Link>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${inventoryRiskPriorityTone(
                                risk.priority,
                              )}`}
                            >
                              {risk.priority}
                            </span>
                          </td>
                          <td className="px-4 py-3">{inventoryRiskLabel(risk.risk_type)}</td>
                          <td className="px-4 py-3 text-slate-400">{inventoryRiskEvidenceSummary(risk)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <p className="mt-4 text-sm text-slate-400">Loading global inventory risks…</p>
            )}
          </details>

          <details className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
            <summary className="cursor-pointer list-none text-sm font-semibold text-white">
              Global inventory action center
            </summary>
            <p className="mt-2 text-sm text-slate-400">
              Cross-tenant deterministic workflow rollup (risk lanes, intelligence signals, preorder gaps where
              distinct, arrivals). Mirrors owner Dashboard semantics at ops scope — visibility only.
            </p>
            <div className="mt-4 flex flex-wrap gap-4">
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Priority lane
                <select
                  className="rounded-2xl border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  value={opsIacPriority}
                  onChange={(event) => setOpsIacPriority(event.target.value as "" | InventoryRiskPriority)}
                >
                  <option value="">All</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                  <option value="info">Info</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Action category
                <select
                  className="rounded-2xl border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  value={opsIacCategory}
                  onChange={(event) =>
                    setOpsIacCategory(event.target.value as "" | InventoryActionCenterCategory)
                  }
                >
                  <option value="">All</option>
                  <option value="review_relationship_conflict">
                    {inventoryActionCenterCategoryUiLabel("review_relationship_conflict")}
                  </option>
                  <option value="review_canonical_suggestion">
                    {inventoryActionCenterCategoryUiLabel("review_canonical_suggestion")}
                  </option>
                  <option value="review_duplicate_ownership">
                    {inventoryActionCenterCategoryUiLabel("review_duplicate_ownership")}
                  </option>
                  <option value="review_duplicate_scan">
                    {inventoryActionCenterCategoryUiLabel("review_duplicate_scan")}
                  </option>
                  <option value="review_variant_family">
                    {inventoryActionCenterCategoryUiLabel("review_variant_family")}
                  </option>
                  <option value="retry_ocr">{inventoryActionCenterCategoryUiLabel("retry_ocr")}</option>
                  <option value="review_cover_processing">
                    {inventoryActionCenterCategoryUiLabel("review_cover_processing")}
                  </option>
                  <option value="scan_missing_cover">
                    {inventoryActionCenterCategoryUiLabel("scan_missing_cover")}
                  </option>
                  <option value="update_preorder_metadata">
                    {inventoryActionCenterCategoryUiLabel("update_preorder_metadata")}
                  </option>
                  <option value="review_run_gap">{inventoryActionCenterCategoryUiLabel("review_run_gap")}</option>
                  <option value="review_high_confidence_match">
                    {inventoryActionCenterCategoryUiLabel("review_high_confidence_match")}
                  </option>
                </select>
              </label>
            </div>
            {opsIacError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{opsIacError}</StatusBanner>
              </div>
            ) : null}
            {opsIacReport ? (
              <>
                <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                  <StatCard
                    label="Critical actions"
                    value={String(opsIacReport.summary.critical_actions)}
                  />
                  <StatCard label="High actions" value={String(opsIacReport.summary.high_actions)} />
                  <StatCard label="Medium actions" value={String(opsIacReport.summary.medium_actions)} />
                  <StatCard label="Low actions" value={String(opsIacReport.summary.low_actions)} />
                  <StatCard label="Copies with actions" value={String(opsIacReport.summary.copies_with_actions)} />
                  <StatCard label="Total actions" value={String(opsIacReport.summary.total_actions)} />
                </div>
                <p className="mt-3 text-[11px] uppercase tracking-[0.14em] text-slate-500">
                  As of {opsIacReport.generated_as_of_date}
                </p>
                <div className="mt-5 overflow-x-auto rounded-2xl border border-white/10">
                  <table className="min-w-full divide-y divide-white/10 text-left text-sm text-slate-200">
                    <thead className="bg-white/5 text-[11px] uppercase tracking-[0.14em] text-slate-400">
                      <tr>
                        <th className="px-4 py-3">Copy</th>
                        <th className="px-4 py-3">Category</th>
                        <th className="px-4 py-3">Lane</th>
                        <th className="px-4 py-3">Source</th>
                        <th className="px-4 py-3">Evidence</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {opsIacReport.actions.slice(0, 40).map((action) => (
                        <tr key={action.action_key}>
                          <td className="px-4 py-3">
                            <Link
                              to={`/inventory/${action.inventory_copy_id}`}
                              className="font-medium text-white hover:text-cyan-200"
                            >
                              {action.publisher} · {action.title} #{action.issue_number}
                            </Link>
                            <p className="mt-1 text-[11px] text-slate-500">Copy #{action.inventory_copy_id}</p>
                          </td>
                          <td className="px-4 py-3">{inventoryActionCenterCategoryUiLabel(action.action_category)}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${inventoryRiskPriorityTone(
                                action.priority,
                              )}`}
                            >
                              {action.priority}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-400">{action.source.replace(/_/g, " ")}</td>
                          <td className="px-4 py-3 text-slate-400">{inventoryActionEvidenceSummary(action)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <p className="mt-4 text-sm text-slate-400">Loading global inventory action center…</p>
            )}
          </details>

          <details className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
            <summary className="cursor-pointer list-none text-sm font-semibold text-white">
              Global order &amp; arrival intelligence
            </summary>
            <p className="mt-2 text-sm text-slate-400">
              Operational preorder and shipment overlays derived purely from deterministic dates and statuses. Visibility
              only (no valuation, speculation, or automatic receipt).
            </p>
            <div className="mt-4 flex flex-wrap gap-4">
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Classification
                <select
                  className="rounded-2xl border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  value={opsOrderArrivalClassification}
                  onChange={(event) =>
                    setOpsOrderArrivalClassification(event.target.value as "" | OrderArrivalClassification)
                  }
                >
                  <option value="">All</option>
                  <option value="upcoming_preorder">Upcoming preorder</option>
                  <option value="releases_this_week">Releases this week</option>
                  <option value="released_not_received">Released / not received</option>
                  <option value="expected_to_ship_soon">Shipping soon</option>
                  <option value="overdue_expected_ship">Shipment overdue</option>
                  <option value="received_recently">Received recently</option>
                  <option value="cancelled_order">Cancelled order</option>
                  <option value="missing_release_date">Missing release date</option>
                  <option value="missing_expected_ship_date">Missing ship date</option>
                </select>
              </label>
            </div>
            {opsOrderArrivalError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{opsOrderArrivalError}</StatusBanner>
              </div>
            ) : null}
            {opsOrderArrivalReport && opsOrderArrivalCalendar ? (
              <>
                <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <StatCard
                    label="Pipeline rows"
                    value={String(opsOrderArrivalReport.summary.total_intel_items)}
                  />
                  <StatCard label="Tagged copies" value={String(opsOrderArrivalReport.summary.copies_tagged)} />
                  <StatCard
                    label="Shipment overdue rows"
                    value={String(
                      opsOrderArrivalReport.items.filter((item) => item.classification === "overdue_expected_ship")
                        .length,
                    )}
                  />
                  <StatCard
                    label="Calendar window"
                    value={`${opsOrderArrivalCalendar.calendar_start} → ${opsOrderArrivalCalendar.calendar_end}`}
                  />
                </div>
                <div className="mt-5 overflow-x-auto rounded-2xl border border-white/10">
                  <table className="min-w-full divide-y divide-white/10 text-left text-sm text-slate-200">
                    <thead className="bg-white/5 text-[11px] uppercase tracking-[0.14em] text-slate-400">
                      <tr>
                        <th className="px-4 py-3">Copy</th>
                        <th className="px-4 py-3">Lane</th>
                        <th className="px-4 py-3">Evidence</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {opsOrderArrivalReport.items.slice(0, 30).map((row) => (
                        <tr key={row.intel_key}>
                          <td className="px-4 py-3">
                            <Link
                              to={`/inventory/${row.inventory_copy_id}`}
                              className="font-medium text-white hover:text-cyan-200"
                            >
                              {row.publisher} · {row.title} #{row.issue_number}
                            </Link>
                            <div className="text-[11px] text-slate-500">{row.retailer}</div>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${opsOrderArrivalTone(
                                row.classification,
                              )}`}
                            >
                              {opsOrderArrivalShortLabel(row.classification)}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-400">{JSON.stringify(row.evidence_json)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="mt-6">
                  <h3 className="text-sm font-semibold text-white">Calendar (dense daily grid)</h3>
                  <p className="mt-1 text-xs text-slate-500">
                    Each row is a calendar day showing copies keyed on declared release versus expected shipment dates (
                    filtered set only).
                  </p>
                  <div className="mt-4 max-h-[28rem] overflow-auto rounded-2xl border border-white/10">
                    <table className="min-w-full divide-y divide-white/10 text-left text-xs text-slate-200">
                      <thead className="sticky top-0 bg-slate-950/95 text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="px-3 py-2">Date</th>
                          <th className="px-3 py-2">Release-dated picks</th>
                          <th className="px-3 py-2">Expected ship picks</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {opsOrderArrivalCalendar.rows
                          .filter(
                            (r) =>
                              Boolean(r.on_release_date.length) ||
                              Boolean(r.on_expected_ship_date.length),
                          )
                          .map((day) => (
                            <tr key={day.calendar_date}>
                              <td className="px-3 py-2 font-medium text-white">{day.calendar_date}</td>
                              <td className="px-3 py-2 text-slate-400">
                                {day.on_release_date
                                  .map((c) => `${c.publisher} · ${c.title} #${c.issue_number}`)
                                  .join(" · ") || "—"}
                              </td>
                              <td className="px-3 py-2 text-slate-400">
                                {day.on_expected_ship_date
                                  .map((c) => `${c.publisher} · ${c.title} #${c.issue_number}`)
                                  .join(" · ") || "—"}
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            ) : opsOrderArrivalError ? null : (
              <p className="mt-4 text-sm text-slate-400">Loading order / arrival overlays…</p>
            )}
          </details>

          <details className="mt-6 rounded-3xl border border-emerald-400/25 bg-emerald-950/15 p-5 shadow-xl shadow-black/20">
            <summary className="cursor-pointer list-none text-sm font-semibold text-white">
              Global physical intake queue
            </summary>
            <p className="mt-2 text-sm text-slate-400">
              Deterministic rollups tying explicit receipt timestamps to intake-only scan placeholders. Filters apply to the
              list rows only; headline counts reflect all copies until filtered by intake state (global scope).
            </p>
            <div className="mt-4 flex flex-wrap gap-4">
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Intake state filter (list only)
                <select
                  className="rounded-2xl border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  value={opsPhysicalIntakeStateFilter}
                  onChange={(event) =>
                    setOpsPhysicalIntakeStateFilter(event.target.value as "" | PhysicalIntakeState)
                  }
                >
                  <option value="">All deterministic states</option>
                  <option value="awaiting_release">Awaiting release</option>
                  <option value="released_awaiting_receipt">Released / awaiting receipt</option>
                  <option value="intake_blocked">Intake blocked (late ship expectations)</option>
                  <option value="received_pending_scan">Received pending scan</option>
                  <option value="received_scanned">Received scanned (OCR incomplete)</option>
                  <option value="completed">Completed intake pipeline</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </label>
            </div>
            {opsPhysicalIntakeError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{opsPhysicalIntakeError}</StatusBanner>
              </div>
            ) : null}
            {opsPhysicalIntakeSummary && opsPhysicalIntakeList ? (
              <>
                <div className="mt-5 grid gap-3 sm:grid-cols-3 xl:grid-cols-6">
                  <StatCard
                    label="Released / not received facet"
                    value={String(opsPhysicalIntakeSummary.counts.released_not_received)}
                  />
                  <StatCard label="Received pending scan" value={String(opsPhysicalIntakeSummary.counts.received_pending_scan)} />
                  <StatCard label="Shipment overdue facet" value={String(opsPhysicalIntakeSummary.counts.overdue_expected_ship)} />
                  <StatCard label="Awaiting release" value={String(opsPhysicalIntakeSummary.counts.awaiting_release)} />
                  <StatCard label="Released awaiting receipt roll-up" value={String(opsPhysicalIntakeSummary.counts.released_awaiting_receipt)} />
                  <StatCard label="Intake blocked roll-up" value={String(opsPhysicalIntakeSummary.counts.intake_blocked)} />
                </div>
                <div className="mt-5 overflow-x-auto rounded-2xl border border-white/10">
                  <table className="min-w-full divide-y divide-white/10 text-left text-sm text-slate-200">
                    <thead className="bg-white/5 text-[11px] uppercase tracking-[0.14em] text-slate-400">
                      <tr>
                        <th className="px-4 py-3">Copy</th>
                        <th className="px-4 py-3">Owner lane</th>
                        <th className="px-4 py-3">Facet tags</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {opsPhysicalIntakeList.items.slice(0, 40).map((row: PhysicalIntakeItemRead) => (
                        <tr key={row.inventory_copy_id}>
                          <td className="px-4 py-3">
                            <Link
                              to={`/inventory/${row.inventory_copy_id}`}
                              className="font-medium text-white hover:text-emerald-100"
                            >
                              {row.publisher} · {row.title} #{row.issue_number}
                            </Link>
                            <div className="text-[11px] text-slate-500">{row.retailer}</div>
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-300">
                            <p className="font-semibold capitalize text-white">{row.intake_state.replace(/_/g, " ")}</p>
                            <p className="text-[11px] text-slate-500">Order · {row.order_status}</p>
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-400">{row.dashboard_buckets.join(", ") || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : opsPhysicalIntakeError ? null : (
              <p className="mt-4 text-sm text-slate-400">Loading physical intake overlays…</p>
            )}
          </details>

          <details className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
            <summary className="cursor-pointer list-none text-sm font-semibold text-white">
              Global inventory intelligence
            </summary>
            <p className="mt-2 text-sm text-slate-400">
              Read-only rollups across every inventory-linked copy for ownership normalization, scans/OCR completeness,
              health buckets, and unresolved conflicts, canonical suggestions, duplicate-inventory reviews, duplicate-scan
              clusters, and variant-family clusters. These endpoints compute only; nothing here mutates data.
            </p>
            {inventoryIntelOpsError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{inventoryIntelOpsError}</StatusBanner>
              </div>
            ) : null}
            {inventoryIntelOpsSummary && inventoryIntelOpsHealth ? (
              <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                <StatCard label="Tracked copies" value={String(inventoryIntelOpsSummary.total_inventory_copies)} />
                <StatCard label="Scanned" value={String(inventoryIntelOpsSummary.scanned_copies)} />
                <StatCard label="Unscanned" value={String(inventoryIntelOpsSummary.unscanned_copies)} />
                <StatCard label="OCR pending" value={String(inventoryIntelOpsSummary.ocr_pending_copies)} />
                <StatCard label="OCR complete" value={String(inventoryIntelOpsSummary.ocr_complete_copies)} />
                <StatCard
                  label="Cover processing failed"
                  value={String(inventoryIntelOpsSummary.cover_processing_failed_copies)}
                />
                <StatCard label="OCR pipeline failed (latest)" value={String(inventoryIntelOpsSummary.ocr_failed_copies)} />
                <StatCard
                  label="Unresolved rollup (total)"
                  value={String(
                    inventoryIntelOpsSummary.unresolved_relationship_conflicts +
                      inventoryIntelOpsSummary.unresolved_canonical_suggestions +
                      inventoryIntelOpsSummary.unresolved_duplicate_inventory_groups +
                      inventoryIntelOpsSummary.unresolved_duplicate_scan_clusters +
                      inventoryIntelOpsSummary.unresolved_variant_family_clusters,
                  )}
                />
                <StatCard
                  label="Open relationship conflicts"
                  value={String(inventoryIntelOpsSummary.unresolved_relationship_conflicts)}
                />
                <StatCard
                  label="Pending canonical rows"
                  value={String(inventoryIntelOpsSummary.unresolved_canonical_suggestions)}
                />
                <StatCard
                  label="Pending dup-inventory groups"
                  value={String(inventoryIntelOpsSummary.unresolved_duplicate_inventory_groups)}
                />
                <StatCard
                  label="Probable dup-scan clusters"
                  value={String(inventoryIntelOpsSummary.unresolved_duplicate_scan_clusters)}
                />
                <StatCard
                  label="Probable variant-family clusters"
                  value={String(inventoryIntelOpsSummary.unresolved_variant_family_clusters)}
                />
                <StatCard label="Health: healthy" value={String(inventoryIntelOpsHealth.healthy)} />
                <StatCard label="Health: needs_review" value={String(inventoryIntelOpsHealth.needs_review)} />
                <StatCard label="Health: incomplete" value={String(inventoryIntelOpsHealth.incomplete)} />
                <StatCard label="Health: blocked" value={String(inventoryIntelOpsHealth.blocked)} />
              </div>
            ) : !inventoryIntelOpsError ? (
              <p className="mt-4 text-sm text-slate-400">Loading global inventory intelligence…</p>
            ) : null}
            {inventoryIntelOpsBreakdown && inventoryIntelOpsBreakdown.unhealthy_sample_inventory_copy_ids.length ? (
              <div className="mt-5 rounded-2xl border border-amber-400/25 bg-amber-400/5 p-4">
                <p className="text-sm font-semibold text-amber-100">Unhealthy inventory sample (deterministic IDs)</p>
                <p className="mt-1 text-xs text-slate-400">
                  Showing up to the first fifty non-healthy inventory copy IDs flagged by deterministic health buckets.
                  These are identifiers only (no destructive actions triggered from this panel).
                </p>
                <p className="mt-3 font-mono text-xs leading-relaxed text-slate-200">
                  {inventoryIntelOpsBreakdown.unhealthy_sample_inventory_copy_ids.join(", ")}
                </p>
              </div>
            ) : inventoryIntelOpsBreakdown ? (
              <p className="mt-5 text-xs text-slate-500">
                No unhealthy sampled inventory IDs (all copies currently classify as healthy, or trackers are idle).
              </p>
            ) : null}
          </details>

          <details className="mt-6 rounded-3xl border border-cyan-400/25 bg-slate-900/70 p-5 shadow-xl shadow-black/25">
            <summary className="cursor-pointer list-none text-sm font-semibold text-white">
              Global historical collection timeline
            </summary>
            <p className="mt-2 text-sm text-slate-400">
              Deterministic event stream across every copy: preorder anchors, release / ship cues, arrivals, scans,
              OCR (including replays), relationship reviews and replays, canonical suggestion reviews, conflict
              detection and resolution, duplicate reviews, variant-family clustering — surfaced as factual timestamps
              only (no valuations, speculative signals, summaries, or write actions from this lane).
            </p>
            {opsHistoricalTimelineError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{opsHistoricalTimelineError}</StatusBanner>
              </div>
            ) : null}
            <div className="mt-4 grid gap-4 lg:grid-cols-6">
              <label className="text-xs uppercase tracking-[0.12em] text-slate-500 lg:col-span-2">
                Event type (optional)
                <select
                  value={opsHistoricalTimelineDraft.event_type}
                  className="mt-1 block w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  onChange={(event) =>
                    setOpsHistoricalTimelineDraft((prev) => ({
                      ...prev,
                      event_type: event.target.value as OpsHistoricalTimelineFilters["event_type"],
                    }))
                  }
                >
                  <option value="">All types</option>
                  {OPS_COLLECTION_HISTORICAL_EVENT_TYPES.map((kind) => (
                    <option key={kind} value={kind}>
                      {kind.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs uppercase tracking-[0.12em] text-slate-500 lg:col-span-2">
                Publisher contains
                <input
                  type="text"
                  value={opsHistoricalTimelineDraft.publisher}
                  placeholder="Substring match upstream"
                  className="mt-1 block w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white placeholder:text-slate-600"
                  onChange={(event) =>
                    setOpsHistoricalTimelineDraft((prev) => ({ ...prev, publisher: event.target.value }))
                  }
                />
              </label>
              <label className="text-xs uppercase tracking-[0.12em] text-slate-500">
                Ownership snapshot (optional)
                <select
                  value={opsHistoricalTimelineDraft.ownership_state}
                  className="mt-1 block w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  onChange={(event) =>
                    setOpsHistoricalTimelineDraft((prev) => ({
                      ...prev,
                      ownership_state: event.target.value as OpsHistoricalTimelineFilters["ownership_state"],
                    }))
                  }
                >
                  <option value="">All</option>
                  <option value="preorder">Preorder</option>
                  <option value="ordered_not_received">Ordered (not received)</option>
                  <option value="in_hand">In hand</option>
                  <option value="cancelled">Cancelled</option>
                  <option value="unknown_state">Unknown state</option>
                </select>
              </label>
              <label className="text-xs uppercase tracking-[0.12em] text-slate-500">
                Release status (optional)
                <select
                  value={opsHistoricalTimelineDraft.release_status}
                  className="mt-1 block w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  onChange={(event) =>
                    setOpsHistoricalTimelineDraft((prev) => ({
                      ...prev,
                      release_status: event.target.value as OpsHistoricalTimelineFilters["release_status"],
                    }))
                  }
                >
                  <option value="">All</option>
                  <option value="released">Released</option>
                  <option value="not_released_yet">Not released yet</option>
                  <option value="unknown">Unknown</option>
                </select>
              </label>
              <label className="text-xs uppercase tracking-[0.12em] text-slate-500">
                Start date
                <input
                  type="date"
                  className="mt-1 block w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  value={opsHistoricalTimelineDraft.start_date}
                  onChange={(event) =>
                    setOpsHistoricalTimelineDraft((prev) => ({ ...prev, start_date: event.target.value }))
                  }
                />
              </label>
              <label className="text-xs uppercase tracking-[0.12em] text-slate-500">
                End date
                <input
                  type="date"
                  className="mt-1 block w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  value={opsHistoricalTimelineDraft.end_date}
                  onChange={(event) =>
                    setOpsHistoricalTimelineDraft((prev) => ({ ...prev, end_date: event.target.value }))
                  }
                />
              </label>
              <fieldset className="flex flex-wrap items-center gap-4 lg:col-span-2">
                <label className="inline-flex items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={opsHistoricalTimelineDraft.preorder_only}
                    onChange={(event) =>
                      setOpsHistoricalTimelineDraft((prev) => ({
                        ...prev,
                        preorder_only: event.target.checked,
                        in_hand_only: event.target.checked ? false : prev.in_hand_only,
                      }))
                    }
                  />
                  Preorder-track only
                </label>
                <label className="inline-flex items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={opsHistoricalTimelineDraft.in_hand_only}
                    onChange={(event) =>
                      setOpsHistoricalTimelineDraft((prev) => ({
                        ...prev,
                        in_hand_only: event.target.checked,
                        preorder_only: event.target.checked ? false : prev.preorder_only,
                      }))
                    }
                  />
                  In-hand snapshot only
                </label>
              </fieldset>
              <label className="text-xs uppercase tracking-[0.12em] text-slate-500">
                Grouping
                <select
                  value={opsHistoricalTimelineDraft.grouping}
                  className="mt-1 block w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  onChange={(event) =>
                    setOpsHistoricalTimelineDraft((prev) => ({
                      ...prev,
                      grouping: event.target.value as CollectionHistoricalTimelineGrouping,
                    }))
                  }
                >
                  <option value="none">None (flat chronological)</option>
                  <option value="day">Day</option>
                  <option value="week">Week</option>
                  <option value="month">Month</option>
                  <option value="publisher">Publisher</option>
                  <option value="series">Series</option>
                  <option value="ownership_state">Ownership state snapshot</option>
                  <option value="preorder_vs_in_hand">Preorder vs in-hand</option>
                  <option value="inventory_item">Inventory item</option>
                </select>
              </label>
              <label className="text-xs uppercase tracking-[0.12em] text-slate-500">
                Sort
                <select
                  value={opsHistoricalTimelineDraft.sort}
                  className="mt-1 block w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  onChange={(event) =>
                    setOpsHistoricalTimelineDraft((prev) => ({
                      ...prev,
                      sort: event.target.value as CollectionHistoricalTimelineSort,
                    }))
                  }
                >
                  <option value="desc">Newest first</option>
                  <option value="asc">Oldest first</option>
                </select>
              </label>
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                disabled={opsHistoricalTimelineLoading}
                className="inline-flex rounded-full bg-cyan-500/90 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => setOpsHistoricalTimelineApplied({ ...opsHistoricalTimelineDraft })}
              >
                {opsHistoricalTimelineLoading ? "Applying…" : "Apply timeline filters"}
              </button>
              <button
                type="button"
                className="inline-flex rounded-full border border-white/15 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/5 disabled:opacity-50"
                disabled={opsHistoricalTimelineLoading}
                onClick={() => {
                  const baseline = defaultOpsHistoricalTimelineFilters();
                  setOpsHistoricalTimelineDraft(baseline);
                  setOpsHistoricalTimelineApplied(baseline);
                }}
              >
                Reset filters & reload defaults
              </button>
              {opsHistoricalTimelineLoading ? (
                <span className="inline-flex items-center gap-2 text-xs text-slate-400">
                  <span className="inline-flex size-2 animate-pulse rounded-full bg-cyan-400/80" />
                  Fetching deterministic rows…
                </span>
              ) : null}
            </div>
            {opsHistoricalTimelinePayload ? (
              <div className="mt-4 space-y-5">
                <p className="text-xs text-slate-500">
                  As-of {opsHistoricalTimelinePayload.generated_as_of_date} · Persisted fleet events counted at{" "}
                  {opsHistoricalTimelinePayload.summary.total_events_present}; response truncated to{" "}
                  {opsHistoricalTimelinePayload.summary.truncated_to} rows (sorted{" "}
                  {opsHistoricalTimelinePayload.filters.sort}).
                  {opsHistoricalTimelinePayload.events.length <
                  opsHistoricalTimelinePayload.summary.total_events_present ? (
                    <span className="text-amber-200/90">
                      {" "}
                      Expand date windows or tighten filters locally if you need narrower slices instead of widening the cap.
                    </span>
                  ) : null}
                </p>
                <div>
                  <h3 className="text-sm font-semibold text-white">Reconciliation-focused feed</h3>
                  <p className="mt-1 text-xs text-slate-500">
                    Link decisions / replays, canonical reviews, conflict lifecycle moves, duplicates, variant family
                    detections — same ordering as timeline API within this reconciliation slice.
                  </p>
                  <div className="mt-3 max-h-60 overflow-auto rounded-2xl border border-white/10 bg-slate-950/55">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="sticky top-0 bg-slate-950/95 px-3 py-2">When</th>
                          <th className="sticky top-0 bg-slate-950/95 px-3 py-2">Signal</th>
                          <th className="sticky top-0 bg-slate-950/95 px-3 py-2">Publisher / series</th>
                          <th className="sticky top-0 bg-slate-950/95 px-3 py-2">Copy</th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-200">
                        {(() => {
                          const recon = opsHistoricalTimelinePayload.events.filter((ev) =>
                            [
                              "relationship_reviewed",
                              "canonical_suggestion_reviewed",
                              "conflict_detected",
                              "conflict_resolved",
                              "duplicate_detected",
                              "variant_family_detected",
                            ].includes(ev.event_type),
                          );
                          const rows = recon.slice(0, 24);
                          if (!rows.length) {
                            return (
                              <tr>
                                <td colSpan={4} className="px-4 py-4 text-xs text-slate-500">
                                  No reconciliation-class events in current window ({recon.length} filtered).
                                </td>
                              </tr>
                            );
                          }
                          return rows.map((event) => (
                            <tr key={`ops-recon-${event.stable_id}`} className="border-t border-white/5">
                              <td className="align-top whitespace-nowrap px-3 py-2 text-[11px] text-slate-400">
                                {formatDateTime(event.occurred_at)}
                              </td>
                              <td className="align-top px-3 py-2">
                                <p className="font-semibold text-white">{describeHistoricalTimelineEvent(event)}</p>
                                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                                  {event.event_type.replace(/_/g, " ")}
                                </p>
                              </td>
                              <td className="align-top px-3 py-2">
                                <p>{event.publisher}</p>
                                <p className="text-[11px] text-slate-400">
                                  {event.series_title} #{event.issue_number}
                                </p>
                              </td>
                              <td className="align-top px-3 py-2">
                                <Link
                                  to={`/inventory/${event.inventory_copy_id}`}
                                  className="text-cyan-200 hover:text-cyan-50"
                                >
                                  #{event.inventory_copy_id}
                                </Link>
                              </td>
                            </tr>
                          ));
                        })()}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div>
                  <div className="flex flex-wrap items-baseline gap-3">
                    <h3 className="text-sm font-semibold text-white">Full timeline lane</h3>
                    <span className="text-[11px] text-slate-500">
                      Group mode:{" "}
                      <span className="font-semibold text-slate-300">
                        {opsHistoricalTimelinePayload.filters.grouping}
                      </span>
                    </span>
                  </div>
                  <div className="mt-3 max-h-[28rem] space-y-4 overflow-auto rounded-2xl border border-white/10 bg-slate-950/40 p-3">
                    {opsHistoricalTimelinePayload.filters.grouping !== "none"
                    && opsHistoricalTimelinePayload.groups.length ? (
                      opsHistoricalTimelinePayload.groups.map((group) => (
                        <article key={`ops-grp-${group.group_key}`} className="rounded-xl border border-white/10 p-3">
                          <header className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                            {group.group_key.replace(/__/g, " · ") || "Grouped window"}
                          </header>
                          <ul className="mt-3 space-y-2">
                            {group.events.map((event) => (
                              <li
                                key={`ops-grp-ev-${event.stable_id}`}
                                className="flex gap-2 rounded-lg border border-white/5 bg-slate-950/55 px-2 py-2 text-xs text-slate-200"
                              >
                                <span
                                  className={`mt-1 inline-block size-2 shrink-0 rounded-full ${timelineDotClass(event)}`}
                                  aria-hidden
                                />
                                <div className="min-w-0 flex-1">
                                  <div className="flex flex-wrap gap-2 font-semibold text-white">
                                    <span>{describeHistoricalTimelineEvent(event)}</span>
                                    <span className="text-[10px] font-normal uppercase tracking-[0.12em] text-slate-500">
                                      {event.event_type.replace(/_/g, " ")}
                                    </span>
                                  </div>
                                  <p className="text-[11px] text-slate-500">{formatDateTime(event.occurred_at)}</p>
                                  <p className="text-[11px] text-slate-400">{event.publisher}</p>
                                  <p className="text-[11px] text-slate-400">
                                    {event.series_title} #{event.issue_number} · preorder track{" "}
                                    {event.preorder_track ? "yes" : "no"}
                                  </p>
                                  <Link
                                    to={`/inventory/${event.inventory_copy_id}`}
                                    className="inline-flex text-[11px] font-semibold text-cyan-200 hover:text-cyan-50"
                                  >
                                    Open #{event.inventory_copy_id}
                                  </Link>
                                </div>
                              </li>
                            ))}
                          </ul>
                        </article>
                      ))
                    ) : opsHistoricalTimelinePayload.events.length ? (
                      <ul className="space-y-2">
                        {opsHistoricalTimelinePayload.events.map((event) => (
                          <li
                            key={`ops-all-${event.stable_id}`}
                            className="flex gap-2 rounded-lg border border-white/10 bg-slate-950/50 px-2 py-2 text-xs text-slate-200"
                          >
                            <span
                              className={`mt-1 inline-block size-2 shrink-0 rounded-full ${timelineDotClass(event)}`}
                              aria-hidden
                            />
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap gap-2 font-semibold text-white">
                                <span>{describeHistoricalTimelineEvent(event)}</span>
                                <span className="text-[10px] font-normal uppercase tracking-[0.12em] text-slate-500">
                                  {event.event_type.replace(/_/g, " ")}
                                </span>
                              </div>
                              <p className="text-[11px] text-slate-500">{formatDateTime(event.occurred_at)}</p>
                              <p className="text-[11px] text-slate-400">{event.publisher}</p>
                              <p className="text-[11px] text-slate-400">{event.series_title} #{event.issue_number}</p>
                              <Link
                                to={`/inventory/${event.inventory_copy_id}`}
                                className="inline-flex text-[11px] font-semibold text-cyan-200 hover:text-cyan-50"
                              >
                                Open #{event.inventory_copy_id}
                              </Link>
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="py-10 text-center text-xs text-slate-500">
                        No deterministic events returned for filters (narrow range or widen window).
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ) : !opsHistoricalTimelineLoading ? (
              <p className="mt-6 text-xs text-slate-500">Timeline unavailable — reload after resolving error.</p>
            ) : (
              <p className="mt-6 text-sm text-slate-400">Initializing historical timeline lane…</p>
            )}
          </details>

          <details className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
            <summary className="cursor-pointer list-none text-sm font-semibold text-white">
              Global collection analytics
            </summary>
            <p className="mt-2 text-sm text-slate-400">
              Deterministic aggregates across every non-cancelled inventory copy in the fleet: publishers,
              fulfillment and ownership mix, preorder calendar gaps, OCR and canonical coverage, duplicate-ownership
              touch rates, graded versus raw splits, timeline buckets, and run-detection–derived series-completion
              signals. Read-only reporting only (no pricing, speculation, or metadata mutation).
            </p>
            {opsCollectionAnalyticsError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{opsCollectionAnalyticsError}</StatusBanner>
              </div>
            ) : null}
            {opsCollectionSummary && opsCollectionQuality && opsCollectionComposition ? (
              <>
                <p className="mt-3 text-xs text-slate-500">
                  As-of anchor:{" "}
                  <span className="font-semibold text-slate-300">
                    {opsCollectionSummary.generated_as_of_date}
                  </span>
                </p>
                <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                  <StatCard label="Total tracked copies" value={String(opsCollectionSummary.total_copies)} />
                  <StatCard label="Preorder copies" value={String(opsCollectionSummary.preorder_copies)} />
                  <StatCard label="In hand copies" value={String(opsCollectionSummary.in_hand_copies)} />
                  <StatCard
                    label="Preorder missing calendar"
                    value={String(opsCollectionSummary.preorder_missing_calendar_copies)}
                  />
                  <StatCard label="Graded copies" value={String(opsCollectionSummary.graded_copies)} />
                  <StatCard label="Raw copies" value={String(opsCollectionSummary.raw_copies)} />
                  <StatCard
                    label="Needs-review workload (distinct)"
                    value={String(opsCollectionSummary.unresolved_review_copies)}
                  />
                  <StatCard
                    label="Canonical-linked copies"
                    value={String(opsCollectionSummary.canonical_linked_copies)}
                  />
                  <StatCard
                    label="Unscanned primary covers"
                    value={String(opsCollectionSummary.unscanned_primary_copies)}
                  />
                  <StatCard
                    label="Publishers represented"
                    value={String(opsCollectionComposition.composition.publisher_concentration.publishers_represented)}
                  />
                  <StatCard
                    label="Top publisher share"
                    value={`${opsCollectionComposition.composition.publisher_concentration.top_publisher_share.percent}%`}
                  />
                </div>

                <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                  <h3 className="text-sm font-semibold text-white">Publisher concentration risk</h3>
                  <p className="mt-1 text-xs text-slate-400">
                    Share of tracked copies attributable to the single largest publisher (deterministic name sort for
                    tie-breaking upstream). surfaced as an exposure headline, not an investment signal.
                  </p>
                  <p className="mt-3 text-lg font-semibold text-amber-100">
                    {opsCollectionComposition.composition.publisher_concentration.top_publisher_share.percent}% of copies
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    (
                    {opsCollectionComposition.composition.publisher_concentration.top_publisher_share.numerator} /{" "}
                    {opsCollectionComposition.composition.publisher_concentration.top_publisher_share.denominator}{" "}
                    copies)
                  </p>
                </div>

                <div className="mt-5 rounded-2xl border border-rose-400/20 bg-rose-950/20 p-4">
                  <h3 className="text-sm font-semibold text-rose-100">Unhealthy / friction exposure (quality lane)</h3>
                  <p className="mt-1 text-xs text-slate-400">
                    Percentages use the same active-copy denominator as OCR quality eligibility. Use this to prioritize
                    pipeline hygiene—not customer worth.
                  </p>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                    <StatCard
                      label="Needs-review share (active scope)"
                      value={`${
                        opsCollectionQuality.inventory_quality.ocr_complete.denominator > 0
                          ? Math.round(
                              (opsCollectionSummary.unresolved_review_copies /
                                opsCollectionQuality.inventory_quality.ocr_complete.denominator) *
                                1000,
                            ) / 10
                          : 0
                      }%`}
                    />
                    <StatCard
                      label="OCR incomplete"
                      value={`${100 - opsCollectionQuality.inventory_quality.ocr_complete.percent}%`}
                    />
                    <StatCard
                      label="Canonical gap"
                      value={`${100 - opsCollectionQuality.inventory_quality.canonical_linked.percent}%`}
                    />
                    <StatCard
                      label="Dup ownership touch"
                      value={`${opsCollectionQuality.inventory_quality.duplicate_ownership_exposure_copies.percent}%`}
                    />
                    <StatCard
                      label="Open conflict touch"
                      value={`${opsCollectionQuality.inventory_quality.unresolved_open_conflict_copies.percent}%`}
                    />
                    <StatCard
                      label="Cover processing failed"
                      value={`${opsCollectionQuality.inventory_quality.primary_cover_failed_processing.percent}%`}
                    />
                    <StatCard
                      label="Latest OCR failed"
                      value={`${opsCollectionQuality.inventory_quality.primary_cover_failed_ocr.percent}%`}
                    />
                    <StatCard
                      label="Missing primary scan"
                      value={`${opsCollectionQuality.inventory_quality.missing_primary_scan.percent}%`}
                    />
                  </div>
                </div>

                <div className="mt-5 rounded-2xl border border-emerald-400/15 bg-emerald-950/10 p-4">
                  <h3 className="text-sm font-semibold text-emerald-100">Composition & preorder / fulfillment mix</h3>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                    <StatCard
                      label="Active preorder pipeline"
                      value={String(opsCollectionComposition.composition.preorder_active_copies)}
                    />
                    <StatCard
                      label="Active in-hand"
                      value={String(opsCollectionComposition.composition.in_hand_active_copies)}
                    />
                    <StatCard label="Cancelled (total)" value={String(opsCollectionComposition.composition.cancelled_copies)} />
                    <StatCard
                      label="Preorder vs owned (eligible)"
                      value={`${opsCollectionComposition.composition.preorder_vs_in_hand.percent}% preorder`}
                    />
                    <StatCard
                      label="Graded vs raw (eligible)"
                      value={`${opsCollectionComposition.composition.graded_vs_raw.percent}% graded`}
                    />
                    <StatCard
                      label="Cancelled vs owned (eligible)"
                      value={`${opsCollectionComposition.composition.cancelled_vs_owned.percent}% cancelled`}
                    />
                  </div>
                </div>

                <div className="mt-5 rounded-2xl border border-violet-400/20 bg-violet-950/15 p-4">
                  <h3 className="text-sm font-semibold text-violet-100">
                    Series signals (run detection intelligence attached)
                  </h3>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <StatCard
                      label="Limited / mini denominators"
                      value={String(
                        opsCollectionComposition.composition.series_signals.mini_series_limited_denominator_groups,
                      )}
                    />
                    <StatCard
                      label="Completed limited arcs"
                      value={String(
                        opsCollectionComposition.composition.series_signals.mini_series_completed_groups,
                      )}
                    />
                    <StatCard
                      label="Limited completion rate"
                      value={`${opsCollectionComposition.composition.series_signals.mini_series_completion_percent}%`}
                    />
                    <StatCard
                      label="Probable ongoing arcs"
                      value={String(
                        opsCollectionComposition.composition.series_signals.probable_ongoing_series_groups,
                      )}
                    />
                    <StatCard
                      label="Ongoing participation (copies)"
                      value={`${opsCollectionComposition.composition.series_signals.ongoing_series_participation_percent}%`}
                    />
                    <StatCard
                      label="Ongoing copy touches"
                      value={String(
                        opsCollectionComposition.composition.series_signals.probable_ongoing_series_copy_touch_count,
                      )}
                    />
                  </div>
                </div>

                {opsCollectionTimeline ? (
                  <div className="mt-5 grid gap-4 lg:grid-cols-2">
                    <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                      <h3 className="text-sm font-semibold text-white">Purchase-year concentration (top ten)</h3>
                      <div className="mt-3 overflow-x-auto">
                        <table className="w-full border-collapse text-left text-xs">
                          <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                            <tr>
                              <th className="pb-2 pr-3 font-medium">Year</th>
                              <th className="pb-2 font-medium">Copies</th>
                            </tr>
                          </thead>
                          <tbody className="text-slate-200">
                            {[...opsCollectionTimeline.timeline.by_purchase_year]
                              .sort((a, b) => Number(b.year_key) - Number(a.year_key))
                              .slice(0, 10)
                              .map((row) => (
                                <tr key={`purchase-${row.year_key}`} className="border-t border-white/5">
                                  <td className="py-2 pr-3">{row.year_key}</td>
                                  <td className="py-2">{row.copies}</td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                      <h3 className="text-sm font-semibold text-white">Upcoming preorder calendar buckets</h3>
                      <p className="mt-1 text-xs text-slate-400">
                        Preorder copies grouped by earliest known release-month bucket still in front of the as-of anchor.
                      </p>
                      <div className="mt-3 overflow-x-auto">
                        <table className="w-full border-collapse text-left text-xs">
                          <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                            <tr>
                              <th className="pb-2 pr-3 font-medium">First bucket</th>
                              <th className="pb-2 font-medium">Preorder copies</th>
                            </tr>
                          </thead>
                          <tbody className="text-slate-200">
                            {opsCollectionTimeline.timeline.upcoming_preorder_calendar.length ? (
                              opsCollectionTimeline.timeline.upcoming_preorder_calendar.map((row) => (
                                <tr key={`up-${row.first_release_bucket}`} className="border-t border-white/5">
                                  <td className="py-2 pr-3 font-mono">{row.first_release_bucket}</td>
                                  <td className="py-2">{row.preorder_copies}</td>
                                </tr>
                              ))
                            ) : (
                              <tr className="border-t border-white/5">
                                <td className="py-3 text-slate-500" colSpan={2}>
                                  No forward-looking preorder buckets for this anchor.
                                </td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                ) : null}

                {opsCollectionPublishers && opsCollectionPublishers.publishers.length ? (
                  <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                    <h3 className="text-sm font-semibold text-white">Publisher breakdown (first twenty)</h3>
                    <p className="mt-1 text-xs text-slate-500">Deterministic alphabetical ordering.</p>
                    <div className="mt-3 overflow-auto">
                      <table className="w-full border-collapse text-left text-xs">
                        <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                          <tr>
                            <th className="pb-2 pr-3 font-medium">Publisher</th>
                            <th className="pb-2 pr-3 font-medium">Copies</th>
                            <th className="pb-2 pr-3 font-medium">In hand</th>
                            <th className="pb-2 pr-3 font-medium">Preorder</th>
                            <th className="pb-2 pr-3 font-medium">Needs review</th>
                            <th className="pb-2 font-medium">Canon-linked</th>
                          </tr>
                        </thead>
                        <tbody className="text-slate-200">
                          {opsCollectionPublishers.publishers.slice(0, 20).map((row) => (
                            <tr key={row.publisher_name} className="border-t border-white/5 align-top">
                              <td className="py-2 pr-3 font-medium text-white">{row.publisher_name}</td>
                              <td className="py-2 pr-3">{row.total_copies}</td>
                              <td className="py-2 pr-3">{row.in_hand_copies}</td>
                              <td className="py-2 pr-3">{row.preorder_copies}</td>
                              <td className="py-2 pr-3">{row.unresolved_review_copies}</td>
                              <td className="py-2">{row.canonical_linked_copies}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : null}
              </>
            ) : !opsCollectionAnalyticsError ? (
              <p className="mt-4 text-sm text-slate-400">Loading global collection analytics…</p>
            ) : null}
          </details>

          <details className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
            <summary className="cursor-pointer list-none text-sm font-semibold text-white">
              Duplicate ownership intelligence (all accounts)
            </summary>
            <p className="mt-2 text-sm text-slate-400">
              Cross-user visibility for deterministic multi-copy clusters. Inputs mirror the owner lane—metadata
              identity keys, duplicate-scan intelligence, pending canonical edges, pending duplicate-inventory reviews,
              preorder + in-hand overlaps, graded + raw coexistence, and active human duplicate/same-cover approvals.
              Purely read-only: no dedupe, deletes, or silent metadata mutation ships from this surface.
            </p>
            <div className="mt-4 flex flex-wrap gap-4">
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Duplicate-scan signal filter
                <select
                  className="rounded-2xl border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  value={duplicateOwnershipDupScanOps}
                  onChange={(event) =>
                    setDuplicateOwnershipDupScanOps(event.target.value as DuplicateScanClassificationFilter)
                  }
                >
                  <option value="all">All</option>
                  <option value="confirmed">Confirmed</option>
                  <option value="probable">Probable</option>
                  <option value="suppressed">Suppressed</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Ownership classification
                <select
                  className="rounded-2xl border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  value={duplicateOwnershipClassificationOps}
                  onChange={(event) =>
                    setDuplicateOwnershipClassificationOps(
                      event.target.value === "all" ? "all" : (event.target.value as DuplicateOwnershipClassification),
                    )
                  }
                >
                  <option value="all">All</option>
                  <option value="intentional_multi_copy">Intentional multi-copy</option>
                  <option value="probable_accidental_duplicate">Probable accidental duplicate</option>
                  <option value="duplicate_scan_only">Duplicate scan match</option>
                  <option value="preorder_plus_owned">Preorder + received copy</option>
                  <option value="graded_plus_raw">Graded + raw pairing</option>
                  <option value="unresolved_duplicate">Unresolved duplicate review</option>
                </select>
              </label>
            </div>
            {duplicateOwnershipOpsError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{duplicateOwnershipOpsError}</StatusBanner>
              </div>
            ) : null}
            {duplicateOwnershipOpsLoading ? (
              <p className="mt-4 text-sm text-slate-400">Loading duplicate ownership intelligence…</p>
            ) : duplicateOwnershipOps ? (
              <>
                <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                  <StatCard
                    label="Total clusters"
                    value={String(duplicateOwnershipOps.summary.total_groups)}
                  />
                  <StatCard
                    label="Probable accidental"
                    value={String(duplicateOwnershipOps.summary.probable_accidental_duplicate_groups)}
                  />
                  <StatCard
                    label="Preorder + received"
                    value={String(duplicateOwnershipOps.summary.preorder_plus_owned_groups)}
                  />
                  <StatCard
                    label="Graded + raw"
                    value={String(duplicateOwnershipOps.summary.graded_plus_raw_groups)}
                  />
                  <StatCard
                    label="Duplicate-scan only"
                    value={String(duplicateOwnershipOps.summary.duplicate_scan_only_groups)}
                  />
                  <StatCard
                    label="Unresolved duplicate review"
                    value={String(duplicateOwnershipOps.summary.unresolved_duplicate_groups)}
                  />
                </div>
                <div className="mt-5 overflow-x-auto rounded-2xl border border-white/10">
                  <table className="min-w-full divide-y divide-white/10 text-left text-sm text-slate-200">
                    <thead className="bg-white/5 text-xs uppercase tracking-wide text-slate-400">
                      <tr>
                        <th className="px-4 py-3">Owner user</th>
                        <th className="px-4 py-3">Group key</th>
                        <th className="px-4 py-3">Classification</th>
                        <th className="px-4 py-3">Inventory copies</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {duplicateOwnershipOps.groups.length ? (
                        duplicateOwnershipOps.groups.slice(0, 200).map((group: DuplicateOwnershipGroup) => (
                          <tr key={group.group_key} className="align-top">
                            <td className="px-4 py-3 font-mono text-xs">
                              {group.owner_user_id != null ? group.owner_user_id : "—"}
                            </td>
                            <td className="max-w-[14rem] break-all px-4 py-3 font-mono text-[11px] text-slate-300">
                              {group.group_key}
                            </td>
                            <td className="px-4 py-3 text-xs text-slate-100">
                              {duplicateOwnershipClassificationLabel(group.classification)}
                              {group.signal_flags?.pending_duplicate_inventory_review ? (
                                <span className="mt-2 block text-[11px] text-rose-200">
                                  Pins pending duplicate-inventory candidate review metadata key.
                                </span>
                              ) : null}
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex flex-wrap gap-2">
                                {group.inventory_copy_ids.map((inventoryId) => (
                                  <Link
                                    key={`${group.group_key}-${inventoryId}`}
                                    to={`/inventory/${inventoryId}`}
                                    className="rounded-full border border-white/15 px-2 py-0.5 text-[11px] font-semibold text-white transition hover:border-cyan-300/60"
                                  >
                                    #{inventoryId}
                                  </Link>
                                ))}
                              </div>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                            No duplicate ownership overlaps detected under the current deterministic filters.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                {duplicateOwnershipOps.groups.length > 200 ? (
                  <p className="mt-3 text-xs text-slate-500">
                    Showing the first 200 rows. Adjust filters via query parameters on `/ops/duplicate-ownership` to narrow
                    the feed.
                  </p>
                ) : null}
              </>
            ) : (
              <p className="mt-4 text-sm text-slate-400">Duplicate ownership rollup unavailable.</p>
            )}
          </details>

          <details className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
            <summary className="cursor-pointer list-none text-sm font-semibold text-white">
              Run detection intelligence (all accounts)
            </summary>
            <p className="mt-2 text-sm text-slate-400">
              Cross-user deterministic series progress and missing-issue visibility. This lane uses canonical series
              identity, issue-number ordering, release timing, preorder state, and pending canonical review pins only.
              It does not mutate metadata or create wantlist entries.
            </p>
            <div className="mt-4 flex flex-wrap gap-4">
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Series status
                <select
                  className="rounded-2xl border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  value={runDetectionStatusOps}
                  onChange={(event) =>
                    setRunDetectionStatusOps(
                      event.target.value === "all" ? "all" : (event.target.value as RunDetectionSeriesStatus),
                    )
                  }
                >
                  <option value="all">All</option>
                  <option value="partial_run">Partial run</option>
                  <option value="complete_limited_series">Complete limited series</option>
                  <option value="incomplete_limited_series">Incomplete limited series</option>
                  <option value="probable_ongoing_series">Probable ongoing series</option>
                  <option value="isolated_special_annual">Special / annual isolated</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Missing issue classification
                <select
                  className="rounded-2xl border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  value={missingIssueOpsClassification}
                  onChange={(event) =>
                    setMissingIssueOpsClassification(
                      event.target.value === "all" ? "all" : (event.target.value as MissingIssueClassification),
                    )
                  }
                >
                  <option value="all">All</option>
                  <option value="confirmed_missing">Confirmed missing</option>
                  <option value="likely_missing">Likely missing</option>
                  <option value="unreleased_future_issue">Unreleased future issue</option>
                  <option value="preorder_pending">Preorder pending</option>
                  <option value="unresolved_identity_gap">Unresolved identity gap</option>
                </select>
              </label>
            </div>
            {runDetectionOpsError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{runDetectionOpsError}</StatusBanner>
              </div>
            ) : null}
            {runDetectionOpsLoading ? (
              <p className="mt-4 text-sm text-slate-400">Loading run detection intelligence…</p>
            ) : runDetectionOps ? (
              <>
                <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                  <StatCard label="Tracked series" value={String(runDetectionOps.summary.total_series_groups)} />
                  <StatCard label="Partial runs" value={String(runDetectionOps.summary.partial_run_groups)} />
                  <StatCard
                    label="Completed limited"
                    value={String(runDetectionOps.summary.complete_limited_series_groups)}
                  />
                  <StatCard
                    label="Incomplete limited"
                    value={String(runDetectionOps.summary.incomplete_limited_series_groups)}
                  />
                  <StatCard
                    label="Probable ongoing"
                    value={String(runDetectionOps.summary.probable_ongoing_series_groups)}
                  />
                  <StatCard
                    label="Unresolved identity gaps"
                    value={String(runDetectionOps.summary.unresolved_identity_gap_rows)}
                  />
                </div>
                <div className="mt-5 overflow-x-auto rounded-2xl border border-white/10">
                  <table className="min-w-full divide-y divide-white/10 text-left text-sm text-slate-200">
                    <thead className="bg-white/5 text-xs uppercase tracking-wide text-slate-400">
                      <tr>
                        <th className="px-4 py-3">Owner user</th>
                        <th className="px-4 py-3">Series</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Owned issues</th>
                        <th className="px-4 py-3">Missing / pending</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {runDetectionOps.series_groups.length ? (
                        runDetectionOps.series_groups.slice(0, 200).map((group: RunDetectionSeries) => {
                          const visibleMissing = group.missing_issues.filter((row) =>
                            missingIssueOpsClassification === "all"
                              ? true
                              : row.classification === missingIssueOpsClassification,
                          );
                          return (
                            <tr key={`${group.owner_user_id}-${group.series_key}`} className="align-top">
                              <td className="px-4 py-3 font-mono text-xs">{group.owner_user_id ?? "—"}</td>
                              <td className="px-4 py-3">
                                <p className="font-medium text-white">
                                  {group.publisher} | {group.title}
                                </p>
                                <p className="mt-1 font-mono text-[11px] text-slate-400">{group.series_key}</p>
                              </td>
                              <td className="px-4 py-3 text-xs text-slate-100">
                                {runDetectionStatusLabel(group.series_status)}
                              </td>
                              <td className="px-4 py-3 text-xs text-slate-300">
                                {group.owned_issue_numbers.length ? group.owned_issue_numbers.join(", ") : "—"}
                              </td>
                              <td className="px-4 py-3 text-xs text-slate-300">
                                {visibleMissing.length ? (
                                  <div className="space-y-1">
                                    {visibleMissing.map((item, idx) => (
                                      <p key={`${group.series_key}-${idx}`}>
                                        <span className="font-semibold text-slate-100">
                                          {item.issue_number ?? "identity"}
                                        </span>{" "}
                                        <span className="text-slate-500">({item.classification.replace(/_/g, " ")})</span>
                                      </p>
                                    ))}
                                  </div>
                                ) : (
                                  "No rows under current missing filter."
                                )}
                              </td>
                            </tr>
                          );
                        })
                      ) : (
                        <tr>
                          <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                            No run-detection groups matched the current deterministic filters.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <p className="mt-4 text-sm text-slate-400">Run detection rollup unavailable.</p>
            )}
          </details>

          <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-white">Cover OCR pipeline health</p>
                <p className="mt-1 text-xs text-slate-400">
                  Rolling {dashboard.pipeline_health.window_hours}-hour visibility window · cutoff{" "}
                  {formatDateTime(dashboard.pipeline_health.cutoff_utc)}
                </p>
              </div>
              <button
                type="button"
                disabled={pipelineRecoverBusy}
                onClick={() => {
                  void handleOcrPipelineRecover();
                }}
                className="rounded-2xl border border-cyan-400/40 bg-cyan-400/15 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:border-cyan-300 disabled:opacity-40"
              >
                {pipelineRecoverBusy ? "Recovering…" : "Recover stale rows"}
              </button>
            </div>
            {pipelineRecoverMessage ? (
              <div className="mt-3">
                <StatusBanner
                  tone={pipelineRecoverMessage.startsWith("Recovery complete") ? "success" : "error"}
                >
                  {pipelineRecoverMessage}
                </StatusBanner>
              </div>
            ) : null}
            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              <StatCard
                label="Failed OCR (window)"
                value={String(dashboard.pipeline_health.failed_ocr_results)}
              />
              <StatCard
                label="Tesseract timeouts"
                value={String(dashboard.pipeline_health.ocr_tesseract_timeouts)}
              />
              <StatCard
                label="Corrupt image"
                value={String(dashboard.pipeline_health.corrupt_image_failures)}
              />
              <StatCard
                label="Batch retry exhausted"
                value={String(dashboard.pipeline_health.retry_exhausted_batch_items)}
              />
              <StatCard
                label="Replay failures"
                value={String(dashboard.pipeline_health.replay_failed_items_total)}
              />
              <StatCard
                label="Stale rows (OCR/batch/replay)"
                value={String(
                  dashboard.pipeline_health.stale_cover_ocr_processing +
                    dashboard.pipeline_health.stale_batch_items +
                    dashboard.pipeline_health.stale_replay_running_items,
                )}
              />
            </div>
            <div className="mt-6">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Recent cover pipeline jobs
              </p>
              <div className="mt-2 overflow-x-auto rounded-2xl border border-white/10">
                <table className="min-w-full divide-y divide-white/10 text-left text-sm">
                  <thead className="bg-white/5 text-xs uppercase text-slate-400">
                    <tr>
                      <th className="px-4 py-2">Job</th>
                      <th className="px-4 py-2">Type</th>
                      <th className="px-4 py-2">Queue</th>
                      <th className="px-4 py-2">Status</th>
                      <th className="px-4 py-2">Ended</th>
                      <th className="px-4 py-2">Error</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 text-slate-200">
                    {dashboard.recent_cover_pipeline_jobs.length ? (
                      dashboard.recent_cover_pipeline_jobs.map((job) => (
                        <tr key={job.job_id} className="align-top">
                          <td className="px-4 py-2 font-mono text-xs">{job.job_id}</td>
                          <td className="px-4 py-2">{job.job_type}</td>
                          <td className="px-4 py-2">{job.queue_name}</td>
                          <td className="px-4 py-2 capitalize">{job.status}</td>
                          <td className="px-4 py-2 text-xs text-slate-400">
                            {job.ended_at ? formatDateTime(job.ended_at) : "—"}
                          </td>
                          <td className="max-w-xs break-words px-4 py-2 text-xs text-rose-200">
                            {job.error ?? "—"}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="px-4 py-4 text-slate-400" colSpan={6}>
                          No recent cover pipeline jobs found in worker queues.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="mt-6">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Recent human cover link decisions
              </p>
              <div className="mt-2 overflow-x-auto rounded-2xl border border-white/10">
                <table className="min-w-full divide-y divide-white/10 text-left text-sm">
                  <thead className="bg-white/5 text-xs uppercase text-slate-400">
                    <tr>
                      <th className="px-4 py-2">Decision</th>
                      <th className="px-4 py-2">Pair</th>
                      <th className="px-4 py-2">State</th>
                      <th className="px-4 py-2">Reviewer</th>
                      <th className="px-4 py-2">Reason</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 text-slate-200">
                    {coverLinkDecisions.length > 0 ? (
                      coverLinkDecisions.map((decision) => (
                        <tr key={decision.id} className="align-top">
                          <td className="px-4 py-2">
                            {decision.decision_type.replace(/_/g, " ")} ·{" "}
                            {decision.relationship_type.replace(/_/g, " ")}
                          </td>
                          <td className="px-4 py-2 font-mono text-xs">
                            #{decision.source_cover_image_id} ↔ #{decision.candidate_cover_image_id}
                          </td>
                          <td className="px-4 py-2">
                            {decision.decision_state}
                            {decision.reverted_at ? ` · reverted ${formatDateTime(decision.reverted_at)}` : ""}
                          </td>
                          <td className="px-4 py-2">{decision.reviewer_user_email ?? "—"}</td>
                          <td className="max-w-xs break-words px-4 py-2 text-xs text-slate-300">
                            {decision.decision_reason ?? "—"}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="px-4 py-4 text-slate-400" colSpan={5}>
                          No cover link decisions recorded yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="mt-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Duplicate scan intelligence (cross-cover clusters)
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Derived from persistent signals only (exact SHA256, fingerprint probable pairings, probable
                    duplicate-scan groupings, human duplicate-scan confirmations). UPC overlaps are supplementary; OCR-only
                    title/issue ties are excluded. Nothing here modifies inventory or cover metadata.
                  </p>
                </div>
                <label className="text-xs text-slate-300">
                  Classification
                  <select
                    value={duplicateScanClustersFilter}
                    onChange={(event) =>
                      setDuplicateScanClustersFilter(event.target.value as DuplicateScanClassificationFilter)
                    }
                    className="ml-2 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-sm text-white"
                  >
                    <option value="all">All actionable</option>
                    <option value="confirmed">Confirmed</option>
                    <option value="probable">Probable</option>
                    <option value="suppressed">Suppressed pairs only</option>
                  </select>
                </label>
              </div>
              {duplicateScanClustersError ? (
                <div className="mt-3">
                  <StatusBanner tone="error">{duplicateScanClustersError}</StatusBanner>
                </div>
              ) : null}
              {duplicateScanClustersLoading ? (
                <p className="mt-3 text-xs text-slate-500">Loading duplicate-scan clusters…</p>
              ) : duplicateScanClustersData &&
                duplicateScanClustersData.clusters.length === 0 &&
                duplicateScanClustersData.suppressed_pairs.length === 0 ? (
                <p className="mt-3 text-xs text-slate-500">
                  No clusters or suppressed pairwise rows for filter &quot;{duplicateScanClustersData.classification_filter}
                  &quot;.
                </p>
              ) : duplicateScanClustersData ? (
                <div className="mt-3 space-y-4">
                  {duplicateScanClustersData.clusters.length > 0 ? (
                    <div className="overflow-x-auto rounded-2xl border border-white/10">
                      <table className="min-w-full divide-y divide-white/10 text-left text-sm">
                        <thead className="bg-white/5 text-xs uppercase text-slate-400">
                          <tr>
                            <th className="px-4 py-2">Cluster</th>
                            <th className="px-4 py-2">Size</th>
                            <th className="px-4 py-2">Classification</th>
                            <th className="px-4 py-2">Evidence strength</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5 text-slate-200">
                          {duplicateScanClustersData.clusters.map((cluster) => (
                            <tr key={cluster.cluster_key} className="align-top">
                              <td className="px-4 py-2 font-mono text-xs">
                                {cluster.cover_image_ids.map((coverIdNum) => (
                                  <span key={coverIdNum} className="mr-2">
                                    #{coverIdNum}
                                  </span>
                                ))}
                                <p className="mt-1 break-all text-[10px] text-slate-600">{cluster.cluster_key}</p>
                              </td>
                              <td className="px-4 py-2">{cluster.cluster_size}</td>
                              <td className="px-4 py-2 capitalize">{cluster.classification}</td>
                              <td className="px-4 py-2">{cluster.evidence_strength.replace(/_/g, " ")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                  {duplicateScanClustersData.suppressed_pairs.length > 0 ? (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Suppressed pairwise signals (active unrelated decisions)
                      </p>
                      <div className="mt-2 overflow-x-auto rounded-2xl border border-amber-400/20 bg-amber-500/5">
                        <table className="min-w-full divide-y divide-amber-500/15 text-left text-sm">
                          <thead className="bg-amber-500/10 text-xs uppercase text-amber-100/70">
                            <tr>
                              <th className="px-4 py-2">Pair</th>
                              <th className="px-4 py-2">Labels</th>
                              <th className="px-4 py-2">Snapshot</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-amber-500/10 text-slate-100">
                            {duplicateScanClustersData.suppressed_pairs.map((suppressed) => (
                              <tr key={suppressed.pair_key} className="align-top">
                                <td className="px-4 py-2 font-mono text-xs">
                                  #{suppressed.left_cover_image_id} ↔ #{suppressed.right_cover_image_id}
                                  <p className="mt-1 text-[10px] text-slate-500">{suppressed.pair_key}</p>
                                </td>
                                <td className="px-4 py-2 text-xs">{suppressed.suppressed_signal_labels.join(", ") || "—"}</td>
                                <td className="px-4 py-2 text-xs text-slate-400">
                                  {[
                                    suppressed.evidence_snapshot.sha256_exact_match ? "SHA256" : "",
                                    suppressed.evidence_snapshot.fingerprint_similarity_probable ? "fingerprint" : "",
                                    suppressed.evidence_snapshot.probable_duplicate_scan_match_group
                                      ? "dup-scan group"
                                      : "",
                                  ]
                                    .filter(Boolean)
                                    .join(", ") || "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
            <div className="mt-6 rounded-lg border border-violet-400/25 bg-violet-500/[0.04] p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-violet-200/90">
                    Variant family intelligence — cross-cover clusters
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Probable grouping, same-issue divergent fingerprints, normalized metadata anchors, supporting UPC echoes,
                    and active human-approved variant_family links (duplicate-scan relationships block variant edges). Fully
                    read-only.
                  </p>
                </div>
                <label className="text-xs text-slate-300">
                  Classification
                  <select
                    value={variantFamilyClustersFilter}
                    onChange={(event) =>
                      setVariantFamilyClustersFilter(event.target.value as VariantFamilyClassificationFilter)
                    }
                    className="ml-2 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-sm text-white"
                  >
                    <option value="all">All actionable</option>
                    <option value="confirmed">Confirmed</option>
                    <option value="probable">Probable</option>
                    <option value="suppressed">Suppressed pairs only</option>
                  </select>
                </label>
              </div>
              {variantFamilyClustersError ? (
                <div className="mt-3">
                  <StatusBanner tone="error">{variantFamilyClustersError}</StatusBanner>
                </div>
              ) : null}
              {variantFamilyClustersLoading ? (
                <p className="mt-3 text-xs text-slate-500">Loading variant-family clusters…</p>
              ) : variantFamilyClustersData &&
                variantFamilyClustersData.clusters.length === 0 &&
                variantFamilyClustersData.suppressed_pairs.length === 0 ? (
                <p className="mt-3 text-xs text-slate-500">
                  No variant clusters for filter &quot;{variantFamilyClustersData.classification_filter}&quot;.
                </p>
              ) : variantFamilyClustersData ? (
                <div className="mt-3 space-y-4">
                  {variantFamilyClustersData.clusters.length > 0 ? (
                    <div className="overflow-x-auto rounded-2xl border border-white/10">
                      <table className="min-w-full divide-y divide-white/10 text-left text-sm">
                        <thead className="bg-white/5 text-xs uppercase text-slate-400">
                          <tr>
                            <th className="px-4 py-2">Cluster</th>
                            <th className="px-4 py-2">Size</th>
                            <th className="px-4 py-2">Classification</th>
                            <th className="px-4 py-2">Evidence strength</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5 text-slate-200">
                          {variantFamilyClustersData.clusters.map((vc) => (
                            <tr key={vc.cluster_key} className="align-top">
                              <td className="px-4 py-2 font-mono text-xs">
                                {vc.cover_image_ids.map((idn) => (
                                  <span key={idn} className="mr-2">
                                    #{idn}
                                  </span>
                                ))}
                                <p className="mt-1 break-all text-[10px] text-slate-600">{vc.cluster_key}</p>
                              </td>
                              <td className="px-4 py-2">{vc.cluster_size}</td>
                              <td className="px-4 py-2 capitalize">{vc.classification}</td>
                              <td className="px-4 py-2">{vc.evidence_strength.replace(/_/g, " ")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                  {variantFamilyClustersData.suppressed_pairs.length > 0 ? (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Suppressed variant-family suggestions (active unrelated decisions)
                      </p>
                      <div className="mt-2 overflow-x-auto rounded-2xl border border-violet-400/20 bg-violet-500/5">
                        <table className="min-w-full divide-y divide-violet-500/15 text-left text-sm">
                          <thead className="bg-violet-500/10 text-xs uppercase text-violet-100/70">
                            <tr>
                              <th className="px-4 py-2">Pair</th>
                              <th className="px-4 py-2">Labels</th>
                              <th className="px-4 py-2">Snapshot</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-violet-500/15 text-slate-100">
                            {variantFamilyClustersData.suppressed_pairs.map((spf) => (
                              <tr key={spf.pair_key} className="align-top">
                                <td className="px-4 py-2 font-mono text-xs">
                                  #{spf.left_cover_image_id} ↔ #{spf.right_cover_image_id}
                                  <p className="mt-1 text-[10px] text-slate-500">{spf.pair_key}</p>
                                </td>
                                <td className="px-4 py-2 text-xs">{spf.suppressed_signal_labels.join(", ") || "—"}</td>
                                <td className="px-4 py-2 text-xs text-slate-400">
                                  {[
                                    spf.evidence_snapshot.probable_variant_family_group ? "variant grouping" : "",
                                    spf.evidence_snapshot.same_issue_divergent_fingerprint ? "divergent fp" : "",
                                    spf.evidence_snapshot.metadata_identity_normalized ? "metadata id" : "",
                                  ]
                                    .filter(Boolean)
                                    .join(", ") || "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
            <div className="mt-6 rounded-lg border border-cyan-400/25 bg-cyan-500/[0.04] p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-cyan-100/90">
                    Canonical issue suggestion review artifacts
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Deterministic review-only suggestions for canonical issue linking. Variant-family and duplicate-scan
                    context can support review, but nothing here writes canonical ids back onto inventory or cover records.
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <label className="text-xs text-slate-300">
                    Review state
                    <select
                      value={canonicalSuggestionReviewState}
                      onChange={(event) =>
                        setCanonicalSuggestionReviewState(
                          event.target.value as CanonicalIssueSuggestionReviewState | "all",
                        )
                      }
                      className="ml-2 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-sm text-white"
                    >
                      <option value="all">All</option>
                      <option value="pending">Pending</option>
                      <option value="approved">Approved</option>
                      <option value="rejected">Rejected</option>
                      <option value="ignored">Ignored</option>
                    </select>
                  </label>
                  <label className="text-xs text-slate-300">
                    Confidence
                    <select
                      value={canonicalSuggestionConfidenceBucket}
                      onChange={(event) =>
                        setCanonicalSuggestionConfidenceBucket(
                          event.target.value as CanonicalIssueSuggestionConfidenceBucket | "all",
                        )
                      }
                      className="ml-2 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-sm text-white"
                    >
                      <option value="all">All</option>
                      <option value="very_high">Very high</option>
                      <option value="high">High</option>
                      <option value="medium">Medium</option>
                      <option value="low">Low</option>
                      <option value="very_low">Very low</option>
                    </select>
                  </label>
                  <label className="text-xs text-slate-300">
                    Type
                    <select
                      value={canonicalSuggestionType}
                      onChange={(event) =>
                        setCanonicalSuggestionType(event.target.value as CanonicalIssueSuggestionType | "all")
                      }
                      className="ml-2 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-sm text-white"
                    >
                      <option value="all">All</option>
                      <option value="exact_identity_key">Exact identity key</option>
                      <option value="normalized_title_issue_publisher">Title + issue + publisher</option>
                      <option value="normalized_title_issue">Title + issue</option>
                      <option value="relationship_context">Relationship context</option>
                      <option value="variant_family_context">Variant family context</option>
                      <option value="duplicate_scan_context">Duplicate scan context</option>
                    </select>
                  </label>
                </div>
              </div>
              {canonicalSuggestionsError ? (
                <div className="mt-3">
                  <StatusBanner tone="error">{canonicalSuggestionsError}</StatusBanner>
                </div>
              ) : null}
              {canonicalSuggestionsLoading ? (
                <p className="mt-3 text-xs text-slate-500">Loading canonical issue suggestions…</p>
              ) : canonicalSuggestionsData && canonicalSuggestionsData.suggestions.length === 0 ? (
                <p className="mt-3 text-xs text-slate-500">No canonical issue suggestions for the active filters.</p>
              ) : canonicalSuggestionsData ? (
                <div className="mt-3 overflow-x-auto rounded-2xl border border-white/10">
                  <table className="min-w-full divide-y divide-white/10 text-left text-sm">
                    <thead className="bg-white/5 text-xs uppercase text-slate-400">
                      <tr>
                        <th className="px-4 py-2">Cover</th>
                        <th className="px-4 py-2">Target</th>
                        <th className="px-4 py-2">Type</th>
                        <th className="px-4 py-2">Confidence</th>
                        <th className="px-4 py-2">Review</th>
                        <th className="px-4 py-2">Evidence</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 text-slate-200">
                      {canonicalSuggestionsData.suggestions.map((row) => (
                        <tr key={row.id} className="align-top">
                          <td className="px-4 py-2 font-mono text-xs">#{row.cover_image_id}</td>
                          <td className="px-4 py-2 text-xs">
                            issue #{row.canonical_issue_id ?? "?"}
                            <p className="mt-1 text-[10px] text-slate-500">
                              series {row.canonical_series_id ?? "—"} · publisher {row.canonical_publisher_id ?? "—"}
                            </p>
                          </td>
                          <td className="px-4 py-2 text-xs">{row.suggestion_type.replace(/_/g, " ")}</td>
                          <td className="px-4 py-2 text-xs">
                            {row.confidence_bucket} · {row.deterministic_score.toFixed(2)}
                          </td>
                          <td className="px-4 py-2 text-xs">
                            {row.review_state}
                            {row.reviewed_by_email ? ` · ${row.reviewed_by_email}` : ""}
                          </td>
                          <td className="max-w-md break-words px-4 py-2 text-xs text-slate-400">
                            {row.suggested_metadata_identity_key ?? "—"}
                            <p className="mt-1">
                              {Object.entries(row.evidence_json)
                                .slice(0, 4)
                                .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`)
                                .join(" · ") || "—"}
                            </p>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
            <div className="mt-6 rounded-lg border border-amber-400/25 bg-amber-500/[0.04] p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-amber-100/90">
                    Relationship conflict detection
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Deterministic conflict visibility across relationship decisions, graph edges, duplicate-scan /
                    variant-family intelligence, canonical suggestions, stale match confidence, and preorder reconciliation
                    warnings. Detection only; nothing auto-corrects or mutates metadata.
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => void handleDetectRelationshipConflicts()}
                    disabled={relationshipConflictsDetectBusy}
                    className="rounded-lg border border-amber-300/30 bg-amber-400/10 px-3 py-2 text-xs font-semibold text-amber-100 transition hover:border-amber-200/60 hover:bg-amber-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {relationshipConflictsDetectBusy ? "Detecting…" : "Bulk detect conflicts"}
                  </button>
                  <label className="text-xs text-slate-300">
                    Severity
                    <select
                      value={relationshipConflictSeverity}
                      onChange={(event) =>
                        setRelationshipConflictSeverity(event.target.value as RelationshipConflictSeverity | "all")
                      }
                      className="ml-2 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-sm text-white"
                    >
                      <option value="all">All</option>
                      <option value="critical">Critical</option>
                      <option value="warning">Warning</option>
                      <option value="info">Info</option>
                    </select>
                  </label>
                  <label className="text-xs text-slate-300">
                    Status
                    <select
                      value={relationshipConflictStatus}
                      onChange={(event) =>
                        setRelationshipConflictStatus(event.target.value as RelationshipConflictStatus | "all")
                      }
                      className="ml-2 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-sm text-white"
                    >
                      <option value="all">All</option>
                      <option value="open">Open</option>
                      <option value="acknowledged">Acknowledged</option>
                      <option value="dismissed">Dismissed</option>
                      <option value="resolved">Resolved</option>
                    </select>
                  </label>
                  <label className="text-xs text-slate-300">
                    Type
                    <select
                      value={relationshipConflictType}
                      onChange={(event) =>
                        setRelationshipConflictType(event.target.value as RelationshipConflictType | "all")
                      }
                      className="ml-2 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-sm text-white"
                    >
                      <option value="all">All</option>
                      <option value="duplicate_scan_vs_variant_family">dup scan vs variant family</option>
                      <option value="same_cover_vs_variant_family">same cover vs variant family</option>
                      <option value="same_issue_vs_unrelated">same issue vs unrelated</option>
                      <option value="approved_link_vs_rejected_link">approved vs rejected</option>
                      <option value="canonical_suggestion_mismatch">canonical suggestion mismatch</option>
                      <option value="duplicate_scan_different_canonical_issue">dup scan / canonical mismatch</option>
                      <option value="variant_family_same_fingerprint">variant family same fingerprint</option>
                      <option value="relationship_cycle_warning">relationship cycle</option>
                      <option value="stale_confidence_after_decision">stale confidence</option>
                      <option value="preorder_not_in_hand_reconciliation_warning">preorder reconciliation</option>
                    </select>
                  </label>
                </div>
              </div>
              {relationshipConflictsDetectMessage ? (
                <div className="mt-3">
                  <StatusBanner tone="info">{relationshipConflictsDetectMessage}</StatusBanner>
                </div>
              ) : null}
              {relationshipConflictsError ? (
                <div className="mt-3">
                  <StatusBanner tone="error">{relationshipConflictsError}</StatusBanner>
                </div>
              ) : null}
              {relationshipConflictsLoading ? (
                <p className="mt-3 text-xs text-slate-500">Loading relationship conflicts…</p>
              ) : relationshipConflictsData && relationshipConflictsData.conflicts.length === 0 ? (
                <p className="mt-3 text-xs text-slate-500">No relationship conflicts for the active filters.</p>
              ) : relationshipConflictsData ? (
                <div className="mt-3 space-y-3">
                  <div className="flex flex-wrap gap-2 text-xs text-slate-400">
                    <span>Total {relationshipConflictsData.total_count}</span>
                    <span>Open {relationshipConflictsData.open_count}</span>
                    <span>Ack {relationshipConflictsData.acknowledged_count}</span>
                    <span>Dismissed {relationshipConflictsData.dismissed_count}</span>
                    <span>Resolved {relationshipConflictsData.resolved_count}</span>
                  </div>
                  <div className="overflow-x-auto rounded-2xl border border-white/10">
                    <table className="min-w-full divide-y divide-white/10 text-left text-sm">
                      <thead className="bg-white/5 text-xs uppercase text-slate-400">
                        <tr>
                          <th className="px-4 py-2">Severity</th>
                          <th className="px-4 py-2">Type</th>
                          <th className="px-4 py-2">Status</th>
                          <th className="px-4 py-2">Covers</th>
                          <th className="px-4 py-2">Evidence</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5 text-slate-200">
                        {relationshipConflictsData.conflicts.map((row) => (
                          <tr key={row.id} className="align-top">
                            <td className="px-4 py-2 text-xs">
                              <span
                                className={`inline-flex rounded-full border px-2 py-1 font-semibold ${relationshipConflictSeverityTone(
                                  row.severity,
                                )}`}
                              >
                                {row.severity}
                              </span>
                            </td>
                            <td className="px-4 py-2 text-xs">{row.conflict_type.replace(/_/g, " ")}</td>
                            <td className="px-4 py-2 text-xs">{row.status}</td>
                            <td className="px-4 py-2 font-mono text-xs">
                              #{row.source_cover_image_id ?? "—"} · #{row.related_cover_image_id ?? "—"}
                            </td>
                            <td className="max-w-lg break-words px-4 py-2 text-xs text-slate-400">
                              {Object.entries(row.evidence_json)
                                .slice(0, 4)
                                .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`)
                                .join(" · ") || "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}
            </div>
            <div className="mt-6">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Relationship graph quick view (human decisions only)
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Load the 1-hop subgraph for a focal cover from active CoverImageLinkDecision rows. Uses the same data as
                Inventory / OCR review graph panels.
              </p>
              <div className="mt-3 flex flex-wrap items-end gap-3">
                <label className="text-xs text-slate-300">
                  Cover image id
                  <input
                    value={graphQuickCoverIdDraft}
                    onChange={(event) => setGraphQuickCoverIdDraft(event.target.value)}
                    className="ml-2 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-sm text-white"
                    placeholder="123"
                  />
                </label>
                <button
                  type="button"
                  disabled={graphQuickBusy}
                  onClick={() => {
                    void loadCoverRelationshipGraphQuickView();
                  }}
                  className="rounded-2xl border border-cyan-400/40 bg-cyan-400/15 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:border-cyan-300 disabled:opacity-40"
                >
                  {graphQuickBusy ? "Loading…" : "Load graph"}
                </button>
              </div>
              {graphQuickError ? (
                <div className="mt-3">
                  <StatusBanner tone="error">{graphQuickError}</StatusBanner>
                </div>
              ) : null}
              {graphQuickPayload ? (
                <div className="mt-4 space-y-3 rounded-2xl border border-white/10 bg-slate-950/50 p-4 text-sm text-slate-200">
                  <p className="text-xs text-slate-400">
                    Focal #{graphQuickPayload.center_cover_image_id} · {graphQuickPayload.edges.length} active edge
                    {graphQuickPayload.edges.length === 1 ? "" : "s"}
                  </p>
                  <div className="space-y-2">
                    {OPS_COVER_GRAPH_LANES.map((lane) => {
                      const laneEdges = graphQuickPayload.edges.filter((edge) => edge.display_lane === lane);
                      if (laneEdges.length === 0) {
                        return null;
                      }
                      return (
                        <div key={lane} className="rounded-xl border border-white/10 px-3 py-2">
                          <p className="text-[11px] font-semibold text-slate-300">
                            {opsCoverGraphLaneLabel(lane)} ({laneEdges.length})
                          </p>
                          <ul className="mt-2 space-y-1 text-[11px] text-slate-400">
                            {laneEdges.map((edge) => (
                              <li key={`${edge.decision_id}-${lane}`}>
                                #{edge.source_cover_image_id} → #{edge.candidate_cover_image_id} · decision #
                                {edge.decision_id} · {formatDateTime(edge.created_at)}
                                {edge.decision_reason ? ` · ${edge.decision_reason}` : ""}
                              </li>
                            ))}
                          </ul>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}
            </div>
          </section>

          <div className="mt-6 space-y-6">
            <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
              <p className="text-sm font-semibold text-white">Duplicate review filter</p>
              <div className="mt-4 flex flex-wrap gap-3">
                {([
                  { label: "All", value: "all" },
                  { label: "Pending review", value: "pending" },
                  { label: "Confirmed duplicate", value: "confirmed_duplicate" },
                  { label: "Not duplicate", value: "not_duplicate" },
                ] as Array<{ label: string; value: InventoryDuplicatesReviewFilter }>).map((option) => {
                  const isActive = duplicateReviewFilter === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setDuplicateReviewFilter(option.value)}
                      className={`rounded-2xl px-4 py-3 text-sm font-semibold transition ${
                        isActive
                          ? "bg-cyan-400 text-slate-950"
                          : "border border-white/10 text-slate-100 hover:border-cyan-300/40 hover:bg-white/5"
                      }`}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </section>

            {duplicateCandidatesError ? (
              <div>
                <StatusBanner tone="error">{duplicateCandidatesError}</StatusBanner>
              </div>
            ) : null}

            {duplicateCandidatesLoading ? (
              <section className="rounded-3xl border border-white/10 bg-slate-900/70 px-8 py-12 text-center text-sm text-slate-400 shadow-xl shadow-black/20">
                Loading duplicate candidate inventory groups…
              </section>
            ) : (
              <TableSection
                title="Duplicate Candidates"
                description="Candidate duplicates are based on matching canonical metadata identity keys. Review before merging. This review system does not merge or modify inventory records."
                headers={[
                  "Identity key",
                  "Copy count",
                  "Comic summary",
                  "Review status",
                  "Reviewer",
                  "Notes",
                  "Copy breakdown",
                  "Actions",
                ]}
                rows={duplicateCandidates.map((group) => {
                  const textareaId = `dup-notes-${group.metadata_identity_key}`;
                  const reviewerLabel = group.reviewed_by ?? "—";
                  const reviewStatusDisplay = group.review_status.replace(/_/g, " ");
                  const isBusyRow = busyDuplicateIdentityKey === group.metadata_identity_key;

                  return [
                    <span key={`${group.metadata_identity_key}-key`} className="break-all font-mono text-xs">
                      {group.metadata_identity_key}
                    </span>,
                    String(group.count),
                    <div key={`${group.metadata_identity_key}-comic-summary`}>
                      <p className="text-sm text-white">{`${group.publisher} · ${group.series_title}`}</p>
                      <p className="text-xs text-slate-400">Issue {group.issue_number}</p>
                      <p className="text-xs text-slate-400">Variant {group.variant || "None"}</p>
                    </div>,
                    <span key={`${group.metadata_identity_key}-status`} className="text-sm capitalize">
                      {reviewStatusDisplay}
                    </span>,
                    <div key={`${group.metadata_identity_key}-reviewer`} className="text-xs text-slate-300">
                      <p className="text-sm text-white">{reviewerLabel}</p>
                      <p className="text-slate-500">
                        {group.reviewed_at ? formatDateTime(group.reviewed_at) : "—"}
                      </p>
                    </div>,
                    <div key={`${group.metadata_identity_key}-notes`} className="flex max-w-[16rem] flex-col gap-2">
                      <label
                        className="text-xs uppercase tracking-[0.16em] text-slate-500"
                        htmlFor={textareaId}
                      >
                        Notes
                      </label>
                      <textarea
                        id={textareaId}
                        rows={3}
                        disabled={isBusyRow}
                        className="w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-white disabled:opacity-60"
                        value={duplicateNotesDraft[group.metadata_identity_key] ?? ""}
                        onChange={(event) => {
                          setDuplicateNotesDraft((previous) => ({
                            ...previous,
                            [group.metadata_identity_key]: event.target.value,
                          }));
                        }}
                      />
                      <button
                        type="button"
                        disabled={isBusyRow}
                        onClick={() => void saveDuplicateCandidateNotes(group.metadata_identity_key)}
                        className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-white transition hover:border-cyan-300/60 hover:bg-cyan-300/10 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        Save notes only
                      </button>
                    </div>,
                    <div
                      key={`${group.metadata_identity_key}-copies`}
                      className="space-y-2 text-xs text-slate-300"
                    >
                      {group.copies.map((copy) => (
                        <div
                          key={copy.inventory_copy_id}
                          className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2"
                        >
                          <p>Copy #{copy.inventory_copy_id}</p>
                          <p>
                            User: {copy.user_email ?? "Unknown"}
                            {copy.user_id !== null ? ` (#${copy.user_id})` : ""}
                          </p>
                          <p>Order: {copy.order_id ? `#${copy.order_id}` : "Unknown"}</p>
                          <p>Retailer: {copy.retailer ?? "Unknown"}</p>
                          <p>Order date: {formatDateTime(copy.order_date)}</p>
                          <p>Acquisition: {copy.acquisition_cost}</p>
                          <p>Created: {formatDateTime(copy.created_at)}</p>
                        </div>
                      ))}
                    </div>,
                    <div key={`${group.metadata_identity_key}-actions`} className="flex flex-col gap-2">
                      <button
                        type="button"
                        disabled={isBusyRow}
                        onClick={() => void persistDuplicateDecision(group, "confirmed_duplicate")}
                        className="rounded-xl border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-xs font-semibold text-rose-100 transition hover:bg-rose-400/20 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isBusyRow ? "Working…" : "Mark confirmed duplicate"}
                      </button>
                      <button
                        type="button"
                        disabled={isBusyRow}
                        onClick={() => void persistDuplicateDecision(group, "not_duplicate")}
                        className="rounded-xl border border-emerald-400/40 bg-emerald-400/10 px-3 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isBusyRow ? "Working…" : "Mark not duplicate"}
                      </button>
                    </div>,
                  ];
                })}
              />
            )}

            <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
              <p className="text-sm font-semibold text-white">Canonical series filters</p>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Publisher</span>
                  <input
                    type="text"
                    value={canonicalSeriesPublisherFilter}
                    onChange={(event) => setCanonicalSeriesPublisherFilter(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="Filter by canonical publisher"
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Title</span>
                  <input
                    type="text"
                    value={canonicalSeriesTitleFilter}
                    onChange={(event) => setCanonicalSeriesTitleFilter(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="Filter by canonical title"
                  />
                </label>
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Earliest year min
                  </span>
                  <input
                    type="number"
                    min={1800}
                    max={2999}
                    value={canonicalSeriesEarliestYearMin}
                    onChange={(event) => setCanonicalSeriesEarliestYearMin(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="e.g. 2024"
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Earliest year max
                  </span>
                  <input
                    type="number"
                    min={1800}
                    max={2999}
                    value={canonicalSeriesEarliestYearMax}
                    onChange={(event) => setCanonicalSeriesEarliestYearMax(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="e.g. 2025"
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Latest year min
                  </span>
                  <input
                    type="number"
                    min={1800}
                    max={2999}
                    value={canonicalSeriesLatestYearMin}
                    onChange={(event) => setCanonicalSeriesLatestYearMin(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="e.g. 2024"
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Latest year max
                  </span>
                  <input
                    type="number"
                    min={1800}
                    max={2999}
                    value={canonicalSeriesLatestYearMax}
                    onChange={(event) => setCanonicalSeriesLatestYearMax(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="e.g. 2026"
                  />
                </label>
              </div>
            </section>

            {canonicalSeriesError ? (
              <div>
                <StatusBanner tone="error">{canonicalSeriesError}</StatusBanner>
              </div>
            ) : null}

            {canonicalSeriesLoading ? (
              <section className="rounded-3xl border border-white/10 bg-slate-900/70 px-8 py-12 text-center text-sm text-slate-400 shadow-xl shadow-black/20">
                Loading canonical series registry…
              </section>
            ) : (
              <TableSection
                title="Canonical Series Registry"
                description="Deterministic canonical series identities used to separate normalized series text from durable registry records."
                headers={[
                  "Publisher",
                  "Canonical Title",
                  "Series Key",
                  "Inventory Count",
                  "Earliest Release",
                  "Latest Release",
                  "Active",
                  "First Seen",
                  "Last Seen",
                ]}
                rows={canonicalSeries.map((row) => [
                  row.canonical_publisher,
                  row.canonical_title,
                  <span key={`${row.id}-series-key`} className="break-all font-mono text-xs">
                    {row.series_key}
                  </span>,
                  String(row.inventory_count),
                  formatCanonicalReleaseCalendar(row.earliest_known_release_date),
                  formatCanonicalReleaseCalendar(row.latest_known_release_date),
                  row.is_active ? "Yes" : "No",
                  formatDateTime(row.first_seen_at),
                  formatDateTime(row.last_seen_at),
                ])}
              />
            )}

            <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
              <p className="text-sm font-semibold text-white">Canonical creator filters</p>
              <p className="mt-2 text-xs text-slate-400">
                Broad search spans canonical name, normalized name, and stored creator keys. Narrow
                fields apply as additional refinements alongside the broad search.
              </p>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Broad match (canonical / normalized / key)
                  </span>
                  <input
                    type="text"
                    value={canonicalCreatorsBroadFilter}
                    onChange={(event) => setCanonicalCreatorsBroadFilter(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="e.g. campbell"
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Canonical display name contains
                  </span>
                  <input
                    type="text"
                    value={canonicalCreatorsCanonicalNameFilter}
                    onChange={(event) => setCanonicalCreatorsCanonicalNameFilter(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="Canonical name substring"
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Normalized lookup name contains
                  </span>
                  <input
                    type="text"
                    value={canonicalCreatorsNormalizedNameFilter}
                    onChange={(event) => setCanonicalCreatorsNormalizedNameFilter(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="Normalized name substring"
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Creator key contains
                  </span>
                  <input
                    type="text"
                    value={canonicalCreatorsKeyFilter}
                    onChange={(event) => setCanonicalCreatorsKeyFilter(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="creator:j scott …"
                  />
                </label>
                <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-300 md:col-span-2">
                  <input
                    type="checkbox"
                    checked={canonicalCreatorsShowKeyColumn}
                    onChange={(event) => setCanonicalCreatorsShowKeyColumn(event.target.checked)}
                    className="h-4 w-4 rounded border-white/20 bg-slate-950 text-cyan-300 focus:ring-cyan-300/40"
                  />
                  Show creator key column in the registry table
                </label>
              </div>
            </section>

            {canonicalCreatorsError ? (
              <div>
                <StatusBanner tone="error">{canonicalCreatorsError}</StatusBanner>
              </div>
            ) : null}

            {canonicalCreatorsLoading ? (
              <section className="rounded-3xl border border-white/10 bg-slate-900/70 px-8 py-12 text-center text-sm text-slate-400 shadow-xl shadow-black/20">
                Loading canonical creator registry…
              </section>
            ) : (
              <TableSection
                title="Canonical Creator Registry"
                description="Deterministic creator identities normalized from writer, artist, and cover-artist metadata without fuzzy merging."
                headers={[
                  "Canonical Name",
                  "Normalized Name",
                  ...(canonicalCreatorsShowKeyColumn ? (["Creator Key"] as const) : []),
                  "Active",
                  "First Seen",
                  "Last Seen",
                ]}
                rows={canonicalCreators.map((row) =>
                  [
                    row.canonical_name,
                    row.normalized_name,
                    ...(canonicalCreatorsShowKeyColumn
                      ? [
                          (
                            <span
                              key={`${row.id}-creator-key-cell`}
                              className="break-all font-mono text-xs"
                            >
                              {row.creator_key}
                            </span>
                          ),
                        ]
                      : []),
                    row.is_active ? "Yes" : "No",
                    formatDateTime(row.first_seen_at),
                    formatDateTime(row.last_seen_at),
                  ] as Array<string | JSX.Element>,
                )}
              />
            )}

            <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
              <div className="flex flex-wrap gap-3">
                {[
                  { label: "All Aliases", value: "all" as const },
                  { label: "Publisher", value: "publisher" as const },
                  { label: "Series", value: "series" as const },
                  { label: "Creator", value: "creator" as const },
                ].map((option) => {
                  const isActive = aliasTypeFilter === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setAliasTypeFilter(option.value)}
                      className={`rounded-2xl px-4 py-3 text-sm font-semibold transition ${
                        isActive
                          ? "bg-cyan-400 text-slate-950"
                          : "border border-white/10 text-slate-100 hover:border-cyan-300/40 hover:bg-white/5"
                      }`}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </section>

            <TableSection
              title="Metadata Aliases"
              description="Manual publisher, series, and creator alias mappings used during deterministic metadata enrichment."
              headers={["Type", "Alias", "Canonical", "Source", "Active", "Updated", "Actions"]}
              rows={filteredAliases.map((alias) => [
                alias.alias_type,
                alias.alias_value,
                alias.canonical_value,
                alias.source,
                alias.is_active ? "Yes" : "No",
                formatDateTime(alias.updated_at),
                alias.is_active ? (
                  <button
                    type="button"
                    disabled={activeAliasId === alias.id}
                    onClick={async () => {
                      setActiveAliasId(alias.id);
                      setError(null);
                      try {
                        await apiClient.deactivateMetadataAlias(alias.id);
                        const aliases = await apiClient.listMetadataAliases();
                        setMetadataAliases(aliases);
                      } catch (actionError) {
                        setError(
                          actionError instanceof ApiError
                            ? actionError.message
                            : "Unable to deactivate metadata alias.",
                        );
                      } finally {
                        setActiveAliasId(null);
                      }
                    }}
                    className="rounded-xl border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-xs font-semibold text-rose-200 transition hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {activeAliasId === alias.id ? "Working..." : "Deactivate"}
                  </button>
                ) : (
                  "Inactive"
                ),
              ])}
            />

            <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
              <p className="text-sm font-semibold text-white">Queue deterministic re-enrichment</p>
              <p className="mt-2 text-sm text-slate-400">
                Re-enrichment re-runs the current deterministic metadata rules only. It preserves raw
                values, avoids fuzzy merging, and does not change inventory business fields like FMV,
                grade, or hold state.
              </p>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Draft import id
                  </span>
                  <input
                    type="number"
                    min={1}
                    value={reenrichDraftImportId}
                    onChange={(event) => setReenrichDraftImportId(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="e.g. 42"
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Inventory copy id
                  </span>
                  <input
                    type="number"
                    min={1}
                    value={reenrichInventoryCopyId}
                    onChange={(event) => setReenrichInventoryCopyId(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="e.g. 108"
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300 md:col-span-2">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Reason (optional)
                  </span>
                  <input
                    type="text"
                    value={reenrichReason}
                    onChange={(event) => setReenrichReason(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="Alias changed, release cleanup, deterministic refresh..."
                  />
                </label>
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={reenrichBusyKey === "draft"}
                  onClick={() => void enqueueDraftReenrichment()}
                  className="rounded-2xl bg-cyan-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {reenrichBusyKey === "draft" ? "Queueing..." : "Queue draft re-enrichment"}
                </button>
                <button
                  type="button"
                  disabled={reenrichBusyKey === "inventory"}
                  onClick={() => void enqueueInventoryReenrichment()}
                  className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {reenrichBusyKey === "inventory" ? "Queueing..." : "Queue inventory re-enrichment"}
                </button>
              </div>
              {reenrichMessage ? (
                <div className="mt-4">
                  <StatusBanner tone="success">{reenrichMessage}</StatusBanner>
                </div>
              ) : null}
            </section>

            <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
              <div className="flex flex-col gap-3 border-b border-white/10 pb-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-white">Relationship Replays</h2>
                  <p className="mt-2 text-sm text-slate-400">
                    Deterministic replay and regression runs compare current relationship outputs against stored
                    snapshots without mutating link decisions, canonical metadata, inventory state, or conflict
                    lifecycle rows.
                  </p>
                </div>
                <button
                  type="button"
                  disabled={relationshipReplaysLoading}
                  onClick={() => void refreshRelationshipReplays()}
                  className="shrink-0 rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-amber-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {relationshipReplaysLoading ? "Refreshing…" : "Refresh"}
                </button>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)_auto] lg:items-end">
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Replay type</span>
                  <select
                    value={relationshipReplayTypeDraft}
                    onChange={(event) =>
                      setRelationshipReplayTypeDraft(event.target.value as RelationshipReplayType)
                    }
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  >
                    <option value="full_relationship_pipeline">full relationship pipeline</option>
                    <option value="link_decisions">link decisions</option>
                    <option value="relationship_graph">relationship graph</option>
                    <option value="duplicate_scan">duplicate scan</option>
                    <option value="variant_family">variant family</option>
                    <option value="canonical_issue_suggestions">canonical issue suggestions</option>
                    <option value="relationship_conflicts">relationship conflicts</option>
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Cover image ids (optional)
                  </span>
                  <input
                    type="text"
                    value={relationshipReplayCoverIdsDraft}
                    onChange={(event) => setRelationshipReplayCoverIdsDraft(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="leave blank for all visible covers, or enter e.g. 101, 102"
                  />
                </label>
                <button
                  type="button"
                  disabled={relationshipReplayBusyAction === "create"}
                  onClick={() => void handleCreateRelationshipReplay()}
                  className="rounded-2xl bg-amber-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {relationshipReplayBusyAction === "create" ? "Creating…" : "Create relationship replay"}
                </button>
              </div>

              {relationshipReplaysError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{relationshipReplaysError}</StatusBanner>
                </div>
              ) : null}
              {relationshipReplayMessage ? (
                <div className="mt-4">
                  <StatusBanner tone="success">{relationshipReplayMessage}</StatusBanner>
                </div>
              ) : null}

              {relationshipReplaysLoading ? (
                <section className="mt-6 rounded-2xl border border-white/5 bg-slate-950/40 px-6 py-12 text-center text-sm text-slate-400">
                  Loading relationship replays…
                </section>
              ) : relationshipReplays.length === 0 ? (
                <section className="mt-6 rounded-2xl border border-white/5 bg-slate-950/40 px-6 py-12 text-center text-sm text-slate-400">
                  No relationship replays recorded yet.
                </section>
              ) : (
                <div className="mt-6 space-y-4">
                  {relationshipReplays.map((replay) => {
                    const busyStart = relationshipReplayBusyAction === `start:${replay.id}`;
                    const busyCancel = relationshipReplayBusyAction === `cancel:${replay.id}`;
                    return (
                      <article
                        key={replay.id}
                        className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 shadow-inner shadow-black/20"
                      >
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold text-white">
                                Relationship replay #{replay.id} · {replay.replay_type.replace(/_/g, " ")}
                              </p>
                              <span
                                className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${relationshipReplayStatusTone(
                                  replay.status,
                                )}`}
                              >
                                {replay.status.replace(/_/g, " ")}
                              </span>
                            </div>
                            <p className="mt-2 text-xs text-slate-400">
                              Created {formatDateTime(replay.created_at)} · updated{" "}
                              {formatDateTime(replay.updated_at)}
                            </p>
                            <p className="mt-2 text-xs text-slate-500">Replay version {replay.replay_version}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              Total {replay.total_items} · changed {replay.changed_items} · unchanged{" "}
                              {replay.unchanged_items} · failed {replay.failed_items}
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              disabled={busyStart || replay.status === "cancelled"}
                              onClick={() => void handleRelationshipReplayAction(replay.id, "start")}
                              className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-100 transition hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {busyStart ? "Starting…" : "Start replay"}
                            </button>
                            <button
                              type="button"
                              disabled={busyCancel || replay.status !== "pending"}
                              onClick={() => void handleRelationshipReplayAction(replay.id, "cancel")}
                              className="rounded-xl border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-xs font-semibold text-rose-100 transition hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {busyCancel ? "Cancelling…" : "Cancel"}
                            </button>
                          </div>
                        </div>

                        <div className="mt-4 grid gap-4 xl:grid-cols-2">
                          <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                              Replay items
                            </p>
                            <div className="mt-3 space-y-2 text-xs text-slate-300">
                              {replay.items.map((item) => (
                                <div
                                  key={item.id}
                                  className="rounded-lg border border-white/10 bg-slate-900/80 px-3 py-2"
                                >
                                  <p className="text-white">
                                    {item.cover_image_id != null
                                      ? `Cover #${item.cover_image_id}`
                                      : item.relationship_key ?? `Item #${item.id}`}{" "}
                                    · {item.status}
                                  </p>
                                  <p className="mt-1 text-slate-500">
                                    Diff {String(item.diff_summary_json.status ?? item.status)}
                                  </p>
                                  {typeof item.diff_summary_json.added === "number" ||
                                  typeof item.diff_summary_json.removed === "number" ||
                                  typeof item.diff_summary_json.changed === "number" ? (
                                    <p className="mt-1 text-slate-500">
                                      Added {String(item.diff_summary_json.added ?? 0)} · removed{" "}
                                      {String(item.diff_summary_json.removed ?? 0)} · changed{" "}
                                      {String(item.diff_summary_json.changed ?? 0)}
                                    </p>
                                  ) : null}
                                  {Array.isArray(item.diff_summary_json.changed_fields) &&
                                  item.diff_summary_json.changed_fields.length > 0 ? (
                                    <p className="mt-1 text-amber-200">
                                      Fields: {(item.diff_summary_json.changed_fields as string[]).join(", ")}
                                    </p>
                                  ) : null}
                                  {item.last_error ? (
                                    <p className="mt-1 text-rose-300">{item.last_error}</p>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          </div>
                          <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                              Changed / failed visibility
                            </p>
                            <div className="mt-3 space-y-3 text-xs text-slate-300">
                              <div>
                                <p className="font-semibold text-slate-100">Changed items</p>
                                <ul className="mt-2 space-y-1 text-slate-400">
                                  {replay.items.filter((item) => item.status === "changed").length === 0 ? (
                                    <li>None.</li>
                                  ) : (
                                    replay.items
                                      .filter((item) => item.status === "changed")
                                      .map((item) => (
                                        <li key={`relationship-changed-${item.id}`}>
                                          {item.cover_image_id != null
                                            ? `Cover #${item.cover_image_id}`
                                            : item.relationship_key ?? `Item #${item.id}`}{" "}
                                          · {String(item.diff_summary_json.status ?? "changed")}
                                        </li>
                                      ))
                                  )}
                                </ul>
                              </div>
                              <div>
                                <p className="font-semibold text-slate-100">Failed items</p>
                                <ul className="mt-2 space-y-1 text-slate-400">
                                  {replay.items.filter((item) => item.status === "failed").length === 0 ? (
                                    <li>None.</li>
                                  ) : (
                                    replay.items
                                      .filter((item) => item.status === "failed")
                                      .map((item) => (
                                        <li key={`relationship-failed-${item.id}`}>
                                          {item.cover_image_id != null
                                            ? `Cover #${item.cover_image_id}`
                                            : item.relationship_key ?? `Item #${item.id}`}{" "}
                                          · {item.last_error ?? "Failed"}
                                        </li>
                                      ))
                                  )}
                                </ul>
                              </div>
                            </div>
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
              <div className="flex flex-col gap-3 border-b border-white/10 pb-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-white">OCR Replays</h2>
                  <p className="mt-2 text-sm text-slate-400">
                    Deterministic replay and regression runs compare current extraction behavior against
                    stored OCR artifacts without overwriting OCR history, metadata, or review rows.
                  </p>
                </div>
                <button
                  type="button"
                  disabled={ocrReplaysLoading}
                  onClick={() => void refreshOcrReplays()}
                  className="shrink-0 rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {ocrReplaysLoading ? "Refreshing…" : "Refresh"}
                </button>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,12rem)_minmax(0,1fr)_auto] lg:items-end">
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Replay type</span>
                  <select
                    value={ocrReplayTypeDraft}
                    onChange={(event) => setOcrReplayTypeDraft(event.target.value as OcrReplayType)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  >
                    <option value="full_pipeline">full pipeline</option>
                    <option value="ocr_result">ocr result</option>
                    <option value="candidate_extraction">candidate extraction</option>
                    <option value="barcode_extraction">barcode extraction</option>
                    <option value="fingerprint_generation">fingerprint generation</option>
                    <option value="reconciliation_warning">reconciliation warning</option>
                    <option value="quality_analysis">quality analysis</option>
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Cover image ids
                  </span>
                  <input
                    type="text"
                    value={ocrReplayCoverIdsDraft}
                    onChange={(event) => setOcrReplayCoverIdsDraft(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="e.g. 101, 102, 103"
                  />
                </label>
                <button
                  type="button"
                  disabled={ocrReplayBusyAction === "create"}
                  onClick={() => void handleCreateOcrReplay()}
                  className="rounded-2xl bg-cyan-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {ocrReplayBusyAction === "create" ? "Creating…" : "Create OCR replay"}
                </button>
              </div>

              {ocrReplaysError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{ocrReplaysError}</StatusBanner>
                </div>
              ) : null}
              {ocrReplayMessage ? (
                <div className="mt-4">
                  <StatusBanner tone="success">{ocrReplayMessage}</StatusBanner>
                </div>
              ) : null}

              {ocrReplaysLoading ? (
                <section className="mt-6 rounded-2xl border border-white/5 bg-slate-950/40 px-6 py-12 text-center text-sm text-slate-400">
                  Loading OCR replays…
                </section>
              ) : ocrReplays.length === 0 ? (
                <section className="mt-6 rounded-2xl border border-white/5 bg-slate-950/40 px-6 py-12 text-center text-sm text-slate-400">
                  No OCR replays recorded yet.
                </section>
              ) : (
                <div className="mt-6 space-y-4">
                  {ocrReplays.map((replay) => {
                    const changedItems = replay.items.filter((item) => item.status === "changed");
                    const failedItems = replay.items.filter((item) => item.status === "failed");
                    const busyStart = ocrReplayBusyAction === `start:${replay.id}`;
                    const busyCancel = ocrReplayBusyAction === `cancel:${replay.id}`;
                    return (
                      <article
                        key={replay.id}
                        className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 shadow-inner shadow-black/20"
                      >
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold text-white">
                                Replay #{replay.id} · {replay.replay_type.replace(/_/g, " ")}
                              </p>
                              <span
                                className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${ocrReplayStatusTone(replay.status)}`}
                              >
                                {replay.status.replace(/_/g, " ")}
                              </span>
                            </div>
                            <p className="mt-2 text-xs text-slate-400">
                              Created {formatDateTime(replay.created_at)} · updated{" "}
                              {formatDateTime(replay.updated_at)}
                            </p>
                            <p className="mt-2 text-xs text-slate-500">
                              Versions {replay.extraction_version_from} → {replay.extraction_version_to}
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                              Total {replay.total_items} · changed {replay.changed_items} · unchanged{" "}
                              {replay.unchanged_items} · failed {replay.failed_items}
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              disabled={busyStart || replay.status === "cancelled"}
                              onClick={() => void handleOcrReplayAction(replay.id, "start")}
                              className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-100 transition hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {busyStart ? "Starting…" : "Start replay"}
                            </button>
                            <button
                              type="button"
                              disabled={busyCancel || replay.status !== "pending"}
                              onClick={() => void handleOcrReplayAction(replay.id, "cancel")}
                              className="rounded-xl border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-xs font-semibold text-rose-100 transition hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {busyCancel ? "Cancelling…" : "Cancel"}
                            </button>
                          </div>
                        </div>

                        <div className="mt-4 grid gap-4 xl:grid-cols-3">
                          <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                              Replay items
                            </p>
                            <div className="mt-3 space-y-2 text-xs text-slate-300">
                              {replay.items.map((item) => {
                                const diffStatus = String(item.diff_summary_json.status ?? item.status);
                                return (
                                  <div
                                    key={item.id}
                                    className="rounded-lg border border-white/10 bg-slate-900/80 px-3 py-2"
                                  >
                                    <p className="text-white">
                                      Cover #{item.cover_image_id} · {item.status}
                                    </p>
                                    <p className="mt-1 text-slate-500">Diff {diffStatus}</p>
                                    {Array.isArray(item.diff_summary_json.changed_fields) &&
                                    item.diff_summary_json.changed_fields.length > 0 ? (
                                      <p className="mt-1 text-amber-200">
                                        Fields:{" "}
                                        {(item.diff_summary_json.changed_fields as string[]).join(", ")}
                                      </p>
                                    ) : null}
                                    {typeof item.diff_summary_json.added === "number" ||
                                    typeof item.diff_summary_json.removed === "number" ||
                                    typeof item.diff_summary_json.changed === "number" ? (
                                      <p className="mt-1 text-slate-500">
                                        Added {String(item.diff_summary_json.added ?? 0)} · removed{" "}
                                        {String(item.diff_summary_json.removed ?? 0)} · changed{" "}
                                        {String(item.diff_summary_json.changed ?? 0)}
                                      </p>
                                    ) : null}
                                    {item.last_error ? (
                                      <p className="mt-1 text-rose-300">{item.last_error}</p>
                                    ) : null}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                          <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                              Changed items
                            </p>
                            {changedItems.length === 0 ? (
                              <p className="mt-3 text-xs text-slate-500">No changed items recorded.</p>
                            ) : (
                              <div className="mt-3 space-y-2 text-xs text-slate-300">
                                {changedItems.map((item) => (
                                  <div
                                    key={`changed-${item.id}`}
                                    className="rounded-lg border border-amber-400/20 bg-amber-500/5 px-3 py-2"
                                  >
                                    <p className="text-white">Cover #{item.cover_image_id}</p>
                                    <p className="mt-1 text-amber-200">
                                      {JSON.stringify(item.diff_summary_json)}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                          <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                              Failed items
                            </p>
                            {failedItems.length === 0 ? (
                              <p className="mt-3 text-xs text-slate-500">No failed items recorded.</p>
                            ) : (
                              <div className="mt-3 space-y-2 text-xs text-slate-300">
                                {failedItems.map((item) => (
                                  <div
                                    key={`failed-replay-${item.id}`}
                                    className="rounded-lg border border-rose-400/20 bg-rose-500/5 px-3 py-2"
                                  >
                                    <p className="text-white">Cover #{item.cover_image_id}</p>
                                    <p className="mt-1 text-rose-300">{item.last_error ?? "Failed"}</p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
              <div className="flex flex-col gap-3 border-b border-white/10 pb-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-white">OCR Batches</h2>
                  <p className="mt-2 text-sm text-slate-400">
                    Deterministic bulk OCR orchestration for existing cover images. Batches only queue
                    and monitor OCR work; they do not mutate metadata or delete OCR history.
                  </p>
                </div>
                <button
                  type="button"
                  disabled={ocrBatchesLoading}
                  onClick={() => void refreshOcrBatches()}
                  className="shrink-0 rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {ocrBatchesLoading ? "Refreshing…" : "Refresh"}
                </button>
              </div>

              <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Cover image ids
                  </span>
                  <input
                    type="text"
                    value={ocrBatchCoverIdsDraft}
                    onChange={(event) => setOcrBatchCoverIdsDraft(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                    placeholder="e.g. 101, 102, 103"
                  />
                </label>
                <button
                  type="button"
                  disabled={ocrBatchBusyAction === "create"}
                  onClick={() => void handleCreateOcrBatch()}
                  className="rounded-2xl bg-cyan-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {ocrBatchBusyAction === "create" ? "Creating…" : "Create OCR batch"}
                </button>
              </div>

              {ocrBatchesError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{ocrBatchesError}</StatusBanner>
                </div>
              ) : null}
              {ocrBatchMessage ? (
                <div className="mt-4">
                  <StatusBanner tone="success">{ocrBatchMessage}</StatusBanner>
                </div>
              ) : null}

              {ocrBatchesLoading ? (
                <section className="mt-6 rounded-2xl border border-white/5 bg-slate-950/40 px-6 py-12 text-center text-sm text-slate-400">
                  Loading OCR batches…
                </section>
              ) : ocrBatches.length === 0 ? (
                <section className="mt-6 rounded-2xl border border-white/5 bg-slate-950/40 px-6 py-12 text-center text-sm text-slate-400">
                  No OCR batches recorded yet.
                </section>
              ) : (
                <div className="mt-6 space-y-4">
                  {ocrBatches.map((batch) => {
                    const failedItems = batch.items.filter((item) => item.status === "failed");
                    const busyEnqueue = ocrBatchBusyAction === `enqueue:${batch.id}`;
                    const busyRetry = ocrBatchBusyAction === `retry-failed:${batch.id}`;
                    const busyCancel = ocrBatchBusyAction === `cancel:${batch.id}`;
                    return (
                      <article
                        key={batch.id}
                        className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 shadow-inner shadow-black/20"
                      >
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold text-white">{batch.batch_key}</p>
                              <span
                                className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${ocrBatchStatusTone(batch.status)}`}
                              >
                                {batch.status.replace(/_/g, " ")}
                              </span>
                            </div>
                            <p className="mt-2 text-xs text-slate-400">
                              Created {formatDateTime(batch.created_at)} · updated {formatDateTime(batch.updated_at)}
                            </p>
                            <p className="mt-2 text-xs text-slate-500">
                              Total {batch.total_items} · pending {batch.pending_count} · running{" "}
                              {batch.running_count} · completed {batch.completed_count} · failed{" "}
                              {batch.failed_count} · skipped {batch.skipped_count}
                            </p>
                            {Array.isArray(batch.batch_options_json.invalid_cover_image_ids) &&
                            batch.batch_options_json.invalid_cover_image_ids.length > 0 ? (
                              <p className="mt-2 text-xs text-amber-200">
                                Invalid ids skipped:{" "}
                                {(batch.batch_options_json.invalid_cover_image_ids as number[]).join(", ")}
                              </p>
                            ) : null}
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              disabled={busyEnqueue || batch.status === "cancelled"}
                              onClick={() => void handleOcrBatchAction(batch.id, "enqueue")}
                              className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-100 transition hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {busyEnqueue ? "Queueing…" : "Enqueue"}
                            </button>
                            <button
                              type="button"
                              disabled={busyRetry || batch.failed_count === 0 || batch.status === "cancelled"}
                              onClick={() => void handleOcrBatchAction(batch.id, "retry-failed")}
                              className="rounded-xl border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs font-semibold text-amber-100 transition hover:bg-amber-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {busyRetry ? "Retrying…" : "Retry failed"}
                            </button>
                            <button
                              type="button"
                              disabled={
                                busyCancel ||
                                batch.status === "cancelled" ||
                                (batch.pending_count === 0 && batch.running_count === 0)
                              }
                              onClick={() => void handleOcrBatchAction(batch.id, "cancel")}
                              className="rounded-xl border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-xs font-semibold text-rose-100 transition hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {busyCancel ? "Cancelling…" : "Cancel"}
                            </button>
                          </div>
                        </div>

                        <div className="mt-4 grid gap-4 lg:grid-cols-2">
                          <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                              Batch items
                            </p>
                            <div className="mt-3 space-y-2 text-xs text-slate-300">
                              {batch.items.map((item) => (
                                <div
                                  key={item.id}
                                  className="rounded-lg border border-white/10 bg-slate-900/80 px-3 py-2"
                                >
                                  <p className="text-white">
                                    Cover #{item.cover_image_id} · {item.status}
                                  </p>
                                  <p className="mt-1 text-slate-500">
                                    Attempts {item.attempt_count}
                                    {item.job_id ? ` · job ${item.job_id}` : ""}
                                  </p>
                                  {item.last_error ? (
                                    <p className="mt-1 text-rose-300">{item.last_error}</p>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          </div>
                          <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                              Failed items
                            </p>
                            {failedItems.length === 0 ? (
                              <p className="mt-3 text-xs text-slate-500">No failed items recorded.</p>
                            ) : (
                              <div className="mt-3 space-y-2 text-xs text-slate-300">
                                {failedItems.map((item) => (
                                  <div
                                    key={`failed-${item.id}`}
                                    className="rounded-lg border border-rose-400/20 bg-rose-500/5 px-3 py-2"
                                  >
                                    <p className="text-white">Cover #{item.cover_image_id}</p>
                                    <p className="mt-1 text-rose-300">{item.last_error ?? "Failed"}</p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>

            <OcrReviewWorkspace />

            <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
              <div className="flex flex-col gap-3 border-b border-white/10 pb-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-white">Recent Cover Images</h2>
                  <p className="mt-2 text-sm text-slate-400">
                    Latest stored cover scans with linkage context. Thumbnails use the same authenticated
                    cover file route as inventory and import screens. Ops can manually repoint linkage to
                    an inventory copy (DB update only — no duplication or moves).
                  </p>
                  <p className="mt-2 text-xs text-slate-500">{MANUAL_COVER_ASSIGN_INFO_OPS}</p>
                  <p className="mt-2 text-xs text-slate-500">{MANUAL_COVER_ASSIGN_MULTI_COPY_OPS}</p>
                  <p className="mt-2 text-xs text-slate-500">{COVER_PROCESSING_INFO_OPS}</p>
                </div>
                <button
                  type="button"
                  disabled={recentCoversLoading}
                  onClick={() => void refreshRecentCoverImages()}
                  className="shrink-0 rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {recentCoversLoading ? "Refreshing…" : "Refresh"}
                </button>
              </div>

              <div className="mt-4 flex flex-wrap gap-4">
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Limit</span>
                  <select
                    value={coverOpsLimit}
                    onChange={(event) => setCoverOpsLimit(Number(event.target.value))}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  >
                    {[25, 50, 100].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Source type</span>
                  <select
                    value={coverOpsSource}
                    onChange={(event) =>
                      setCoverOpsSource(event.target.value as "all" | CoverImageSourceType)
                    }
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  >
                    <option value="all">All</option>
                    <option value="upload">upload</option>
                    <option value="gmail_attachment">gmail_attachment</option>
                    <option value="import_image">import_image</option>
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Linkage</span>
                  <select
                    value={coverOpsLinkage}
                    onChange={(event) =>
                      setCoverOpsLinkage(event.target.value as "all" | "inventory" | "import")
                    }
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  >
                    <option value="all">All</option>
                    <option value="inventory">Inventory copy</option>
                    <option value="import">Draft import</option>
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Matching status
                  </span>
                  <select
                    value={coverOpsMatchingStatus}
                    onChange={(event) =>
                      setCoverOpsMatchingStatus(
                        event.target.value as
                          | "all"
                          | "ready"
                          | "needs_review"
                          | "failed"
                          | "not_ready",
                      )
                    }
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  >
                    <option value="all">All</option>
                    <option value="ready">ready</option>
                    <option value="needs_review">needs_review</option>
                    <option value="failed">failed</option>
                    <option value="not_ready">not_ready</option>
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    OCR quality severity
                  </span>
                  <select
                    value={coverOpsQualitySeverityFilter}
                    onChange={(event) =>
                      setCoverOpsQualitySeverityFilter(
                        event.target.value as "all" | CoverOcrQualitySeverity,
                      )
                    }
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  >
                    <option value="all">All</option>
                    <option value="critical">critical</option>
                    <option value="warning">warning</option>
                    <option value="info">info</option>
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    OCR quality type
                  </span>
                  <select
                    value={coverOpsQualityTypeFilter}
                    onChange={(event) =>
                      setCoverOpsQualityTypeFilter(event.target.value as "all" | CoverOcrQualityType)
                    }
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  >
                    <option value="all">All</option>
                    <option value="overall_quality">overall quality</option>
                    <option value="blur_detection">blur detection</option>
                    <option value="low_resolution">low resolution</option>
                    <option value="low_contrast">low contrast</option>
                    <option value="unreadable_ocr">unreadable ocr</option>
                    <option value="crop_quality">crop quality</option>
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Match confidence
                  </span>
                  <select
                    value={coverOpsMatchConfidenceFilter}
                    onChange={(event) =>
                      setCoverOpsMatchConfidenceFilter(
                        event.target.value as "all" | CoverMatchConfidenceBucket,
                      )
                    }
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  >
                    <option value="all">All</option>
                    <option value="very_high">very_high</option>
                    <option value="high">high</option>
                    <option value="medium">medium</option>
                    <option value="low">low</option>
                    <option value="very_low">very_low</option>
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Match signal type
                  </span>
                  <select
                    value={coverOpsMatchTypeFilter}
                    onChange={(event) =>
                      setCoverOpsMatchTypeFilter(
                        event.target.value as
                          | "all"
                          | "fingerprint_similarity"
                          | "barcode_similarity"
                          | "ocr_similarity"
                          | "combined_similarity",
                      )
                    }
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  >
                    <option value="all">All</option>
                    <option value="combined_similarity">combined similarity</option>
                    <option value="barcode_similarity">barcode similarity</option>
                    <option value="ocr_similarity">ocr similarity</option>
                    <option value="fingerprint_similarity">fingerprint similarity</option>
                  </select>
                </label>
              </div>

              {recentCoversError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{recentCoversError}</StatusBanner>
                </div>
              ) : null}

              {recentCoversLoading ? (
                <section className="mt-6 rounded-2xl border border-white/5 bg-slate-950/40 px-6 py-12 text-center text-sm text-slate-400">
                  Loading recent cover uploads…
                </section>
              ) : filteredRecentCoverImages.length === 0 ? (
                <section className="mt-6 rounded-2xl border border-white/5 bg-slate-950/40 px-6 py-12 text-center text-sm text-slate-400">
                  No cover uploads match the current filters.
                </section>
              ) : (
                <div className="mt-6 grid gap-4 lg:grid-cols-2">
                  {filteredRecentCoverImages.map((row) => {
                    const thumbUrl = coverThumbUrls[row.id];
                    const thumbFailed = coverThumbErrors[row.id];
                    const ocrHeadline = resolveCoverImageOcrHeadline({
                      ocr_visibility: row.ocr_visibility,
                      latest_ocr_result: row.latest_ocr_result,
                    });
                    return (
                      <article
                        key={row.id}
                        className="flex gap-4 rounded-2xl border border-white/10 bg-slate-950/60 p-4 shadow-inner shadow-black/20"
                      >
                        <div className="relative h-28 w-24 shrink-0 overflow-hidden rounded-xl border border-white/10 bg-slate-900">
                          {thumbUrl ? (
                            <img
                              src={thumbUrl}
                              alt=""
                              className="h-full w-full object-cover"
                            />
                          ) : thumbFailed ? (
                            <div className="flex h-full w-full items-center justify-center px-1 text-center text-[10px] text-slate-500">
                              Preview unavailable
                            </div>
                          ) : (
                            <div className="flex h-full w-full items-center justify-center text-xs text-slate-500">
                              …
                            </div>
                          )}
                        </div>
                        <div className="min-w-0 flex-1 space-y-2 text-sm text-slate-200">
                          <div>
                            <p className="truncate font-medium text-white" title={row.original_filename ?? ""}>
                              {row.original_filename ?? "Untitled file"}
                            </p>
                            <div className="mt-1 flex flex-wrap items-center gap-2">
                              <p className="text-xs text-slate-500">
                                Cover #{row.id} · {formatDateTime(row.created_at)}
                              </p>
                              {row.is_primary ? (
                                <span className="rounded-full border border-amber-400/35 bg-amber-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-100">
                                  Primary
                                </span>
                              ) : null}
                            </div>
                            {row.owner_email ? (
                              <p className="text-xs text-slate-500">Owner {row.owner_email}</p>
                            ) : null}
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              <span
                                className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${coverProcessingTone(row.processing_status)}`}
                              >
                                {row.processing_status}
                              </span>
                              <span
                                className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${coverMatchingTone(row.matching_status)}`}
                              >
                                matching {row.matching_status}
                              </span>
                              <span
                                className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${coverOcrHeadlineTone(ocrHeadline)}`}
                              >
                                ocr {ocrHeadline}
                              </span>
                              <span className="text-xs text-slate-500">
                                Refreshed {formatDateTime(row.metadata_refreshed_at)}
                              </span>
                            </div>
                            {row.processing_error ? (
                              <p className="mt-2 text-xs text-rose-300">{row.processing_error}</p>
                            ) : null}
                            {row.matching_notes ? (
                              <p className="mt-2 text-xs text-amber-100/90">{row.matching_notes}</p>
                            ) : null}
                            {row.latest_ocr_result?.processing_error ? (
                              <p className="mt-2 text-xs text-rose-300">
                                {row.latest_ocr_result.processing_error}
                              </p>
                            ) : null}
                            <p className="mt-2 text-xs text-slate-500">
                              OCR runs {row.ocr_visibility?.ocr_run_count ?? 0} · latest{" "}
                              {formatDateTime(row.latest_ocr_result?.processed_at ?? null)}
                            </p>
                            <p className="mt-2 text-xs text-slate-500">
                              OCR regions {row.ocr_region_count}
                            </p>
                            <p className="mt-2 text-xs text-slate-500">
                              OCR candidates {row.ocr_candidate_count}
                              {" · "}pending {(row.ocr_candidate_review_counts?.pending ?? 0)}, approved{" "}
                              {(row.ocr_candidate_review_counts?.approved ?? 0)}, rejected{" "}
                              {(row.ocr_candidate_review_counts?.rejected ?? 0)}
                            </p>
                            <p className="mt-2 text-xs text-slate-500">
                              Barcode candidates {row.barcode_candidate_count ?? 0}
                              {" · "}pending {(row.barcode_candidate_review_counts?.pending ?? 0)}, approved{" "}
                              {(row.barcode_candidate_review_counts?.approved ?? 0)}, rejected{" "}
                              {(row.barcode_candidate_review_counts?.rejected ?? 0)}
                            </p>
                            <p className="mt-2 text-xs text-slate-500">
                              Fingerprints {row.fingerprint_count ?? 0}
                            </p>
                            <p className="mt-2 text-xs text-slate-500">
                              OCR quality analyses {row.ocr_quality_analysis_count ?? 0}
                            </p>
                            {(row.ocr_quality_analyses ?? []).length > 0 ? (
                              <div className="mt-2 flex flex-wrap gap-2">
                                {(row.ocr_quality_analyses ?? []).map((analysis) => (
                                  <span
                                    key={analysis.id}
                                    className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${qualitySeverityTone(analysis.severity)}`}
                                  >
                                    {analysis.quality_type.replace(/_/g, " ")} · score{" "}
                                    {analysis.deterministic_score.toFixed(2)}
                                  </span>
                                ))}
                              </div>
                            ) : null}
                            <p className="mt-2 text-xs text-slate-500">
                              OCR reconciliation warnings open{" "}
                              {row.ocr_reconciliation_warning_counts?.open ?? row.open_ocr_reconciliation_warning_count ?? 0}
                              {" · "}acknowledged {row.ocr_reconciliation_warning_counts?.acknowledged ?? 0}
                              {" · "}dismissed {row.ocr_reconciliation_warning_counts?.dismissed ?? 0}
                            </p>
                            <p className="mt-2 text-xs text-slate-500">
                              Match candidates {row.match_candidate_count ?? 0}
                              {" · "}open {row.open_match_candidate_count ?? 0}
                            </p>
                            {(row.match_candidates ?? []).length > 0 ? (
                              <div className="mt-2 space-y-2">
                                {[...(row.match_candidates ?? [])]
                                  .sort(
                                    (a, b) =>
                                      a.candidate_rank - b.candidate_rank ||
                                      b.ranking_score - a.ranking_score ||
                                      b.normalized_confidence_score - a.normalized_confidence_score,
                                  )
                                  .slice(0, 3)
                                  .map((candidate) => (
                                    <div
                                      key={candidate.id}
                                      className={`rounded-lg border px-3 py-2 text-[11px] ${matchCandidateTone(candidate.confidence_bucket)}`}
                                    >
                                      <div className="flex flex-wrap items-center justify-between gap-2">
                                        <span className="font-semibold uppercase tracking-wide">
                                          #{candidate.candidate_rank} · {candidate.candidate_type.replace(/_/g, " ")}
                                        </span>
                                        <span>
                                          {candidate.confidence_bucket} ·{" "}
                                          {(candidate.normalized_confidence_score * 100).toFixed(0)}%
                                        </span>
                                      </div>
                                      <p className="mt-1 text-slate-100">
                                        {candidate.confidence_explanation_summary ?? "No explanation recorded."}
                                      </p>
                                      <p className="mt-1 text-slate-300">
                                        {String(
                                          candidate.ranking_reason_json.ranking_explanation_summary ??
                                            "No ranking explanation recorded.",
                                        )}
                                      </p>
                                      {candidate.grouping_type ? (
                                        <p className="mt-1 text-slate-300">
                                          Grouped as {formatMatchGroupingType(candidate.grouping_type)} ·{" "}
                                          {candidate.grouping_reason_summary ?? "No grouping explanation recorded."}
                                        </p>
                                      ) : null}
                                      {(candidate.penalties ?? []).length > 0 ? (
                                        <p className="mt-1 text-slate-300">
                                          Penalties:{" "}
                                          {candidate.penalties
                                            .slice(0, 2)
                                            .map((item) => String(item.label ?? item.signal ?? "penalty"))
                                            .join(", ")}
                                        </p>
                                      ) : null}
                                    </div>
                                  ))}
                              </div>
                            ) : null}
                            {row.has_pending_ocr_candidate_review ? (
                              <p className="mt-2 inline-flex rounded-full border border-amber-400/30 bg-amber-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-100">
                                Pending OCR review
                              </p>
                            ) : null}
                            {(row.open_ocr_reconciliation_warning_count ?? 0) > 0 ? (
                              <p className="mt-2 inline-flex rounded-full border border-rose-400/30 bg-rose-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-rose-100">
                                OCR reconciliation warnings
                              </p>
                            ) : null}
                            {row.latest_ocr_result?.replay_of_ocr_result_id != null ? (
                              <p className="mt-2 text-xs text-slate-500">
                                Latest OCR replayed from #{row.latest_ocr_result.replay_of_ocr_result_id}
                                {row.latest_ocr_result.replay_reason
                                  ? ` · reason: ${row.latest_ocr_result.replay_reason}`
                                  : ""}
                              </p>
                            ) : null}
                            {row.latest_ocr_result?.source_cover_image_sha256 ? (
                              <p className="mt-2 text-xs text-slate-500">
                                OCR snapshot img {shortSha256(row.latest_ocr_result.source_cover_image_sha256)}
                                {row.latest_ocr_result.source_processing_version
                                  ? ` · ${row.latest_ocr_result.source_processing_version}`
                                  : ""}
                                {row.latest_ocr_result.normalization_version
                                  ? ` · ${row.latest_ocr_result.normalization_version}`
                                  : ""}
                              </p>
                            ) : null}
                          </div>
                          <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
                            <div>
                              <dt className="text-slate-500">Source type</dt>
                              <dd className="font-mono text-slate-300">{row.source_type}</dd>
                            </div>
                            <div>
                              <dt className="text-slate-500">MIME</dt>
                              <dd className="font-mono text-slate-300">{row.mime_type}</dd>
                            </div>
                            <div>
                              <dt className="text-slate-500">Dimensions</dt>
                              <dd>{formatOpsCoverDimensions(row.image_width, row.image_height)}</dd>
                            </div>
                            <div>
                              <dt className="text-slate-500">Size</dt>
                              <dd>{formatOpsCoverFileSize(row.file_size ?? null)}</dd>
                            </div>
                            <div>
                              <dt className="text-slate-500">SHA256</dt>
                              <dd className="font-mono text-slate-300" title={row.sha256_hash}>
                                {shortSha256(row.sha256_hash)}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-slate-500">Canonical series</dt>
                              <dd className="font-mono text-slate-300">
                                {row.canonical_series_id != null ? `#${row.canonical_series_id}` : "—"}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-slate-500">Ready at</dt>
                              <dd>{formatDateTime(row.ready_for_matching_at)}</dd>
                            </div>
                            <div className="sm:col-span-2">
                              <dt className="text-slate-500">Inventory copy</dt>
                              <dd>
                                {row.inventory_copy_id != null ? (
                                  <Link
                                    to={`/inventory/${row.inventory_copy_id}`}
                                    className="text-cyan-300 underline decoration-cyan-300/40 underline-offset-2 hover:text-cyan-200"
                                  >
                                    #{row.inventory_copy_id}
                                  </Link>
                                ) : (
                                  "—"
                                )}
                              </dd>
                            </div>
                            <div className="sm:col-span-2">
                              <dt className="text-slate-500">Draft import</dt>
                              <dd>
                                {row.draft_import_id != null ? (
                                  <Link
                                    to="/imports"
                                    className="text-cyan-300 underline decoration-cyan-300/40 underline-offset-2 hover:text-cyan-200"
                                    title={`Open imports list (draft #${row.draft_import_id})`}
                                  >
                                    #{row.draft_import_id}
                                  </Link>
                                ) : (
                                  "—"
                                )}
                              </dd>
                            </div>
                          </dl>
                          <div className="border-t border-white/10 pt-3">
                            <button
                              type="button"
                              disabled={coverOpsProcessBusyId === row.id || recentCoversLoading}
                              onClick={() => void handleOpsProcessCoverImage(row.id)}
                              className="mb-3 inline-flex w-full justify-center rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white transition hover:border-cyan-300/40 hover:bg-cyan-300/10 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {coverOpsProcessBusyId === row.id ? "Queueing…" : "Reprocess metadata"}
                            </button>
                            {coverOpsProcessMessage[row.id] ? (
                              <p
                                className={`mb-3 text-[11px] leading-snug ${
                                  coverOpsProcessMessage[row.id]?.includes("queued")
                                    ? "text-emerald-300"
                                    : "text-rose-300"
                                }`}
                              >
                                {coverOpsProcessMessage[row.id]}
                              </p>
                            ) : null}
                            <button
                              type="button"
                              disabled={coverOpsEvaluateBusyId === row.id || recentCoversLoading}
                              onClick={() => void handleOpsEvaluateCoverImage(row.id)}
                              className="mb-3 inline-flex w-full justify-center rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white transition hover:border-cyan-300/40 hover:bg-cyan-300/10 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {coverOpsEvaluateBusyId === row.id ? "Evaluating…" : "Evaluate readiness"}
                            </button>
                            {coverOpsEvaluateMessage[row.id] ? (
                              <p
                                className={`mb-3 text-[11px] leading-snug ${
                                  coverOpsEvaluateMessage[row.id] === "Matching readiness evaluated."
                                    ? "text-emerald-300"
                                    : "text-rose-300"
                                }`}
                              >
                                {coverOpsEvaluateMessage[row.id]}
                              </p>
                            ) : null}
                            <button
                              type="button"
                              disabled={coverOpsOcrBusyId === row.id || recentCoversLoading}
                              onClick={() => void handleOpsQueueCoverImageOcr(row)}
                              className="mb-3 inline-flex w-full justify-center rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white transition hover:border-cyan-300/40 hover:bg-cyan-300/10 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {coverOpsOcrBusyId === row.id
                                ? "Queueing…"
                                : ocrHeadline === "failed"
                                  ? "Retry OCR"
                                  : row.latest_ocr_result
                                    ? "Replay OCR"
                                    : "Run OCR"}
                            </button>
                            <button
                              type="button"
                              disabled={coverOpsFingerprintBusyId === row.id || recentCoversLoading}
                              onClick={() => void handleOpsGenerateFingerprints(row.id)}
                              className="mb-3 inline-flex w-full justify-center rounded-lg border border-violet-400/25 bg-violet-500/10 px-3 py-2 text-xs font-semibold text-violet-100 transition hover:border-violet-300/40 hover:bg-violet-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {coverOpsFingerprintBusyId === row.id ? "Generating…" : "Generate fingerprints"}
                            </button>
                            {coverOpsFingerprintMessage[row.id] ? (
                              <p
                                className={`mb-3 text-[11px] leading-snug ${
                                  coverOpsFingerprintMessage[row.id]?.includes("refreshed")
                                    ? "text-emerald-300"
                                    : "text-rose-300"
                                }`}
                              >
                                {coverOpsFingerprintMessage[row.id]}
                              </p>
                            ) : null}
                            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                              Manual assignment
                            </p>
                            <label className="mt-2 block text-xs text-slate-400">
                              Inventory copy id
                              <input
                                type="text"
                                inputMode="numeric"
                                value={coverOpsAssignInvDraft[row.id] ?? ""}
                                disabled={coverOpsAssignBusyId === row.id || recentCoversLoading}
                                onChange={(event) =>
                                  setCoverOpsAssignInvDraft((prev) => ({
                                    ...prev,
                                    [row.id]: event.target.value,
                                  }))
                                }
                                className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white outline-none focus:border-cyan-300/40"
                                placeholder="#"
                              />
                            </label>
                            <label className="mt-2 flex cursor-pointer items-center gap-2 text-xs text-slate-300">
                              <input
                                type="checkbox"
                                checked={coverOpsAssignPrimary[row.id] ?? false}
                                disabled={coverOpsAssignBusyId === row.id || recentCoversLoading}
                                onChange={(event) =>
                                  setCoverOpsAssignPrimary((prev) => ({
                                    ...prev,
                                    [row.id]: event.target.checked,
                                  }))
                                }
                                className="rounded border-white/30 bg-slate-950 accent-cyan-400"
                              />
                              Set as primary
                            </label>
                            <button
                              type="button"
                              disabled={coverOpsAssignBusyId === row.id || recentCoversLoading}
                              onClick={() => void handleOpsAssignCoverToInventory(row.id)}
                              className="mt-2 inline-flex w-full justify-center rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-100 transition hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {coverOpsAssignBusyId === row.id ? "Assigning…" : "Assign to inventory copy"}
                            </button>
                            {coverOpsAssignMessage[row.id] ? (
                              <p
                                className={`mt-2 text-[11px] leading-snug ${
                                  coverOpsAssignMessage[row.id] === "Assigned."
                                    ? "text-emerald-300"
                                    : "text-rose-300"
                                }`}
                              >
                                {coverOpsAssignMessage[row.id]}
                              </p>
                            ) : null}
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
              <div className="flex flex-col gap-3 border-b border-white/10 pb-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-white">Duplicate Cover Images</h2>
                  <p className="mt-2 text-sm text-slate-400">
                    Duplicate cover images are based on identical file hashes. This view does not
                    delete, merge, or relink images.
                  </p>
                </div>
                <button
                  type="button"
                  disabled={duplicateCoversLoading}
                  onClick={() => void refreshDuplicateCoverGroups()}
                  className="shrink-0 rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {duplicateCoversLoading ? "Refreshing…" : "Refresh"}
                </button>
              </div>

              <div className="mt-4 flex flex-wrap gap-4">
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Groups limit</span>
                  <select
                    value={dupCoverLimit}
                    onChange={(event) => setDupCoverLimit(Number(event.target.value))}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  >
                    {[25, 50, 100].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Minimum count</span>
                  <select
                    value={dupCoverMinCount}
                    onChange={(event) => setDupCoverMinCount(Number(event.target.value))}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  >
                    {[2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>
                        {n}+
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Source type</span>
                  <select
                    value={dupCoverSource}
                    onChange={(event) =>
                      setDupCoverSource(event.target.value as "all" | CoverImageSourceType)
                    }
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  >
                    <option value="all">All</option>
                    <option value="upload">upload</option>
                    <option value="gmail_attachment">gmail_attachment</option>
                    <option value="import_image">import_image</option>
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm text-slate-300">
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Linkage</span>
                  <select
                    value={dupCoverLinkage}
                    onChange={(event) =>
                      setDupCoverLinkage(
                        event.target.value as "all" | "inventory" | "import" | "unlinked",
                      )
                    }
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
                  >
                    <option value="all">All</option>
                    <option value="inventory">Inventory copy</option>
                    <option value="import">Draft import</option>
                    <option value="unlinked">Unlinked</option>
                  </select>
                </label>
              </div>

              {duplicateCoversError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{duplicateCoversError}</StatusBanner>
                </div>
              ) : null}

              {duplicateCoversLoading ? (
                <section className="mt-6 rounded-2xl border border-white/5 bg-slate-950/40 px-6 py-12 text-center text-sm text-slate-400">
                  Loading duplicate cover groups…
                </section>
              ) : duplicateCoverGroups.length === 0 ? (
                <section className="mt-6 rounded-2xl border border-white/5 bg-slate-950/40 px-6 py-12 text-center text-sm text-slate-400">
                  No duplicate file hashes matched the filters.
                </section>
              ) : (
                <div className="mt-6 space-y-6">
                  {duplicateCoverGroups.map((group) => (
                    <article
                      key={group.sha256_hash}
                      className="rounded-2xl border border-white/10 bg-slate-950/60 p-5 shadow-inner shadow-black/20"
                    >
                      <div className="flex flex-wrap items-baseline gap-3 border-b border-white/10 pb-3">
                        <p className="font-mono text-lg font-semibold text-white">
                          {shortSha256(group.sha256_hash)}
                        </p>
                        <span className="rounded-full border border-amber-400/35 bg-amber-400/10 px-3 py-0.5 text-xs font-semibold uppercase tracking-wide text-amber-100">
                          {group.count} identical files
                        </span>
                      </div>
                      <p
                        className="mt-2 break-all font-mono text-[11px] text-slate-500"
                        title={group.sha256_hash}
                      >
                        Full SHA256: {group.sha256_hash}
                      </p>
                      <div className="mt-4 flex flex-wrap gap-4">
                        {group.covers.map((cover) => {
                          const dupOcrHeadline = resolveCoverImageOcrHeadline({
                            ocr_visibility: cover.ocr_visibility,
                            latest_ocr_result: cover.latest_ocr_result,
                          });
                          const thumbUrl = dupCoverThumbUrls[cover.id];
                          const thumbFailed = dupCoverThumbErrors[cover.id];
                          return (
                            <div
                              key={cover.id}
                              className="flex gap-3 rounded-xl border border-white/10 bg-slate-950/80 p-3 text-sm text-slate-200"
                            >
                              <div className="relative h-28 w-24 shrink-0 overflow-hidden rounded-lg border border-white/10 bg-slate-900">
                                {thumbUrl ? (
                                  <img
                                    src={thumbUrl}
                                    alt=""
                                    className="h-full w-full object-cover"
                                  />
                                ) : thumbFailed ? (
                                  <div className="flex h-full w-full items-center justify-center px-1 text-center text-[10px] text-slate-500">
                                    Preview unavailable
                                  </div>
                                ) : (
                                  <div className="flex h-full w-full items-center justify-center text-xs text-slate-500">
                                    …
                                  </div>
                                )}
                              </div>
                              <div className="min-w-0 space-y-2">
                                <div className="flex flex-wrap items-center gap-2">
                                  <p className="font-medium text-white">Cover #{cover.id}</p>
                                  {cover.is_primary ? (
                                    <span className="rounded-full border border-amber-400/35 bg-amber-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-100">
                                      Primary
                                    </span>
                                  ) : null}
                                  <span
                                    className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${coverMatchingTone(cover.matching_status)}`}
                                  >
                                    matching {cover.matching_status}
                                  </span>
                                  <span
                                    className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${coverOcrHeadlineTone(dupOcrHeadline)}`}
                                  >
                                    ocr {dupOcrHeadline}
                                  </span>
                                </div>
                                {cover.matching_notes ? (
                                  <p className="text-xs text-amber-100/90">{cover.matching_notes}</p>
                                ) : null}
                                {cover.latest_ocr_result?.replay_of_ocr_result_id != null ? (
                                  <p className="text-xs text-slate-500">
                                    OCR replay of #{cover.latest_ocr_result.replay_of_ocr_result_id}
                                  </p>
                                ) : null}
                                <dl className="grid grid-cols-1 gap-x-3 gap-y-1 text-xs sm:grid-cols-2">
                                  <div>
                                    <dt className="text-slate-500">Source</dt>
                                    <dd className="font-mono text-slate-300">{cover.source_type}</dd>
                                  </div>
                                  <div>
                                    <dt className="text-slate-500">Created</dt>
                                    <dd>{formatDateTime(cover.created_at)}</dd>
                                  </div>
                                  <div className="sm:col-span-2">
                                    <dt className="text-slate-500">Dimensions / size</dt>
                                    <dd>
                                      {formatOpsCoverDimensions(cover.image_width, cover.image_height)} ·{" "}
                                      {formatOpsCoverFileSize(cover.file_size ?? null)}
                                    </dd>
                                  </div>
                                  <div className="sm:col-span-2">
                                    <dt className="text-slate-500">Filename</dt>
                                    <dd className="truncate" title={cover.original_filename ?? ""}>
                                      {cover.original_filename ?? "—"}
                                    </dd>
                                  </div>
                                  <div className="sm:col-span-2">
                                    <dt className="text-slate-500">Ready at</dt>
                                    <dd>{formatDateTime(cover.ready_for_matching_at)}</dd>
                                  </div>
                                  <div className="sm:col-span-2">
                                    <dt className="text-slate-500">Inventory</dt>
                                    <dd>
                                      {cover.inventory_copy_id != null ? (
                                        <Link
                                          to={`/inventory/${cover.inventory_copy_id}`}
                                          className="text-cyan-300 underline decoration-cyan-300/40 underline-offset-2 hover:text-cyan-200"
                                        >
                                          #{cover.inventory_copy_id}
                                        </Link>
                                      ) : (
                                        "—"
                                      )}
                                    </dd>
                                  </div>
                                  <div className="sm:col-span-2">
                                    <dt className="text-slate-500">Draft import</dt>
                                    <dd>
                                      {cover.draft_import_id != null ? (
                                        <Link
                                          to={`/orders/import?importId=${cover.draft_import_id}`}
                                          className="text-cyan-300 underline decoration-cyan-300/40 underline-offset-2 hover:text-cyan-200"
                                        >
                                          #{cover.draft_import_id}
                                        </Link>
                                      ) : (
                                        "—"
                                      )}
                                    </dd>
                                  </div>
                                  <div className="sm:col-span-2">
                                    <dt className="text-slate-500">Canonical series</dt>
                                    <dd className="font-mono">
                                      {cover.canonical_series_id != null ? `#${cover.canonical_series_id}` : "—"}
                                    </dd>
                                  </div>
                                  {cover.owner_email ? (
                                    <div className="sm:col-span-2">
                                      <dt className="text-slate-500">Owner</dt>
                                      <dd>{cover.owner_email}</dd>
                                    </div>
                                  ) : null}
                                </dl>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>

            {metadataAuditsError ? (
              <div>
                <StatusBanner tone="error">{metadataAuditsError}</StatusBanner>
              </div>
            ) : null}

            {metadataAuditsLoading ? (
              <section className="rounded-3xl border border-white/10 bg-slate-900/70 px-8 py-12 text-center text-sm text-slate-400 shadow-xl shadow-black/20">
                Loading metadata audit history…
              </section>
            ) : (
              <TableSection
                title="Metadata Audit History"
                description="Recent metadata mutations and queued deterministic re-enrichment requests. Snapshots stay compact and omit secrets."
                headers={[
                  "When",
                  "Action",
                  "Entity",
                  "Actor",
                  "Reason",
                  "Before",
                  "After",
                ]}
                rows={metadataAudits.map((row) => [
                  formatDateTime(row.created_at),
                  row.action,
                  `${row.entity_type} #${row.entity_id}`,
                  row.actor_email ??
                    (row.actor_user_id !== null ? `User #${row.actor_user_id}` : "System"),
                  row.reason ?? "—",
                  summarizeAuditSnapshot(row.before_snapshot),
                  summarizeAuditSnapshot(row.after_snapshot),
                ])}
              />
            )}

            <TableSection
              title="Queue Health"
              description="Current RQ queue depth, started jobs, failed jobs, and the most recent job result."
              headers={["Queue", "Queued", "Started", "Failed", "Most Recent Result"]}
              rows={dashboard.queue_health.map((queue) => [
                queue.queue_name,
                String(queue.queued_jobs),
                String(queue.started_jobs),
                String(queue.failed_jobs),
                queue.most_recent_job_result ?? "None",
              ])}
            />

            <TableSection
              title="Gmail Sync Visibility"
              description="Latest Gmail sync state, counts, and failure details by connected account."
              headers={[
                "User",
                "Gmail",
                "Status",
                "Started",
                "Completed",
                "Processed",
                "Created",
                "Duplicates",
                "Last Error",
              ]}
              rows={dashboard.gmail_sync_statuses.map((row) => [
                `${row.user_email} (#${row.user_id})`,
                row.gmail_email,
                row.last_sync_status ?? "Never run",
                formatDateTime(row.last_sync_started_at),
                formatDateTime(row.last_sync_completed_at),
                row.processed_messages === null ? "Unknown" : String(row.processed_messages),
                row.created_draft_imports === null ? "Unknown" : String(row.created_draft_imports),
                row.skipped_duplicates === null ? "Unknown" : String(row.skipped_duplicates),
                row.last_error_message ?? "None",
              ])}
            />

            <TableSection
              title="Recent Draft Imports"
              description="Draft lifecycle state, user ownership, confidence, warnings, and linked orders."
              headers={[
                "Draft",
                "User",
                "Retailer",
                "Status",
                "Confidence",
                "Warnings",
                "Created",
                "Linked Order",
              ]}
              rows={dashboard.recent_draft_imports.map((row) => [
                String(row.draft_id),
                `${row.user_email} (#${row.user_id})`,
                row.retailer ?? "Unknown",
                row.status,
                row.confidence,
                String(row.warning_count),
                formatDateTime(row.created_at),
                row.linked_order_id ? (
                  <Link className="text-cyan-200 hover:text-cyan-100" to={`/orders/${row.linked_order_id}`}>
                    Order #{row.linked_order_id}
                  </Link>
                ) : (
                  "None"
                ),
              ])}
            />

            <TableSection
              title="Recent Gmail Sync Jobs"
              description="Recent Gmail sync job activity and result summaries."
              headers={["Job", "Queue", "Status", "User", "Started", "Ended", "Result", "Error"]}
              rows={dashboard.recent_gmail_sync_jobs.map((row) => [
                row.job_id,
                row.queue_name,
                row.status,
                row.user_email ?? "Unknown",
                formatDateTime(row.started_at),
                formatDateTime(row.ended_at),
                row.result_summary ?? "None",
                row.error ?? "None",
              ])}
            />

            <TableSection
              title="Recent AI Parse Jobs"
              description="Recent AI parser job activity and surfaced failures."
              headers={["Job", "Queue", "Status", "User", "Started", "Ended", "Result", "Error"]}
              rows={dashboard.recent_ai_parse_jobs.map((row) => [
                row.job_id,
                row.queue_name,
                row.status,
                row.user_email ?? "Unknown",
                formatDateTime(row.started_at),
                formatDateTime(row.ended_at),
                row.result_summary ?? "None",
                row.error ?? "None",
              ])}
            />

            <TableSection
              title="Parser Failures"
              description="Quota, malformed receipt, unsupported provider, and validation failures surfaced without log inspection."
              headers={["When", "Type", "User", "Draft", "External Message", "Message"]}
              rows={dashboard.parser_failures.map((row) => [
                formatDateTime(row.created_at),
                row.event_type,
                row.user_email ?? "Unknown",
                row.draft_import_id ? String(row.draft_import_id) : "None",
                row.external_message_id ?? "None",
                row.message ?? "None",
              ])}
            />

            <TableSection
              title="Duplicate Skips"
              description="Duplicate Gmail imports that were safely skipped."
              headers={["When", "User", "External Message", "Original Import", "Draft"]}
              rows={dashboard.duplicate_skip_events.map((row) => [
                formatDateTime(row.created_at),
                row.user_email ?? "Unknown",
                row.external_message_id ?? "None",
                typeof row.details.original_imported_at === "string"
                  ? formatDateTime(row.details.original_imported_at)
                  : "Unknown",
                row.draft_import_id ? String(row.draft_import_id) : "None",
              ])}
            />

            <TableSection
              title="Confirm Events"
              description="Recent confirm successes and failures for the import lifecycle."
              headers={["When", "Status", "User", "Draft", "Order", "Message"]}
              rows={dashboard.confirm_events.map((row) => [
                formatDateTime(row.created_at),
                row.status,
                row.user_email ?? "Unknown",
                row.draft_import_id ? String(row.draft_import_id) : "None",
                row.order_id ? (
                  <Link className="text-cyan-200 hover:text-cyan-100" to={`/orders/${row.order_id}`}>
                    Order #{row.order_id}
                  </Link>
                ) : (
                  "None"
                ),
                row.message ?? "None",
              ])}
            />
          </div>
        </>
      ) : null}
    </AppShell>
  );
}
