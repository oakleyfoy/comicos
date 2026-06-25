import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { describeHistoricalTimelineEvent, timelineDotClass } from "../lib/collectionHistoricalTimelineUi";
import { DashboardProfileTabs } from "../components/DashboardProfileTabs";
import { CollectionInsightsSummaryStrip } from "../components/CollectionInsightsSummaryStrip";
import {
  buildPortfolioDeferredWidgetPromises,
  buildDashboardShellWidgetPromises,
  buildDashboardWidgetPromises,
  buildInventoryListWidgetPromises,
  dashboardLoadsDealerEffects,
  dashboardLoadsGradingEffects,
  dashboardLoadsMarketEffects,
  dashboardProfileMeta,
  dashboardShowsAutomationScanCards,
  dashboardShowsCollectionPanels,
  dashboardShowsExtendedWorkbench,
  dashboardShowsInventoryGrid,
  dashboardShowsPortfolioMetricCards,
  dashboardShowsPortfolioPerformance,
  type DashboardLoadProfile,
  type DashboardPortfolioFilters,
} from "../lib/dashboardLoadProfile";
import { settleDashboardWidgets, type DashboardWidgetKey } from "../lib/dashboardPartialLoad";
import { parseReleaseYearFilterInput } from "../lib/inventoryQueryParams";
import {
  canQuickReceiveInventoryCopy,
  countNewlyMarkedFromBulk,
  mergeInventoryRowsAfterReceive,
  summaryAfterReceiveMarked,
} from "../lib/inventoryReceiving";
import { formatCurrencyAmount, formatUsdCurrency, normalizeCurrencyCode } from "../lib/currencyFormat";
import {
  ApiError,
  apiClient,
  type InventoryItem,
  type InventoryOwnershipNormalized,
  type InventoryQueryParams,
  type InventoryReleaseCalendar,
  type InventorySummary,
  type InventoryUpdatePayload,
  type InventoryIntelligenceHealthLevel,
  type DuplicateOwnershipListResponse,
  type DuplicateOwnershipClassification,
  type RunDetectionAttachment,
  type RunDetectionListResponse,
  type RunDetectionSeriesStatus,
  type PortfolioPerformance,
  type PortfolioPerformanceItem,
  type PortfolioLiquiditySnapshotDetailResponse,
  type PortfolioRecommendationListResponse,
  type AcquisitionPriorityListResponse,
  type ConcentrationRiskListResponse,
  type InventoryIntelligenceHealthRollup,
  type InventoryIntelligenceRollupSummary,
  type CollectionAnalyticsSummary,
  type CollectionPublisherAnalyticsResponse,
  type CollectionQualityAnalyticsResponse,
  type CollectionHistoricalTimelineEventsResponse,
  type InventoryRiskPriority,
  type InventoryRiskRead,
  type InventoryRiskSummary,
  type InventoryRiskType,
  type SortBy,
  type InventoryActionCenterAttachment,
  type InventoryActionCenterCategory,
  type InventoryActionCenterSummary,
  type OrderArrivalClassification,
  type OrderArrivalIntelSummary,
  type PhysicalIntakeSummaryResponse,
  type InventoryArrivalTrackingResponse,
  type PortfolioIntelligenceSummary,
  type DuplicateIntelligenceSummary,
  type MarketSourceImportRunSummaryRead,
  type MarketSourceRead,
  type MarketSaleMatchSuggestionOpsListResponse,
  type MarketSaleCompEligibilityListResponse,
  type MarketComparableListResponse,
  type MarketFmvSnapshotListResponse,
  type MarketTrendSnapshotListResponse,
  type MarketSaleSummaryRead,
  type MarketSaleReviewQueueSummaryRead,
  type MarketFmvConfidenceBucket,
  type ScanPipelineDashboardResponse,
  type ScanSessionSummary,
  type InventoryValuationScope,
  type PortfolioValueSummaryResponse,
  type ListingDashboardSummary,
  type ListingIntelligenceDashboardSummary,
  type ListingExportDashboardSummary,
  type DealerDashboardAlertRead,
  type DealerDashboardFeedEventRead,
  type DealerDashboardGetResponse,
  type PortfolioStrategyDashboardAlertRead,
  type PortfolioStrategyDashboardFeedEventRead,
  type PortfolioStrategyDashboardGetResponse,
  type PortfolioStrategyDashboardMetricRead,
  type DealerGradingDashboardAlertRead,
  type DealerGradingDashboardFeedEventRead,
  type DealerGradingDashboardGetResponse,
  type DealerGradingDashboardMetricRead,
  type GradingOperationalReportRunListResponse,
  type ConventionDashboardSummary,
  type LiquidityDashboardSummary,
  type SalesDashboardSummary,
  type OperationalReportingDashboardRollup,
  type GradingCandidateDashboardSummary,
  type GradingRecommendationDashboardSummary,
  type GradingRiskDashboardSummary,
  type GradingReconciliationDashboardSummary,
  type GradingSpreadDashboardSummary,
  type GradingRoiDashboardSummary,
  type GradingSubmissionDashboardSummary,
  type InventoryResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { MarketIntelligenceDashboard } from "../components/MarketIntelligenceDashboard";
import { PageHeader } from "../components/PageHeader";
import { PortfolioInventoryList } from "../components/PortfolioInventoryList";
import { PortfolioInventoryDetailDrawer } from "../components/PortfolioInventoryDetailDrawer";
import { ScanIngestionSummaryCard } from "../components/ScanIngestionSummaryCard";
import { ScanNormalizationSummaryCard } from "../components/ScanNormalizationSummaryCard";
import { ScanBoundarySummaryCard } from "../components/ScanBoundarySummaryCard";
import { ScanOcrSummaryCard } from "../components/ScanOcrSummaryCard";
import { ScanReconciliationSummaryCard } from "../components/ScanReconciliationSummaryCard";
import { ScanDefectsSummaryCard } from "../components/ScanDefectsSummaryCard";
import { ScanSpineTicksSummaryCard } from "../components/ScanSpineTicksSummaryCard";
import { ScanCornerEdgesSummaryCard } from "../components/ScanCornerEdgesSummaryCard";
import { ScanSurfaceDefectsSummaryCard } from "../components/ScanSurfaceDefectsSummaryCard";
import { ScanStructuralDamageSummaryCard } from "../components/ScanStructuralDamageSummaryCard";
import { ScanDefectAggregationSummaryCard } from "../components/ScanDefectAggregationSummaryCard";
import { ScanGradingAssistanceSummaryCard } from "../components/ScanGradingAssistanceSummaryCard";
import { ScanVisualEvidenceSummaryCard } from "../components/ScanVisualEvidenceSummaryCard";
import { ScanReviewSummaryCard } from "../components/ScanReviewSummaryCard";
import { ScanHistoricalComparisonSummaryCard } from "../components/ScanHistoricalComparisonSummaryCard";
import { ScanAuthenticationSummaryCard } from "../components/ScanAuthenticationSummaryCard";
import { ScanIntelligenceFeedSummaryCard } from "../components/ScanIntelligenceFeedSummaryCard";
import { ScanReplaySummaryCard } from "../components/ScanReplaySummaryCard";
import { AutomationBatchSummaryCard } from "../components/AutomationBatchSummaryCard";
import { AutomationNotificationsSummaryCard } from "../components/AutomationNotificationsSummaryCard";
import { AutomationAnalyticsSummaryCard } from "../components/AutomationAnalyticsSummaryCard";
import { AutomationOpsSummaryCard } from "../components/AutomationOpsSummaryCard";
import { AutomationRulesSummaryCard } from "../components/AutomationRulesSummaryCard";
import { AutomationJobsSummaryCard } from "../components/AutomationJobsSummaryCard";
import { AutomationRecoverySummaryCard } from "../components/AutomationRecoverySummaryCard";
import { AutomationWorkersSummaryCard } from "../components/AutomationWorkersSummaryCard";
import { AutomationWorkflowsSummaryCard } from "../components/AutomationWorkflowsSummaryCard";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../auth/AuthContext";

const sortOptions: Array<{ label: string; value: SortBy }> = [
  { label: "Purchase Date", value: "purchase_date" },
  { label: "Title", value: "title" },
  { label: "Acquisition Cost", value: "acquisition_cost" },
  { label: "Current FMV", value: "current_fmv" },
  { label: "Gain / Loss", value: "gain_loss" },
];

function formatMaybeCurrency(value?: string | null): string {
  return value ? formatUsdCurrency(value) : "—";
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function shortenChecksum(value: string | null): string {
  if (!value) {
    return "—";
  }
  if (value.length <= 18) {
    return value;
  }
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
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
      return "border-cyan-400/35 bg-cyan-400/10 text-blue-800";
  }
}

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-patriot-navy">{value}</p>
    </div>
  );
}

function variantLabel(item: InventoryItem): string {
  return [item.cover_name, item.printing, item.ratio, item.variant_type]
    .filter(Boolean)
    .join(" / ");
}

function inventoryReleaseChronologyCell(item: InventoryItem): JSX.Element {
  return (
    <div>
      <p
        className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${assetStateTone(
          item.asset_state,
        )}`}
      >
        {assetStateLabel(item.asset_state)}
      </p>
      <p className="text-slate-600">{item.release_year ?? "—"}</p>
      {item.release_date ? (
        <p className="text-[11px] text-slate-500">{formatDate(item.release_date)}</p>
      ) : null}
      {item.expected_ship_date ? (
        <p className="text-[11px] text-slate-500">Expected {formatDate(item.expected_ship_date)}</p>
      ) : null}
      {item.received_at ? (
        <p className="text-[11px] text-emerald-300">Received {formatDate(item.received_at)}</p>
      ) : null}
    </div>
  );
}

function assetStateLabel(state: InventoryItem["asset_state"]): string {
  switch (state) {
    case "in_hand":
      return "Owned / In Hand";
    case "ordered_not_received":
      return "Ordered / Not Received";
    case "preorder_not_released_yet":
      return "Preorder / Not Released Yet";
    case "cancelled":
      return "Cancelled";
    default:
      return state;
  }
}

function assetStateTone(state: InventoryItem["asset_state"]): string {
  switch (state) {
    case "in_hand":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
    case "ordered_not_received":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "preorder_not_released_yet":
      return "border-blue-300 bg-blue-50 text-blue-800";
    case "cancelled":
      return "border-rose-400/30 bg-rose-400/10 text-rose-200";
    default:
      return "border-slate-200 bg-white/5 text-slate-700";
  }
}

function inventoryOwnershipIntelLabel(state: InventoryOwnershipNormalized): string {
  switch (state) {
    case "in_hand":
      return "In hand";
    case "preorder":
      return "Preorder";
    case "ordered_not_received":
      return "Ordered (not received)";
    case "cancelled":
      return "Cancelled";
    default:
      return "Unknown ownership";
  }
}

function intelligenceHealthTone(level: InventoryIntelligenceHealthLevel): string {
  switch (level) {
    case "healthy":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "needs_review":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "incomplete":
      return "border-cyan-400/35 bg-cyan-400/10 text-blue-800";
    case "blocked":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    default:
      return "border-slate-200 bg-white/5 text-slate-700";
  }
}

function duplicateOwnershipClassificationTitle(value: DuplicateOwnershipClassification): string {
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

function duplicateOwnershipBadgeTone(value: DuplicateOwnershipClassification): string {
  switch (value) {
    case "probable_accidental_duplicate":
    case "unresolved_duplicate":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "duplicate_scan_only":
      return "border-violet-400/35 bg-violet-400/10 text-violet-100";
    case "preorder_plus_owned":
    case "graded_plus_raw":
      return "border-cyan-400/35 bg-cyan-400/10 text-blue-800";
    default:
      return "border-white/15 bg-white/5 text-slate-200";
  }
}

function runDetectionStatusTitle(value: RunDetectionSeriesStatus): string {
  switch (value) {
    case "partial_run":
      return "Partial run";
    case "complete_limited_series":
      return "Complete limited series";
    case "incomplete_limited_series":
      return "Incomplete limited series";
    case "probable_ongoing_series":
      return "Probable ongoing";
    case "isolated_special_annual":
      return "Special / annual isolated";
    default:
      return value;
  }
}

function runDetectionBadgeTone(value: RunDetectionSeriesStatus): string {
  switch (value) {
    case "incomplete_limited_series":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "partial_run":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "probable_ongoing_series":
      return "border-cyan-400/35 bg-cyan-400/10 text-blue-800";
    case "complete_limited_series":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    default:
      return "border-white/15 bg-white/5 text-slate-200";
  }
}

function marketTrendTone(value: string): string {
  switch (value) {
    case "rising":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "stable":
      return "border-cyan-400/35 bg-cyan-400/10 text-blue-800";
    case "falling":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "volatile":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    default:
      return "border-white/15 bg-white/5 text-slate-200";
  }
}

function countInventoryIntelUnresolvedPins(intel: NonNullable<InventoryItem["inventory_intelligence"]>): number {
  let n = 0;
  if (intel.has_open_relationship_conflict) n += 1;
  if (intel.has_pending_canonical_suggestion) n += 1;
  if (intel.in_pending_duplicate_inventory_group) n += 1;
  if (intel.touches_probable_duplicate_scan_cluster) n += 1;
  if (intel.touches_probable_variant_family_cluster) n += 1;
  return n;
}

function InventoryIntelBadges(props: { item: InventoryItem; compact?: boolean }): JSX.Element | null {
  const { item, compact } = props;
  const intel = item.inventory_intelligence;
  const dup = item.duplicate_ownership;
  const run = item.run_detection;
  if (!intel && !dup && !run) {
    return null;
  }

  const pinCount = intel ? countInventoryIntelUnresolvedPins(intel) : 0;

  const wrap = compact ? "mt-2 flex flex-wrap gap-2" : "mt-2 flex flex-wrap gap-2";

  return (
    <div className={wrap}>
      {intel ? (
        <>
          <span
            title="Normalized operational ownership (computed from existing order/release fields)."
            className="inline-flex rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-200"
          >
            Ops: {inventoryOwnershipIntelLabel(intel.ownership_state)}
          </span>
          <span
            title="Deterministic health bucket combining scan completeness, preorder calendar gaps, OCR/cover-processing failures, conflicts, duplicates, clusters, reviews."
            className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${intelligenceHealthTone(
              intel.inventory_health,
            )}`}
          >
            Health: {intel.inventory_health.replace(/_/g, " ")}
          </span>
          {!intel.has_cover_scan ? (
            <span className="inline-flex rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-700">
              Unscanned
            </span>
          ) : null}
          {intel.preorder_missing_release_calendar ? (
            <span className="inline-flex rounded-full border border-amber-400/30 bg-amber-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-amber-100">
              Preorder needs calendar
            </span>
          ) : null}
          {pinCount > 0 ? (
            <span className="inline-flex rounded-full border border-violet-400/35 bg-violet-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-violet-100">
              {pinCount} open signal{pinCount === 1 ? "" : "s"}
            </span>
          ) : null}
        </>
      ) : null}
      {dup ? (
        <span
          title="Deterministic duplicate ownership grouping across metadata identity keys, scans, approvals, preorder/grade lanes, and review pins. Nothing here dedupes inventory."
          className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${duplicateOwnershipBadgeTone(
            dup.classification,
          )}`}
        >
          Dup owner: {duplicateOwnershipClassificationTitle(dup.classification)}
        </span>
      ) : null}
      {run ? (
        <span
          title="Deterministic series-progress lane computed from known issue registry ordering, canonical series identity, ownership state, release timing, and pending canonical issue review pins."
          className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${runDetectionBadgeTone(
            run.series_status,
          )}`}
        >
          Run: {runDetectionStatusTitle(run.series_status)}
          {run.missing_issue_numbers.length ? ` · missing ${run.missing_issue_numbers.length}` : ""}
          {!run.missing_issue_numbers.length && run.pending_issue_numbers.length
            ? ` · pending ${run.pending_issue_numbers.length}`
            : ""}
        </span>
      ) : null}
    </div>
  );
}

function inventoryRiskPriorityTone(priority: InventoryRiskPriority): string {
  switch (priority) {
    case "critical":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "high":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "medium":
      return "border-cyan-400/35 bg-cyan-400/10 text-blue-800";
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

function InventoryRiskBadges(props: { risks?: InventoryRiskRead[] | null }): JSX.Element | null {
  const { risks } = props;
  if (!risks || !risks.length) {
    return null;
  }

  const top = risks.slice(0, 3);
  const more = risks.length - top.length;

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {top.map((risk) => (
        <span
          key={risk.risk_key}
          title={JSON.stringify(risk.evidence_json)}
          className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${inventoryRiskPriorityTone(
            risk.priority,
          )}`}
        >
          {inventoryRiskLabel(risk.risk_type)}
        </span>
      ))}
      {more > 0 ? (
        <span className="inline-flex rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-700">
          +{more} more
        </span>
      ) : null}
    </div>
  );
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

function InventoryActionCenterBadges(props: {
  attachment?: InventoryActionCenterAttachment | null;
}): JSX.Element | null {
  const list = props.attachment?.action_categories ?? [];
  if (!list.length) {
    return null;
  }
  const top = list.slice(0, 3);
  const more = list.length - top.length;

  function short(cat: InventoryActionCenterCategory): string {
    switch (cat) {
      case "review_relationship_conflict":
        return "Conflict";
      case "review_canonical_suggestion":
        return "Canon";
      case "review_duplicate_ownership":
        return "Dup own";
      case "review_duplicate_scan":
        return "Dup scan";
      case "review_variant_family":
        return "Variant fam";
      case "retry_ocr":
        return "Retry OCR";
      case "review_cover_processing":
        return "Cover proc";
      case "scan_missing_cover":
        return "No scan";
      case "update_preorder_metadata":
        return "Preorder meta";
      case "review_run_gap":
        return "Run gap";
      case "review_high_confidence_match":
        return "Match review";
      default:
        return inventoryActionCenterCategoryUiLabel(cat);
    }
  }

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {top.map((cat) => (
        <span
          key={cat}
          className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${
            props.attachment?.urgent_lane
              ? "border-rose-400/35 bg-rose-400/10 text-rose-100"
              : "border-teal-400/30 bg-teal-400/10 text-teal-100"
          }`}
        >
          {short(cat)}
        </span>
      ))}
      {more > 0 ? (
        <span className="inline-flex rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-700">
          +{more} actions
        </span>
      ) : null}
    </div>
  );
}

function orderArrivalTone(value: OrderArrivalClassification): string {
  switch (value) {
    case "overdue_expected_ship":
    case "released_not_received":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "missing_release_date":
    case "missing_expected_ship_date":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "upcoming_preorder":
    case "releases_this_week":
      return "border-cyan-400/35 bg-cyan-400/10 text-blue-800";
    case "expected_to_ship_soon":
      return "border-violet-400/35 bg-violet-400/10 text-violet-100";
    case "received_recently":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "cancelled_order":
      return "border-white/15 bg-white/5 text-slate-700";
    default:
      return "border-white/15 bg-white/5 text-slate-700";
  }
}

function orderArrivalLabelShort(value: OrderArrivalClassification): string {
  switch (value) {
    case "upcoming_preorder":
      return "Upcoming preorder";
    case "releases_this_week":
      return "Release this week";
    case "released_not_received":
      return "Released / not recv";
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

function OrderArrivalBadges(props: { classifications?: OrderArrivalClassification[] | null }): JSX.Element | null {
  const list = props.classifications ?? [];
  if (!list.length) {
    return null;
  }

  const top = list.slice(0, 3);
  const more = list.length - top.length;

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {top.map((c) => (
        <span
          key={c}
          className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${orderArrivalTone(c)}`}
        >
          Ord: {orderArrivalLabelShort(c)}
        </span>
      ))}
      {more > 0 ? (
        <span className="inline-flex rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-700">
          +{more} more
        </span>
      ) : null}
    </div>
  );
}

function orderArrivalBucketCount(summary: OrderArrivalIntelSummary, key: OrderArrivalClassification): number {
  const row = summary.by_classification.find((r) => r.key === key);
  return typeof row?.count === "number" ? row.count : 0;
}
function totalInventoryIntelUnresolvedRollup(summary: InventoryIntelligenceRollupSummary): number {
  return (
    summary.unresolved_relationship_conflicts +
    summary.unresolved_canonical_suggestions +
    summary.unresolved_duplicate_inventory_groups +
    summary.unresolved_duplicate_scan_clusters +
    summary.unresolved_variant_family_clusters
  );
}

function gainLossClass(value: string | null): string {
  if (value === null) {
    return "text-slate-600";
  }

  const amount = Number(value);
  if (amount > 0) {
    return "text-emerald-300";
  }
  if (amount < 0) {
    return "text-rose-800";
  }
  return "text-slate-700";
}

function normalizeDecimalInput(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function performanceLabel(item: PortfolioPerformanceItem): string {
  return `${item.title} #${item.issue_number}`;
}

function formatScanSessionType(value: ScanSessionSummary["session_type"]): string {
  return value.replace(/_/g, " ");
}

function ScanSessionMiniTable(props: {
  caption: string;
  rows: ScanSessionSummary[];
}): JSX.Element {
  const { caption, rows } = props;

  const processedSum = rows.reduce((acc, r) => acc + r.processed_items, 0);
  const itemsSum = rows.reduce((acc, r) => acc + r.total_items, 0);

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{caption}</p>
        <p className="text-[11px] text-slate-500">
          Row progress rollup:{" "}
          <span className="font-semibold text-slate-700">
            {processedSum}/{itemsSum}
          </span>{" "}
          processed / total scans
        </p>
      </div>
      {rows.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">No sessions yet.</p>
      ) : (
        <div className="mt-3 overflow-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
              <tr>
                <th className="pb-2 pr-3 font-medium">Session</th>
                <th className="pb-2 pr-3 font-medium">Kind</th>
                <th className="pb-2 pr-3 font-medium">Status</th>
                <th className="pb-2 pr-3 font-medium">Processed</th>
                <th className="pb-2 pr-3 font-medium">Failed</th>
                <th className="pb-2 font-medium">Skipped</th>
              </tr>
            </thead>
            <tbody className="text-slate-200">
              {rows.map((row) => (
                <tr key={row.id} className="border-t border-slate-200">
                  <td className="py-2 pr-3 font-mono text-[11px] text-white">#{row.id}</td>
                  <td className="py-2 pr-3 capitalize text-slate-700">{formatScanSessionType(row.session_type)}</td>
                  <td className="py-2 pr-3 capitalize text-slate-700">{row.status.replace(/_/g, " ")}</td>
                  <td className="py-2 pr-3 text-slate-700">
                    {row.processed_items}/{row.total_items}
                  </td>
                  <td className="py-2 pr-3">{row.failed_items}</td>
                  <td className="py-2">{row.skipped_items}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function DashboardPage({ loadProfile = "portfolio" }: { loadProfile?: DashboardLoadProfile }) {
  const { user } = useAuth();
  const profileMeta = dashboardProfileMeta(loadProfile);
  const loadsMarketData = dashboardLoadsMarketEffects(loadProfile);
  const loadsDealerData = dashboardLoadsDealerEffects(loadProfile);
  const loadsGradingData = dashboardLoadsGradingEffects(loadProfile);
  const showExtendedWorkbench = dashboardShowsExtendedWorkbench(loadProfile);
  const showCollectionPanels = dashboardShowsCollectionPanels(loadProfile);
  const showInventoryGrid = dashboardShowsInventoryGrid(loadProfile);
  const showAutomationScanCards = dashboardShowsAutomationScanCards(loadProfile);
  const loadsFullWorkspace = loadProfile === "full";
  const showPortfolioMetricCards = dashboardShowsPortfolioMetricCards(loadProfile);
  const showPortfolioPerformance = dashboardShowsPortfolioPerformance(loadProfile);
  const showCompactHeadlineStats =
    !showPortfolioMetricCards &&
    loadProfile !== "collection" &&
    (loadProfile === "market" || loadProfile === "grading" || loadProfile === "dealer");

  const [searchParams] = useSearchParams();
  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [performance, setPerformance] = useState<PortfolioPerformance | null>(null);
  const [portfolioValueSummary, setPortfolioValueSummary] = useState<PortfolioValueSummaryResponse | null>(null);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");

  useEffect(() => {
    const q = searchParams.get("q")?.trim();
    if (q) {
      setSearchInput(q);
      setSearch(q);
    }
  }, [searchParams]);

  const [publisher, setPublisher] = useState("");
  const [holdStatus, setHoldStatus] = useState("");
  const [gradeStatus, setGradeStatus] = useState("");
  const [releaseYearFilter, setReleaseYearFilter] = useState("");
  const [releaseCalendarFilter, setReleaseCalendarFilter] = useState<"" | InventoryReleaseCalendar>(
    "",
  );
  const [assetStateFilter, setAssetStateFilter] = useState<"" | InventoryItem["asset_state"]>("");
  const [intelHealthFilter, setIntelHealthFilter] = useState<
    "" | InventoryIntelligenceHealthLevel | "not_healthy"
  >("");
  const [ownershipIntelFilter, setOwnershipIntelFilter] = useState<"" | InventoryOwnershipNormalized>(
    "",
  );
  const [valuationScopeFilter, setValuationScopeFilter] = useState<"" | InventoryValuationScope>("");
  const [confidenceBucketFilter, setConfidenceBucketFilter] = useState<"" | MarketFmvConfidenceBucket>("");
  const [riskPriorityFilter, setRiskPriorityFilter] = useState<"" | InventoryRiskPriority>("");
  const [riskTypeFilter, setRiskTypeFilter] = useState<"" | InventoryRiskType>("");
  const [needsAttentionFilter, setNeedsAttentionFilter] = useState(false);
  const [actionAttentionFilter, setActionAttentionFilter] = useState(false);
  const [actionCategoryFilter, setActionCategoryFilter] = useState<"" | InventoryActionCenterCategory>("");
  const [arrivalClassificationFilter, setArrivalClassificationFilter] = useState<"" | OrderArrivalClassification>("");
  const [sortBy, setSortBy] = useState<SortBy>("purchase_date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [isLoading, setIsLoading] = useState(true);
  const [inventoryListLoading, setInventoryListLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [receivingCopyIds, setReceivingCopyIds] = useState<ReadonlySet<number>>(() => new Set());
  const [dashboardWidgetErrors, setDashboardWidgetErrors] = useState<
    Partial<Record<DashboardWidgetKey, string>>
  >({});
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkHoldStatus, setBulkHoldStatus] = useState<"hold" | "sell" | "sold">("sell");
  const [fMvDrafts, setFmvDrafts] = useState<Record<number, string>>({});
  const [holdDrafts, setHoldDrafts] = useState<Record<number, InventoryItem["hold_status"]>>({});
  const [gradeDrafts, setGradeDrafts] = useState<Record<number, InventoryItem["grade_status"]>>({});
  const [starDrafts, setStarDrafts] = useState<Record<number, string>>({});
  const [activeNotesItem, setActiveNotesItem] = useState<InventoryItem | null>(null);
  const [drawerInventoryCopyId, setDrawerInventoryCopyId] = useState<number | null>(null);
  const [notesDraft, setNotesDraft] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [inventoryIntelSummary, setInventoryIntelSummary] = useState<InventoryIntelligenceRollupSummary | null>(
    null,
  );
  const [inventoryIntelHealth, setInventoryIntelHealth] = useState<InventoryIntelligenceHealthRollup | null>(
    null,
  );
  const [inventoryRiskSummary, setInventoryRiskSummary] = useState<InventoryRiskSummary | null>(null);
  const [inventoryActionSummary, setInventoryActionSummary] = useState<InventoryActionCenterSummary | null>(null);
  const [orderArrivalSummary, setOrderArrivalSummary] = useState<OrderArrivalIntelSummary | null>(null);
  const [duplicateOwnershipReport, setDuplicateOwnershipReport] =
    useState<DuplicateOwnershipListResponse | null>(null);
  const [runDetectionReport, setRunDetectionReport] = useState<RunDetectionListResponse | null>(null);

  const [collectionAnalyticsSummary, setCollectionAnalyticsSummary] = useState<CollectionAnalyticsSummary | null>(null);
  const [collectionAnalyticsPublishers, setCollectionAnalyticsPublishers] =
    useState<CollectionPublisherAnalyticsResponse | null>(null);
  const [collectionAnalyticsQuality, setCollectionAnalyticsQuality] = useState<CollectionQualityAnalyticsResponse | null>(
      null,
    );

  const [collectionHistoricalTimeline, setCollectionHistoricalTimeline] =
    useState<CollectionHistoricalTimelineEventsResponse | null>(null);
  const [scanPipelineDash, setScanPipelineDash] = useState<ScanPipelineDashboardResponse | null>(null);
  const [physicalIntakeSummary, setPhysicalIntakeSummary] =
    useState<PhysicalIntakeSummaryResponse | null>(null);
  const [inventoryArrivalTracking, setInventoryArrivalTracking] =
    useState<InventoryArrivalTrackingResponse | null>(null);
  const [marketSources, setMarketSources] = useState<MarketSourceRead[]>([]);
  const [marketSourcesLoading, setMarketSourcesLoading] = useState(true);
  const [marketSourcesError, setMarketSourcesError] = useState<string | null>(null);
  const [marketImportRuns, setMarketImportRuns] = useState<MarketSourceImportRunSummaryRead[]>([]);
  const [marketImportRunsLoading, setMarketImportRunsLoading] = useState(true);
  const [marketImportRunsError, setMarketImportRunsError] = useState<string | null>(null);
  const [marketSalesPreview, setMarketSalesPreview] = useState<MarketSaleSummaryRead[]>([]);
  const [marketSalesLoading, setMarketSalesLoading] = useState(true);
  const [marketSalesError, setMarketSalesError] = useState<string | null>(null);
  const [marketSaleReviewQueueSummary, setMarketSaleReviewQueueSummary] =
    useState<MarketSaleReviewQueueSummaryRead | null>(null);
  const [marketSaleReviewQueueSummaryLoading, setMarketSaleReviewQueueSummaryLoading] = useState(true);
  const [marketSaleReviewQueueSummaryError, setMarketSaleReviewQueueSummaryError] = useState<string | null>(null);
  const [marketMatchSuggestionsPendingCount, setMarketMatchSuggestionsPendingCount] = useState(0);
  const [marketMatchSuggestionsPendingLoading, setMarketMatchSuggestionsPendingLoading] = useState(true);
  const [marketMatchSuggestionsPendingError, setMarketMatchSuggestionsPendingError] = useState<string | null>(null);
  const [marketCompEligibilitySummary, setMarketCompEligibilitySummary] =
    useState<MarketSaleCompEligibilityListResponse | null>(null);
  const [marketCompEligibilitySummaryLoading, setMarketCompEligibilitySummaryLoading] = useState(true);
  const [marketCompEligibilitySummaryError, setMarketCompEligibilitySummaryError] = useState<string | null>(null);
  const [marketCompsSummary, setMarketCompsSummary] = useState<MarketComparableListResponse | null>(null);
  const [marketCompsSummaryLoading, setMarketCompsSummaryLoading] = useState(true);
  const [marketCompsSummaryError, setMarketCompsSummaryError] = useState<string | null>(null);
  const [marketFmvSummary, setMarketFmvSummary] = useState<MarketFmvSnapshotListResponse | null>(null);
  const [marketFmvSummaryLoading, setMarketFmvSummaryLoading] = useState(true);
  const [marketFmvSummaryError, setMarketFmvSummaryError] = useState<string | null>(null);
  const [marketTrendSummary, setMarketTrendSummary] = useState<MarketTrendSnapshotListResponse | null>(null);
  const [marketTrendSummaryLoading, setMarketTrendSummaryLoading] = useState(true);
  const [marketTrendSummaryError, setMarketTrendSummaryError] = useState<string | null>(null);
  const [listingRegistrySummary, setListingRegistrySummary] = useState<ListingDashboardSummary | null>(null);
  const [listingRegistrySummaryLoading, setListingRegistrySummaryLoading] = useState(true);
  const [listingRegistrySummaryError, setListingRegistrySummaryError] = useState<string | null>(null);
  const [listingIntelligenceSummary, setListingIntelligenceSummary] = useState<ListingIntelligenceDashboardSummary | null>(null);
  const [listingIntelligenceSummaryLoading, setListingIntelligenceSummaryLoading] = useState(true);
  const [listingIntelligenceSummaryError, setListingIntelligenceSummaryError] = useState<string | null>(null);
  const [conventionSummary, setConventionSummary] = useState<ConventionDashboardSummary | null>(null);
  const [conventionSummaryLoading, setConventionSummaryLoading] = useState(true);
  const [conventionSummaryError, setConventionSummaryError] = useState<string | null>(null);
  const [liquiditySummary, setLiquiditySummary] = useState<LiquidityDashboardSummary | null>(null);
  const [liquiditySummaryLoading, setLiquiditySummaryLoading] = useState(true);
  const [liquiditySummaryError, setLiquiditySummaryError] = useState<string | null>(null);
  const [salesLedgerSummary, setSalesLedgerSummary] = useState<SalesDashboardSummary | null>(null);
  const [salesLedgerSummaryLoading, setSalesLedgerSummaryLoading] = useState(true);
  const [salesLedgerSummaryError, setSalesLedgerSummaryError] = useState<string | null>(null);

  const [listingExportDash, setListingExportDash] = useState<ListingExportDashboardSummary | null>(null);
  const [listingExportDashLoading, setListingExportDashLoading] = useState(true);
  const [listingExportDashError, setListingExportDashError] = useState<string | null>(null);

  const [dealerDashResp, setDealerDashResp] = useState<DealerDashboardGetResponse | null>(null);
  const [dealerDashLoading, setDealerDashLoading] = useState(true);
  const [dealerDashError, setDealerDashError] = useState<string | null>(null);
  const [dealerAlerts, setDealerAlerts] = useState<DealerDashboardAlertRead[]>([]);
  const [dealerFeed, setDealerFeed] = useState<DealerDashboardFeedEventRead[]>([]);
  const [dealerGenBusy, setDealerGenBusy] = useState(false);
  const [strategyDashResp, setStrategyDashResp] = useState<PortfolioStrategyDashboardGetResponse | null>(null);
  const [strategyDashLoading, setStrategyDashLoading] = useState(true);
  const [strategyDashError, setStrategyDashError] = useState<string | null>(null);
  const [strategyAlerts, setStrategyAlerts] = useState<PortfolioStrategyDashboardAlertRead[]>([]);
  const [strategyFeed, setStrategyFeed] = useState<PortfolioStrategyDashboardFeedEventRead[]>([]);
  const [strategyMetrics, setStrategyMetrics] = useState<PortfolioStrategyDashboardMetricRead[]>([]);
  const [strategyGenBusy, setStrategyGenBusy] = useState(false);
  const [dealerGradingDashResp, setDealerGradingDashResp] = useState<DealerGradingDashboardGetResponse | null>(null);
  const [dealerGradingDashLoading, setDealerGradingDashLoading] = useState(true);
  const [dealerGradingDashError, setDealerGradingDashError] = useState<string | null>(null);
  const [dealerGradingAlerts, setDealerGradingAlerts] = useState<DealerGradingDashboardAlertRead[]>([]);
  const [dealerGradingFeed, setDealerGradingFeed] = useState<DealerGradingDashboardFeedEventRead[]>([]);
  const [dealerGradingMetrics, setDealerGradingMetrics] = useState<DealerGradingDashboardMetricRead[]>([]);
  const [dealerGradingGenBusy, setDealerGradingGenBusy] = useState(false);
  const [opReportRollups, setOpReportRollups] = useState<OperationalReportingDashboardRollup | null>(null);
  const [opReportRollupsLoading, setOpReportRollupsLoading] = useState(true);
  const [opReportRollupsError, setOpReportRollupsError] = useState<string | null>(null);
  const [opReportBusy, setOpReportBusy] = useState(false);
  const [gradingReportsRecent, setGradingReportsRecent] = useState<GradingOperationalReportRunListResponse | null>(null);
  const [gradingReportsFailed, setGradingReportsFailed] = useState<GradingOperationalReportRunListResponse | null>(null);
  const [gradingReportsLoading, setGradingReportsLoading] = useState(true);
  const [gradingReportsError, setGradingReportsError] = useState<string | null>(null);
  const [gradingReportBusy, setGradingReportBusy] = useState(false);
  const [gradingDashSummary, setGradingDashSummary] = useState<GradingCandidateDashboardSummary | null>(null);
  const [gradingDashLoading, setGradingDashLoading] = useState(true);
  const [gradingDashError, setGradingDashError] = useState<string | null>(null);
  const [gradingSpreadSummary, setGradingSpreadSummary] = useState<GradingSpreadDashboardSummary | null>(null);
  const [gradingSpreadLoading, setGradingSpreadLoading] = useState(true);
  const [gradingSpreadError, setGradingSpreadError] = useState<string | null>(null);
  const [gradingRoiSummary, setGradingRoiSummary] = useState<GradingRoiDashboardSummary | null>(null);
  const [gradingRoiLoading, setGradingRoiLoading] = useState(true);
  const [gradingRoiError, setGradingRoiError] = useState<string | null>(null);
  const [gradingRiskSummary, setGradingRiskSummary] = useState<GradingRiskDashboardSummary | null>(null);
  const [gradingRiskLoading, setGradingRiskLoading] = useState(true);
  const [gradingRiskError, setGradingRiskError] = useState<string | null>(null);
  const [gradingSubmissionSummary, setGradingSubmissionSummary] = useState<GradingSubmissionDashboardSummary | null>(
    null,
  );
  const [gradingSubmissionLoading, setGradingSubmissionLoading] = useState(true);
  const [gradingSubmissionError, setGradingSubmissionError] = useState<string | null>(null);
  const [gradingReconciliationSummary, setGradingReconciliationSummary] =
    useState<GradingReconciliationDashboardSummary | null>(null);
  const [gradingReconciliationLoading, setGradingReconciliationLoading] = useState(true);
  const [gradingReconciliationError, setGradingReconciliationError] = useState<string | null>(null);
  const [gradingRecommendationSummary, setGradingRecommendationSummary] =
    useState<GradingRecommendationDashboardSummary | null>(null);
  const [gradingRecommendationLoading, setGradingRecommendationLoading] = useState(true);
  const [gradingRecommendationError, setGradingRecommendationError] = useState<string | null>(null);
  const [portfolioIntelSummary, setPortfolioIntelSummary] = useState<PortfolioIntelligenceSummary | null>(null);
  const [portfolioIntelLoading, setPortfolioIntelLoading] = useState(true);
  const [portfolioIntelError, setPortfolioIntelError] = useState<string | null>(null);
  const [portfolioIntelGenBusy, setPortfolioIntelGenBusy] = useState(false);
  const [dupIntelSummary, setDupIntelSummary] = useState<DuplicateIntelligenceSummary | null>(null);
  const [dupIntelLoading, setDupIntelLoading] = useState(true);
  const [dupIntelError, setDupIntelError] = useState<string | null>(null);
  const [dupIntelGenBusy, setDupIntelGenBusy] = useState(false);
  const [portfolioLiquidityDetail, setPortfolioLiquidityDetail] = useState<PortfolioLiquiditySnapshotDetailResponse | null>(null);
  const [portfolioLiquidityLoading, setPortfolioLiquidityLoading] = useState(true);
  const [portfolioLiquidityError, setPortfolioLiquidityError] = useState<string | null>(null);
  const [portfolioLiquidityGenBusy, setPortfolioLiquidityGenBusy] = useState(false);
  const [portfolioRecommendationList, setPortfolioRecommendationList] = useState<PortfolioRecommendationListResponse | null>(
    null,
  );
  const [portfolioRecommendationLoading, setPortfolioRecommendationLoading] = useState(true);
  const [portfolioRecommendationError, setPortfolioRecommendationError] = useState<string | null>(null);
  const [portfolioRecommendationGenBusy, setPortfolioRecommendationGenBusy] = useState(false);
  const [acquisitionPriorityList, setAcquisitionPriorityList] = useState<AcquisitionPriorityListResponse | null>(null);
  const [acquisitionPriorityLoading, setAcquisitionPriorityLoading] = useState(true);
  const [acquisitionPriorityError, setAcquisitionPriorityError] = useState<string | null>(null);
  const [acquisitionPriorityGenBusy, setAcquisitionPriorityGenBusy] = useState(false);
  const [concentrationRiskList, setConcentrationRiskList] = useState<ConcentrationRiskListResponse | null>(null);
  const [concentrationRiskLoading, setConcentrationRiskLoading] = useState(true);
  const [concentrationRiskError, setConcentrationRiskError] = useState<string | null>(null);
  const [concentrationRiskGenBusy, setConcentrationRiskGenBusy] = useState(false);
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const dealerGradingMetricMap = useMemo(
    () => new Map(dealerGradingMetrics.map((row) => [row.metric_key, row])),
    [dealerGradingMetrics],
  );
  const strategyMetricMap = useMemo(
    () => new Map(strategyMetrics.map((row) => [row.metric_key, row])),
    [strategyMetrics],
  );
  const strategyDuplicateClusters = useMemo(() => {
    const clusters = strategyMetricMap.get("duplicate_top_clusters")?.metric_metadata_json;
    if (!clusters || typeof clusters !== "object" || !("clusters" in clusters) || !Array.isArray(clusters.clusters)) {
      return [] as Array<Record<string, unknown>>;
    }
    return clusters.clusters as Array<Record<string, unknown>>;
  }, [strategyMetricMap]);
  const strategyAcquisitionFocusRows = useMemo(() => {
    const rows = strategyMetricMap.get("acquisition_focus_rows")?.metric_metadata_json;
    if (!rows || typeof rows !== "object" || !("rows" in rows) || !Array.isArray(rows.rows)) {
      return [] as Array<Record<string, unknown>>;
    }
    return rows.rows as Array<Record<string, unknown>>;
  }, [strategyMetricMap]);
  const loadPortfolioStrategyDashboard = useCallback(async () => {
    if (!user) {
      setStrategyDashResp(null);
      setStrategyAlerts([]);
      setStrategyFeed([]);
      setStrategyMetrics([]);
      setStrategyDashLoading(false);
      setStrategyDashError(null);
      return;
    }
    setStrategyDashLoading(true);
    setStrategyDashError(null);
    const [dashResult, alertsResult, feedResult, metricsResult] = await Promise.allSettled([
      apiClient.getPortfolioStrategyDashboard(),
      apiClient.listPortfolioStrategyDashboardAlerts({ limit: 24, offset: 0 }),
      apiClient.listPortfolioStrategyDashboardFeed({ limit: 24, offset: 0 }),
      apiClient.listPortfolioStrategyDashboardMetrics({ limit: 80, offset: 0 }),
    ]);
    const dash = dashResult.status === "fulfilled" ? dashResult.value : null;
    const failedParts: string[] = [];
    if (dashResult.status === "rejected") {
      failedParts.push("snapshot");
    }
    if (alertsResult.status === "fulfilled") {
      setStrategyAlerts(alertsResult.value.items);
    } else {
      setStrategyAlerts([]);
      failedParts.push("alerts");
    }
    if (feedResult.status === "fulfilled") {
      setStrategyFeed(feedResult.value.items);
    } else {
      setStrategyFeed([]);
      failedParts.push("feed");
    }
    if (metricsResult.status === "fulfilled") {
      setStrategyMetrics(metricsResult.value.items);
    } else {
      setStrategyMetrics([]);
      failedParts.push("metrics");
    }
    setStrategyDashResp(dash);
    if (failedParts.length > 0) {
      const primaryMessage =
        dashResult.status === "rejected"
          ? dashResult.reason instanceof ApiError
            ? dashResult.reason.message
            : "Unable to load portfolio strategy dashboard."
          : `Strategy dashboard partially loaded. Missing ${failedParts.join(", ")}.`;
      setStrategyDashError(primaryMessage);
    } else {
      setStrategyDashError(null);
    }
    setStrategyDashLoading(false);
  }, [user]);
  const portfolioRecommendationSummary = useMemo(() => {
    const items = portfolioRecommendationList?.items ?? [];
    const summary = {
      total: portfolioRecommendationList?.total ?? 0,
      holdCount: 0,
      sellCount: 0,
      reduceExposureCount: 0,
      gradeThenSellCount: 0,
      consolidateCount: 0,
      watchCount: 0,
      estimatedCapitalRelease: 0,
      estimatedPortfolioEfficiencyGain: 0,
    };
    for (const row of items) {
      switch (row.recommendation_action) {
        case "HOLD":
          summary.holdCount += 1;
          break;
        case "SELL":
          summary.sellCount += 1;
          break;
        case "REDUCE_EXPOSURE":
          summary.reduceExposureCount += 1;
          break;
        case "GRADE_THEN_SELL":
          summary.gradeThenSellCount += 1;
          break;
        case "CONSOLIDATE":
          summary.consolidateCount += 1;
          break;
        case "WATCH":
        default:
          summary.watchCount += 1;
          break;
      }
      summary.estimatedCapitalRelease += Number(row.estimated_capital_release ?? 0);
      summary.estimatedPortfolioEfficiencyGain += Number(row.estimated_portfolio_efficiency_gain ?? 0);
    }
    return summary;
  }, [portfolioRecommendationList]);
  const concentrationRiskSummary = useMemo(() => {
    const items = concentrationRiskList?.items ?? [];
    const summary = {
      total: concentrationRiskList?.total ?? 0,
      concentratedCount: 0,
      criticalCount: 0,
      avgDiversificationScore: 0,
      highLiquidityFragilityCount: 0,
      duplicateWarningCount: 0,
    };
    if (!items.length) {
      return summary;
    }
    let diversificationTotal = 0;
    for (const row of items) {
      if (["CONCENTRATED", "OVEREXPOSED", "CRITICAL"].includes(row.exposure_status)) {
        summary.concentratedCount += 1;
      }
      if (row.exposure_status === "CRITICAL") {
        summary.criticalCount += 1;
      }
      diversificationTotal += Number(row.diversification_score ?? 0);
      if (Number(row.liquidity_weighted_concentration ?? 0) >= 45) {
        summary.highLiquidityFragilityCount += 1;
      }
      if (["grading_status", "liquidity_status", "variant_family"].includes(row.concentration_type) && row.exposure_status !== "HEALTHY") {
        summary.duplicateWarningCount += 1;
      }
    }
    summary.avgDiversificationScore = diversificationTotal / items.length;
    return summary;
  }, [concentrationRiskList]);
  const acquisitionPrioritySummary = useMemo(() => {
    const items = acquisitionPriorityList?.items ?? [];
    const summary = {
      total: acquisitionPriorityList?.total ?? 0,
      highPriority: 0,
      eliteOpportunities: 0,
      diversificationOpportunities: 0,
      liquidityImprovementOpportunities: 0,
      gradingOpportunityCount: 0,
    };
    for (const row of items) {
      if (row.acquisition_priority === "HIGH" || row.acquisition_priority === "ELITE") {
        summary.highPriority += 1;
      }
      if (row.acquisition_priority === "ELITE") {
        summary.eliteOpportunities += 1;
      }
      if (row.acquisition_category === "DIVERSIFICATION" || row.acquisition_category === "LOW_EXPOSURE_CATEGORY") {
        summary.diversificationOpportunities += 1;
      }
      if (row.acquisition_category === "LIQUIDITY_IMPROVEMENT") {
        summary.liquidityImprovementOpportunities += 1;
      }
      if (row.acquisition_category === "GRADING_OPPORTUNITY") {
        summary.gradingOpportunityCount += 1;
      }
    }
    return summary;
  }, [acquisitionPriorityList]);
  const inventoryQuery = useMemo<InventoryQueryParams>(
    () => ({
      page,
      page_size: pageSize,
      search: search || undefined,
      publisher: publisher || undefined,
      hold_status: holdStatus || undefined,
      grade_status: gradeStatus || undefined,
      release_year: parseReleaseYearFilterInput(releaseYearFilter),
      release_calendar: releaseCalendarFilter || undefined,
      asset_state: assetStateFilter || undefined,
      intelligence_health:
        intelHealthFilter ||
        undefined,
      ownership_intel: ownershipIntelFilter || undefined,
      valuation_scope: valuationScopeFilter || undefined,
      confidence_bucket: confidenceBucketFilter || undefined,
      risk_priority: riskPriorityFilter || undefined,
      risk_type: riskTypeFilter || undefined,
      needs_attention: needsAttentionFilter || undefined,
      action_attention: actionAttentionFilter || undefined,
      action_center_category: actionCategoryFilter || undefined,
      arrival_classification: arrivalClassificationFilter || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
      list_enrichment: loadProfile === "portfolio" ? "card" : "full",
    }),
    [
      gradeStatus,
      holdStatus,
      page,
      pageSize,
      publisher,
      releaseCalendarFilter,
      assetStateFilter,
      intelHealthFilter,
      needsAttentionFilter,
      actionAttentionFilter,
      actionCategoryFilter,
      ownershipIntelFilter,
      valuationScopeFilter,
      confidenceBucketFilter,
      riskPriorityFilter,
      riskTypeFilter,
      arrivalClassificationFilter,
      releaseYearFilter,
      search,
      sortBy,
      sortDir,
      loadProfile,
    ],
  );

  const dashboardPortfolioFilters = useMemo<DashboardPortfolioFilters>(
    () => ({
      publisher,
      ownershipIntelFilter,
      valuationScopeFilter,
      confidenceBucketFilter,
    }),
    [publisher, ownershipIntelFilter, valuationScopeFilter, confidenceBucketFilter],
  );

  const applyDashboardWidgetResults = useCallback((data: Partial<Record<string, unknown>>) => {
    if (data.inventorySummary) {
      setSummary(data.inventorySummary as InventorySummary);
    }
    if (data.inventoryList) {
      const inventoryResponse = data.inventoryList as InventoryResponse;
      setInventory(inventoryResponse.items);
      setTotal(inventoryResponse.total);
      setSelectedIds((current) =>
        current.filter((id) =>
          inventoryResponse.items.some((item) => item.inventory_copy_id === id),
        ),
      );
    }
    if (data.portfolioPerformance) {
      setPerformance(data.portfolioPerformance as PortfolioPerformance);
    }
    if (data.portfolioValue) {
      setPortfolioValueSummary(data.portfolioValue as PortfolioValueSummaryResponse);
    }
    if (data.inventoryIntelSummary) {
      setInventoryIntelSummary(data.inventoryIntelSummary as InventoryIntelligenceRollupSummary);
    }
    if (data.inventoryIntelHealth) {
      setInventoryIntelHealth(data.inventoryIntelHealth as InventoryIntelligenceHealthRollup);
    }
    if (data.inventoryRisks) {
      setInventoryRiskSummary(data.inventoryRisks as InventoryRiskSummary);
    }
    if (data.inventoryAction) {
      setInventoryActionSummary(data.inventoryAction as InventoryActionCenterSummary);
    }
    if (data.orderArrival) {
      setOrderArrivalSummary(data.orderArrival as OrderArrivalIntelSummary);
    }
    if (data.collectionTimeline) {
      setCollectionHistoricalTimeline(data.collectionTimeline as CollectionHistoricalTimelineEventsResponse);
    }
    if (data.duplicateOwnership) {
      setDuplicateOwnershipReport(data.duplicateOwnership as DuplicateOwnershipListResponse);
    }
    if (data.runDetection) {
      setRunDetectionReport(data.runDetection as RunDetectionListResponse);
    }
    if (data.collectionAnalyticsSummary) {
      setCollectionAnalyticsSummary(data.collectionAnalyticsSummary as CollectionAnalyticsSummary);
    }
    if (data.collectionAnalyticsPublishers) {
      setCollectionAnalyticsPublishers(
        data.collectionAnalyticsPublishers as CollectionPublisherAnalyticsResponse,
      );
    }
    if (data.collectionAnalyticsQuality) {
      setCollectionAnalyticsQuality(data.collectionAnalyticsQuality as CollectionQualityAnalyticsResponse);
    }
    if (data.scanPipeline) {
      setScanPipelineDash(data.scanPipeline as ScanPipelineDashboardResponse);
    }
    if (data.physicalIntake) {
      setPhysicalIntakeSummary(data.physicalIntake as PhysicalIntakeSummaryResponse);
    }
    if (data.inventoryArrivalTracking) {
      setInventoryArrivalTracking(data.inventoryArrivalTracking as InventoryArrivalTrackingResponse);
    }
  }, []);

  const exportChipClass =
    "rounded-xl border border-white/15 px-3 py-2 text-xs font-semibold text-slate-100 transition hover:border-cyan-300/35 hover:bg-white/5";

  async function runInventoryExport(download: () => Promise<void>): Promise<void> {
    try {
      setError(null);
      await download();
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Export failed.";
      setError(`Export: ${message}`);
    }
  }

  async function loadDashboardData(query: InventoryQueryParams = inventoryQuery): Promise<void> {
    const { data, errors } = await settleDashboardWidgets(
      buildDashboardWidgetPromises(query, dashboardPortfolioFilters, loadProfile),
    );
    setDashboardWidgetErrors(errors);
    applyDashboardWidgetResults(data);
  }

  useEffect(() => {
    let ignore = false;

    async function fetchShellWidgets() {
      setIsLoading(true);
      setError(null);

      const { data, errors } = await settleDashboardWidgets(
        buildDashboardShellWidgetPromises(dashboardPortfolioFilters, loadProfile),
      );

      if (ignore) {
        return;
      }

      setDashboardWidgetErrors((current) => {
        const next = { ...current };
        for (const key of Object.keys(errors)) {
          next[key as DashboardWidgetKey] = errors[key as DashboardWidgetKey];
        }
        return next;
      });
      applyDashboardWidgetResults(data);

      const hasInventoryData = Boolean(data.inventorySummary);
      if (!hasInventoryData && Object.keys(data).length === 0) {
        setError("Unable to load dashboard.");
      }

      setIsLoading(false);
    }

    void fetchShellWidgets();

    return () => {
      ignore = true;
    };
  }, [applyDashboardWidgetResults, dashboardPortfolioFilters, loadProfile]);

  useEffect(() => {
    if (loadProfile !== "portfolio" && loadProfile !== "full") {
      return;
    }

    let ignore = false;

    async function fetchDeferredPortfolioWidgets() {
      const { data, errors } = await settleDashboardWidgets(
        buildPortfolioDeferredWidgetPromises(dashboardPortfolioFilters, loadProfile),
      );

      if (ignore) {
        return;
      }

      setDashboardWidgetErrors((current) => {
        const next = { ...current };
        for (const key of Object.keys(errors)) {
          next[key as DashboardWidgetKey] = errors[key as DashboardWidgetKey];
        }
        return next;
      });
      applyDashboardWidgetResults(data);
    }

    void fetchDeferredPortfolioWidgets();

    return () => {
      ignore = true;
    };
  }, [applyDashboardWidgetResults, dashboardPortfolioFilters, loadProfile]);

  useEffect(() => {
    if (!showInventoryGrid) {
      return;
    }

    let ignore = false;

    async function fetchInventoryList() {
      setInventoryListLoading(true);
      setError(null);

      const { data, errors } = await settleDashboardWidgets(
        buildInventoryListWidgetPromises(inventoryQuery, loadProfile),
      );

      if (ignore) {
        return;
      }

      setDashboardWidgetErrors((current) => {
        const next = { ...current };
        for (const key of Object.keys(errors)) {
          next[key as DashboardWidgetKey] = errors[key as DashboardWidgetKey];
        }
        return next;
      });
      applyDashboardWidgetResults(data);

      if (errors.inventoryList && !data.inventoryList) {
        setError(`Inventory list: ${errors.inventoryList}`);
      }

      setInventoryListLoading(false);
    }

    void fetchInventoryList();

    return () => {
      ignore = true;
    };
  }, [applyDashboardWidgetResults, inventoryQuery, loadProfile, showInventoryGrid]);

  useEffect(() => {
    if (loadsDealerData) {
      return;
    }
    setListingRegistrySummaryLoading(false);
    setListingIntelligenceSummaryLoading(false);
    setConventionSummaryLoading(false);
    setLiquiditySummaryLoading(false);
    setSalesLedgerSummaryLoading(false);
    setListingExportDashLoading(false);
    setDealerDashLoading(false);
    setStrategyDashLoading(false);
    setPortfolioIntelLoading(false);
    setDupIntelLoading(false);
    setPortfolioLiquidityLoading(false);
    setPortfolioRecommendationLoading(false);
    setAcquisitionPriorityLoading(false);
    setConcentrationRiskLoading(false);
    setOpReportRollupsLoading(false);
  }, [loadsDealerData]);

  useEffect(() => {
    if (loadsGradingData) {
      return;
    }
    setDealerGradingDashLoading(false);
    setGradingReportsLoading(false);
    setGradingDashLoading(false);
    setGradingSpreadLoading(false);
    setGradingRoiLoading(false);
    setGradingRiskLoading(false);
    setGradingSubmissionLoading(false);
    setGradingReconciliationLoading(false);
    setGradingRecommendationLoading(false);
  }, [loadsGradingData]);

  useEffect(() => {
    if (!loadsMarketData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setMarketSalesLoading(true);
      setMarketSalesError(null);
      try {
        const list = await apiClient.getMarketSales();
        if (!ignore) {
          setMarketSalesPreview(list.items);
        }
      } catch (loadError) {
        if (!ignore) {
          setMarketSalesPreview([]);
          setMarketSalesError(loadError instanceof ApiError ? loadError.message : "Unable to load market sales.");
        }
      } finally {
        if (!ignore) {
          setMarketSalesLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsMarketData]);

  useEffect(() => {
    if (!loadsMarketData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setMarketSaleReviewQueueSummaryLoading(true);
      setMarketSaleReviewQueueSummaryError(null);
      try {
        const summary = await apiClient.getMarketSaleReviewQueueSummary();
        if (!ignore) {
          setMarketSaleReviewQueueSummary(summary);
        }
      } catch (loadError) {
        if (!ignore) {
          setMarketSaleReviewQueueSummary(null);
          setMarketSaleReviewQueueSummaryError(
            loadError instanceof ApiError ? loadError.message : "Unable to load market sale review summary.",
          );
        }
      } finally {
        if (!ignore) {
          setMarketSaleReviewQueueSummaryLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsMarketData]);

  useEffect(() => {
    if (!loadsMarketData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setMarketCompEligibilitySummaryLoading(true);
      setMarketCompEligibilitySummaryError(null);
      try {
        const list = await apiClient.getMarketCompEligibility();
        if (!ignore) {
          setMarketCompEligibilitySummary(list);
        }
      } catch (loadError) {
        if (!ignore) {
          setMarketCompEligibilitySummary(null);
          setMarketCompEligibilitySummaryError(
            loadError instanceof ApiError ? loadError.message : "Unable to load market comp eligibility summary.",
          );
        }
      } finally {
        if (!ignore) {
          setMarketCompEligibilitySummaryLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsMarketData]);

  useEffect(() => {
    if (!loadsMarketData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setMarketCompsSummaryLoading(true);
      setMarketCompsSummaryError(null);
      try {
        const list = await apiClient.getMarketComps({ include_excluded: true });
        if (!ignore) {
          setMarketCompsSummary(list);
        }
      } catch (loadError) {
        if (!ignore) {
          setMarketCompsSummary(null);
          setMarketCompsSummaryError(loadError instanceof ApiError ? loadError.message : "Unable to load comparable sales summary.");
        }
      } finally {
        if (!ignore) {
          setMarketCompsSummaryLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsMarketData]);

  useEffect(() => {
    if (!loadsMarketData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setMarketFmvSummaryLoading(true);
      setMarketFmvSummaryError(null);
      try {
        const list = await apiClient.getMarketFmv();
        if (!ignore) {
          setMarketFmvSummary(list);
        }
      } catch (loadError) {
        if (!ignore) {
          setMarketFmvSummary(null);
          setMarketFmvSummaryError(loadError instanceof ApiError ? loadError.message : "Unable to load market FMV snapshots.");
        }
      } finally {
        if (!ignore) {
          setMarketFmvSummaryLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsMarketData]);

  useEffect(() => {
    if (!loadsMarketData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setMarketTrendSummaryLoading(true);
      setMarketTrendSummaryError(null);
      try {
        const list = await apiClient.getMarketTrends();
        if (!ignore) {
          setMarketTrendSummary(list);
        }
      } catch (loadError) {
        if (!ignore) {
          setMarketTrendSummary(null);
          setMarketTrendSummaryError(loadError instanceof ApiError ? loadError.message : "Unable to load market trend snapshots.");
        }
      } finally {
        if (!ignore) {
          setMarketTrendSummaryLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsMarketData]);

  useEffect(() => {
    if (!loadsMarketData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setMarketMatchSuggestionsPendingLoading(true);
      setMarketMatchSuggestionsPendingError(null);
      try {
        const list: MarketSaleMatchSuggestionOpsListResponse = await apiClient.getMarketMatchSuggestions({
          review_state: "pending",
        });
        if (!ignore) {
          setMarketMatchSuggestionsPendingCount(list.total_count);
        }
      } catch (loadError) {
        if (!ignore) {
          setMarketMatchSuggestionsPendingCount(0);
          setMarketMatchSuggestionsPendingError(
            loadError instanceof ApiError ? loadError.message : "Unable to load market match suggestions.",
          );
        }
      } finally {
        if (!ignore) {
          setMarketMatchSuggestionsPendingLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsMarketData]);

  useEffect(() => {
    if (!loadsMarketData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setMarketSourcesLoading(true);
      setMarketSourcesError(null);
      try {
        const list = await apiClient.getMarketSources();
        if (!ignore) {
          setMarketSources(list);
        }
      } catch (loadError) {
        if (!ignore) {
          setMarketSources([]);
          setMarketSourcesError(loadError instanceof ApiError ? loadError.message : "Unable to load market sources.");
        }
      } finally {
        if (!ignore) {
          setMarketSourcesLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsMarketData]);

  useEffect(() => {
    if (!loadsMarketData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setMarketImportRunsLoading(true);
      setMarketImportRunsError(null);
      try {
        const list = await apiClient.getMarketImportRuns();
        if (!ignore) {
          setMarketImportRuns(list.items);
        }
      } catch (loadError) {
        if (!ignore) {
          setMarketImportRuns([]);
          setMarketImportRunsError(
            loadError instanceof ApiError ? loadError.message : "Unable to load market import runs.",
          );
        }
      } finally {
        if (!ignore) {
          setMarketImportRunsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsMarketData]);

  useEffect(() => {
    if (!loadsDealerData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setListingRegistrySummaryLoading(true);
      setListingRegistrySummaryError(null);
      try {
        const summary = await apiClient.getListingRegistrySummary();
        if (!ignore) {
          setListingRegistrySummary(summary);
        }
      } catch (loadError) {
        if (!ignore) {
          setListingRegistrySummary(null);
          setListingRegistrySummaryError(
            loadError instanceof ApiError ? loadError.message : "Unable to load listing registry summary.",
          );
        }
      } finally {
        if (!ignore) {
          setListingRegistrySummaryLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsDealerData]);

  useEffect(() => {
    if (!loadsDealerData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setListingIntelligenceSummaryLoading(true);
      setListingIntelligenceSummaryError(null);
      try {
        const summary = await apiClient.getListingIntelligenceDashboardSummary();
        if (!ignore) {
          setListingIntelligenceSummary(summary);
        }
      } catch (loadError) {
        if (!ignore) {
          setListingIntelligenceSummary(null);
          setListingIntelligenceSummaryError(
            loadError instanceof ApiError ? loadError.message : "Unable to load listing intelligence summary.",
          );
        }
      } finally {
        if (!ignore) {
          setListingIntelligenceSummaryLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsDealerData]);

  useEffect(() => {
    if (!loadsDealerData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setSalesLedgerSummaryLoading(true);
      setSalesLedgerSummaryError(null);
      try {
        const summary = await apiClient.getSalesDashboardSummary();
        if (!ignore) {
          setSalesLedgerSummary(summary);
        }
      } catch (loadError) {
        if (!ignore) {
          setSalesLedgerSummary(null);
          setSalesLedgerSummaryError(
            loadError instanceof ApiError ? loadError.message : "Unable to load sales ledger summary.",
          );
        }
      } finally {
        if (!ignore) {
          setSalesLedgerSummaryLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsDealerData]);

  useEffect(() => {
    if (!loadsDealerData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setLiquiditySummaryLoading(true);
      setLiquiditySummaryError(null);
      try {
        const summary = await apiClient.getLiquidityDashboardSummary();
        if (!ignore) {
          setLiquiditySummary(summary);
        }
      } catch (loadError) {
        if (!ignore) {
          setLiquiditySummary(null);
          setLiquiditySummaryError(
            loadError instanceof ApiError ? loadError.message : "Unable to load liquidity summary.",
          );
        }
      } finally {
        if (!ignore) {
          setLiquiditySummaryLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsDealerData]);

  useEffect(() => {
    if (!loadsDealerData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setConventionSummaryLoading(true);
      setConventionSummaryError(null);
      try {
        const summary = await apiClient.getConventionDashboardSummary();
        if (!ignore) {
          setConventionSummary(summary);
        }
      } catch (loadError) {
        if (!ignore) {
          setConventionSummary(null);
          setConventionSummaryError(
            loadError instanceof ApiError ? loadError.message : "Unable to load convention summary.",
          );
        }
      } finally {
        if (!ignore) {
          setConventionSummaryLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsDealerData]);

  useEffect(() => {
    if (!loadsDealerData) {
      return;
    }
    let ignore = false;
    void (async () => {
      setListingExportDashLoading(true);
      setListingExportDashError(null);
      try {
        const summary = await apiClient.getListingExportDashboardSummary();
        if (!ignore) {
          setListingExportDash(summary);
        }
      } catch (loadError) {
        if (!ignore) {
          setListingExportDash(null);
          setListingExportDashError(
            loadError instanceof ApiError ? loadError.message : "Unable to load marketplace export summary.",
          );
        }
      } finally {
        if (!ignore) {
          setListingExportDashLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsDealerData]);

  useEffect(() => {
    if (!loadsDealerData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setDealerDashResp(null);
          setDealerAlerts([]);
          setDealerFeed([]);
          setDealerDashLoading(false);
          setDealerDashError(null);
        }
        return;
      }
      setDealerDashLoading(true);
      setDealerDashError(null);
      try {
        const [dash, alerts, feed] = await Promise.all([
          apiClient.getDealerDashboard(),
          apiClient.listDealerDashboardAlerts({ limit: 25, offset: 0 }),
          apiClient.listDealerDashboardFeed({ limit: 35, offset: 0 }),
        ]);
        if (!ignore) {
          setDealerDashResp(dash);
          setDealerAlerts(alerts.items);
          setDealerFeed(feed.items);
        }
      } catch (loadErr) {
        if (!ignore) {
          setDealerDashResp(null);
          setDealerAlerts([]);
          setDealerFeed([]);
          setDealerDashError(loadErr instanceof ApiError ? loadErr.message : "Unable to load dealer dashboard.");
        }
      } finally {
        if (!ignore) {
          setDealerDashLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsDealerData, user?.id]);

  useEffect(() => {
    if (!loadsDealerData) {
      return;
    }
    void loadPortfolioStrategyDashboard();
  }, [loadPortfolioStrategyDashboard, loadsDealerData]);

  useEffect(() => {
    if (!loadsDealerData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setAcquisitionPriorityList(null);
          setAcquisitionPriorityLoading(false);
          setAcquisitionPriorityError(null);
        }
        return;
      }
      setAcquisitionPriorityLoading(true);
      setAcquisitionPriorityError(null);
      try {
        const list = await apiClient.listAcquisitionPriorities({ limit: 500 });
        if (!ignore) {
          setAcquisitionPriorityList(list);
        }
      } catch (loadErr) {
        if (!ignore) {
          setAcquisitionPriorityList(null);
          setAcquisitionPriorityError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load acquisition priorities.",
          );
        }
      } finally {
        if (!ignore) {
          setAcquisitionPriorityLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsDealerData, user?.id]);

  useEffect(() => {
    if (!loadsDealerData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setConcentrationRiskList(null);
          setConcentrationRiskLoading(false);
          setConcentrationRiskError(null);
        }
        return;
      }
      setConcentrationRiskLoading(true);
      setConcentrationRiskError(null);
      try {
        const list = await apiClient.listConcentrationRisk({ limit: 500 });
        if (!ignore) {
          setConcentrationRiskList(list);
        }
      } catch (loadErr) {
        if (!ignore) {
          setConcentrationRiskList(null);
          setConcentrationRiskError(loadErr instanceof ApiError ? loadErr.message : "Unable to load concentration risk.");
        }
      } finally {
        if (!ignore) {
          setConcentrationRiskLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsDealerData, user?.id]);

  useEffect(() => {
    if (!loadsGradingData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setGradingReportsRecent(null);
          setGradingReportsFailed(null);
          setGradingReportsLoading(false);
          setGradingReportsError(null);
        }
        return;
      }
      setGradingReportsLoading(true);
      setGradingReportsError(null);
      try {
        const [recentRsp, failedRsp] = await Promise.all([
          apiClient.listGradingReports({ limit: 8, offset: 0 }),
          apiClient.listGradingReports({ status: "FAILED", limit: 5, offset: 0 }),
        ]);
        if (!ignore) {
          setGradingReportsRecent(recentRsp);
          setGradingReportsFailed(failedRsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setGradingReportsRecent(null);
          setGradingReportsFailed(null);
          setGradingReportsError(loadErr instanceof ApiError ? loadErr.message : "Unable to load grading reports.");
        }
      } finally {
        if (!ignore) {
          setGradingReportsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsGradingData, user?.id]);

  useEffect(() => {
    if (!loadsGradingData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setDealerGradingDashResp(null);
          setDealerGradingAlerts([]);
          setDealerGradingFeed([]);
          setDealerGradingMetrics([]);
          setDealerGradingDashLoading(false);
          setDealerGradingDashError(null);
        }
        return;
      }
      setDealerGradingDashLoading(true);
      setDealerGradingDashError(null);
      try {
        const [dash, alerts, feed, metrics] = await Promise.all([
          apiClient.getDealerGradingDashboard(),
          apiClient.listDealerGradingDashboardAlerts({ limit: 24, offset: 0 }),
          apiClient.listDealerGradingDashboardFeed({ limit: 28, offset: 0 }),
          apiClient.listDealerGradingDashboardMetrics({ limit: 40, offset: 0 }),
        ]);
        if (!ignore) {
          setDealerGradingDashResp(dash);
          setDealerGradingAlerts(alerts.items);
          setDealerGradingFeed(feed.items);
          setDealerGradingMetrics(metrics.items);
        }
      } catch (loadErr) {
        if (!ignore) {
          setDealerGradingDashResp(null);
          setDealerGradingAlerts([]);
          setDealerGradingFeed([]);
          setDealerGradingMetrics([]);
          setDealerGradingDashError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load grading command center.",
          );
        }
      } finally {
        if (!ignore) {
          setDealerGradingDashLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsGradingData, user?.id]);

  useEffect(() => {
    if (!loadsDealerData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setPortfolioIntelSummary(null);
          setPortfolioIntelLoading(false);
          setPortfolioIntelError(null);
        }
        return;
      }
      setPortfolioIntelLoading(true);
      setPortfolioIntelError(null);
      try {
        const summary = await apiClient.getPortfolioIntelligenceSummary();
        if (!ignore) {
          setPortfolioIntelSummary(summary);
        }
      } catch (loadErr) {
        if (!ignore) {
          setPortfolioIntelSummary(null);
          setPortfolioIntelError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load portfolio intelligence rollup.",
          );
        }
      } finally {
        if (!ignore) {
          setPortfolioIntelLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsDealerData, user?.id]);

  useEffect(() => {
    if (!loadsDealerData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setDupIntelSummary(null);
          setDupIntelLoading(false);
          setDupIntelError(null);
        }
        return;
      }
      setDupIntelLoading(true);
      setDupIntelError(null);
      try {
        const summary = await apiClient.getDuplicateIntelligenceSummary();
        if (!ignore) {
          setDupIntelSummary(summary);
        }
      } catch (loadErr) {
        if (!ignore) {
          setDupIntelSummary(null);
          setDupIntelError(loadErr instanceof ApiError ? loadErr.message : "Unable to load duplicate intelligence rollup.");
        }
      } finally {
        if (!ignore) {
          setDupIntelLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsDealerData, user?.id]);

  useEffect(() => {
    if (!loadsDealerData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setPortfolioLiquidityDetail(null);
          setPortfolioLiquidityLoading(false);
          setPortfolioLiquidityError(null);
        }
        return;
      }
      setPortfolioLiquidityLoading(true);
      setPortfolioLiquidityError(null);
      try {
        const list = await apiClient.listPortfolioLiquidity({ latest_only: true });
        const first = list.items[0];
        if (!first) {
          if (!ignore) {
            setPortfolioLiquidityDetail(null);
          }
        } else {
          const detail = await apiClient.getPortfolioLiquiditySnapshot(first.id);
          if (!ignore) {
            setPortfolioLiquidityDetail(detail);
          }
        }
      } catch (loadErr) {
        if (!ignore) {
          setPortfolioLiquidityDetail(null);
          setPortfolioLiquidityError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load portfolio liquidity rollup.",
          );
        }
      } finally {
        if (!ignore) {
          setPortfolioLiquidityLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsDealerData, user?.id]);

  useEffect(() => {
    if (!loadsDealerData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setPortfolioRecommendationList(null);
          setPortfolioRecommendationLoading(false);
          setPortfolioRecommendationError(null);
        }
        return;
      }
      setPortfolioRecommendationLoading(true);
      setPortfolioRecommendationError(null);
      try {
        const list = await apiClient.listPortfolioRecommendations({ limit: 500 });
        if (!ignore) {
          setPortfolioRecommendationList(list);
        }
      } catch (loadErr) {
        if (!ignore) {
          setPortfolioRecommendationList(null);
          setPortfolioRecommendationError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load portfolio recommendations.",
          );
        }
      } finally {
        if (!ignore) {
          setPortfolioRecommendationLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsDealerData, user?.id]);

  useEffect(() => {
    if (!loadsGradingData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setGradingRiskSummary(null);
          setGradingRiskLoading(false);
          setGradingRiskError(null);
        }
        return;
      }
      setGradingRiskLoading(true);
      setGradingRiskError(null);
      try {
        const rsp = await apiClient.getGradingRiskDashboardSummary();
        if (!ignore) {
          setGradingRiskSummary(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setGradingRiskSummary(null);
          setGradingRiskError(loadErr instanceof ApiError ? loadErr.message : "Unable to load grading risk summary.");
        }
      } finally {
        if (!ignore) {
          setGradingRiskLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsGradingData, user?.id]);

  useEffect(() => {
    if (!loadsGradingData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setGradingRecommendationSummary(null);
          setGradingRecommendationLoading(false);
          setGradingRecommendationError(null);
        }
        return;
      }
      setGradingRecommendationLoading(true);
      setGradingRecommendationError(null);
      try {
        const rsp = await apiClient.getGradingRecommendationDashboardSummary();
        if (!ignore) {
          setGradingRecommendationSummary(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setGradingRecommendationSummary(null);
          setGradingRecommendationError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load grading recommendation summary.",
          );
        }
      } finally {
        if (!ignore) {
          setGradingRecommendationLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsGradingData, user?.id]);

  useEffect(() => {
    if (!loadsGradingData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setGradingReconciliationSummary(null);
          setGradingReconciliationLoading(false);
          setGradingReconciliationError(null);
        }
        return;
      }
      setGradingReconciliationLoading(true);
      setGradingReconciliationError(null);
      try {
        const rsp = await apiClient.getGradingReconciliationDashboardSummary();
        if (!ignore) {
          setGradingReconciliationSummary(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setGradingReconciliationSummary(null);
          setGradingReconciliationError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load grading reconciliation summary.",
          );
        }
      } finally {
        if (!ignore) {
          setGradingReconciliationLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsGradingData, user?.id]);

  useEffect(() => {
    if (!loadsGradingData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setGradingSubmissionSummary(null);
          setGradingSubmissionLoading(false);
          setGradingSubmissionError(null);
        }
        return;
      }
      setGradingSubmissionLoading(true);
      setGradingSubmissionError(null);
      try {
        const rsp = await apiClient.getGradingSubmissionDashboardSummary();
        if (!ignore) {
          setGradingSubmissionSummary(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setGradingSubmissionSummary(null);
          setGradingSubmissionError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load grading submission summary.",
          );
        }
      } finally {
        if (!ignore) {
          setGradingSubmissionLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsGradingData, user?.id]);

  useEffect(() => {
    if (!loadsGradingData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setGradingRoiSummary(null);
          setGradingRoiLoading(false);
          setGradingRoiError(null);
        }
        return;
      }
      setGradingRoiLoading(true);
      setGradingRoiError(null);
      try {
        const rsp = await apiClient.getGradingRoiDashboardSummary();
        if (!ignore) {
          setGradingRoiSummary(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setGradingRoiSummary(null);
          setGradingRoiError(loadErr instanceof ApiError ? loadErr.message : "Unable to load grading ROI summary.");
        }
      } finally {
        if (!ignore) {
          setGradingRoiLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsGradingData, user?.id]);

  useEffect(() => {
    if (!loadsFullWorkspace) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setOpReportRollups(null);
          setOpReportRollupsLoading(false);
          setOpReportRollupsError(null);
        }
        return;
      }
      setOpReportRollupsLoading(true);
      setOpReportRollupsError(null);
      try {
        const roll = await apiClient.getOperationalReportRollups();
        if (!ignore) {
          setOpReportRollups(roll);
        }
      } catch (loadErr) {
        if (!ignore) {
          setOpReportRollups(null);
          setOpReportRollupsError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load operational reporting rollups.",
          );
        }
      } finally {
        if (!ignore) {
          setOpReportRollupsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsFullWorkspace, user?.id]);

  useEffect(() => {
    if (!loadsGradingData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setGradingDashSummary(null);
          setGradingDashLoading(false);
          setGradingDashError(null);
        }
        return;
      }
      setGradingDashLoading(true);
      setGradingDashError(null);
      try {
        const rsp = await apiClient.getGradingCandidateDashboardSummary();
        if (!ignore) {
          setGradingDashSummary(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setGradingDashSummary(null);
          setGradingDashError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load grading candidate summary.",
          );
        }
      } finally {
        if (!ignore) {
          setGradingDashLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsGradingData, user?.id]);

  useEffect(() => {
    if (!loadsGradingData) {
      return;
    }
    let ignore = false;
    void (async () => {
      if (!user) {
        if (!ignore) {
          setGradingSpreadSummary(null);
          setGradingSpreadLoading(false);
          setGradingSpreadError(null);
        }
        return;
      }
      setGradingSpreadLoading(true);
      setGradingSpreadError(null);
      try {
        const rsp = await apiClient.getGradingSpreadDashboardSummary();
        if (!ignore) {
          setGradingSpreadSummary(rsp);
        }
      } catch (loadErr) {
        if (!ignore) {
          setGradingSpreadSummary(null);
          setGradingSpreadError(
            loadErr instanceof ApiError ? loadErr.message : "Unable to load grading spread summary.",
          );
        }
      } finally {
        if (!ignore) {
          setGradingSpreadLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadsGradingData, user?.id]);

  useEffect(() => {
    const nextFmvDrafts: Record<number, string> = {};
    const nextHoldDrafts: Record<number, InventoryItem["hold_status"]> = {};
    const nextGradeDrafts: Record<number, InventoryItem["grade_status"]> = {};
    const nextStarDrafts: Record<number, string> = {};

    inventory.forEach((item) => {
      nextFmvDrafts[item.inventory_copy_id] = item.current_fmv ?? "";
      nextHoldDrafts[item.inventory_copy_id] = item.hold_status;
      nextGradeDrafts[item.inventory_copy_id] = item.grade_status;
      nextStarDrafts[item.inventory_copy_id] = item.star_rating ? String(item.star_rating) : "";
    });

    setFmvDrafts(nextFmvDrafts);
    setHoldDrafts(nextHoldDrafts);
    setGradeDrafts(nextGradeDrafts);
    setStarDrafts(nextStarDrafts);
  }, [inventory]);

  function applySearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  }

  async function generateDealerDashboardSnapshot(): Promise<void> {
    if (!user) {
      return;
    }
    setDealerDashError(null);
    setDealerGenBusy(true);
    try {
      await apiClient.generateDealerDashboard({ replay_key: `web-dash-${Date.now()}` });
      const [dash, alerts, feed] = await Promise.all([
        apiClient.getDealerDashboard(),
        apiClient.listDealerDashboardAlerts({ limit: 25, offset: 0 }),
        apiClient.listDealerDashboardFeed({ limit: 35, offset: 0 }),
      ]);
      setDealerDashResp(dash);
      setDealerAlerts(alerts.items);
      setDealerFeed(feed.items);
    } catch (err) {
      setDealerDashError(err instanceof ApiError ? err.message : "Unable to generate dealer dashboard snapshot.");
    } finally {
      setDealerGenBusy(false);
    }
  }

  async function refreshPortfolioStrategyDashboard(): Promise<void> {
    if (!user) {
      return;
    }
    setStrategyGenBusy(true);
    setStrategyDashError(null);
    try {
      await apiClient.generatePortfolioStrategyDashboard({ replay_key: `web-psd-dash-${Date.now()}` });
      await loadPortfolioStrategyDashboard();
    } catch (err) {
      setStrategyDashError(
        err instanceof ApiError ? err.message : "Unable to refresh portfolio strategy dashboard.",
      );
    } finally {
      setStrategyGenBusy(false);
    }
  }

  async function generateDealerGradingDashboardSnapshot(): Promise<void> {
    if (!user) {
      return;
    }
    setDealerGradingDashError(null);
    setDealerGradingGenBusy(true);
    try {
      await apiClient.generateDealerGradingDashboard({ replay_key: `web-grading-dash-${Date.now()}` });
      const [dash, alerts, feed, metrics] = await Promise.all([
        apiClient.getDealerGradingDashboard(),
        apiClient.listDealerGradingDashboardAlerts({ limit: 24, offset: 0 }),
        apiClient.listDealerGradingDashboardFeed({ limit: 28, offset: 0 }),
        apiClient.listDealerGradingDashboardMetrics({ limit: 40, offset: 0 }),
      ]);
      setDealerGradingDashResp(dash);
      setDealerGradingAlerts(alerts.items);
      setDealerGradingFeed(feed.items);
      setDealerGradingMetrics(metrics.items);
    } catch (err) {
      setDealerGradingDashError(err instanceof ApiError ? err.message : "Unable to generate grading dashboard snapshot.");
    } finally {
      setDealerGradingGenBusy(false);
    }
  }

  async function refreshPortfolioIntelligenceSnapshots(): Promise<void> {
    if (!user) {
      return;
    }
    setPortfolioIntelGenBusy(true);
    setPortfolioIntelError(null);
    try {
      const rk = `web-portfolio-dash-${Date.now()}`;
      await apiClient.generatePortfolioExposures({ replay_key: rk });
      await apiClient.generatePortfolioAllocations({ replay_key: rk });
      setPortfolioIntelSummary(await apiClient.getPortfolioIntelligenceSummary());
    } catch (err) {
      setPortfolioIntelError(err instanceof ApiError ? err.message : "Unable to refresh portfolio intelligence.");
    } finally {
      setPortfolioIntelGenBusy(false);
    }
  }

  async function refreshDuplicateIntelligenceSnapshots(): Promise<void> {
    if (!user) {
      return;
    }
    setDupIntelGenBusy(true);
    setDupIntelError(null);
    try {
      const rk = `web-dup-dash-${Date.now()}`;
      await apiClient.generateDuplicateClusters({ replay_key: rk });
      setDupIntelSummary(await apiClient.getDuplicateIntelligenceSummary());
    } catch (err) {
      setDupIntelError(err instanceof ApiError ? err.message : "Unable to refresh duplicate intelligence.");
    } finally {
      setDupIntelGenBusy(false);
    }
  }

  async function refreshPortfolioLiquiditySnapshots(): Promise<void> {
    if (!user) {
      return;
    }
    setPortfolioLiquidityGenBusy(true);
    setPortfolioLiquidityError(null);
    try {
      const rk = `web-plq-dash-${Date.now()}`;
      await apiClient.generatePortfolioLiquidity({ replay_key: rk });
      const list = await apiClient.listPortfolioLiquidity({ latest_only: true });
      const first = list.items[0];
      setPortfolioLiquidityDetail(first ? await apiClient.getPortfolioLiquiditySnapshot(first.id) : null);
    } catch (err) {
      setPortfolioLiquidityError(err instanceof ApiError ? err.message : "Unable to refresh portfolio liquidity.");
    } finally {
      setPortfolioLiquidityGenBusy(false);
    }
  }

  async function refreshPortfolioRecommendations(): Promise<void> {
    if (!user) {
      return;
    }
    setPortfolioRecommendationGenBusy(true);
    setPortfolioRecommendationError(null);
    try {
      await apiClient.generatePortfolioRecommendations({ replay_key: `web-prd-dash-${Date.now()}` });
      const list = await apiClient.listPortfolioRecommendations({ limit: 500 });
      setPortfolioRecommendationList(list);
    } catch (err) {
      setPortfolioRecommendationError(err instanceof ApiError ? err.message : "Unable to refresh portfolio recommendations.");
    } finally {
      setPortfolioRecommendationGenBusy(false);
    }
  }

  async function refreshAcquisitionPriorities(): Promise<void> {
    if (!user) {
      return;
    }
    setAcquisitionPriorityGenBusy(true);
    setAcquisitionPriorityError(null);
    try {
      await apiClient.generateAcquisitionPriorities({ replay_key: `web-apr-dash-${Date.now()}` });
      const list = await apiClient.listAcquisitionPriorities({ limit: 500 });
      setAcquisitionPriorityList(list);
    } catch (err) {
      setAcquisitionPriorityError(err instanceof ApiError ? err.message : "Unable to refresh acquisition priorities.");
    } finally {
      setAcquisitionPriorityGenBusy(false);
    }
  }

  async function refreshConcentrationRisk(): Promise<void> {
    if (!user) {
      return;
    }
    setConcentrationRiskGenBusy(true);
    setConcentrationRiskError(null);
    try {
      await apiClient.generateConcentrationRisk({ replay_key: `web-crk-dash-${Date.now()}` });
      const list = await apiClient.listConcentrationRisk({ limit: 500 });
      setConcentrationRiskList(list);
    } catch (err) {
      setConcentrationRiskError(err instanceof ApiError ? err.message : "Unable to refresh concentration risk.");
    } finally {
      setConcentrationRiskGenBusy(false);
    }
  }

  async function generateQuickListingOperationalReport(): Promise<void> {
    if (!user) {
      return;
    }
    setOpReportBusy(true);
    setOpReportRollupsError(null);
    try {
      await apiClient.generateOperationalReport({
        report_type: "listing_summary",
        replay_key: `dash-listing-${Date.now()}`,
      });
      setOpReportRollups(await apiClient.getOperationalReportRollups());
    } catch (err) {
      setOpReportRollupsError(err instanceof ApiError ? err.message : "Unable to generate operational report.");
    } finally {
      setOpReportBusy(false);
    }
  }

  async function generateQuickGradingReport(): Promise<void> {
    if (!user) {
      return;
    }
    setGradingReportBusy(true);
    setGradingReportsError(null);
    try {
      await apiClient.generateGradingReport({
        report_type: "grading_dashboard_summary",
        replay_key: `dash-grading-${Date.now()}`,
      });
      const [recentRsp, failedRsp] = await Promise.all([
        apiClient.listGradingReports({ limit: 8, offset: 0 }),
        apiClient.listGradingReports({ status: "FAILED", limit: 5, offset: 0 }),
      ]);
      setGradingReportsRecent(recentRsp);
      setGradingReportsFailed(failedRsp);
    } catch (err) {
      setGradingReportsError(err instanceof ApiError ? err.message : "Unable to generate grading report.");
    } finally {
      setGradingReportBusy(false);
    }
  }

  async function downloadOperationalReportCsvClient(reportId: number): Promise<void> {
    try {
      setError(null);
      await apiClient.downloadOperationalReportCsv(reportId);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Operational report download failed.";
      setError(`Operational report: ${message}`);
    }
  }

  async function downloadGradingReportCsvClient(reportId: number): Promise<void> {
    try {
      setError(null);
      await apiClient.downloadGradingReportCsv(reportId);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Grading report download failed.";
      setError(`Grading report: ${message}`);
    }
  }

  function resetPageAndUpdate(callback: () => void) {
    setPage(1);
    callback();
  }

  async function saveInventoryUpdate(
    inventoryCopyId: number,
    updates: InventoryUpdatePayload,
  ): Promise<void> {
    setError(null);
    setIsSaving(true);

    try {
      await apiClient.updateInventoryCopy(inventoryCopyId, updates);
      await loadDashboardData();
    } catch (saveError) {
      if (saveError instanceof ApiError) {
        setError(saveError.message);
      } else {
        setError("Unable to save inventory changes.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function refreshReceivingSummaries(): Promise<void> {
    try {
      const [inventorySummary, intakeSummary] = await Promise.all([
        apiClient.getInventorySummary(),
        apiClient.getPhysicalIntakeSummary(),
      ]);
      setSummary(inventorySummary);
      setPhysicalIntakeSummary(intakeSummary);
    } catch {
      // Keep optimistic summary if lightweight refresh fails.
    }
  }

  async function markInventoryCopyReceived(inventoryCopyId: number): Promise<void> {
    setError(null);
    setSuccessMessage(null);
    setReceivingCopyIds((current) => new Set(current).add(inventoryCopyId));
    const wasEligible = inventory.some(
      (row) => row.inventory_copy_id === inventoryCopyId && canQuickReceiveInventoryCopy(row),
    );
    try {
      const updated = await apiClient.markInventoryPhysicallyReceived(inventoryCopyId, {});
      setInventory((current) => mergeInventoryRowsAfterReceive(current, [updated]));
      if (wasEligible) {
        setSummary((current) => summaryAfterReceiveMarked(current, 1));
        setPhysicalIntakeSummary((current) =>
          current
            ? {
                ...current,
                counts: {
                  ...current.counts,
                  released_not_received: Math.max(0, current.counts.released_not_received - 1),
                },
              }
            : current,
        );
      }
      void refreshReceivingSummaries();
      setSuccessMessage("Marked copy as received.");
    } catch (saveError) {
      if (saveError instanceof ApiError) {
        setError(saveError.message);
      } else {
        setError("Unable to mark copy as received.");
      }
    } finally {
      setReceivingCopyIds((current) => {
        const next = new Set(current);
        next.delete(inventoryCopyId);
        return next;
      });
    }
  }

  async function applyBulkMarkReceived(): Promise<void> {
    if (!selectedIds.length) {
      return;
    }
    const eligibleIds = selectedIds.filter((id) => {
      const item = inventory.find((row) => row.inventory_copy_id === id);
      return item != null && canQuickReceiveInventoryCopy(item);
    });
    if (!eligibleIds.length) {
      setError("No selected copies are eligible to mark received (already in hand, sold, or cancelled).");
      return;
    }

    setError(null);
    setSuccessMessage(null);
    setIsSaving(true);
    setReceivingCopyIds((current) => {
      const next = new Set(current);
      for (const id of eligibleIds) {
        next.add(id);
      }
      return next;
    });

    try {
      const response = await apiClient.bulkMarkInventoryPhysicallyReceived({
        inventory_copy_ids: eligibleIds,
      });
      const rows = response.results.map((r) => r.row).filter(Boolean);
      setInventory((current) => mergeInventoryRowsAfterReceive(current, rows));
      const newlyMarked = countNewlyMarkedFromBulk(response);
      if (newlyMarked > 0) {
        setSummary((current) => summaryAfterReceiveMarked(current, newlyMarked));
        setPhysicalIntakeSummary((current) =>
          current
            ? {
                ...current,
                counts: {
                  ...current.counts,
                  released_not_received: Math.max(
                    0,
                    current.counts.released_not_received - newlyMarked,
                  ),
                },
              }
            : current,
        );
      }
      void refreshReceivingSummaries();
      setSelectedIds([]);
      const skipped = selectedIds.length - eligibleIds.length + response.skipped_count;
      if (response.error_count > 0) {
        setError(
          `Marked ${response.marked_count} received; ${response.skipped_count} skipped; ${response.error_count} errors.`,
        );
      } else {
        setSuccessMessage(
          skipped > 0
            ? `Marked ${response.marked_count} cop${response.marked_count === 1 ? "y" : "ies"} received (${skipped} skipped).`
            : `Marked ${response.marked_count} cop${response.marked_count === 1 ? "y" : "ies"} received.`,
        );
      }
    } catch (saveError) {
      if (saveError instanceof ApiError) {
        setError(saveError.message);
      } else {
        setError("Unable to mark selected copies as received.");
      }
    } finally {
      setIsSaving(false);
      setReceivingCopyIds((current) => {
        const next = new Set(current);
        for (const id of eligibleIds) {
          next.delete(id);
        }
        return next;
      });
    }
  }

  async function applyBulkHoldUpdate(): Promise<void> {
    if (!selectedIds.length) {
      return;
    }

    setError(null);
    setIsSaving(true);

    try {
      await apiClient.bulkUpdateInventory({
        inventory_copy_ids: selectedIds,
        updates: { hold_status: bulkHoldStatus },
      });
      setSelectedIds([]);
      await loadDashboardData();
    } catch (saveError) {
      if (saveError instanceof ApiError) {
        setError(saveError.message);
      } else {
        setError("Unable to apply bulk update.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  function toggleSelection(inventoryCopyId: number): void {
    setSelectedIds((current) =>
      current.includes(inventoryCopyId)
        ? current.filter((id) => id !== inventoryCopyId)
        : [...current, inventoryCopyId],
    );
  }

  function toggleSelectAll(): void {
    if (selectedIds.length === inventory.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(inventory.map((item) => item.inventory_copy_id));
    }
  }

  const hasEligibleReceivingSelection = useMemo(
    () =>
      selectedIds.some((id) => {
        const item = inventory.find((row) => row.inventory_copy_id === id);
        return item != null && canQuickReceiveInventoryCopy(item);
      }),
    [inventory, selectedIds],
  );

  const marketWorkbenchRailsVisible =
    marketSalesLoading ||
    marketSalesError ||
    marketSalesPreview.length > 0 ||
    marketSaleReviewQueueSummaryLoading ||
    marketSaleReviewQueueSummaryError ||
    Boolean(marketSaleReviewQueueSummary) ||
    marketCompEligibilitySummaryLoading ||
    marketCompEligibilitySummaryError ||
    Boolean(marketCompEligibilitySummary) ||
    marketCompsSummaryLoading ||
    marketCompsSummaryError ||
    Boolean(marketCompsSummary) ||
    marketFmvSummaryLoading ||
    marketFmvSummaryError ||
    Boolean(marketFmvSummary) ||
    marketTrendSummaryLoading ||
    marketTrendSummaryError ||
    Boolean(marketTrendSummary) ||
    marketMatchSuggestionsPendingLoading ||
    marketMatchSuggestionsPendingError ||
    (loadsDealerData &&
      (conventionSummaryLoading ||
        conventionSummaryError ||
        Boolean(conventionSummary) ||
        liquiditySummaryLoading ||
        liquiditySummaryError ||
        Boolean(liquiditySummary) ||
        salesLedgerSummaryLoading ||
        salesLedgerSummaryError ||
        Boolean(salesLedgerSummary) ||
        listingRegistrySummaryLoading ||
        listingRegistrySummaryError ||
        Boolean(listingRegistrySummary) ||
        listingIntelligenceSummaryLoading ||
        listingIntelligenceSummaryError ||
        Boolean(listingIntelligenceSummary) ||
        listingExportDashLoading ||
        listingExportDashError ||
        Boolean(listingExportDash))) ||
    (loadsDealerData &&
      (dealerDashLoading || dealerDashError || dealerDashResp !== null));

  const marketRegistryRailsVisible =
    marketSourcesLoading ||
    marketSourcesError ||
    marketImportRunsLoading ||
    marketImportRunsError ||
    marketSources.length > 0 ||
    marketImportRuns.length > 0;

  const portfolioValue = portfolioValueSummary?.items[0] ?? null;
  const portfolioHasMultipleCurrencies = (portfolioValueSummary?.items.length ?? 0) > 1;
  const cards = [
    { label: "Copies", value: summary?.total_copies ?? 0 },
    { label: "In Hand", value: summary?.in_hand_copies ?? 0 },
    { label: "Ordered", value: summary?.ordered_not_received_copies ?? 0 },
    { label: "Preordered", value: summary?.preordered_copies ?? 0 },
    { label: "Cancelled", value: summary?.cancelled_copies ?? 0 },
    { label: "Cost Basis", value: formatUsdCurrency(summary?.total_cost_basis ?? "0") },
    { label: "Current FMV", value: formatUsdCurrency(summary?.total_current_fmv ?? "0") },
    {
      label: "Active Market Value",
      value: formatCurrencyAmount(portfolioValue?.total_active_market_value ?? "0", portfolioValue?.currency_code ?? "USD"),
    },
    {
      label: "Raw Market Value",
      value: formatCurrencyAmount(portfolioValue?.raw_market_value ?? "0", portfolioValue?.currency_code ?? "USD"),
    },
    {
      label: "Graded Market Value",
      value: formatCurrencyAmount(portfolioValue?.graded_market_value ?? "0", portfolioValue?.currency_code ?? "USD"),
    },
    {
      label: "Low-Confidence Value",
      value: formatCurrencyAmount(portfolioValue?.low_confidence_value ?? "0", portfolioValue?.currency_code ?? "USD"),
    },
    {
      label: "Preorder Informational",
      value: formatCurrencyAmount(
        portfolioValue?.preorder_informational_value ?? "0",
        portfolioValue?.currency_code ?? "USD",
      ),
    },
    {
      label: "Stale Value",
      value: formatCurrencyAmount(portfolioValue?.stale_value ?? "0", portfolioValue?.currency_code ?? "USD"),
    },
    { label: "No Market Data", value: portfolioValue?.no_market_data_count ?? 0 },
    { label: "Cancelled Excluded", value: portfolioValue?.cancelled_excluded_count ?? 0 },
    {
      label: "Unrealized P/L",
      value: formatUsdCurrency(summary?.total_unrealized_gain_loss ?? "0"),
    },
  ];
  const compactHeadlineCards = cards.slice(0, 4);

  const analyticsSections = [
    {
      title: "Top Gainers",
      items: performance?.top_gainers ?? [],
      empty: "No positive gainers yet.",
      valueLabel: "Gain",
      valueFor: (item: PortfolioPerformanceItem) => item.gain_loss,
    },
    {
      title: "Top Losers",
      items: performance?.top_losers ?? [],
      empty: "No unrealized losers yet.",
      valueLabel: "Loss",
      valueFor: (item: PortfolioPerformanceItem) => item.gain_loss,
    },
    {
      title: "Highest Value Books",
      items: performance?.highest_value_books ?? [],
      empty: "No valued books yet.",
      valueLabel: "FMV",
      valueFor: (item: PortfolioPerformanceItem) => item.current_fmv,
    },
  ];

  const hasPerformanceData = analyticsSections.some((section) => section.items.length > 0);
  const isInitialLoad =
    isLoading &&
    !summary &&
    !performance &&
    inventory.length === 0 &&
    !(loadProfile === "collection" && collectionAnalyticsSummary);

  if (isInitialLoad) {
    return (
      <AppShell>
        <PageHeader
          eyebrow="ComicOS Dashboard"
          title={profileMeta.title}
          description={profileMeta.description}
          actions={
            <div className="rounded-2xl border border-slate-200 bg-white/5 px-4 py-3 text-sm text-slate-700">
              Signed in as <span className="font-medium text-slate-900">{user?.email ?? "Loading..."}</span>
            </div>
          }
        />
        <div className="mt-6">
          <LoadingState
            title={loadProfile === "collection" ? "Loading collection insights" : "Loading portfolio workspace"}
            description={
              loadProfile === "collection"
                ? "Fetching risk lanes, timeline, and analytics for your library."
                : "Refreshing summary cards, performance leaders, and inventory rows."
            }
          />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="ComicOS Dashboard"
        title={profileMeta.title}
        description={profileMeta.description}
        actions={
          <>
            <div className="hidden rounded-2xl border border-slate-200 bg-blue-50 px-4 py-3 text-sm text-slate-700 sm:block">
              Signed in as <span className="font-medium text-slate-900">{user?.email ?? "Loading..."}</span>
            </div>
            {loadProfile !== "portfolio" && loadProfile !== "full" ? (
              <Link
                to="/dashboard"
                className="rounded-2xl border border-blue-300 bg-blue-50 px-4 py-2.5 text-sm font-semibold text-blue-800 transition hover:border-cyan-300/50"
              >
                Portfolio
              </Link>
            ) : null}
            {loadProfile === "portfolio" || loadProfile === "full" ? (
              <>
                <Link
                  to="/connected-retailers/import"
                  className="rounded-2xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-blue-400 hover:bg-blue-50"
                >
                  Import
                </Link>
                <Link
                  to="/scan-sessions"
                  className="rounded-2xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-blue-400 hover:bg-blue-50"
                >
                  Scan
                </Link>
                <Link
                  to="/settings/account"
                  className="rounded-2xl border border-rose-200 px-4 py-2.5 text-sm font-semibold text-rose-800 transition hover:border-rose-300 hover:bg-rose-50"
                >
                  Reset collection
                </Link>
              </>
            ) : null}
            <Link
              to="/orders/new"
              className="rounded-2xl bg-patriot-blue px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-900"
            >
              Add order
            </Link>
          </>
        }
      />

      <DashboardProfileTabs activeProfile={loadProfile} />

      {loadProfile === "collection" ? (
        <CollectionInsightsSummaryStrip
          loading={isLoading}
          summary={collectionAnalyticsSummary}
          error={dashboardWidgetErrors.collectionAnalyticsSummary ?? null}
        />
      ) : null}

      {loadProfile === "collection" &&
      isLoading &&
      !inventoryRiskSummary &&
      !inventoryActionSummary &&
      collectionAnalyticsSummary ? (
        <p className="mt-4 text-sm text-slate-500">Loading risk lanes, arrivals, and series progress…</p>
      ) : null}

      {loadProfile !== "collection" &&
      (dashboardWidgetErrors.inventorySummary ||
        dashboardWidgetErrors.portfolioPerformance ||
        dashboardWidgetErrors.portfolioValue) ? (
        <div className="mt-6 space-y-2">
          {dashboardWidgetErrors.inventorySummary ? (
            <StatusBanner tone="error">
              Inventory summary: {dashboardWidgetErrors.inventorySummary}
            </StatusBanner>
          ) : null}
          {dashboardWidgetErrors.portfolioPerformance ? (
            <StatusBanner tone="error">
              Portfolio performance: {dashboardWidgetErrors.portfolioPerformance}
            </StatusBanner>
          ) : null}
          {dashboardWidgetErrors.portfolioValue ? (
            <StatusBanner tone="error">
              Portfolio value: {dashboardWidgetErrors.portfolioValue}
            </StatusBanner>
          ) : null}
        </div>
      ) : null}

      {showPortfolioMetricCards ? (
        <>
      <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <article
            key={card.label}
            className="rounded-3xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/50"
          >
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-slate-500">{card.label}</p>
            <p className="mt-2 text-2xl font-semibold text-patriot-navy sm:text-3xl">{card.value}</p>
          </article>
        ))}
      </section>
      {portfolioValue ? (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
          Showing {normalizeCurrencyCode(portfolioValue.currency_code)} market value.{" "}
          {portfolioHasMultipleCurrencies ? "Multiple currencies are kept separate." : "Single-currency summary."}{" "}
          Low-confidence and stale values are surfaced in the cards above without changing acquisition data.
        </div>
      ) : null}
        </>
      ) : null}

      {showCompactHeadlineStats && summary ? (
        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {compactHeadlineCards.map((card) => (
            <article
              key={card.label}
              className="rounded-2xl border border-slate-200 bg-white p-4"
            >
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-500">{card.label}</p>
              <p className="mt-2 text-xl font-semibold text-patriot-navy">{card.value}</p>
            </article>
          ))}
        </section>
      ) : null}

      {(loadProfile === "portfolio" || loadProfile === "full") &&
      (inventoryArrivalTracking || dashboardWidgetErrors.inventoryArrivalTracking) ? (
        <section
          id="inventory-arrival-tracking"
          className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/50"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Ordered / not in hand</p>
              <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Inventory arrival tracking</h2>
              <p className="mt-1 max-w-prose text-sm text-slate-600">
                Read-only split from persisted order status, release dates, expected ship dates, and receipt timestamps —
                no FMV or market rebuilds.
              </p>
            </div>
            {inventoryArrivalTracking ? (
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                As of {inventoryArrivalTracking.summary.generated_as_of_date}
              </p>
            ) : null}
          </div>
          {dashboardWidgetErrors.inventoryArrivalTracking ? (
            <div className="mt-4">
              <StatusBanner tone="error">{dashboardWidgetErrors.inventoryArrivalTracking}</StatusBanner>
            </div>
          ) : null}
          {inventoryArrivalTracking ? (
            <>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <article className="rounded-2xl border border-sky-200 bg-sky-50 p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.14em] text-sky-900/80">On the way</p>
                  <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                    {inventoryArrivalTracking.summary.on_the_way_count}
                  </p>
                  <p className="mt-1 text-[11px] text-slate-600">Shipped or expected ship window</p>
                </article>
                <article className="rounded-2xl border border-violet-200 bg-violet-50 p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.14em] text-violet-900/80">Not released yet</p>
                  <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                    {inventoryArrivalTracking.summary.not_released_yet_count}
                  </p>
                  <p className="mt-1 text-[11px] text-slate-600">Preorder / future release date</p>
                </article>
                <article className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.14em] text-amber-900/80">
                    Released, not received
                  </p>
                  <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                    {inventoryArrivalTracking.summary.released_not_received_count}
                  </p>
                  <p className="mt-1 text-[11px] text-slate-600">Past release, still awaiting receipt</p>
                </article>
              </div>
              <div className="mt-5 overflow-auto rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <h3 className="text-sm font-semibold text-patriot-navy">Not released yet</h3>
                <p className="mt-1 text-xs text-slate-600">Sorted by release date (soonest first).</p>
                {inventoryArrivalTracking.not_released_yet_items.length === 0 ? (
                  <p className="mt-3 text-sm text-slate-500">No upcoming-not-released copies in this lane.</p>
                ) : (
                  <div className="mt-3 overflow-auto">
                    <table className="w-full border-collapse text-left text-xs text-slate-800">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="pb-2 pr-3 font-medium">Title</th>
                          <th className="pb-2 pr-3 font-medium">Release</th>
                          <th className="pb-2 pr-3 font-medium">Order</th>
                          <th className="pb-2 pr-3 font-medium">Source</th>
                          <th className="pb-2 font-medium">Expected ship</th>
                        </tr>
                      </thead>
                      <tbody>
                        {inventoryArrivalTracking.not_released_yet_items.map((row) => (
                          <tr key={row.inventory_copy_id} className="border-t border-slate-200 align-top">
                            <td className="py-2 pr-3">
                              <Link
                                to={`/inventory/${row.inventory_copy_id}`}
                                className="font-medium text-slate-900 hover:text-blue-700"
                              >
                                {row.publisher} · {row.title} #{row.issue_number}
                              </Link>
                              <div className="text-[11px] text-slate-500">{row.retailer}</div>
                            </td>
                            <td className="py-2 pr-3 font-medium text-slate-900">
                              {row.release_date ? formatDate(row.release_date) : "—"}
                            </td>
                            <td className="py-2 pr-3 text-slate-700">{row.order_status.replace(/_/g, " ")}</td>
                            <td className="py-2 pr-3 text-slate-600">
                              {row.source_type ? row.source_type.replace(/_/g, " ") : "—"}
                            </td>
                            <td className="py-2 text-slate-600">
                              {row.expected_ship_date ? formatDate(row.expected_ship_date) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          ) : null}
        </section>
      ) : null}

      {loadProfile === "portfolio" && physicalIntakeSummary ? (
        <section
          id="physical-intake"
          className="mt-6 rounded-3xl border border-emerald-400/25 bg-white ring-1 ring-emerald-100 p-5 shadow-xl shadow-slate-200/50"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-emerald-200/70">Physical intake</p>
              <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Receiving &amp; scan placeholders</h2>
              <p className="mt-1 max-w-prose text-sm text-slate-600">
                Mark copies received from the inventory list or detail page, then stage scan sessions when ready.
              </p>
            </div>
            <Link
              to="/scan-sessions"
              className="rounded-2xl border border-emerald-400/35 px-4 py-3 text-xs font-semibold text-emerald-100 transition hover:border-emerald-300/60 hover:bg-emerald-500/10"
            >
              Open scan sessions
            </Link>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <article className="rounded-2xl border border-slate-200 bg-white p-4">
              <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Released, not received</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {physicalIntakeSummary.counts.released_not_received}
              </p>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-white p-4">
              <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Received, pending scan</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {physicalIntakeSummary.counts.received_pending_scan}
              </p>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-white p-4">
              <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Shipment overdue (expected ship)</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {physicalIntakeSummary.counts.overdue_expected_ship}
              </p>
            </article>
          </div>
        </section>
      ) : null}

      {showExtendedWorkbench &&
      (physicalIntakeSummary || scanPipelineDash || marketWorkbenchRailsVisible || marketRegistryRailsVisible) ? (
        <section className="mt-6 space-y-6" aria-label="Receiving, scan pipeline, and market intelligence">
          {physicalIntakeSummary ? (
            <section
              id="physical-intake"
              className="rounded-3xl border border-emerald-400/25 bg-white ring-1 ring-emerald-100 p-5 shadow-xl shadow-slate-200/50"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-emerald-200/70">Physical intake</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Receiving & scan placeholders</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Canonical receiving counts stay here — mark received explicitly, then stage intake scan sessions via
                    the API when eligible. Same logic backs pipeline intake rollups elsewhere (no OCR or ingest runs automatically).
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <Link
                      to="/scan-sessions"
                      className="rounded-full border border-emerald-400/35 px-3 py-1.5 font-semibold text-emerald-100 transition hover:border-emerald-300/60 hover:bg-emerald-500/10"
                    >
                      Stage sessions
                    </Link>
                  </div>
                </div>
                <Link
                  to="/scan-sessions"
                  className="rounded-2xl border border-emerald-400/35 px-4 py-3 text-xs font-semibold text-emerald-100 transition hover:border-emerald-300/60 hover:bg-emerald-500/10"
                >
                  Open scan sessions
                </Link>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <article className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Released, not received</p>
                  <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                    {physicalIntakeSummary.counts.released_not_received}
                  </p>
                </article>
                <article className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Received, pending scan</p>
                  <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                    {physicalIntakeSummary.counts.received_pending_scan}
                  </p>
                </article>
                <article className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                    Shipment overdue (expected ship)
                  </p>
                  <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                    {physicalIntakeSummary.counts.overdue_expected_ship}
                  </p>
                </article>
              </div>
              <div className="mt-4 flex flex-wrap gap-4 text-[11px] text-slate-500">
                <span>Intake blocked: {physicalIntakeSummary.counts.intake_blocked}</span>
                <span>Released awaiting receipt (state roll-up): {physicalIntakeSummary.counts.released_awaiting_receipt}</span>
                <span>As of {physicalIntakeSummary.generated_as_of}</span>
              </div>
            </section>
          ) : null}

          {scanPipelineDash ? (
            <section
              id="bulk-scan-pipeline"
              className="rounded-3xl border border-teal-300/60 bg-white p-5 shadow-xl shadow-slate-200/50 ring-1 ring-teal-100"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-teal-800">Bulk scan pipeline · read-only snapshot</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Session & queue visibility</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Condensed aggregates (QA ledger, unresolved routing signals, queued high-res asks, presets, replay deltas).
                    Receiving placeholders stay in Physical intake above — avoids duplicating shipment vs scan semantics here.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <Link
                      to="/scan-sessions"
                      className="rounded-full border border-teal-400/45 px-3 py-1.5 font-semibold text-teal-800 transition hover:border-teal-500/55 hover:bg-teal-50"
                    >
                      Lifecycle &amp; ingest
                    </Link>
                    <Link
                      to="/scan-sessions#scan-qa-and-routing"
                      className="rounded-full border border-white/15 px-3 py-1.5 font-semibold text-slate-200 transition hover:border-white/30 hover:bg-white/5"
                    >
                      Persisted QA &amp; routing
                    </Link>
                    <Link
                      to="/settings/scanner-profiles"
                      className="rounded-full border border-white/15 px-3 py-1.5 font-semibold text-slate-200 transition hover:border-white/30 hover:bg-white/5"
                    >
                      Scanner presets
                    </Link>
                  </div>
                </div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-teal-800">
                  Tables · Active {scanPipelineDash.active_sessions.length} · Recent{" "}
                  {scanPipelineDash.recent_sessions.length}
                </p>
              </div>

              <div className="mt-6 grid gap-3 sm:grid-cols-2">
                {(
                  [
                    ["Sessions · active / triage", scanPipelineDash.summary.active_sessions],
                    ["Sessions · completed with errors", scanPipelineDash.summary.sessions_completed_with_errors],
                  ] as const
                ).map(([label, value]) => (
                  <article key={label} className="rounded-2xl border border-slate-200 bg-white p-3">
                    <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-500">{label}</p>
                    <p className="mt-1 text-xl font-semibold text-patriot-navy">{value}</p>
                  </article>
                ))}
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {(
                  [
                    ["Scan items · failures (rollup)", scanPipelineDash.summary.failed_items],
                    ["Scan items · review required", scanPipelineDash.summary.review_required_items],
                    ["Replay runs with changes", scanPipelineDash.summary.replay_runs_with_changes],
                  ] as const
                ).map(([label, value]) => (
                  <article key={label} className="rounded-2xl border border-slate-200 bg-white p-3">
                    <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-500">{label}</p>
                    <p className="mt-1 text-xl font-semibold text-patriot-navy">{value}</p>
                  </article>
                ))}
              </div>

              <p className="mt-6 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                Persisted QA (after Run QA) & routing requests (Generate routing snapshot)
              </p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                {(
                  [
                    ["Needs rescan (persisted)", scanPipelineDash.summary.qa_needs_rescan],
                    ["Corrupt / unreadable (persisted)", scanPipelineDash.summary.qa_corrupt_or_unreadable],
                    ["Open routing · recommend OCR", scanPipelineDash.summary.routing_recommend_ocr],
                    ["Open routing · high-res lane", scanPipelineDash.summary.routing_recommend_high_res_review],
                    ["High-resolution requests · pending", scanPipelineDash.summary.high_res_pending],
                  ] as const
                ).map(([label, value]) => (
                  <article
                    key={label}
                    className="rounded-2xl border border-teal-500/15 bg-white p-3"
                  >
                    <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-500">{label}</p>
                    <p className="mt-1 text-xl font-semibold text-patriot-navy">{value}</p>
                  </article>
                ))}
              </div>

              <p className="mt-2 text-[11px] text-slate-500">
                Receipt-to-scan bridging never runs automatically — use Physical intake above for Received / pending scan
                counts tied to explicit mark-received flows.
              </p>

              {scanPipelineDash.summary.most_used_scanner_profiles.length > 0 ? (
                <div className="mt-5">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Scanner presets · ledger usage (bulk ingest)
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {scanPipelineDash.summary.most_used_scanner_profiles.slice(0, 8).map((row, idx) => (
                      <span
                        key={`${row.scanner_profile_id ?? "none"}-${row.profile_label}-${idx}`}
                        className="rounded-full border border-teal-400/25 bg-teal-500/10 px-3 py-1 text-[11px] text-teal-100"
                      >
                        {row.profile_label}{" "}
                        <span className="font-mono text-teal-200/90">×{row.scan_session_count}</span>
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}

              {scanPipelineDash.active_sessions.length > 0 || scanPipelineDash.recent_sessions.length > 0 ? (
                <div className="mt-6 grid gap-4 xl:grid-cols-2">
                  <ScanSessionMiniTable caption="Active / paused" rows={scanPipelineDash.active_sessions} />
                  <ScanSessionMiniTable caption="Recently completed / cancelled" rows={scanPipelineDash.recent_sessions} />
                </div>
              ) : (
                <p className="mt-6 text-sm text-slate-500">No active or recently finished scan sessions in your account.</p>
              )}
            </section>
          ) : null}

          {marketSalesLoading || marketSalesError || marketSalesPreview.length > 0 ? (
            <section
              id="market-intelligence"
              className="rounded-3xl border border-emerald-300/60 bg-white p-5 shadow-xl shadow-slate-200/50 ring-1 ring-emerald-100"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-800">Market sales foundation</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Read-only record preview</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Deterministic sales records, source names, and normalization states from the new market-sales layer.
                    The dashboard stays read-only; see the ops panel for explicit import-upsert detail.
                  </p>
                </div>
                <Link
                  to="/ops"
                  className="rounded-full border border-emerald-400/45 px-3 py-1.5 text-xs font-semibold text-emerald-800 transition hover:border-emerald-500/60 hover:bg-emerald-50"
                >
                  Open ops view
                </Link>
              </div>
              {marketSalesLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading market sales preview…</p>
              ) : marketSalesError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{marketSalesError}</StatusBanner>
                </div>
              ) : marketSalesPreview.length === 0 ? (
                <p className="mt-4 text-sm text-slate-500">No market-sale records recorded yet.</p>
              ) : (
                <div className="mt-5 overflow-auto rounded-2xl border border-slate-200 bg-slate-50">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                      <tr>
                        <th className="p-3 font-medium">Source</th>
                        <th className="p-3 font-medium">Title / issue</th>
                        <th className="p-3 font-medium">Sale</th>
                        <th className="p-3 font-medium">Status</th>
                        <th className="p-3 font-medium">Issues</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 text-slate-800">
                      {marketSalesPreview.slice(0, 6).map((row) => (
                        <tr key={row.id}>
                          <td className="p-3 align-top">
                            <div className="text-slate-900">{row.source_name}</div>
                            <div className="mt-1 text-[11px] text-slate-500">{row.source_type}</div>
                          </td>
                          <td className="p-3 align-top">
                            <div className="font-medium text-slate-900">{row.normalized_title ?? row.raw_title}</div>
                            <div className="mt-1 text-[11px] text-slate-600">
                              Issue {row.normalized_issue ?? row.raw_issue}
                            </div>
                          </td>
                          <td className="p-3 align-top">
                            {row.total_price ?? row.sale_price ?? "—"} {row.currency_code}
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
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ) : null}

          <MarketIntelligenceDashboard ownerUserId={user?.id} />

          {marketSaleReviewQueueSummaryLoading || marketSaleReviewQueueSummaryError || marketSaleReviewQueueSummary ? (
            <section className="mt-6 rounded-3xl border border-cyan-300/60 bg-white p-5 shadow-xl shadow-slate-200/50 ring-1 ring-cyan-100">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-blue-800">Market sale review queue</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Read-only review summary</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Deterministic queue counts only. Operators can open the review workspace to update normalized fields
                    and log explicit review actions; the dashboard stays read-only.
                  </p>
                </div>
                <Link
                  to="/ops#market-sale-review-queue"
                  className="rounded-full border border-cyan-400/35 px-3 py-1.5 text-xs font-semibold text-blue-800 transition hover:border-cyan-300/60 hover:bg-cyan-500/10"
                >
                  Open ops review queue
                </Link>
              </div>
              {marketSaleReviewQueueSummaryLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading market sale review summary…</p>
              ) : marketSaleReviewQueueSummaryError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{marketSaleReviewQueueSummaryError}</StatusBanner>
                </div>
              ) : marketSaleReviewQueueSummary ? (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
                    <StatCard label="Queue total" value={String(marketSaleReviewQueueSummary.total)} />
                    <StatCard label="Critical" value={String(marketSaleReviewQueueSummary.by_priority.critical ?? 0)} />
                    <StatCard label="High" value={String(marketSaleReviewQueueSummary.by_priority.high ?? 0)} />
                    <StatCard label="Medium" value={String(marketSaleReviewQueueSummary.by_priority.medium ?? 0)} />
                    <StatCard label="Low" value={String(marketSaleReviewQueueSummary.by_priority.low ?? 0)} />
                    <StatCard label="Info" value={String(marketSaleReviewQueueSummary.by_priority.info ?? 0)} />
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <StatCard
                      label="Needs title review"
                      value={String(marketSaleReviewQueueSummary.by_classification.needs_title_review ?? 0)}
                    />
                    <StatCard
                      label="Needs issue review"
                      value={String(marketSaleReviewQueueSummary.by_classification.needs_issue_review ?? 0)}
                    />
                    <StatCard
                      label="Possible duplicate"
                      value={String(marketSaleReviewQueueSummary.by_classification.possible_duplicate ?? 0)}
                    />
                  </div>
                </>
              ) : null}
            </section>
          ) : null}

          {marketCompEligibilitySummaryLoading || marketCompEligibilitySummaryError || marketCompEligibilitySummary ? (
            <section className="mt-6 rounded-3xl border border-emerald-400/25 bg-white ring-1 ring-emerald-100 p-5 shadow-xl shadow-slate-200/50">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-800">Market comp eligibility</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Read-only readiness counts</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Deterministic comp eligibility only. The dashboard stays read-only and shows lightweight readiness
                    counts; inspect the ops workspace for the full evidence drawer and filters.
                  </p>
                </div>
                <Link
                  to="/ops#market-comp-eligibility"
                  className="rounded-full border border-emerald-400/45 px-3 py-1.5 text-xs font-semibold text-emerald-800 transition hover:border-emerald-500/60 hover:bg-emerald-50"
                >
                  Open ops eligibility
                </Link>
              </div>
              {marketCompEligibilitySummaryLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading market comp eligibility summary…</p>
              ) : marketCompEligibilitySummaryError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{marketCompEligibilitySummaryError}</StatusBanner>
                </div>
              ) : marketCompEligibilitySummary ? (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
                    <StatCard label="Total" value={String(marketCompEligibilitySummary.total)} />
                    <StatCard
                      label="Eligible"
                      value={String(marketCompEligibilitySummary.by_eligibility_status.eligible ?? 0)}
                    />
                    <StatCard
                      label="Needs review"
                      value={String(marketCompEligibilitySummary.by_eligibility_status.needs_review ?? 0)}
                    />
                    <StatCard
                      label="Ineligible"
                      value={String(marketCompEligibilitySummary.by_eligibility_status.ineligible ?? 0)}
                    />
                    <StatCard
                      label="Eligible raw"
                      value={String(marketCompEligibilitySummary.by_eligibility_classification.eligible_raw_comp ?? 0)}
                    />
                    <StatCard
                      label="Eligible graded"
                      value={String(marketCompEligibilitySummary.by_eligibility_classification.eligible_graded_comp ?? 0)}
                    />
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <StatCard
                      label="Needs review before comp"
                      value={String(
                        marketCompEligibilitySummary.by_eligibility_classification.needs_review_before_comp ?? 0,
                      )}
                    />
                    <StatCard
                      label="Missing price"
                      value={String(
                        marketCompEligibilitySummary.by_eligibility_classification.ineligible_missing_price ?? 0,
                      )}
                    />
                    <StatCard
                      label="Unsupported currency"
                      value={String(
                        marketCompEligibilitySummary.by_eligibility_classification.ineligible_unsupported_currency ?? 0,
                      )}
                    />
                  </div>
                </>
              ) : null}
            </section>
          ) : null}

          {marketCompsSummaryLoading || marketCompsSummaryError || marketCompsSummary ? (
            <section className="mt-6 rounded-3xl border border-emerald-400/25 bg-white ring-1 ring-emerald-100 p-5 shadow-xl shadow-slate-200/50">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-800">Comparable sales</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Comp readiness overview</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Lightweight grouped-comp summary. Open the ops explorer for full included and excluded sales evidence.
                  </p>
                </div>
                <Link
                  to="/ops#market-comps"
                  className="rounded-full border border-emerald-400/45 px-3 py-1.5 text-xs font-semibold text-emerald-800 transition hover:border-emerald-500/60 hover:bg-emerald-50"
                >
                  Open comp explorer
                </Link>
              </div>
              {marketCompsSummaryLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading comparable sales summary…</p>
              ) : marketCompsSummaryError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{marketCompsSummaryError}</StatusBanner>
                </div>
              ) : marketCompsSummary ? (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
                    <StatCard label="Groups" value={String(marketCompsSummary.total_groups)} />
                    <StatCard label="Records" value={String(marketCompsSummary.total_comps)} />
                    <StatCard label="Included" value={String(marketCompsSummary.by_classification.included_comp ?? 0)} />
                    <StatCard label="Duplicate" value={String(marketCompsSummary.by_classification.excluded_duplicate ?? 0)} />
                    <StatCard label="Review required" value={String(marketCompsSummary.by_classification.excluded_review_required ?? 0)} />
                    <StatCard label="Stale" value={String(marketCompsSummary.by_classification.excluded_stale ?? 0)} />
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <StatCard label="Wrong scope" value={String(marketCompsSummary.by_classification.excluded_wrong_scope ?? 0)} />
                    <StatCard label="Wrong grade" value={String(marketCompsSummary.by_classification.excluded_wrong_grade ?? 0)} />
                    <StatCard label="Unsupported currency" value={String(marketCompsSummary.by_classification.excluded_unsupported_currency ?? 0)} />
                  </div>
                </>
              ) : null}
            </section>
          ) : null}

          {marketFmvSummaryLoading || marketFmvSummaryError || marketFmvSummary ? (
            <section className="mt-6 rounded-3xl border border-cyan-300/60 bg-white p-5 shadow-xl shadow-slate-200/50 ring-1 ring-cyan-100">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-blue-800">Market FMV snapshots</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Deterministic valuation ledger</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Snapshot-only FMV built from eligible comparable sales. This stays separate from manual inventory FMV edits
                    and never performs prediction, FX conversion, or automated portfolio mutation.
                  </p>
                </div>
                <Link
                  to="/ops#market-fmv"
                  className="rounded-full border border-cyan-400/35 px-3 py-1.5 text-xs font-semibold text-blue-800 transition hover:border-cyan-300/60 hover:bg-cyan-500/10"
                >
                  Open ops FMV workspace
                </Link>
              </div>
              {marketFmvSummaryLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading market FMV snapshots…</p>
              ) : marketFmvSummaryError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{marketFmvSummaryError}</StatusBanner>
                </div>
              ) : marketFmvSummary ? (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <StatCard
                    label="Raw FMV snapshots"
                    value={String(marketFmvSummary.items.filter((row) => row.snapshot_scope === "raw").length)}
                  />
                  <StatCard
                    label="Graded FMV snapshots"
                    value={String(marketFmvSummary.items.filter((row) => row.snapshot_scope !== "raw").length)}
                  />
                  <StatCard
                    label="High confidence"
                    value={String(
                      (marketFmvSummary.by_confidence_bucket.very_high ?? 0) +
                        (marketFmvSummary.by_confidence_bucket.high ?? 0),
                    )}
                  />
                  <StatCard label="Stale snapshots" value={String(marketFmvSummary.stale_count)} />
                </div>
              ) : null}
            </section>
          ) : null}

          {marketTrendSummaryLoading || marketTrendSummaryError || marketTrendSummary ? (
            <section className="mt-6 rounded-3xl border border-violet-400/25 bg-white ring-1 ring-violet-100 p-5 shadow-xl shadow-slate-200/50">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-violet-800">Market trend snapshots</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Deterministic trend signal strip</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Compare FMV history over fixed windows to surface rising, falling, stable, and volatile movement without
                    forecasting, speculation scoring, or inventory mutation.
                  </p>
                </div>
                <Link
                  to="/ops#market-trends"
                  className="rounded-full border border-violet-400/45 px-3 py-1.5 text-xs font-semibold text-violet-800 transition hover:border-violet-500/60 hover:bg-violet-50"
                >
                  Open ops trend workspace
                </Link>
              </div>
              {marketTrendSummaryLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading market trend snapshots…</p>
              ) : marketTrendSummaryError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{marketTrendSummaryError}</StatusBanner>
                </div>
              ) : marketTrendSummary ? (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <StatCard label="Rising" value={String(marketTrendSummary.by_trend_direction.rising ?? 0)} />
                  <StatCard label="Falling" value={String(marketTrendSummary.by_trend_direction.falling ?? 0)} />
                  <StatCard label="Volatile" value={String(marketTrendSummary.by_trend_direction.volatile ?? 0)} />
                  <StatCard label="Stale trends" value={String(marketTrendSummary.stale_count)} />
                </div>
              ) : null}
            </section>
          ) : null}

          {marketMatchSuggestionsPendingLoading || marketMatchSuggestionsPendingError || marketMatchSuggestionsPendingCount >= 0 ? (
            <section className="mt-6 rounded-3xl border border-violet-400/25 bg-white ring-1 ring-violet-100 p-5 shadow-xl shadow-slate-200/50">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-violet-800">Market match suggestions</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Read-only pending-count widget</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Deterministic match suggestions only. Open the ops review workspace to inspect evidence and approve,
                    reject, or ignore suggestion artifacts without mutating canonical or inventory data.
                  </p>
                </div>
                <Link
                  to="/ops#market-match-suggestions"
                  className="rounded-full border border-violet-400/45 px-3 py-1.5 text-xs font-semibold text-violet-800 transition hover:border-violet-500/60 hover:bg-violet-50"
                >
                  Open ops match suggestions
                </Link>
              </div>
              {marketMatchSuggestionsPendingLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading market match suggestion count…</p>
              ) : marketMatchSuggestionsPendingError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{marketMatchSuggestionsPendingError}</StatusBanner>
                </div>
              ) : (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  <StatCard label="Pending suggestions" value={String(marketMatchSuggestionsPendingCount)} />
                </div>
              )}
            </section>
          ) : null}

          {user && loadsDealerData ? (
            <section
              id="dealer-command-dash"
              className="mt-6 rounded-3xl border border-lime-500/35 bg-white p-5 shadow-xl shadow-black/35"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-lime-800">Dealer command</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Operational cockpit · Bloomberg-style density</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Deterministic overlays only: inventory movement, liquidity posture, exporter health, show operations, ledger sales,
                    listing intelligence completeness. No forecasting, staffing, outbound notifications, repricing bots, or automatic
                    alert resolution — generate snapshots explicitly to freeze evidence.
                  </p>
                  {(() => {
                    const snap = dealerDashResp?.snapshot;
                    return snap ? (
                      <p className="mt-2 text-[11px] font-mono text-slate-500">
                        snapshot #{snap.id} · {snap.snapshot_date} · checksum {shortenChecksum(snap.checksum)}
                      </p>
                    ) : (
                      <p className="mt-2 text-[11px] font-mono text-slate-500">No persisted snapshot yet — generate to materialize.</p>
                    );
                  })()}
                </div>
                <div className="flex flex-wrap items-end gap-2">
                  <button
                    type="button"
                    onClick={() => void generateDealerDashboardSnapshot()}
                    disabled={dealerGenBusy}
                    className="rounded-xl border border-lime-400/45 bg-lime-500/10 px-4 py-2 text-xs font-semibold text-lime-100 transition hover:bg-lime-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {dealerGenBusy ? "Generating…" : "Generate snapshot"}
                  </button>
                  <Link
                    to="/ops#dealer-dashboard-ops"
                    className="rounded-xl border border-white/15 px-4 py-2 text-xs font-semibold text-slate-100 transition hover:border-lime-300/45 hover:bg-white/5"
                  >
                    Ops drill-down tables
                  </Link>
                </div>
              </div>

              {dealerDashLoading ? (
                <p className="mt-6 text-sm text-slate-600">Loading dealer rollups…</p>
              ) : dealerDashError ? (
                <div className="mt-6">
                  <StatusBanner tone="error">{dealerDashError}</StatusBanner>
                </div>
              ) : (
                <div className="mt-6 space-y-5">
                  {(() => {
                    const snap = dealerDashResp?.snapshot;
                    return (
                      <>
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">A · Operational overview</p>
                          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                            <StatCard label="Active listings (registry)" value={snap ? String(snap.active_listing_count) : "—"} />
                            <StatCard label="Export-ready (intel≥100)" value={snap ? String(snap.export_ready_count) : "—"} />
                            <StatCard label="Incomplete intel" value={snap ? String(snap.incomplete_listing_count) : "—"} />
                            <StatCard label="Stale posture" value={snap ? String(snap.stale_listing_count) : "—"} />
                            <StatCard label="Liquidity HIGH / LOW*" value={
                              snap ? `${snap.liquidity_high_count} / ${snap.liquidity_low_count}` : "—"
                            } />
                            <StatCard
                              label="Gross / Net 30d"
                              value={snap ? `${formatUsdCurrency(snap.gross_sales_30d)} / ${formatUsdCurrency(snap.net_sales_30d)}` : "—"}
                            />
                          </div>
                          <p className="mt-2 text-[10px] text-slate-500">
                            *LOW bucket counts inventory rows flagged LOW / ILLIQUID minus ambiguous overlaps on the pinned snapshot_date.
                          </p>
                        </div>

                        <div className="grid gap-5 xl:grid-cols-2">
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">B · Alerts</p>
                            <div className="mt-2 overflow-auto rounded-2xl border border-slate-200 bg-slate-50">
                              <table className="w-full border-collapse text-left text-xs">
                                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                                  <tr>
                                    <th className="p-3 font-medium">Severity</th>
                                    <th className="p-3 font-medium">Type</th>
                                    <th className="p-3 font-medium">Evidence</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-200 text-slate-800">
                                  {dealerAlerts.length === 0 ? (
                                    <tr>
                                      <td className="p-3 text-slate-500" colSpan={3}>
                                        No routed alerts loaded (generate a dashboard snapshot to hydrate feed-backed alerts).
                                      </td>
                                    </tr>
                                  ) : (
                                    dealerAlerts.slice(0, 12).map((a) => (
                                      <tr key={a.id}>
                                        <td className="p-3 font-semibold text-lime-200/90">{a.severity}</td>
                                        <td className="p-3 text-slate-100">{a.alert_type}</td>
                                        <td className="p-3 text-slate-600">{a.message}</td>
                                      </tr>
                                    ))
                                  )}
                                </tbody>
                              </table>
                            </div>
                          </div>

                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">C · Operational feed</p>
                            <div className="mt-2 overflow-auto rounded-2xl border border-slate-200 bg-slate-50">
                              <table className="w-full border-collapse text-left text-xs">
                                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                                  <tr>
                                    <th className="p-3 font-medium">Time</th>
                                    <th className="p-3 font-medium">Signal</th>
                                    <th className="p-3 font-medium">Summary</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-200 text-slate-800">
                                  {dealerFeed.length === 0 ? (
                                    <tr>
                                      <td className="p-3 text-slate-500" colSpan={3}>
                                        Feed is append-only across dashboard generations — run a snapshot to hydrate missing keys.
                                      </td>
                                    </tr>
                                  ) : (
                                    dealerFeed.slice(0, 14).map((evt) => (
                                      <tr key={evt.id}>
                                        <td className="whitespace-nowrap p-3 text-slate-500">{formatDateTime(evt.created_at)}</td>
                                        <td className="p-3 font-semibold text-slate-100">{evt.event_type}</td>
                                        <td className="p-3 text-slate-600">{evt.summary}</td>
                                      </tr>
                                    ))
                                  )}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        </div>

                        <div className="grid gap-5 xl:grid-cols-2">
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">D · Convention snapshot</p>
                            {conventionSummaryLoading ? (
                              <p className="mt-2 text-sm text-slate-600">Loading convention aggregates…</p>
                            ) : conventionSummaryError ? (
                              <StatusBanner tone="error">{conventionSummaryError}</StatusBanner>
                            ) : conventionSummary ? (
                              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                                <StatCard label="Active shows" value={String(conventionSummary.active_convention_count)} />
                                <StatCard label="Assigned inventory ids" value={String(conventionSummary.assigned_inventory_count)} />
                                <StatCard label="Open sale sessions" value={String(conventionSummary.active_sale_session_count)} />
                                <StatCard label="Wall / Showcase" value={`${conventionSummary.wall_book_count} · ${conventionSummary.showcase_count}`} />
                              </div>
                            ) : (
                              <p className="mt-2 text-sm text-slate-500">No convention summaries yet.</p>
                            )}
                          </div>

                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">E · Export ops</p>
                            {listingExportDashLoading ? (
                              <p className="mt-2 text-sm text-slate-600">Loading exporter rollups…</p>
                            ) : listingExportDashError ? (
                              <StatusBanner tone="error">{listingExportDashError}</StatusBanner>
                            ) : listingExportDash ? (
                              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                                <StatCard label="Completed runs" value={String(listingExportDash.completed_run_count)} />
                                <StatCard label="Skipped rows (lifetime)" value={String(listingExportDash.skipped_rows_lifetime_sum)} />
                                <StatCard label="Failed exports (dash 30d)" value={snap ? String(snap.failed_export_count_30d) : "—"} />
                                <StatCard label="Export runs (dash 30d)" value={snap ? String(snap.export_run_count_30d) : "—"} />
                              </div>
                            ) : (
                              <p className="mt-2 text-sm text-slate-500">No exporter history.</p>
                            )}
                          </div>
                        </div>

                        <div className="grid gap-5 xl:grid-cols-2">
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">F · Ledger sales · 30d</p>
                            {salesLedgerSummaryLoading ? (
                              <p className="mt-2 text-sm text-slate-600">Loading ledger summary…</p>
                            ) : salesLedgerSummaryError ? (
                              <StatusBanner tone="error">{salesLedgerSummaryError}</StatusBanner>
                            ) : salesLedgerSummary ? (
                              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                                <StatCard label="Gross 30d" value={snap ? formatUsdCurrency(snap.gross_sales_30d) : formatUsdCurrency(salesLedgerSummary.gross_sales_total)} />
                                <StatCard label="Net 30d" value={snap ? formatUsdCurrency(snap.net_sales_30d) : formatUsdCurrency(salesLedgerSummary.net_proceeds_total)} />
                                <StatCard label="Realized profit 30d" value={snap ? formatUsdCurrency(snap.realized_profit_30d) : formatUsdCurrency(salesLedgerSummary.realized_profit_total)} />
                                <StatCard label="Recent recorded rows" value={String(salesLedgerSummary.recent_sales.length)} />
                              </div>
                            ) : (
                              <p className="mt-2 text-sm text-slate-500">Ledger summary unavailable.</p>
                            )}
                          </div>

                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">G · Listing intelligence</p>
                            {listingIntelligenceSummaryLoading ? (
                              <p className="mt-2 text-sm text-slate-600">Loading intelligence rollup…</p>
                            ) : listingIntelligenceSummaryError ? (
                              <StatusBanner tone="error">{listingIntelligenceSummaryError}</StatusBanner>
                            ) : listingIntelligenceSummary ? (
                              <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                                <StatCard label="Avg completeness" value={listingIntelligenceSummary.average_completeness_score ?? "—"} />
                                <StatCard label="Export-ready listings" value={String(listingIntelligenceSummary.export_ready_count)} />
                                <StatCard label="Weak listings" value={String(listingIntelligenceSummary.recent_weak_or_incomplete.length)} />
                                <StatCard label="Strong" value={String(listingIntelligenceSummary.strong_listing_count)} />
                              </div>
                            ) : (
                              <p className="mt-2 text-sm text-slate-500">Listing intelligence rollup unavailable.</p>
                            )}
                          </div>
                        </div>
                      </>
                    );
                  })()}
                </div>
              )}
            </section>
          ) : null}

          {user && loadsDealerData ? (
            <>
              <section
                id="portfolio-intelligence-dash"
              className="mt-6 rounded-3xl border border-amber-400/35 bg-white ring-1 ring-amber-100 p-5 shadow-xl shadow-slate-200/50"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-900">Portfolio intelligence</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Deterministic exposure & allocation truth</h2>
                  <p className="mt-1 max-w-3xl text-sm text-slate-600">
                    Registry-grade rollups: portfolio counts, FMV and cost basis anchors (when present), concentration flags,
                    liquidity split, graded vs raw posture. Observational — no trades, acquisitions, predictive signals, or
                    hidden inventory mutation.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void refreshPortfolioIntelligenceSnapshots()}
                    disabled={portfolioIntelGenBusy}
                    className="rounded-xl border border-amber-400/45 bg-amber-500/10 px-4 py-2 text-xs font-semibold text-amber-50 transition hover:bg-amber-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {portfolioIntelGenBusy ? "Refreshing…" : "Refresh exposures & allocation"}
                  </button>
                  <Link
                    to="/ops#portfolio-registry-ops"
                    className="rounded-xl border border-white/15 px-4 py-2 text-xs font-semibold text-slate-100 transition hover:border-amber-300/45 hover:bg-white/5"
                  >
                    Ops portfolio tables
                  </Link>
                </div>
              </div>

              {portfolioIntelLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading portfolio rollup…</p>
              ) : portfolioIntelError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{portfolioIntelError}</StatusBanner>
                </div>
              ) : portfolioIntelSummary ? (
                <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <StatCard label="Active portfolios" value={String(portfolioIntelSummary.active_portfolio_count)} />
                  <StatCard label="Items in scope" value={String(portfolioIntelSummary.total_item_count ?? "—")} />
                  <StatCard label="Total FMV (scope)" value={formatMaybeCurrency(portfolioIntelSummary.total_fmv_amount)} />
                  <StatCard label="Cost basis (scope)" value={formatMaybeCurrency(portfolioIntelSummary.total_cost_basis_amount)} />
                  <StatCard
                    label="Graded / raw"
                    value={`${portfolioIntelSummary.graded_item_count ?? "—"} · ${portfolioIntelSummary.raw_item_count ?? "—"}`}
                  />
                  <StatCard
                    label="Liquidity high · low"
                    value={`${portfolioIntelSummary.high_liquidity_count ?? "—"} · ${portfolioIntelSummary.low_liquidity_count ?? "—"}`}
                  />
                  <StatCard
                    label="Concentrated / overexposed"
                    value={
                      portfolioIntelSummary.overexposed_rows.length
                        ? `${portfolioIntelSummary.overexposed_rows.length} buckets (see Ops for detail)`
                        : "—"
                    }
                  />
                  <StatCard
                    label="Exposure batch checksum"
                    value={
                      portfolioIntelSummary.latest_generation_batch_checksum
                        ? shortenChecksum(portfolioIntelSummary.latest_generation_batch_checksum)
                        : "—"
                    }
                  />
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-500">No portfolio intelligence loaded.</p>
              )}
            </section>

            <section
              id="portfolio-liquidity-dash"
              className="mt-6 rounded-3xl border border-teal-400/35 bg-white ring-1 ring-teal-100 p-5 shadow-xl shadow-slate-200/50"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-teal-800">Portfolio liquidity allocation</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Deterministic capital &amp; liquidity posture</h2>
                  <p className="mt-1 max-w-3xl text-sm text-slate-600">
                    Portfolio-wide liquidity buckets, weighted FMV posture, observational dead-capital estimate, balance status,
                    and explicit checksum fingerprints. Inputs are read-only liquidity engine, FMV, listings, sales ledger,
                    allocations, and convention assignments — no liquidation, predictive timing, or FMV/portfolio mutation.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void refreshPortfolioLiquiditySnapshots()}
                    disabled={portfolioLiquidityGenBusy}
                    className="rounded-xl border border-teal-400/45 bg-teal-500/10 px-4 py-2 text-xs font-semibold text-teal-50 transition hover:bg-teal-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {portfolioLiquidityGenBusy ? "Generating…" : "Generate liquidity snapshot"}
                  </button>
                  <Link
                    to="/ops#portfolio-liquidity-ops"
                    className="rounded-xl border border-white/15 px-4 py-2 text-xs font-semibold text-slate-100 transition hover:border-teal-300/45 hover:bg-white/5"
                  >
                    Ops liquidity tables
                  </Link>
                </div>
              </div>
              {portfolioLiquidityLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading portfolio liquidity rollup…</p>
              ) : portfolioLiquidityError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{portfolioLiquidityError}</StatusBanner>
                </div>
              ) : portfolioLiquidityDetail ? (
                <div className="mt-6 space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <StatCard
                      label="Liquid FMV (HIGH bucket)"
                      value={formatMaybeCurrency(portfolioLiquidityDetail.snapshot.liquid_portfolio_value)}
                    />
                    <StatCard
                      label="Illiquid FMV"
                      value={formatMaybeCurrency(portfolioLiquidityDetail.snapshot.illiquid_portfolio_value)}
                    />
                    <StatCard
                      label="Liquidity efficiency"
                      value={portfolioLiquidityDetail.snapshot.liquidity_efficiency_score ?? "—"}
                    />
                    <StatCard
                      label="Dead capital estimate"
                      value={formatMaybeCurrency(portfolioLiquidityDetail.snapshot.dead_capital_estimate)}
                    />
                    <StatCard label="Liquidity imbalance" value={portfolioLiquidityDetail.snapshot.liquidity_balance_status} />
                    <StatCard
                      label="Checksum"
                      value={shortenChecksum(portfolioLiquidityDetail.snapshot.checksum)}
                    />
                    <StatCard
                      label="HIGH · MED buckets"
                      value={`${portfolioLiquidityDetail.snapshot.high_liquidity_count} · ${portfolioLiquidityDetail.snapshot.medium_liquidity_count}`}
                    />
                    <StatCard
                      label="LOW · ILLIQ buckets"
                      value={`${portfolioLiquidityDetail.snapshot.low_liquidity_count} · ${portfolioLiquidityDetail.snapshot.illiquid_count}`}
                    />
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-700">
                    <p className="font-semibold uppercase tracking-[0.14em] text-slate-500">Liquidity buckets (% of FMV)</p>
                    <ul className="mt-2 space-y-1">
                      {portfolioLiquidityDetail.buckets.map((b) => (
                        <li key={b.id} className="flex justify-between gap-4">
                          <span>{b.liquidity_bucket}</span>
                          <span className="text-slate-600">
                            {(b.percentage_of_portfolio ?? "—").toString()}% · counts {b.item_count}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-500">Generate a portfolio liquidity snapshot to populate this panel.</p>
              )}
            </section>

            <section
              id="duplicate-intelligence-dash"
              className="mt-6 rounded-3xl border border-rose-400/30 bg-white ring-1 ring-rose-100 p-5 shadow-xl shadow-slate-200/50"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-rose-800">Duplicate intelligence</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Deterministic overlaps & consolidation posture</h2>
                  <p className="mt-1 max-w-3xl text-sm text-slate-600">
                    Observational duplicate clusters, deterministic strength tiers, liquidity-aware profiles, and consolidation
                    captions only. No auto-selling, acquisitions, predictive AI, FMV mutation, or hidden inventory changes.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void refreshDuplicateIntelligenceSnapshots()}
                    disabled={dupIntelGenBusy}
                    className="rounded-xl border border-rose-400/45 bg-rose-500/10 px-4 py-2 text-xs font-semibold text-rose-50 transition hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {dupIntelGenBusy ? "Generating…" : "Generate duplicate snapshot"}
                  </button>
                  <Link
                    to="/ops#duplicate-consolidation-ops"
                    className="rounded-xl border border-white/15 px-4 py-2 text-xs font-semibold text-slate-100 transition hover:border-rose-300/45 hover:bg-white/5"
                  >
                    Ops duplicate tables
                  </Link>
                </div>
              </div>
              {dupIntelLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading duplicate rollup…</p>
              ) : dupIntelError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{dupIntelError}</StatusBanner>
                </div>
              ) : dupIntelSummary ? (
                <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <StatCard label="Clusters (latest)" value={String(dupIntelSummary.cluster_count)} />
                  <StatCard label="Overexposed clusters" value={String(dupIntelSummary.overexposed_cluster_count)} />
                  <StatCard
                    label="Redundant tail capital"
                    value={
                      dupIntelSummary.redundant_capital_amount
                        ? formatUsdCurrency(dupIntelSummary.redundant_capital_amount)
                        : "—"
                    }
                  />
                  <StatCard
                    label="Graded/raw overlap buckets"
                    value={`${dupIntelSummary.graded_overlap_cluster_count} · ${dupIntelSummary.raw_graded_overlap_cluster_count}`}
                  />
                  <StatCard
                    label="Duplicate unit rollups"
                    value={`${dupIntelSummary.graded_duplicate_units} graded cols · ${dupIntelSummary.raw_duplicate_units} raw/pipe`}
                  />
                  <StatCard
                    label="Batch checksum"
                    value={
                      dupIntelSummary.generation_batch_checksum
                        ? shortenChecksum(dupIntelSummary.generation_batch_checksum)
                        : "—"
                    }
                  />
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-500">Generate a duplicate snapshot to populate this panel.</p>
              )}
            </section>
            </>
          ) : null}

          {user && loadsGradingData ? (
            <section
              id="dealer-grading-command-center"
              className="mt-6 rounded-3xl border border-cyan-400/35 bg-white ring-1 ring-cyan-100 p-5 shadow-xl shadow-slate-200/60"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-blue-800">Dealer grading dashboard</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Unified grading intelligence cockpit</h2>
                  <p className="mt-1 max-w-3xl text-sm text-slate-600">
                    Dense dealer-grade grading operations only: candidate posture, recommendation quality, submission flow,
                    reconciliation outcomes, risk overlays, alerts, and append-safe feed evidence. No scan AI, autonomous
                    grading, or hidden mutation.
                  </p>
                  {dealerGradingDashResp?.snapshot ? (
                    <p className="mt-2 text-[11px] font-mono text-slate-500">
                      snapshot #{dealerGradingDashResp.snapshot.id} · {dealerGradingDashResp.snapshot.snapshot_date} · checksum{" "}
                      {shortenChecksum(dealerGradingDashResp.snapshot.checksum)}
                    </p>
                  ) : (
                    <p className="mt-2 text-[11px] font-mono text-slate-500">No persisted grading snapshot yet — generate to materialize.</p>
                  )}
                </div>
                <div className="flex flex-wrap items-end gap-2">
                  <button
                    type="button"
                    onClick={() => void generateDealerGradingDashboardSnapshot()}
                    disabled={dealerGradingGenBusy}
                    className="rounded-xl border border-cyan-400/45 bg-cyan-500/10 px-4 py-2 text-xs font-semibold text-blue-800 transition hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {dealerGradingGenBusy ? "Generating…" : "Generate grading snapshot"}
                  </button>
                  <Link
                    to="/ops#dealer-grading-dashboard-ops"
                    className="rounded-xl border border-white/15 px-4 py-2 text-xs font-semibold text-slate-100 transition hover:border-cyan-300/45 hover:bg-white/5"
                  >
                    Ops grading tables
                  </Link>
                </div>
              </div>

              {dealerGradingDashLoading ? (
                <p className="mt-6 text-sm text-slate-600">Loading grading command center…</p>
              ) : dealerGradingDashError ? (
                <div className="mt-6">
                  <StatusBanner tone="error">{dealerGradingDashError}</StatusBanner>
                </div>
              ) : (
                (() => {
                  const snap = dealerGradingDashResp?.snapshot;
                  const metricValue = (key: string) => dealerGradingMetricMap.get(key)?.metric_value_decimal ?? "—";
                  const graderRollup = Array.isArray(
                    (dealerGradingMetricMap.get("grader_performance_rollup")?.metric_metadata_json as { graders?: unknown } | undefined)
                      ?.graders,
                  )
                    ? (
                        dealerGradingMetricMap.get("grader_performance_rollup")?.metric_metadata_json as {
                          graders?: Array<Record<string, unknown>>;
                        }
                      ).graders ?? []
                    : [];
                  return (
                    <div className="mt-6 space-y-5">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                          A · Grading pipeline overview
                        </p>
                        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                          <StatCard label="Active candidates" value={snap ? String(snap.active_candidate_count) : "—"} />
                          <StatCard label="Submitted candidates" value={snap ? String(snap.submitted_candidate_count) : "—"} />
                          <StatCard label="Graded candidates" value={snap ? String(snap.graded_candidate_count) : "—"} />
                          <StatCard label="Pipeline value" value={formatMaybeCurrency(snap?.grading_pipeline_value)} />
                          <StatCard label="Expected profit" value={formatMaybeCurrency(snap?.expected_total_profit)} />
                        </div>
                      </div>

                      <div className="grid gap-5 xl:grid-cols-2">
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                            B · Recommendation summary
                          </p>
                          <div className="mt-3 grid gap-3 sm:grid-cols-2">
                            <StatCard label="Grade recommendations" value={metricValue("grade_recommendation_count")} />
                            <StatCard label="Elite opportunities" value={metricValue("elite_opportunity_count")} />
                            <StatCard label="Hold raw" value={metricValue("hold_raw_count")} />
                            <StatCard label="Review manually" value={metricValue("review_manually_count")} />
                          </div>
                        </div>

                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                            C · Risk / confidence summary
                          </p>
                          <div className="mt-3 grid gap-3 sm:grid-cols-2">
                            <StatCard label="Low-risk candidates" value={metricValue("low_risk_count")} />
                            <StatCard label="High-risk candidates" value={snap ? String(snap.high_risk_candidate_count) : "—"} />
                            <StatCard label="Low-confidence" value={snap ? String(snap.low_confidence_candidate_count) : "—"} />
                            <StatCard label="Avg risk-adjusted ROI" value={snap?.average_risk_adjusted_roi ?? "—"} />
                          </div>
                        </div>
                      </div>

                      <div className="grid gap-5 xl:grid-cols-2">
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                            D · Submission operations
                          </p>
                          <div className="mt-3 grid gap-3 sm:grid-cols-2">
                            <StatCard label="Active batches" value={snap ? String(snap.active_submission_batch_count) : "—"} />
                            <StatCard label="Shipped batches" value={metricValue("shipped_batch_count")} />
                            <StatCard label="Delayed batches" value={metricValue("delayed_batch_count")} />
                            <StatCard label="Turnaround metric" value={metricValue("average_turnaround_days")} />
                          </div>
                        </div>

                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                            E · Reconciliation summary
                          </p>
                          <div className="mt-3 grid gap-3 sm:grid-cols-2">
                            <StatCard label="Above expectation" value={metricValue("above_expectation_count")} />
                            <StatCard label="Below expectation" value={metricValue("below_expectation_count")} />
                            <StatCard label="Avg ROI delta" value={metricValue("average_roi_delta")} />
                            <StatCard label="Avg estimated ROI" value={snap?.average_estimated_roi ?? "—"} />
                          </div>
                          <div className="mt-4 grid gap-3 sm:grid-cols-2">
                            {graderRollup.length === 0 ? (
                              <p className="text-sm text-slate-500">No grader performance rollups on this snapshot.</p>
                            ) : (
                              graderRollup.slice(0, 4).map((row) => (
                                <div key={String(row.grader ?? Math.random())} className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                                  <p className="text-sm font-semibold text-patriot-navy">{String(row.grader ?? "Unknown grader")}</p>
                                  <p className="mt-1 text-xs text-slate-600">
                                    submissions {String(row.submission_count ?? "—")} · below {String(row.below_expectation_count ?? "—")}
                                  </p>
                                  <p className="mt-1 text-[11px] text-slate-500">
                                    ROI delta {String(row.average_roi_delta ?? "—")} · turnaround {String(row.average_turnaround_days ?? "—")}
                                  </p>
                                </div>
                              ))
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="grid gap-5 xl:grid-cols-2">
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">F · Alerts panel</p>
                          <div className="mt-2 overflow-auto rounded-2xl border border-slate-200 bg-slate-50">
                            <table className="w-full border-collapse text-left text-xs">
                              <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                                <tr>
                                  <th className="p-3 font-medium">Severity</th>
                                  <th className="p-3 font-medium">Type</th>
                                  <th className="p-3 font-medium">Evidence</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-200 text-slate-800">
                                {dealerGradingAlerts.length === 0 ? (
                                  <tr>
                                    <td className="p-3 text-slate-500" colSpan={3}>
                                      No grading alerts loaded.
                                    </td>
                                  </tr>
                                ) : (
                                  dealerGradingAlerts.slice(0, 12).map((row) => (
                                    <tr key={row.id}>
                                      <td className="p-3 font-semibold text-blue-700/90">{row.severity}</td>
                                      <td className="p-3 text-slate-100">{row.alert_type}</td>
                                      <td className="p-3 text-slate-600">{row.message}</td>
                                    </tr>
                                  ))
                                )}
                              </tbody>
                            </table>
                          </div>
                        </div>

                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">G · Grading feed</p>
                          <div className="mt-2 overflow-auto rounded-2xl border border-slate-200 bg-slate-50">
                            <table className="w-full border-collapse text-left text-xs">
                              <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                                <tr>
                                  <th className="p-3 font-medium">Time</th>
                                  <th className="p-3 font-medium">Signal</th>
                                  <th className="p-3 font-medium">Summary</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-200 text-slate-800">
                                {dealerGradingFeed.length === 0 ? (
                                  <tr>
                                    <td className="p-3 text-slate-500" colSpan={3}>
                                      Feed is append-only across grading snapshot generations.
                                    </td>
                                  </tr>
                                ) : (
                                  dealerGradingFeed.slice(0, 14).map((evt) => (
                                    <tr key={evt.id}>
                                      <td className="whitespace-nowrap p-3 text-slate-500">{formatDateTime(evt.created_at)}</td>
                                      <td className="p-3 font-semibold text-slate-100">{evt.event_type}</td>
                                      <td className="p-3 text-slate-600">{evt.summary}</td>
                                    </tr>
                                  ))
                                )}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })()
              )}
            </section>
          ) : null}

          {user && loadsGradingData ? (
            <section
              id="grading-reporting-dash"
              className="mt-6 rounded-3xl border border-indigo-400/35 bg-white ring-1 ring-indigo-100 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-indigo-800">Grading reporting</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">P37 closeout CSV registry</h2>
                  <p className="mt-1 max-w-3xl text-sm text-slate-600">
                    Deterministic grading closeout reports for candidates, economics, submissions, reconciliation,
                    recommendations, risk, the grading dashboard, and grader performance. Reports are observational only
                    and keep replay-safe checksums plus append-safe history.
                  </p>
                </div>
                <div className="flex flex-wrap items-end gap-2">
                  <button
                    type="button"
                    onClick={() => void generateQuickGradingReport()}
                    disabled={gradingReportBusy}
                    className="rounded-xl border border-indigo-400/45 bg-indigo-500/12 px-4 py-2 text-xs font-semibold text-indigo-100 transition hover:bg-indigo-400/18 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {gradingReportBusy ? "Generating…" : "Generate grading dashboard CSV"}
                  </button>
                  <Link
                    to="/ops#grading-reporting-ops"
                    className="rounded-xl border border-white/15 px-4 py-2 text-xs font-semibold text-slate-100 transition hover:border-indigo-300/55 hover:bg-white/5"
                  >
                    Ops grading reports
                  </Link>
                </div>
              </div>

              {gradingReportsLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading grading report registry…</p>
              ) : gradingReportsError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{gradingReportsError}</StatusBanner>
                </div>
              ) : (
                <div className="mt-5 grid gap-4 xl:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Recent grading reports</p>
                    {gradingReportsRecent && gradingReportsRecent.items.length > 0 ? (
                      <ul className="mt-3 space-y-2 text-xs text-slate-200">
                        {gradingReportsRecent.items.map((run) => (
                          <li key={run.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2">
                            <div>
                              <p className="font-semibold text-slate-900">{run.report_type}</p>
                              <p className="font-mono text-[10px] text-slate-500">
                                #{run.id} · {run.status} · rows {run.csv_row_count}
                              </p>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <span className="rounded-full border border-white/15 px-2 py-1 text-[10px] text-slate-700">
                                {shortenChecksum(run.checksum)}
                              </span>
                              {run.status === "COMPLETED" ? (
                                <button
                                  type="button"
                                  className="rounded-full border border-indigo-300/55 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-indigo-100"
                                  onClick={() => void downloadGradingReportCsvClient(run.id)}
                                >
                                  Download CSV
                                </button>
                              ) : null}
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-3 text-sm text-slate-500">No grading reports recorded yet.</p>
                    )}
                  </div>

                  <div className="rounded-2xl border border-rose-400/35 bg-white ring-1 ring-rose-100 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-rose-800">Failed reports</p>
                    {gradingReportsFailed && gradingReportsFailed.items.length > 0 ? (
                      <ul className="mt-3 space-y-2 text-xs text-rose-100">
                        {gradingReportsFailed.items.map((run) => (
                          <li key={run.id} className="border-b border-slate-200 pb-2">
                            <p className="font-semibold">{run.report_type}</p>
                            <p className="font-mono text-[10px] text-rose-200/80">
                              #{run.id} · {shortenChecksum(run.checksum)} · {(run.failure_reason ?? "UNKNOWN").slice(0, 120)}
                            </p>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-3 text-sm text-rose-200/70">No failed grading report generations on record.</p>
                    )}
                  </div>
                </div>
              )}
            </section>
          ) : null}

          {user && loadsGradingData ? (
            <section
              id="grading-candidates-dash"
              className="mt-6 rounded-3xl border border-amber-400/35 bg-white ring-1 ring-amber-100 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-900">Grading operations</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">P37 grading candidate ledger</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Owner-scoped grading intentions, economics placeholders, replay-safe inserts, checksum snapshots, and
                    append-only evidence — not grade prediction or scan AI on this lane.
                  </p>
                </div>
                <Link
                  to="/ops#grading-candidate-ops"
                  className="rounded-xl border border-amber-300/35 px-4 py-2 text-xs font-semibold text-amber-100 transition hover:border-amber-200/60 hover:bg-white/5"
                >
                  Ops grading table
                </Link>
              </div>
              {gradingDashLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading grading candidate rollup…</p>
              ) : gradingDashError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{gradingDashError}</StatusBanner>
                </div>
              ) : gradingDashSummary ? (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                  <StatCard label="Total candidates" value={String(gradingDashSummary.total_candidates)} />
                  <StatCard label="Pipeline active" value={String(gradingDashSummary.pipeline_active_count)} />
                  <StatCard label="Ready for submission" value={String(gradingDashSummary.ready_for_submission_count)} />
                  <StatCard label="Submitted" value={String(gradingDashSummary.submitted_count)} />
                  <StatCard label="Graded" value={String(gradingDashSummary.graded_count)} />
                  <StatCard label="Elite priority" value={String(gradingDashSummary.elite_priority_count)} />
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-500">Grading rollup unavailable.</p>
              )}
            </section>
          ) : null}

          {user && loadsGradingData ? (
            <section
              id="grading-spreads-dash"
              className="mt-6 rounded-3xl border border-violet-400/35 bg-white ring-1 ring-violet-100 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-violet-800">Grading economics</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">P37 raw-vs-graded spread engine</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Deterministic spread checks compare raw FMV, graded FMV, grading cost assumptions, and liquidity
                    weighting. No prediction, recommendation, or scan AI enters this lane.
                  </p>
                </div>
                <Link
                  to="/ops#grading-spread-ops"
                  className="rounded-xl border border-violet-300/35 px-4 py-2 text-xs font-semibold text-violet-100 transition hover:border-violet-200/60 hover:bg-white/5"
                >
                  Ops spread table
                </Link>
              </div>
              {gradingSpreadLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading grading spread rollup…</p>
              ) : gradingSpreadError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{gradingSpreadError}</StatusBanner>
                </div>
              ) : gradingSpreadSummary ? (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                  <StatCard label="Strong spreads" value={String(gradingSpreadSummary.strong_spread_count)} />
                  <StatCard label="Elite spreads" value={String(gradingSpreadSummary.elite_spread_count)} />
                  <StatCard label="Negative spreads" value={String(gradingSpreadSummary.negative_spread_count)} />
                  <StatCard
                    label="Average upside"
                    value={gradingSpreadSummary.average_estimated_upside ?? "—"}
                  />
                  <StatCard
                    label="Liquidity-adjusted total"
                    value={gradingSpreadSummary.liquidity_adjusted_upside_total ?? "—"}
                  />
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-500">Grading spread rollup unavailable.</p>
              )}
            </section>
          ) : null}

          {user && loadsGradingData ? (
            <section
              id="grading-roi-dash"
              className="mt-6 rounded-3xl border border-emerald-400/35 bg-white ring-1 ring-emerald-100 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-800">Grading economics</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">P37 grading ROI engine</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Deterministic ROI snapshots combine grading fees, shipping, insurance, liquidity weighting, and
                    realized-sale evidence. The lane stays explainable and mutation-free.
                  </p>
                </div>
                <Link
                  to="/ops#grading-roi-ops"
                  className="rounded-xl border border-emerald-300/35 px-4 py-2 text-xs font-semibold text-emerald-100 transition hover:border-emerald-200/60 hover:bg-white/5"
                >
                  Ops ROI table
                </Link>
              </div>
              {gradingRoiLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading grading ROI rollup…</p>
              ) : gradingRoiError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{gradingRoiError}</StatusBanner>
                </div>
              ) : gradingRoiSummary ? (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                  <StatCard label="Strong ROI" value={String(gradingRoiSummary.strong_roi_count)} />
                  <StatCard label="Elite ROI" value={String(gradingRoiSummary.elite_roi_count)} />
                  <StatCard label="Negative ROI" value={String(gradingRoiSummary.negative_roi_count)} />
                  <StatCard label="Average ROI" value={gradingRoiSummary.average_estimated_roi ?? "—"} />
                  <StatCard
                    label="Liquidity-adjusted total"
                    value={gradingRoiSummary.liquidity_adjusted_roi_total ?? "—"}
                  />
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-500">Grading ROI rollup unavailable.</p>
              )}
            </section>
          ) : null}

          {user && loadsGradingData ? (
            <section
              id="grading-submission-dash"
              className="mt-6 rounded-3xl border border-sky-400/35 bg-white ring-1 ring-sky-100 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-800">Submission workflow</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">P37 submission batch operations</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Deterministic submission batches track grading groups, shipment states, lifecycle milestones, and
                    estimated turnaround without any carrier or grader integrations.
                  </p>
                </div>
                <Link
                  to="/ops#grading-submission-ops"
                  className="rounded-xl border border-sky-300/35 px-4 py-2 text-xs font-semibold text-sky-100 transition hover:border-sky-200/60 hover:bg-white/5"
                >
                  Ops batches
                </Link>
              </div>
              {gradingSubmissionLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading grading submissions…</p>
              ) : gradingSubmissionError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{gradingSubmissionError}</StatusBanner>
                </div>
              ) : gradingSubmissionSummary ? (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                  <StatCard label="Active batches" value={String(gradingSubmissionSummary.active_batch_count)} />
                  <StatCard label="Shipped batches" value={String(gradingSubmissionSummary.shipped_batch_count)} />
                  <StatCard label="Grading batches" value={String(gradingSubmissionSummary.grading_batch_count)} />
                  <StatCard label="Completed batches" value={String(gradingSubmissionSummary.completed_batch_count)} />
                  <StatCard
                    label="Avg turnaround"
                    value={gradingSubmissionSummary.average_turnaround_days ?? "—"}
                  />
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-500">Grading submission rollup unavailable.</p>
              )}
            </section>
          ) : null}

          {user && loadsGradingData ? (
            <section
              id="grading-reconciliation-dash"
              className="mt-6 rounded-3xl border border-cyan-400/35 bg-white ring-1 ring-cyan-100 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-blue-800">Result reconciliation</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">P37 grading outcome reconciliation</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Actual returned grades, ROI deltas, and grader performance snapshots without changing FMV,
                    pricing, or inventory automatically.
                  </p>
                </div>
                <Link
                  to="/ops#grading-reconciliation-ops"
                  className="rounded-xl border border-cyan-300/35 px-4 py-2 text-xs font-semibold text-blue-800 transition hover:border-cyan-200/60 hover:bg-white/5"
                >
                  Ops reconciliation
                </Link>
              </div>
              {gradingReconciliationLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading grading reconciliation…</p>
              ) : gradingReconciliationError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{gradingReconciliationError}</StatusBanner>
                </div>
              ) : gradingReconciliationSummary ? (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <StatCard label="Reconciled" value={String(gradingReconciliationSummary.reconciled_count)} />
                    <StatCard
                      label="Above expectation"
                      value={String(gradingReconciliationSummary.above_expectation_count)}
                    />
                    <StatCard
                      label="Below expectation"
                      value={String(gradingReconciliationSummary.below_expectation_count)}
                    />
                    <StatCard label="Average ROI delta" value={gradingReconciliationSummary.average_roi_delta ?? "—"} />
                  </div>
                  <div className="mt-4 grid gap-3 lg:grid-cols-3">
                    {gradingReconciliationSummary.grader_performance.length === 0 ? (
                      <p className="text-sm text-slate-500">No grader performance snapshots yet.</p>
                    ) : (
                      gradingReconciliationSummary.grader_performance.map((row) => (
                        <div key={`${row.grader}-${row.snapshot_date}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                          <p className="text-sm font-semibold text-patriot-navy">{row.grader}</p>
                          <p className="mt-1 text-xs text-slate-600">
                            submissions {row.submission_count} · ROI delta {row.average_roi_delta ?? "—"}
                          </p>
                          <p className="mt-1 text-[11px] text-slate-500">
                            above {row.above_expectation_count} · met {row.met_expectation_count} · below{" "}
                            {row.below_expectation_count}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                </>
              ) : (
                <p className="mt-4 text-sm text-slate-500">Grading reconciliation rollup unavailable.</p>
              )}
            </section>
          ) : null}

          {user && loadsGradingData ? (
            <section
              id="grading-recommendation-dash"
              className="mt-6 rounded-3xl border border-fuchsia-400/35 bg-white ring-1 ring-fuchsia-100 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-fuchsia-800">Recommendation engine</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">P37 grading decision support</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Explainable grading recommendations built from ROI, spread, liquidity, reconciliation, grader
                    performance, and listing-intelligence evidence.
                  </p>
                </div>
                <Link
                  to="/ops#grading-recommendation-ops"
                  className="rounded-xl border border-fuchsia-300/35 px-4 py-2 text-xs font-semibold text-fuchsia-100 transition hover:border-fuchsia-200/60 hover:bg-white/5"
                >
                  Ops recommendations
                </Link>
              </div>
              {gradingRecommendationLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading grading recommendations…</p>
              ) : gradingRecommendationError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{gradingRecommendationError}</StatusBanner>
                </div>
              ) : gradingRecommendationSummary ? (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                  <StatCard
                    label="Grade recommendations"
                    value={String(gradingRecommendationSummary.grade_recommendation_count)}
                  />
                  <StatCard label="Hold raw" value={String(gradingRecommendationSummary.hold_raw_count)} />
                  <StatCard
                    label="Elite opportunities"
                    value={String(gradingRecommendationSummary.elite_opportunity_count)}
                  />
                  <StatCard label="High risk" value={String(gradingRecommendationSummary.high_risk_count)} />
                  <StatCard
                    label="Average expected ROI"
                    value={gradingRecommendationSummary.average_expected_roi ?? "—"}
                  />
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-500">Grading recommendation rollup unavailable.</p>
              )}
            </section>
          ) : null}

          {loadsDealerData ? (
          <>
          <section
            id="portfolio-strategy-dashboard-dash"
            className="mt-6 rounded-3xl border border-emerald-400/35 bg-white ring-1 ring-emerald-100 p-5 shadow-xl shadow-black/18"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-800">Portfolio strategy dashboard</p>
                <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Unified strategic portfolio command center</h2>
                <p className="mt-1 max-w-3xl text-sm text-slate-600">
                  Dealer-grade portfolio cockpit consolidating exposure, duplicates, liquidity, hold/sell posture,
                  concentration risk, and acquisition gaps into one deterministic strategic readout.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void refreshPortfolioStrategyDashboard()}
                  disabled={strategyGenBusy}
                  className="rounded-xl border border-emerald-400/45 bg-emerald-500/10 px-4 py-2 text-xs font-semibold text-emerald-50 transition hover:bg-emerald-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {strategyGenBusy ? "Generating…" : "Generate strategy dashboard"}
                </button>
                <Link
                  to="/ops#portfolio-strategy-dashboard-ops"
                  className="rounded-xl border border-white/15 px-4 py-2 text-xs font-semibold text-slate-100 transition hover:border-emerald-300/45 hover:bg-white/5"
                >
                  Ops strategy tables
                </Link>
              </div>
            </div>
            {strategyDashLoading ? (
              <p className="mt-4 text-sm text-slate-600">Loading strategy dashboard…</p>
            ) : strategyDashResp?.snapshot ? (
              <>
                {strategyDashError ? (
                  <div className="mt-4">
                    <StatusBanner tone="warning">{strategyDashError}</StatusBanner>
                  </div>
                ) : null}
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                  <StatCard label="Portfolios" value={String(strategyDashResp.snapshot.portfolio_count)} />
                  <StatCard label="Total value" value={formatMaybeCurrency(strategyDashResp.snapshot.total_portfolio_value)} />
                  <StatCard label="Cost basis" value={formatMaybeCurrency(strategyDashResp.snapshot.total_cost_basis)} />
                  <StatCard label="Realized sales" value={formatMaybeCurrency(strategyDashResp.snapshot.total_realized_sales)} />
                  <StatCard label="Diversification" value={strategyDashResp.snapshot.diversification_score ?? "—"} />
                </div>
                <div className="mt-4 grid gap-4 xl:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Exposure & diversification</p>
                    <div className="mt-3 grid gap-3 sm:grid-cols-3">
                      <StatCard label="Overexposed categories" value={String(strategyDashResp.snapshot.overexposed_category_count)} />
                      <StatCard label="Concentration score" value={strategyDashResp.snapshot.concentration_risk_score ?? "—"} />
                      <StatCard
                        label="Critical alerts"
                        value={String(strategyAlerts.filter((row) => row.alert_type === "CONCENTRATION_CRITICAL").length)}
                      />
                    </div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Liquidity & capital efficiency</p>
                    <div className="mt-3 grid gap-3 sm:grid-cols-4">
                      <StatCard label="Liquidity efficiency" value={strategyDashResp.snapshot.liquidity_efficiency_score ?? "—"} />
                      <StatCard label="Dead capital" value={formatMaybeCurrency(strategyDashResp.snapshot.dead_capital_estimate)} />
                      <StatCard label="Liquid %" value={strategyDashResp.snapshot.liquid_inventory_percentage ?? "—"} />
                      <StatCard label="Illiquid %" value={strategyDashResp.snapshot.illiquid_inventory_percentage ?? "—"} />
                    </div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Duplicate & consolidation</p>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <StatCard label="Duplicate clusters" value={String(strategyDashResp.snapshot.duplicate_cluster_count)} />
                      <StatCard
                        label="Warning clusters"
                        value={strategyMetricMap.get("duplicate_warning_clusters")?.metric_value_decimal ?? "0"}
                      />
                    </div>
                    <div className="mt-3 space-y-2 text-xs text-slate-700">
                      {strategyDuplicateClusters.length ? (
                        strategyDuplicateClusters.slice(0, 3).map((row) => (
                          <div key={String(row.cluster_id ?? row.cluster_key)} className="rounded-xl border border-slate-200 px-3 py-2">
                            <p className="font-semibold text-slate-900">{String(row.cluster_key ?? "cluster")}</p>
                            <p className="text-[11px] text-slate-600">
                              {String(row.duplication_status ?? "UNKNOWN")} · items {String(row.total_item_count ?? "—")} · FMV{" "}
                              {formatMaybeCurrency(String(row.total_fmv_amount ?? ""))}
                            </p>
                          </div>
                        ))
                      ) : (
                        <p className="text-slate-500">No duplicate consolidation hotspots recorded.</p>
                      )}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Hold / sell intelligence</p>
                    <div className="mt-3 grid gap-3 sm:grid-cols-4">
                      <StatCard label="HOLD" value={String(strategyDashResp.snapshot.hold_recommendation_count)} />
                      <StatCard label="SELL" value={String(strategyDashResp.snapshot.sell_recommendation_count)} />
                      <StatCard label="Reduce exposure" value={String(strategyDashResp.snapshot.reduce_exposure_count)} />
                      <StatCard label="Capital release" value={formatMaybeCurrency(strategyMetricMap.get("capital_release_estimate")?.metric_value_decimal)} />
                    </div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Acquisition intelligence</p>
                    <div className="mt-3 grid gap-3 sm:grid-cols-4">
                      <StatCard label="Opportunities" value={String(strategyDashResp.snapshot.acquisition_opportunity_count)} />
                      <StatCard label="Elite" value={String(strategyDashResp.snapshot.elite_acquisition_count)} />
                      <StatCard
                        label="Diversification"
                        value={strategyMetricMap.get("diversification_acquisitions")?.metric_value_decimal ?? "0"}
                      />
                      <StatCard
                        label="Liquidity-improvement"
                        value={strategyMetricMap.get("liquidity_improvement_acquisitions")?.metric_value_decimal ?? "0"}
                      />
                    </div>
                    <div className="mt-3 space-y-2 text-xs text-slate-700">
                      {strategyAcquisitionFocusRows.length ? (
                        strategyAcquisitionFocusRows.slice(0, 3).map((row) => (
                          <div key={String(row.snapshot_id ?? row.issue_id)} className="rounded-xl border border-slate-200 px-3 py-2">
                            <p className="font-semibold text-slate-900">
                              {String(row.acquisition_category ?? "Opportunity")} · {String(row.acquisition_priority ?? "—")}
                            </p>
                            <p className="text-[11px] text-slate-600">
                              issue {String(row.issue_id ?? "gap")} · diversification {String(row.diversification_impact ?? "—")}
                              {" · "}liquidity {String(row.liquidity_impact ?? "—")}
                            </p>
                          </div>
                        ))
                      ) : (
                        <p className="text-slate-500">No strategic acquisition gap rows recorded yet.</p>
                      )}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Strategic alerts</p>
                    <div className="mt-3 space-y-2 text-xs text-slate-200">
                      {strategyAlerts.length ? (
                        strategyAlerts.slice(0, 5).map((row) => (
                          <div key={row.alert_replay_key} className="rounded-xl border border-slate-200 px-3 py-2">
                            <p className="font-semibold text-slate-900">
                              {row.alert_type} · <span className="text-slate-700">{row.severity}</span>
                            </p>
                            <p className="mt-1 text-[11px] text-slate-600">{row.message}</p>
                          </div>
                        ))
                      ) : (
                        <p className="text-slate-500">No strategy alerts have been persisted yet.</p>
                      )}
                    </div>
                  </div>
                </div>
                <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Strategic feed</p>
                  <div className="mt-3 space-y-2 text-xs text-slate-200">
                    {strategyFeed.length ? (
                      strategyFeed.slice(0, 8).map((row) => (
                        <div key={row.deterministic_key} className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-slate-200 px-3 py-2">
                          <div>
                            <p className="font-semibold text-slate-900">{row.event_type}</p>
                            <p className="mt-1 text-[11px] text-slate-600">{row.summary}</p>
                          </div>
                          <span className="text-[10px] text-slate-500">{formatDate(row.created_at)}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-slate-500">No strategy feed events yet.</p>
                    )}
                  </div>
                </div>
              </>
            ) : strategyDashError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{strategyDashError}</StatusBanner>
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">Generate a strategy snapshot to populate the strategic cockpit.</p>
            )}
          </section>

          <section
            id="acquisition-priority-dash"
            className="mt-6 rounded-3xl border border-sky-400/35 bg-white ring-1 ring-sky-100 p-5 shadow-xl shadow-black/18"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-800">Acquisition intelligence</p>
                <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Deterministic expansion and gap-analysis layer</h2>
                <p className="mt-1 max-w-3xl text-sm text-slate-600">
                  Explainable acquisition priorities that highlight diversification, liquidity, grading upside, sales velocity,
                  and low-overlap growth opportunities without any autonomous buying or predictive market timing.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void refreshAcquisitionPriorities()}
                  disabled={acquisitionPriorityGenBusy}
                  className="rounded-xl border border-sky-400/45 bg-sky-500/10 px-4 py-2 text-xs font-semibold text-sky-50 transition hover:bg-sky-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {acquisitionPriorityGenBusy ? "Generating…" : "Generate acquisition priorities"}
                </button>
                <Link
                  to="/ops#acquisition-priority-ops"
                  className="rounded-xl border border-white/15 px-4 py-2 text-xs font-semibold text-slate-100 transition hover:border-sky-300/45 hover:bg-white/5"
                >
                  Ops acquisition tables
                </Link>
              </div>
            </div>
            {acquisitionPriorityLoading ? (
              <p className="mt-4 text-sm text-slate-600">Loading acquisition priorities…</p>
            ) : acquisitionPriorityError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{acquisitionPriorityError}</StatusBanner>
              </div>
            ) : acquisitionPriorityList ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="High-priority acquisitions" value={String(acquisitionPrioritySummary.highPriority)} />
                <StatCard label="Elite opportunities" value={String(acquisitionPrioritySummary.eliteOpportunities)} />
                <StatCard
                  label="Diversification opportunities"
                  value={String(acquisitionPrioritySummary.diversificationOpportunities)}
                />
                <StatCard
                  label="Liquidity-improvement opportunities"
                  value={String(acquisitionPrioritySummary.liquidityImprovementOpportunities)}
                />
                <StatCard label="Grading opportunities" value={String(acquisitionPrioritySummary.gradingOpportunityCount)} />
                <StatCard label="Total modeled rows" value={String(acquisitionPrioritySummary.total)} />
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">Generate acquisition rows to populate this panel.</p>
            )}
          </section>

          <section
            id="portfolio-recommendation-dash"
            className="mt-6 rounded-3xl border border-amber-400/35 bg-white ring-1 ring-amber-100 p-5 shadow-xl shadow-black/18"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-900">Hold / sell intelligence</p>
                <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Deterministic strategic recommendation layer</h2>
                <p className="mt-1 max-w-3xl text-sm text-slate-600">
                  Explainable HOLD, SELL, REDUCE_EXPOSURE, GRADE_THEN_SELL, CONSOLIDATE, and WATCH signals built from
                  liquidity, exposure, duplicates, grading economics, sales history, listing activity, and risk evidence.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void refreshPortfolioRecommendations()}
                  disabled={portfolioRecommendationGenBusy}
                  className="rounded-xl border border-amber-400/45 bg-amber-500/10 px-4 py-2 text-xs font-semibold text-amber-50 transition hover:bg-amber-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {portfolioRecommendationGenBusy ? "Generating…" : "Generate recommendations"}
                </button>
                <Link
                  to="/ops#portfolio-recommendation-ops"
                  className="rounded-xl border border-white/15 px-4 py-2 text-xs font-semibold text-slate-100 transition hover:border-amber-300/45 hover:bg-white/5"
                >
                  Ops recommendation tables
                </Link>
              </div>
            </div>
            {portfolioRecommendationLoading ? (
              <p className="mt-4 text-sm text-slate-600">Loading portfolio recommendations…</p>
            ) : portfolioRecommendationError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{portfolioRecommendationError}</StatusBanner>
              </div>
            ) : portfolioRecommendationList ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="HOLD" value={String(portfolioRecommendationSummary.holdCount)} />
                <StatCard label="SELL" value={String(portfolioRecommendationSummary.sellCount)} />
                <StatCard label="REDUCE_EXPOSURE" value={String(portfolioRecommendationSummary.reduceExposureCount)} />
                <StatCard label="GRADE_THEN_SELL" value={String(portfolioRecommendationSummary.gradeThenSellCount)} />
                <StatCard label="CONSOLIDATE" value={String(portfolioRecommendationSummary.consolidateCount)} />
                <StatCard label="WATCH" value={String(portfolioRecommendationSummary.watchCount)} />
                <StatCard
                  label="Estimated capital release"
                  value={formatUsdCurrency(String(portfolioRecommendationSummary.estimatedCapitalRelease))}
                />
                <StatCard
                  label="Efficiency opportunities"
                  value={formatUsdCurrency(String(portfolioRecommendationSummary.estimatedPortfolioEfficiencyGain))}
                />
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">Generate recommendation rows to populate this panel.</p>
            )}
          </section>

          <section
            id="concentration-risk-dash"
            className="mt-6 rounded-3xl border border-fuchsia-400/35 bg-white ring-1 ring-fuchsia-100 p-5 shadow-xl shadow-black/18"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-fuchsia-800">Concentration intelligence</p>
                <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Deterministic concentration-risk layer</h2>
                <p className="mt-1 max-w-3xl text-sm text-slate-600">
                  Explicit portfolio concentration modeling across publishers, titles, eras, grading posture, liquidity posture,
                  variant families, and acquisition channels. Scores remain replay-safe and fully formula-driven.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void refreshConcentrationRisk()}
                  disabled={concentrationRiskGenBusy}
                  className="rounded-xl border border-fuchsia-400/45 bg-fuchsia-500/10 px-4 py-2 text-xs font-semibold text-fuchsia-50 transition hover:bg-fuchsia-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {concentrationRiskGenBusy ? "Generating…" : "Generate concentration risk"}
                </button>
                <Link
                  to="/ops#concentration-risk-ops"
                  className="rounded-xl border border-white/15 px-4 py-2 text-xs font-semibold text-slate-100 transition hover:border-fuchsia-300/45 hover:bg-white/5"
                >
                  Ops concentration tables
                </Link>
              </div>
            </div>
            {concentrationRiskLoading ? (
              <p className="mt-4 text-sm text-slate-600">Loading concentration risk…</p>
            ) : concentrationRiskError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{concentrationRiskError}</StatusBanner>
              </div>
            ) : concentrationRiskList ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="Concentrated+" value={String(concentrationRiskSummary.concentratedCount)} />
                <StatCard label="Critical rows" value={String(concentrationRiskSummary.criticalCount)} />
                <StatCard
                  label="Avg diversification"
                  value={concentrationRiskSummary.total ? concentrationRiskSummary.avgDiversificationScore.toFixed(2) : "0.00"}
                />
                <StatCard label="High liquidity fragility" value={String(concentrationRiskSummary.highLiquidityFragilityCount)} />
                <StatCard label="Non-healthy posture warnings" value={String(concentrationRiskSummary.duplicateWarningCount)} />
                <StatCard label="Total modeled rows" value={String(concentrationRiskSummary.total)} />
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">Generate concentration rows to populate this panel.</p>
            )}
          </section>
          </>
          ) : null}

          {user && loadsGradingData ? (
            <section
              id="grading-risk-dash"
              className="mt-6 rounded-3xl border border-rose-400/35 bg-white ring-1 ring-rose-100 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-rose-800">Risk and confidence</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">P37 grading uncertainty layer</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Deterministic risk and confidence snapshots explaining where grading economics are stable, thin,
                    or too volatile to trust fully.
                  </p>
                </div>
                <Link
                  to="/ops#grading-risk-ops"
                  className="rounded-xl border border-rose-300/35 px-4 py-2 text-xs font-semibold text-rose-100 transition hover:border-rose-200/60 hover:bg-white/5"
                >
                  Ops risk view
                </Link>
              </div>
              {gradingRiskLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading grading risk snapshots…</p>
              ) : gradingRiskError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{gradingRiskError}</StatusBanner>
                </div>
              ) : gradingRiskSummary ? (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                  <StatCard label="Low risk candidates" value={String(gradingRiskSummary.low_risk_count)} />
                  <StatCard label="High risk candidates" value={String(gradingRiskSummary.high_risk_count)} />
                  <StatCard label="High confidence" value={String(gradingRiskSummary.high_confidence_count)} />
                  <StatCard label="Low confidence" value={String(gradingRiskSummary.low_confidence_count)} />
                  <StatCard
                    label="Average risk-adjusted ROI"
                    value={gradingRiskSummary.average_risk_adjusted_roi ?? "—"}
                  />
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-500">Grading risk rollup unavailable.</p>
              )}
            </section>
          ) : null}

          {user && loadsDealerData ? (
            <section
              id="operational-reporting-dash"
              className="mt-6 rounded-3xl border border-sky-400/30 bg-white p-5 shadow-xl shadow-slate-200/60"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-800">Operational reporting</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">P36 closeout CSV registry</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Deterministic, checksum-backed summaries across listings, liquidity, conventions, exporters, ledger sales,
                    dealer snapshots, and inventory health signals. Replay keys keep generation idempotent — no corrective writes,
                    forecasting, or notification fan-out on this lane.
                  </p>
                </div>
                <div className="flex flex-wrap items-end gap-2">
                  <button
                    type="button"
                    onClick={() => void generateQuickListingOperationalReport()}
                    disabled={opReportBusy}
                    className="rounded-xl border border-sky-400/45 bg-sky-500/12 px-4 py-2 text-xs font-semibold text-sky-100 transition hover:bg-sky-400/18 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {opReportBusy ? "Generating…" : "Generate listing summary CSV"}
                  </button>
                  <Link
                    to="/ops#operational-reporting-ops"
                    className="rounded-xl border border-white/15 px-4 py-2 text-xs font-semibold text-slate-100 transition hover:border-sky-300/55 hover:bg-white/5"
                  >
                    Ops reporting table
                  </Link>
                </div>
              </div>

              {opReportRollupsLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading operational report fingerprints…</p>
              ) : opReportRollupsError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{opReportRollupsError}</StatusBanner>
                </div>
              ) : (
                <div className="mt-5 grid gap-4 xl:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Recent runs (14d)</p>
                    {opReportRollups && opReportRollups.recent_runs.length > 0 ? (
                      <ul className="mt-3 space-y-2 text-xs text-slate-200">
                        {opReportRollups.recent_runs.map((run) => (
                          <li key={run.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2">
                            <div>
                              <p className="font-semibold text-slate-900">{run.report_type}</p>
                              <p className="font-mono text-[10px] text-slate-500">
                                #{run.id} · {run.status} · rows {run.csv_row_count}
                              </p>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <span className="rounded-full border border-white/15 px-2 py-1 text-[10px] text-slate-700">
                                {shortenChecksum(run.checksum)}
                              </span>
                              {run.status === "COMPLETED" ? (
                                <button
                                  type="button"
                                  className="rounded-full border border-sky-300/55 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-sky-100"
                                  onClick={() => void downloadOperationalReportCsvClient(run.id)}
                                >
                                  Download CSV
                                </button>
                              ) : null}
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-3 text-sm text-slate-500">No report runs logged in the trailing window.</p>
                    )}
                  </div>

                  <div className="rounded-2xl border border-rose-400/35 bg-white ring-1 ring-rose-100 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-rose-800">Failed reports</p>
                    {opReportRollups && opReportRollups.failed_runs.length > 0 ? (
                      <ul className="mt-3 space-y-2 text-xs text-rose-100">
                        {opReportRollups.failed_runs.map((run) => (
                          <li key={run.id} className="border-b border-slate-200 pb-2">
                            <p className="font-semibold">{run.report_type}</p>
                            <p className="font-mono text-[10px] text-rose-200/80">
                              #{run.id} · {(run.failure_reason ?? "UNKNOWN").slice(0, 120)}
                            </p>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-3 text-sm text-rose-200/70">No failed generations on record.</p>
                    )}
                  </div>
                </div>
              )}
            </section>
          ) : null}

          {listingRegistrySummaryLoading ||
          listingRegistrySummaryError ||
          listingRegistrySummary ? (
            <section
              id="listing-registry-dash"
              className="mt-6 rounded-3xl border border-amber-400/25 bg-white ring-1 ring-amber-100 p-5 shadow-xl shadow-slate-200/50"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-900">Listing registry</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Canonical listing truth (manual + exports)</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Read-only workbook snapshot: draft/ready roll-up, live and sold counts, and the most recent lifecycle audit
                    spine. No marketplace posting, auto pricing, or inventory decrements on this path.
                  </p>
                </div>
                <Link
                  to="/ops#listing-registry-ops"
                  className="rounded-full border border-amber-400/35 px-3 py-1.5 text-xs font-semibold text-amber-100 transition hover:border-amber-300/60 hover:bg-amber-500/10"
                >
                  Ops listing explorer
                </Link>
              </div>
              {listingRegistrySummaryLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading listing registry summary…</p>
              ) : listingRegistrySummaryError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{listingRegistrySummaryError}</StatusBanner>
                </div>
              ) : listingRegistrySummary ? (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <StatCard label="Draft + ready listings" value={String(listingRegistrySummary.draft_count)} />
                    <StatCard label="Active listings" value={String(listingRegistrySummary.active_count)} />
                    <StatCard label="Sold listings (ledger)" value={String(listingRegistrySummary.sold_count)} />
                    <StatCard label="Recent audit events shown" value={String(listingRegistrySummary.recent_events.length)} />
                  </div>
                  <div className="mt-4 overflow-auto rounded-2xl border border-slate-200 bg-slate-50">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Listing</th>
                          <th className="p-3 font-medium">Event</th>
                          <th className="p-3 font-medium">Statuses</th>
                          <th className="p-3 font-medium">Recorded</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 text-slate-800">
                        {listingRegistrySummary.recent_events.slice(0, 6).map((evt) => (
                          <tr key={evt.id}>
                            <td className="p-3 font-mono text-[11px] text-slate-700">#{evt.listing_id}</td>
                            <td className="p-3">{evt.event_type.replace(/_/g, " ")}</td>
                            <td className="p-3 text-slate-600">
                              {(evt.prior_status ?? "—")} → {(evt.new_status ?? "—")}
                            </td>
                            <td className="p-3 text-slate-600">{formatDateTime(evt.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : null}
            </section>
          ) : null}

          {listingIntelligenceSummaryLoading ||
          listingIntelligenceSummaryError ||
          listingIntelligenceSummary ? (
            <section
              id="listing-intelligence-dash"
              className="mt-6 rounded-3xl border border-fuchsia-400/25 bg-white ring-1 ring-fuchsia-100 p-5 shadow-xl shadow-slate-200/50"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-fuchsia-800">Listing intelligence</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Completeness, export readiness, and cleanup signals</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Deterministic analysis only: listing quality, missing fields, stale-risk flags, and channel performance
                    rollups. No recommendations, repricing, or hidden mutation.
                  </p>
                </div>
                <Link
                  to="/ops#listing-intelligence-ops"
                  className="rounded-full border border-fuchsia-400/35 px-3 py-1.5 text-xs font-semibold text-fuchsia-100 transition hover:border-fuchsia-300/60 hover:bg-fuchsia-500/10"
                >
                  Ops intelligence explorer
                </Link>
              </div>
              {listingIntelligenceSummaryLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading listing intelligence summary…</p>
              ) : listingIntelligenceSummaryError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{listingIntelligenceSummaryError}</StatusBanner>
                </div>
              ) : listingIntelligenceSummary ? (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                    <StatCard label="Strong listings" value={String(listingIntelligenceSummary.strong_listing_count)} />
                    <StatCard label="Incomplete listings" value={String(listingIntelligenceSummary.incomplete_listing_count)} />
                    <StatCard
                      label="Average completeness"
                      value={
                        listingIntelligenceSummary.average_completeness_score ?? "—"
                      }
                    />
                    <StatCard label="Export-ready listings" value={String(listingIntelligenceSummary.export_ready_count)} />
                    <StatCard label="Stale-risk listings" value={String(listingIntelligenceSummary.stale_risk_count)} />
                  </div>
                  <div className="mt-4 overflow-auto rounded-2xl border border-slate-200 bg-slate-50">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Listing</th>
                          <th className="p-3 font-medium">Status</th>
                          <th className="p-3 font-medium">Score</th>
                          <th className="p-3 font-medium">Missing fields</th>
                          <th className="p-3 font-medium">Stale-risk</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 text-slate-800">
                        {listingIntelligenceSummary.recent_weak_or_incomplete.length === 0 ? (
                          <tr>
                            <td className="p-3 text-slate-600" colSpan={5}>
                              No weak or incomplete listings were found in the latest intelligence snapshot.
                            </td>
                          </tr>
                        ) : (
                          listingIntelligenceSummary.recent_weak_or_incomplete.slice(0, 6).map((row) => (
                            <tr key={row.id}>
                              <td className="p-3 font-mono text-[11px] text-slate-700">#{row.listing_id}</td>
                              <td className="p-3">{row.intelligence_status}</td>
                              <td className="p-3 text-slate-700">{row.completeness_score}</td>
                              <td className="p-3 text-slate-600">
                                {row.missing_required_fields_json.length > 0
                                  ? row.missing_required_fields_json.join(", ")
                                  : "—"}
                              </td>
                              <td className="p-3 text-slate-600">{row.stale_risk_flag ? "Yes" : "No"}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : null}
            </section>
          ) : null}

          {liquiditySummaryLoading || liquiditySummaryError || liquiditySummary ? (
            <section
              id="liquidity-dash"
              className="mt-6 rounded-3xl border border-sky-400/25 bg-white ring-1 ring-sky-100 p-5 shadow-xl shadow-slate-200/50"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-800">Liquidity engine</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Evidence-backed inventory liquidity snapshot</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Deterministic snapshots derived from listing velocity, stale thresholds, and actual sales. This panel is
                    descriptive only and never reprices, predicts, or auto-closes inventory.
                  </p>
                </div>
                <Link
                  to="/ops#liquidity-ops"
                  className="rounded-full border border-sky-400/35 px-3 py-1.5 text-xs font-semibold text-sky-100 transition hover:border-sky-300/60 hover:bg-sky-500/10"
                >
                  Open ops liquidity
                </Link>
              </div>
              {liquiditySummaryLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading liquidity summary…</p>
              ) : liquiditySummaryError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{liquiditySummaryError}</StatusBanner>
                </div>
              ) : liquiditySummary ? (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <StatCard label="High liquidity snapshots" value={String(liquiditySummary.high_liquidity_count)} />
                    <StatCard label="Stale inventory snapshots" value={String(liquiditySummary.stale_inventory_count)} />
                    <StatCard
                      label="Median days to sale"
                      value={liquiditySummary.median_days_to_sale ? `${liquiditySummary.median_days_to_sale} days` : "—"}
                    />
                    <StatCard label="Sell-through %" value={`${liquiditySummary.sell_through_pct}%`} />
                  </div>
                  <div className="mt-4 overflow-auto rounded-2xl border border-slate-200 bg-slate-50">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Event</th>
                          <th className="p-3 font-medium">Threshold</th>
                          <th className="p-3 font-medium">Days active</th>
                          <th className="p-3 font-medium">Listing</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 text-slate-800">
                        {liquiditySummary.recent_stale_events.length === 0 ? (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={4}>
                              No stale events recorded yet.
                            </td>
                          </tr>
                        ) : (
                          liquiditySummary.recent_stale_events.slice(0, 6).map((event) => (
                            <tr key={event.id}>
                              <td className="p-3 text-slate-800">{event.event_type.replace(/_/g, " ")}</td>
                              <td className="p-3 text-slate-700">{event.threshold_days}+ days</td>
                              <td className="p-3 text-slate-700">{event.days_active} days</td>
                              <td className="p-3 font-mono text-[11px] text-slate-700">#{event.listing_id}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : null}
            </section>
          ) : null}

          {conventionSummaryLoading || conventionSummaryError || conventionSummary ? (
            <section
              id="convention-dash"
              className="mt-6 rounded-3xl border border-violet-300/60 bg-white p-5 shadow-xl shadow-slate-200/50 ring-1 ring-violet-100"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-violet-800">Convention ops</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Dealer workflow and show inventory snapshot</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Deterministic convention assignments, movement history, temporary pricing, and active sale sessions.
                    This panel stays operational and never mutates inventory quantities or posts payments.
                  </p>
                </div>
                <Link
                  to="/ops#convention-ops"
                  className="rounded-full border border-violet-400/45 px-3 py-1.5 text-xs font-semibold text-violet-800 transition hover:border-violet-500/60 hover:bg-violet-50"
                >
                  Open ops convention
                </Link>
              </div>
              {conventionSummaryLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading convention summary…</p>
              ) : conventionSummaryError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{conventionSummaryError}</StatusBanner>
                </div>
              ) : conventionSummary ? (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                    <StatCard label="Active conventions" value={String(conventionSummary.active_convention_count)} />
                    <StatCard label="Assigned inventory" value={String(conventionSummary.assigned_inventory_count)} />
                    <StatCard label="Wall books" value={String(conventionSummary.wall_book_count)} />
                    <StatCard label="Showcases" value={String(conventionSummary.showcase_count)} />
                    <StatCard label="Active sale sessions" value={String(conventionSummary.active_sale_session_count)} />
                  </div>
                  <div className="mt-4 overflow-auto rounded-2xl border border-slate-200 bg-slate-50">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Event</th>
                          <th className="p-3 font-medium">Type</th>
                          <th className="p-3 font-medium">Status</th>
                          <th className="p-3 font-medium">Window</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 text-slate-800">
                        {conventionSummary.recent_events.length === 0 ? (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={4}>
                              No convention events recorded yet.
                            </td>
                          </tr>
                        ) : (
                          conventionSummary.recent_events.slice(0, 5).map((event) => (
                            <tr key={event.id}>
                              <td className="p-3 text-slate-800">{event.name}</td>
                              <td className="p-3 text-slate-700">{event.event_type.replace(/_/g, " ")}</td>
                              <td className="p-3 text-slate-700">{event.status}</td>
                              <td className="p-3 text-slate-700">
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
            </section>
          ) : null}

          {salesLedgerSummaryLoading || salesLedgerSummaryError || salesLedgerSummary ? (
            <section
              id="sales-ledger-dash"
              className="mt-6 rounded-3xl border border-emerald-300/60 bg-white p-5 shadow-xl shadow-slate-200/50 ring-1 ring-emerald-100"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-800">Sales ledger</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Realized sale truth and profit snapshot</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Recorded sales only. This ledger captures realized outcomes, linked listing transitions, and stable money
                    math without marketplace posting, inventory decrements, or hidden mutation.
                  </p>
                </div>
                <Link
                  to="/ops#sales-ledger-ops"
                  className="rounded-full border border-emerald-400/45 px-3 py-1.5 text-xs font-semibold text-emerald-800 transition hover:border-emerald-500/60 hover:bg-emerald-50"
                >
                  Open ops sales ledger
                </Link>
              </div>
              {salesLedgerSummaryLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading sales ledger summary…</p>
              ) : salesLedgerSummaryError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{salesLedgerSummaryError}</StatusBanner>
                </div>
              ) : salesLedgerSummary ? (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <StatCard label="Recorded sales" value={String(salesLedgerSummary.completed_sale_count)} />
                    <StatCard label="Gross sales" value={formatUsdCurrency(salesLedgerSummary.gross_sales_total)} />
                    <StatCard label="Net proceeds" value={formatUsdCurrency(salesLedgerSummary.net_proceeds_total)} />
                    <StatCard label="Realized profit" value={formatUsdCurrency(salesLedgerSummary.realized_profit_total)} />
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {salesLedgerSummary.sales_count_by_channel.map((row) => (
                      <span
                        key={row.channel}
                        className="rounded-full border border-emerald-300/50 bg-emerald-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-800"
                      >
                        {row.channel.replace(/_/g, " ")} · {row.count}
                      </span>
                    ))}
                  </div>
                  <div className="mt-4 overflow-auto rounded-2xl border border-slate-200 bg-slate-50">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Sale</th>
                          <th className="p-3 font-medium">Channel</th>
                          <th className="p-3 font-medium">Status</th>
                          <th className="p-3 font-medium">Gross</th>
                          <th className="p-3 font-medium">Net</th>
                          <th className="p-3 font-medium">Profit</th>
                          <th className="p-3 font-medium">Date</th>
                          <th className="p-3 font-medium">Linked listing</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 text-slate-800">
                        {salesLedgerSummary.recent_sales.length === 0 ? (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={8}>
                              No recorded sales yet for this collector.
                            </td>
                          </tr>
                        ) : (
                          salesLedgerSummary.recent_sales.slice(0, 6).map((sale) => (
                            <tr key={sale.id}>
                              <td className="p-3 font-mono text-[11px] text-slate-700">#{sale.id}</td>
                              <td className="p-3 text-slate-800">{sale.channel.replace(/_/g, " ")}</td>
                              <td className="p-3 text-slate-800">{sale.status}</td>
                              <td className="p-3 text-slate-700">{formatUsdCurrency(sale.gross_sale_amount)}</td>
                              <td className="p-3 text-slate-700">{formatUsdCurrency(sale.net_proceeds_amount)}</td>
                              <td className="p-3 text-slate-700">{formatUsdCurrency(sale.realized_profit_amount)}</td>
                              <td className="p-3 text-slate-600">{formatDate(sale.sale_date)}</td>
                              <td className="p-3 text-slate-600">{sale.listing_id ? `#${sale.listing_id}` : "—"}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : null}
            </section>
          ) : null}

          {listingExportDashLoading || listingExportDashError || listingExportDash ? (
            <section
              id="listing-export-dash"
              className="mt-6 rounded-3xl border border-cyan-300/60 bg-white p-5 shadow-xl shadow-slate-200/50 ring-1 ring-cyan-100"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-800">Marketplace exports</p>
                  <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Deterministic CSV ledger (read-only)</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-600">
                    Channel-shaped listing files with checksums and append-only run history. Exports never post to marketplaces,
                    mutate listing status, or touch inventory balances. Bulk multi-select in the SPA is deferred; use the API for
                    batch <span className="font-mono text-[11px] text-blue-800/90">POST /listing-export-runs</span> calls.
                  </p>
                </div>
                <Link
                  to="/ops#listing-export-ops"
                  className="rounded-full border border-cyan-400/35 px-3 py-1.5 text-xs font-semibold text-blue-800 transition hover:border-cyan-300/60 hover:bg-cyan-500/10"
                >
                  Ops export runs
                </Link>
              </div>
              {listingExportDashLoading ? (
                <p className="mt-4 text-sm text-slate-600">Loading marketplace export summary…</p>
              ) : listingExportDashError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{listingExportDashError}</StatusBanner>
                </div>
              ) : listingExportDash ? (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <StatCard label="Completed export runs" value={String(listingExportDash.completed_run_count)} />
                    <StatCard label="Skipped rows (lifetime)" value={String(listingExportDash.skipped_rows_lifetime_sum)} />
                    <StatCard label="Latest completed checksum" value={shortenChecksum(listingExportDash.latest_completed_checksum)} />
                    <StatCard label="Recent runs shown" value={String(listingExportDash.recent_runs.length)} />
                  </div>
                  <div className="mt-4 overflow-auto rounded-2xl border border-slate-200 bg-slate-50">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="p-3 font-medium">Run</th>
                          <th className="p-3 font-medium">Channel</th>
                          <th className="p-3 font-medium">Status</th>
                          <th className="p-3 font-medium">Exported</th>
                          <th className="p-3 font-medium">Skipped</th>
                          <th className="p-3 font-medium">Checksum</th>
                          <th className="p-3 font-medium">Completed</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 text-slate-800">
                        {listingExportDash.recent_runs.length === 0 ? (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={7}>
                              No export attempts recorded yet for this collector.
                            </td>
                          </tr>
                        ) : (
                          listingExportDash.recent_runs.slice(0, 6).map((run) => (
                            <tr key={run.id}>
                              <td className="p-3 font-mono text-[11px] text-slate-700">#{run.id}</td>
                              <td className="p-3 text-slate-800">{run.channel}</td>
                              <td className="p-3 text-slate-800">{run.status}</td>
                              <td className="p-3 text-slate-700">{run.exported_listing_count}</td>
                              <td className="p-3 text-slate-700">{run.skipped_listing_count}</td>
                              <td className="p-3 font-mono text-[10px] text-slate-600">{shortenChecksum(run.checksum)}</td>
                              <td className="p-3 text-slate-600">
                                {run.completed_at ? formatDateTime(run.completed_at) : "—"}
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : null}
            </section>
          ) : null}

      {marketSourcesLoading ||
      marketSourcesError ||
      marketImportRunsLoading ||
      marketImportRunsError ||
      marketSources.length > 0 ||
      marketImportRuns.length > 0 ? (
        <section className="mt-6 rounded-3xl border border-sky-400/25 bg-white ring-1 ring-sky-100 p-5 shadow-xl shadow-slate-200/50">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-800">Market source registry</p>
              <h2 className="mt-1 text-lg font-semibold text-patriot-navy">Registry and import-run summaries</h2>
              <p className="mt-1 max-w-prose text-sm text-slate-600">
                Deterministic source rows and append-only import-run history. The dashboard only reads these records;
                lifecycle changes remain in the ops API.
              </p>
            </div>
          </div>
          {marketSourcesLoading || marketImportRunsLoading ? (
            <p className="mt-4 text-sm text-slate-600">Loading market registry…</p>
          ) : marketSourcesError || marketImportRunsError ? (
            <div className="mt-4 space-y-3">
              {marketSourcesError ? <StatusBanner tone="error">{marketSourcesError}</StatusBanner> : null}
              {marketImportRunsError ? <StatusBanner tone="error">{marketImportRunsError}</StatusBanner> : null}
            </div>
          ) : (
            <div className="mt-5 grid gap-4 xl:grid-cols-2">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Source registry</p>
                {marketSources.length === 0 ? (
                  <p className="mt-3 text-sm text-slate-500">No market sources available yet.</p>
                ) : (
                  <div className="mt-3 overflow-auto">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="pb-2 pr-3 font-medium">Source</th>
                          <th className="pb-2 pr-3 font-medium">Type</th>
                          <th className="pb-2 pr-3 font-medium">Priority</th>
                          <th className="pb-2 font-medium">Enabled</th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-800">
                        {marketSources.slice(0, 8).map((row) => (
                          <tr key={row.id} className="border-t border-slate-200">
                            <td className="py-2 pr-3 font-medium text-slate-900">{row.source_name}</td>
                            <td className="py-2 pr-3 text-slate-700">{row.source_type}</td>
                            <td className="py-2 pr-3 text-slate-700">{row.import_priority}</td>
                            <td className="py-2 text-slate-700">{row.enabled ? "Yes" : "No"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Recent import runs</p>
                {marketImportRuns.length === 0 ? (
                  <p className="mt-3 text-sm text-slate-500">No import runs recorded yet.</p>
                ) : (
                  <div className="mt-3 overflow-auto">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        <tr>
                          <th className="pb-2 pr-3 font-medium">Source</th>
                          <th className="pb-2 pr-3 font-medium">Status</th>
                          <th className="pb-2 pr-3 font-medium">Counts</th>
                          <th className="pb-2 font-medium">Started / updated</th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-800">
                        {marketImportRuns.slice(0, 8).map((row) => (
                          <tr key={row.id} className="border-t border-slate-200">
                            <td className="py-2 pr-3">
                              <div className="text-slate-900">{row.source_name}</div>
                              <div className="mt-1 text-[11px] text-slate-500">#{row.market_source_id}</div>
                            </td>
                            <td className="py-2 pr-3 text-slate-700">{row.status.replace(/_/g, " ")}</td>
                            <td className="py-2 pr-3 text-slate-700">
                              {row.imported_records}/{row.total_records} imported
                            </td>
                            <td className="py-2 text-slate-600">
                              <div>{row.started_at ? formatDateTime(row.started_at) : "Not started"}</div>
                              <div className="mt-1 text-[11px] text-slate-500">{formatDateTime(row.updated_at)}</div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
      ) : null}

        </section>
      ) : null}

      {showCollectionPanels || loadsFullWorkspace ? (
      <>
      {loadsFullWorkspace ? (
      <details className="group mt-6 rounded-3xl border border-slate-200 bg-slate-50 p-4 shadow-inner shadow-black/30 [&>summary::-webkit-details-marker]:hidden">
        <summary className="flex cursor-pointer list-none flex-wrap items-start justify-between gap-3 rounded-2xl border border-transparent p-3 transition hover:border-slate-200 hover:bg-slate-50">
          <div>
            <h2 className="text-sm font-semibold text-patriot-navy">Deterministic exports (CSV / JSON)</h2>
            <p className="mt-1 max-w-xl text-[11px] text-slate-600">
              Read-only snapshots aligned with risk, action center, order/arrival, run gaps, timeline, collection summary,
              and market intelligence (eligible comps, FMV/trend CSVs, inventory FMV subsets, deterministic JSON rollup).
              Filtered exports mirror the workbook controls below when exporting from filtered inventory grids.
            </p>
          </div>
          <span className="rounded-full border border-cyan-400/25 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-blue-800/80">
            Owner scope
          </span>
        </summary>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            className={exportChipClass}
            onClick={() => void runInventoryExport(() => apiClient.downloadOwnerReportsInventoryCsvAll())}
          >
            Inventory CSV (full snapshot)
          </button>
          <button
            type="button"
            className={exportChipClass}
            onClick={() => void runInventoryExport(() => apiClient.downloadOwnerReportsInventoryCsvFiltered(inventoryQuery))}
          >
            Inventory CSV (current filters)
          </button>
          <button
            type="button"
            className={exportChipClass}
            onClick={() => void runInventoryExport(() => apiClient.downloadOwnerReportsInventoryJsonAll())}
          >
            Inventory JSON (full snapshot)
          </button>
          <button
            type="button"
            className={exportChipClass}
            onClick={() =>
              void runInventoryExport(() => apiClient.downloadOwnerReportsInventoryJsonFiltered(inventoryQuery))
            }
          >
            Inventory JSON (current filters)
          </button>
          <button
            type="button"
            className={exportChipClass}
            onClick={() => void runInventoryExport(() => apiClient.downloadOwnerReportsActionCenterCsv())}
          >
            Action center CSV
          </button>
          <button
            type="button"
            className={exportChipClass}
            onClick={() => void runInventoryExport(() => apiClient.downloadOwnerReportsOrderArrivalCsv())}
          >
            Order / arrival CSV
          </button>
          <button
            type="button"
            className={exportChipClass}
            onClick={() => void runInventoryExport(() => apiClient.downloadOwnerReportsRunDetectionCsv())}
          >
            Missing issues CSV
          </button>
          <button
            type="button"
            className={exportChipClass}
            onClick={() => void runInventoryExport(() => apiClient.downloadOwnerReportsTimelineCsv())}
          >
            Timeline CSV
          </button>
          <button
            type="button"
            className={exportChipClass}
            onClick={() => void runInventoryExport(() => apiClient.downloadOwnerReportsMarketDeterministicSummaryJson())}
          >
            Market rollup JSON (summary)
          </button>
          <button
            type="button"
            className={exportChipClass}
            onClick={() => void runInventoryExport(() => apiClient.downloadOwnerReportsMarketEligibleCompsCsv())}
          >
            Market eligible comps CSV
          </button>
          <button
            type="button"
            className={exportChipClass}
            onClick={() =>
              void runInventoryExport(() =>
                apiClient.downloadOwnerReportsPortfolioValueSummaryCsv({
                  publisher: publisher || undefined,
                  ownership_state: ownershipIntelFilter || undefined,
                }),
              )
            }
          >
            Portfolio value summary CSV (filters)
          </button>
          <button
            type="button"
            className={exportChipClass}
            onClick={() => void runInventoryExport(() => apiClient.downloadOwnerReportsCollectionSummaryJson())}
          >
            Collection summary JSON
          </button>
        </div>
      </details>
      ) : null}

      {inventoryRiskSummary ? (
        <section className="mt-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/50">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-patriot-navy">Inventory risk lanes</h2>
              <p className="mt-1 text-sm text-slate-600">
                Attention surface derived deterministically from conflicts, canonical reviews, scans/OCR, preorder gaps,
                duplicate uncertainty, and run gaps — no pricing or automated fixes.
              </p>
            </div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
              As of {inventoryRiskSummary.generated_as_of_date}
            </p>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <article className="rounded-2xl border border-rose-400/20 bg-rose-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-rose-100/80">Critical copies</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryRiskSummary.critical_copies}</p>
            </article>
            <article className="rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-amber-100/80">High copies</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryRiskSummary.high_copies}</p>
            </article>
            <article className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-blue-800/80">Medium copies</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryRiskSummary.medium_copies}</p>
            </article>
            <article className="rounded-2xl border border-violet-400/20 bg-violet-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-violet-100/80">Low copies</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryRiskSummary.low_copies}</p>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Risk items</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryRiskSummary.total_risk_items}</p>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Copies with risk</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryRiskSummary.copies_with_risk}</p>
            </article>
          </div>
          <div className="mt-5 overflow-auto rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <h3 className="text-sm font-semibold text-patriot-navy">Top action items</h3>
            <div className="mt-3 overflow-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="pb-2 pr-3 font-medium">Copy</th>
                    <th className="pb-2 pr-3 font-medium">Priority</th>
                    <th className="pb-2 pr-3 font-medium">Risks</th>
                    <th className="pb-2 font-medium">Evidence</th>
                  </tr>
                </thead>
                <tbody className="text-slate-200">
                  {inventoryRiskSummary.top_action_items.slice(0, 5).map((item) => (
                    <tr key={item.inventory_copy_id} className="border-t border-slate-100 align-top">
                      <td className="py-2 pr-3 font-medium text-slate-900">
                        <Link to={`/inventory/${item.inventory_copy_id}`} className="hover:text-blue-700">
                          {item.publisher} · {item.title} #{item.issue_number}
                        </Link>
                      </td>
                      <td className="py-2 pr-3">
                        <span
                          className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${inventoryRiskPriorityTone(
                            item.highest_priority,
                          )}`}
                        >
                          {item.highest_priority}
                        </span>
                      </td>
                      <td className="py-2 pr-3">
                        <div className="flex flex-wrap gap-1">
                          {item.risk_types.map((riskType) => (
                            <span
                              key={riskType}
                              className="inline-flex rounded-full border border-slate-200 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-200"
                            >
                              {inventoryRiskLabel(riskType)}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-2 text-slate-600">
                        {item.evidence_preview.join(" · ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      ) : null}

      {inventoryActionSummary ? (
        <section className="mt-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/50">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-patriot-navy">Workflow action center</h2>
              <p className="mt-1 text-sm text-slate-600">
                Same priority ladder as risk lanes: conflicts, canon, duplication, scans/OCR, preorder-arrival overlaps.
                Read-only — no mutations.
              </p>
            </div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
              As of {inventoryActionSummary.generated_as_of_date}
            </p>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <article className="rounded-2xl border border-rose-400/20 bg-rose-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-rose-100/80">
                Critical actions
              </p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryActionSummary.critical_actions}</p>
            </article>
            <article className="rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-amber-100/80">High actions</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryActionSummary.high_actions}</p>
            </article>
            <article className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-blue-800/80">Medium actions</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryActionSummary.medium_actions}</p>
            </article>
            <article className="rounded-2xl border border-violet-400/20 bg-violet-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-violet-100/80">Low actions</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryActionSummary.low_actions}</p>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Copies with actions</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryActionSummary.copies_with_actions}</p>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Total actions</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryActionSummary.total_actions}</p>
            </article>
          </div>
          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <div className="overflow-auto rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <h3 className="text-sm font-semibold text-patriot-navy">Actions by category</h3>
              <ul className="mt-3 space-y-2 text-xs text-slate-700">
                {inventoryActionSummary.by_category
                  .filter((row) => row.count > 0)
                  .slice(0, 8)
                  .map((row) => (
                    <li key={row.key ?? "null"} className="flex justify-between gap-3 border-b border-slate-100 pb-2">
                      <span className="text-slate-600">
                        {row.key ? inventoryActionCenterCategoryUiLabel(row.key as InventoryActionCenterCategory) : "—"}
                      </span>
                      <span className="font-semibold text-slate-900">{row.count}</span>
                    </li>
                  ))}
              </ul>
            </div>
            <div className="overflow-auto rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <h3 className="text-sm font-semibold text-patriot-navy">Copies needing the most workflows</h3>
              <div className="mt-3 overflow-auto">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="pb-2 pr-3 font-medium">Copy</th>
                      <th className="pb-2 pr-3 font-medium">Lane</th>
                      <th className="pb-2 pr-3 font-medium">Workflows</th>
                      <th className="pb-2 font-medium">Categories</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-200">
                    {inventoryActionSummary.top_unresolved_inventory.slice(0, 6).map((item) => (
                      <tr key={item.inventory_copy_id} className="border-t border-slate-100 align-top">
                        <td className="py-2 pr-3 font-medium text-slate-900">
                          <Link to={`/inventory/${item.inventory_copy_id}`} className="hover:text-blue-700">
                            {item.publisher} · {item.title} #{item.issue_number}
                          </Link>
                        </td>
                        <td className="py-2 pr-3">
                          <span
                            className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${inventoryRiskPriorityTone(
                              item.highest_lane_priority,
                            )}`}
                          >
                            {item.highest_lane_priority}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-slate-600">{item.action_count}</td>
                        <td className="py-2 text-slate-600">
                          {item.action_categories
                            .map((c) => inventoryActionCenterCategoryUiLabel(c))
                            .join(" · ")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {collectionHistoricalTimeline && collectionHistoricalTimeline.events.length > 0 ? (
        <section className="mt-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/50">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-patriot-navy">Collection timeline (activity history)</h2>
              <p className="mt-1 text-sm text-slate-600">
                Persisted timestamps for purchases, arrivals, scans/OCR (and replays), link decisions, duplicate reviews,
                conflicts, variants — valuations never appear here.
              </p>
              <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
                <p className="w-full text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  Release / preorder markers
                </p>
                {collectionHistoricalTimeline.events
                  .filter((event) =>
                    ["preorder_created", "release_day", "expected_ship_window"].includes(event.event_type),
                  )
                  .slice(0, 8)
                  .map((event) => (
                    <article
                      key={`strip-${event.stable_id}`}
                      className="flex min-w-[10rem] flex-1 gap-3 rounded-2xl border border-cyan-400/25 bg-slate-50 p-3"
                    >
                      <span className={`mt-1 inline-block size-2.5 shrink-0 rounded-full ${timelineDotClass(event)}`} />
                      <div className="text-xs">
                        <p className="font-semibold text-blue-800">{describeHistoricalTimelineEvent(event)}</p>
                        <p className="mt-1 text-[11px] text-slate-500">
                          {new Intl.DateTimeFormat("en-US", {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          }).format(new Date(event.occurred_at))}
                        </p>
                        <p className="mt-1 font-medium text-slate-900">
                          {event.publisher} · {event.series_title} #{event.issue_number}
                        </p>
                        <Link
                          to={`/inventory/${event.inventory_copy_id}`}
                          className="mt-2 inline-flex text-[11px] font-semibold text-blue-700 hover:text-blue-800"
                        >
                          Open copy #{event.inventory_copy_id}
                        </Link>
                      </div>
                    </article>
                  ))}
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                As of {collectionHistoricalTimeline.generated_as_of_date}
              </p>
              <p className="mt-2 text-[11px] text-slate-500">
                {collectionHistoricalTimeline.summary.total_events_present} persisted events tracked (showing newest{" "}
                {collectionHistoricalTimeline.events.length}).
              </p>
            </div>
          </div>
          <div className="mt-6 space-y-6">
            <div>
              <h3 className="text-sm font-semibold text-patriot-navy">Recent reconciliation & reviews</h3>
              <div className="mt-3 overflow-auto rounded-2xl border border-slate-200 bg-slate-50">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="px-4 py-2">When</th>
                      <th className="px-4 py-2">Signal</th>
                      <th className="px-4 py-2">Issue</th>
                      <th className="px-4 py-2">Copy</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-200">
                    {collectionHistoricalTimeline.events
                      .filter((event) =>
                        [
                          "relationship_reviewed",
                          "canonical_suggestion_reviewed",
                          "conflict_detected",
                          "conflict_resolved",
                          "duplicate_detected",
                          "variant_family_detected",
                        ].includes(event.event_type),
                      )
                      .slice(0, 10)
                      .map((event) => (
                        <tr key={`review-${event.stable_id}`} className="border-t border-slate-100">
                          <td className="px-4 py-2 text-[11px] text-slate-600">
                            {new Intl.DateTimeFormat("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                              hour: "numeric",
                              minute: "2-digit",
                            }).format(new Date(event.occurred_at))}
                          </td>
                          <td className="px-4 py-2 font-semibold text-slate-900">
                            {describeHistoricalTimelineEvent(event)}
                          </td>
                          <td className="px-4 py-2">
                            {event.publisher} · {event.series_title} #{event.issue_number}
                          </td>
                          <td className="px-4 py-2">
                            <Link
                              className="text-blue-700 hover:text-cyan-50"
                              to={`/inventory/${event.inventory_copy_id}`}
                            >
                              #{event.inventory_copy_id}
                            </Link>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-patriot-navy">Latest collection activity</h3>
              <div className="mt-3 overflow-auto rounded-2xl border border-slate-200 bg-slate-50">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="px-4 py-2">When</th>
                      <th className="px-4 py-2">Type</th>
                      <th className="px-4 py-2">Issue</th>
                      <th className="px-4 py-2">Copy</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-200">
                    {collectionHistoricalTimeline.events.slice(0, 14).map((event) => (
                      <tr key={`all-${event.stable_id}`} className="border-t border-slate-100 align-top">
                        <td className="px-4 py-2 text-[11px] text-slate-600 whitespace-nowrap">
                          {new Intl.DateTimeFormat("en-US", {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                            hour: "numeric",
                            minute: "2-digit",
                          }).format(new Date(event.occurred_at))}
                        </td>
                        <td className="px-4 py-2">
                          <p className="font-semibold text-slate-900">{describeHistoricalTimelineEvent(event)}</p>
                          <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">{event.event_type}</p>
                        </td>
                        <td className="px-4 py-2">
                          <p>{event.publisher}</p>
                          <p className="text-[11px] text-slate-600">
                            {event.series_title} #{event.issue_number}
                          </p>
                        </td>
                        <td className="px-4 py-2">
                          <Link
                            className="text-blue-700 hover:text-cyan-50"
                            to={`/inventory/${event.inventory_copy_id}`}
                          >
                            #{event.inventory_copy_id}
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {orderArrivalSummary ? (
        <section className="mt-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/50">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-patriot-navy">Order / arrival lanes</h2>
              <p className="mt-1 text-sm text-slate-600">
                Derived from persisted purchase, release, expected-ship, and receipt fields plus order status — logistics
                only (no FMV, pricing, speculation, or auto-receiving).
              </p>
            </div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
              As of {orderArrivalSummary.generated_as_of_date}
            </p>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <article className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-blue-800/80">
                Releases this week
              </p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {orderArrivalBucketCount(orderArrivalSummary, "releases_this_week")}
              </p>
            </article>
            <article className="rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-amber-100/80">
                Released / not received
              </p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {orderArrivalBucketCount(orderArrivalSummary, "released_not_received")}
              </p>
            </article>
            <article className="rounded-2xl border border-violet-400/20 bg-violet-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-violet-100/80">Shipping soon</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {orderArrivalBucketCount(orderArrivalSummary, "expected_to_ship_soon")}
              </p>
            </article>
            <article className="rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-rose-100/80">Shipment overdue</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {orderArrivalBucketCount(orderArrivalSummary, "overdue_expected_ship")}
              </p>
            </article>
          </div>
          <div className="mt-5 overflow-auto rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <h3 className="text-sm font-semibold text-patriot-navy">Upcoming preorder / arrivals</h3>
            <div className="mt-3 overflow-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="pb-2 pr-3 font-medium">Copy</th>
                    <th className="pb-2 pr-3 font-medium">Lanes</th>
                    <th className="pb-2 font-medium">Evidence</th>
                  </tr>
                </thead>
                <tbody className="text-slate-200">
                  {orderArrivalSummary.top_action_items.slice(0, 6).map((item) => (
                    <tr key={item.inventory_copy_id} className="border-t border-slate-100 align-top">
                      <td className="py-2 pr-3 font-medium text-slate-900">
                        <Link to={`/inventory/${item.inventory_copy_id}`} className="hover:text-blue-700">
                          {item.publisher} · {item.title} #{item.issue_number}
                        </Link>
                        <div className="text-[11px] text-slate-500">{item.retailer}</div>
                      </td>
                      <td className="py-2 pr-3">
                        <div className="flex flex-wrap gap-1">
                          {item.classifications.map((c) => (
                            <span
                              key={c}
                              className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${orderArrivalTone(
                                c,
                              )}`}
                            >
                              {orderArrivalLabelShort(c)}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-2 text-slate-600">{item.evidence_preview.join(" · ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      ) : null}

      {((inventoryIntelSummary && inventoryIntelHealth) ||
        collectionAnalyticsSummary ||
        collectionAnalyticsQuality ||
        collectionAnalyticsPublishers ||
        dashboardWidgetErrors.inventoryIntelSummary ||
        dashboardWidgetErrors.inventoryIntelHealth ||
        dashboardWidgetErrors.collectionAnalyticsSummary ||
        dashboardWidgetErrors.collectionAnalyticsQuality ||
        dashboardWidgetErrors.collectionAnalyticsPublishers) ? (
        <details
          className="mt-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/50 [&>summary::-webkit-details-marker]:hidden"
          open={loadProfile === "collection"}
        >
          <summary className="flex cursor-pointer list-none flex-wrap items-start justify-between gap-3 rounded-2xl border border-slate-100 bg-slate-50 p-4">
            <div>
              <h2 className="text-lg font-semibold text-patriot-navy">Coverage rollup & publishers</h2>
              <p className="mt-1 max-w-prose text-sm text-slate-600">
                {loadProfile === "collection"
                  ? "Ownership mix, health buckets, preorder exposure, and publisher totals."
                  : "Collapsed by default — ownership mix, health buckets, preorder exposure, OCR/canon coverage and deterministic publisher totals."}
              </p>
            </div>
          </summary>
          <div className="mt-8 space-y-12 border-t border-slate-100 pt-8">
            {dashboardWidgetErrors.inventoryIntelSummary ||
            dashboardWidgetErrors.inventoryIntelHealth ? (
              <div className="space-y-2">
                {dashboardWidgetErrors.inventoryIntelSummary ? (
                  <StatusBanner tone="error">
                    Inventory intelligence summary: {dashboardWidgetErrors.inventoryIntelSummary}
                  </StatusBanner>
                ) : null}
                {dashboardWidgetErrors.inventoryIntelHealth ? (
                  <StatusBanner tone="error">
                    Inventory intelligence health: {dashboardWidgetErrors.inventoryIntelHealth}
                  </StatusBanner>
                ) : null}
              </div>
            ) : null}
            {inventoryIntelSummary && inventoryIntelHealth ? (
              <div className="space-y-4">
                <div>
                  <h3 className="text-base font-semibold text-patriot-navy">Inventory intelligence rollup</h3>
                  <p className="mt-1 text-sm text-slate-600">
                    Scans/OCR backlog, unresolved review workloads, deterministic duplicate/variant clustering touch —
                    read-only projections.
                  </p>
                </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-5">
            <article className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">In hand</p>
              <p className="mt-1 text-lg font-semibold text-patriot-navy">{inventoryIntelSummary.ownership_in_hand}</p>
            </article>
            <article className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Preorder</p>
              <p className="mt-1 text-lg font-semibold text-patriot-navy">{inventoryIntelSummary.ownership_preorder}</p>
            </article>
            <article className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Ordered (not recv)</p>
              <p className="mt-1 text-lg font-semibold text-patriot-navy">
                {inventoryIntelSummary.ownership_ordered_not_received}
              </p>
            </article>
            <article className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Cancelled</p>
              <p className="mt-1 text-lg font-semibold text-patriot-navy">{inventoryIntelSummary.ownership_cancelled}</p>
            </article>
            <article className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Unknown ops state</p>
              <p className="mt-1 text-lg font-semibold text-patriot-navy">
                {inventoryIntelSummary.ownership_unknown_state}
              </p>
            </article>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Tracked copies</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryIntelSummary.total_inventory_copies}</p>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Cover scans</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryIntelSummary.scanned_copies}</p>
              <p className="mt-1 text-[11px] text-slate-500">
                {inventoryIntelSummary.unscanned_copies} still unscanned · OCR pending{" "}
                {inventoryIntelSummary.ocr_pending_copies}, complete {inventoryIntelSummary.ocr_complete_copies} · corrupt
                /failed cover processing {inventoryIntelSummary.cover_processing_failed_copies} · OCR failed{" "}
                {inventoryIntelSummary.ocr_failed_copies}
              </p>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Unresolved rollups</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {totalInventoryIntelUnresolvedRollup(inventoryIntelSummary)}
              </p>
              <p className="mt-1 text-[11px] text-slate-500">
                Conflicts {inventoryIntelSummary.unresolved_relationship_conflicts} · canonical{" "}
                {inventoryIntelSummary.unresolved_canonical_suggestions} · dup-inv groups{" "}
                {inventoryIntelSummary.unresolved_duplicate_inventory_groups} · dup-scan clusters touching you{" "}
                {inventoryIntelSummary.unresolved_duplicate_scan_clusters} · variant-family clusters touching you{" "}
                {inventoryIntelSummary.unresolved_variant_family_clusters}
              </p>
            </article>
            <article className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-emerald-200/80">Healthy</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryIntelHealth.healthy}</p>
            </article>
            <article className="rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-amber-100/80">Needs review</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryIntelHealth.needs_review}</p>
            </article>
            <article className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-blue-800/80">Incomplete</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">{inventoryIntelHealth.incomplete}</p>
              <p className="mt-1 text-[11px] text-slate-600">
                Blocked copies: {inventoryIntelHealth.blocked} (normally cancelled/stranded workflows)
              </p>
            </article>
          </div>
              </div>
            ) : null}
            {dashboardWidgetErrors.collectionAnalyticsSummary ||
            dashboardWidgetErrors.collectionAnalyticsQuality ||
            dashboardWidgetErrors.collectionAnalyticsPublishers ? (
              <div className="space-y-2">
                {dashboardWidgetErrors.collectionAnalyticsSummary ? (
                  <StatusBanner tone="error">
                    Collection analytics summary: {dashboardWidgetErrors.collectionAnalyticsSummary}
                  </StatusBanner>
                ) : null}
                {dashboardWidgetErrors.collectionAnalyticsQuality ? (
                  <StatusBanner tone="error">
                    Collection quality analytics: {dashboardWidgetErrors.collectionAnalyticsQuality}
                  </StatusBanner>
                ) : null}
                {dashboardWidgetErrors.collectionAnalyticsPublishers ? (
                  <StatusBanner tone="error">
                    Collection publisher analytics: {dashboardWidgetErrors.collectionAnalyticsPublishers}
                  </StatusBanner>
                ) : null}
              </div>
            ) : null}
            {collectionAnalyticsSummary || collectionAnalyticsQuality ? (
              <div className="space-y-4">
                <div>
                  <h3 className="text-base font-semibold text-patriot-navy">Publisher & quality rollups</h3>
                  {collectionAnalyticsSummary ? (
                    <p className="mt-1 text-sm text-slate-600">
                      As-of anchor:{" "}
                      <span className="font-semibold text-slate-200">
                        {collectionAnalyticsSummary.generated_as_of_date}
                      </span>
                    </p>
                  ) : null}
                </div>
                {collectionAnalyticsSummary ? (
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Preorder exposure</p>
                      <p className="mt-2 text-2xl font-semibold text-patriot-navy">{collectionAnalyticsSummary.preorder_copies}</p>
                      <p className="mt-1 text-[11px] text-slate-500">
                        Missing calendar cues: {collectionAnalyticsSummary.preorder_missing_calendar_copies}
                      </p>
                    </article>
                    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">In hand copies</p>
                      <p className="mt-2 text-2xl font-semibold text-patriot-navy">{collectionAnalyticsSummary.in_hand_copies}</p>
                      <p className="mt-1 text-[11px] text-slate-500">
                        Total tracked: {collectionAnalyticsSummary.total_copies}
                      </p>
                    </article>
                    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
                        Unresolved review workload
                      </p>
                      <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                        {collectionAnalyticsSummary.unresolved_review_copies}
                      </p>
                      <p className="mt-1 text-[11px] text-slate-500">Distinct copies in needs_review health bucket.</p>
                    </article>
                    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Canonical-linked copies</p>
                      <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                        {collectionAnalyticsSummary.canonical_linked_copies}
                      </p>
                      <p className="mt-1 text-[11px] text-slate-500">
                        Unscanned primaries: {collectionAnalyticsSummary.unscanned_primary_copies}
                      </p>
                    </article>
                  </div>
                ) : null}
                {collectionAnalyticsQuality ? (
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <article className="rounded-2xl border border-emerald-400/25 bg-emerald-400/5 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-200">OCR complete</p>
              <p className="mt-2 text-xl font-semibold text-patriot-navy">
                {collectionAnalyticsQuality.inventory_quality.ocr_complete.percent}%{" "}
                <span className="text-[11px] text-slate-600">
                  ({collectionAnalyticsQuality.inventory_quality.ocr_complete.numerator}/
                  {collectionAnalyticsQuality.inventory_quality.ocr_complete.denominator})
                </span>
              </p>
            </article>
            <article className="rounded-2xl border border-cyan-400/25 bg-cyan-400/5 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-blue-800">Canonical coverage</p>
              <p className="mt-2 text-xl font-semibold text-patriot-navy">
                {collectionAnalyticsQuality.inventory_quality.canonical_linked.percent}%{" "}
                <span className="text-[11px] text-slate-600">
                  ({collectionAnalyticsQuality.inventory_quality.canonical_linked.numerator}/
                  {collectionAnalyticsQuality.inventory_quality.canonical_linked.denominator})
                </span>
              </p>
            </article>
            <article className="rounded-2xl border border-amber-400/25 bg-amber-400/5 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-100">Dup ownership touch</p>
              <p className="mt-2 text-xl font-semibold text-patriot-navy">
                {collectionAnalyticsQuality.inventory_quality.duplicate_ownership_exposure_copies.percent}%{" "}
                <span className="text-[11px] text-slate-600">
                  (
                  {
                    collectionAnalyticsQuality.inventory_quality.duplicate_ownership_exposure_copies.numerator
                  }/
                  {collectionAnalyticsQuality.inventory_quality.duplicate_ownership_exposure_copies.denominator})
                </span>
              </p>
            </article>
            <article className="rounded-2xl border border-violet-400/25 bg-violet-400/5 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-violet-100">Open conflicts touch</p>
              <p className="mt-2 text-xl font-semibold text-patriot-navy">
                {
                  collectionAnalyticsQuality.inventory_quality.unresolved_open_conflict_copies.percent
                }%
                <span className="text-[11px] text-slate-600">
                  {" "}
                  (
                  {collectionAnalyticsQuality.inventory_quality.unresolved_open_conflict_copies.numerator}
                  /
                  {collectionAnalyticsQuality.inventory_quality.unresolved_open_conflict_copies.denominator})
                </span>
              </p>
            </article>
            <article className="rounded-2xl border border-rose-400/25 bg-rose-400/5 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-rose-100">Cover processing failures</p>
              <p className="mt-2 text-xl font-semibold text-patriot-navy">
                {
                  collectionAnalyticsQuality.inventory_quality.primary_cover_failed_processing.percent
                }%
                <span className="text-[11px] text-slate-600">
                  {" "}
                  ({collectionAnalyticsQuality.inventory_quality.primary_cover_failed_processing.numerator}/
                  {collectionAnalyticsQuality.inventory_quality.primary_cover_failed_processing.denominator})
                </span>
              </p>
            </article>
            <article className="rounded-2xl border border-orange-400/25 bg-orange-400/5 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-orange-100">Latest OCR failures</p>
              <p className="mt-2 text-xl font-semibold text-patriot-navy">
                {collectionAnalyticsQuality.inventory_quality.primary_cover_failed_ocr.percent}%
                <span className="text-[11px] text-slate-600">
                  {" "}
                  ({collectionAnalyticsQuality.inventory_quality.primary_cover_failed_ocr.numerator}/
                  {collectionAnalyticsQuality.inventory_quality.primary_cover_failed_ocr.denominator})
                </span>
              </p>
            </article>
                  </div>
                ) : null}
          {collectionAnalyticsPublishers && collectionAnalyticsPublishers.publishers.length ? (
            <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <h3 className="text-sm font-semibold text-patriot-navy">Publisher breakdown</h3>
              <p className="mt-1 text-xs text-slate-500">Sorted deterministically by publisher name.</p>
              <div className="mt-3 overflow-auto">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="pb-2 pr-3 font-medium">Publisher</th>
                      <th className="pb-2 pr-3 font-medium">Copies</th>
                      <th className="pb-2 pr-3 font-medium">In hand</th>
                      <th className="pb-2 pr-3 font-medium">Preorder</th>
                      <th className="pb-2 pr-3 font-medium">Unresolved review</th>
                      <th className="pb-2 font-medium">Canon-linked</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-200">
                    {collectionAnalyticsPublishers.publishers.slice(0, 20).map((row) => (
                      <tr key={row.publisher_name} className="border-t border-slate-100 align-top">
                        <td className="py-2 pr-3 font-medium text-slate-900">{row.publisher_name}</td>
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
              </div>
            ) : null}
          </div>
        </details>
      ) : null}

      {duplicateOwnershipReport ? (
        <details
          className="mt-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/50 [&>summary::-webkit-details-marker]:hidden"
          open={
            duplicateOwnershipReport.summary.probable_accidental_duplicate_groups > 0 ||
            duplicateOwnershipReport.summary.unresolved_duplicate_groups > 0
          }
        >
          <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-patriot-navy">Duplicate ownership clustering</h2>
                <p className="mt-1 text-sm text-slate-600">
                  Read-only owner overlap buckets (deterministic clustering — never auto-dedupe or silent metadata edits).
                  <span className="ml-1 text-[11px] text-slate-500"> Tap header to collapse.</span>
                </p>
              </div>
            </div>
          </summary>
          <div className="mt-4 border-t border-slate-100 pt-4">
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-7">
            <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Overlap groups</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {duplicateOwnershipReport.summary.total_groups}
              </p>
              <p className="mt-1 text-[11px] text-slate-600">Multi-copy groups only (&ge; two inventory IDs).</p>
            </article>
            <article className="rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-rose-100">
                Probable accidental
              </p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {duplicateOwnershipReport.summary.probable_accidental_duplicate_groups}
              </p>
              <p className="mt-1 text-[11px] text-slate-100/80">
                Heuristic raw-heavy clusters flagged by deterministic scan/canonical cues.
              </p>
            </article>
            <article className="rounded-2xl border border-cyan-400/25 bg-cyan-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-blue-800">
                Preorder + received
              </p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {duplicateOwnershipReport.summary.preorder_plus_owned_groups}
              </p>
              <p className="mt-1 text-[11px] text-slate-100/70">
                You still carry a preorder row while another copy already shows in-hand for the clustered issue surface.
              </p>
            </article>
            <article className="rounded-2xl border border-violet-400/25 bg-violet-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-violet-100">
                Duplicate scan only
              </p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {duplicateOwnershipReport.summary.duplicate_scan_only_groups}
              </p>
            </article>
            <article className="rounded-2xl border border-cyan-300/25 bg-white/5 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-blue-800">Graded + raw</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {duplicateOwnershipReport.summary.graded_plus_raw_groups}
              </p>
            </article>
            <article className="rounded-2xl border border-amber-300/35 bg-amber-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-amber-100">
                Unresolved duplicates
              </p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {duplicateOwnershipReport.summary.unresolved_duplicate_groups}
              </p>
              <p className="mt-1 text-[11px] text-slate-100/75">
                Touching duplicate-inventory candidate reviews that are still pending.
              </p>
            </article>
            <article className="rounded-2xl border border-emerald-300/25 bg-emerald-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-emerald-100">
                Intentional multi-copy
              </p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {duplicateOwnershipReport.summary.intentional_multi_copy_groups}
              </p>
              <p className="mt-1 text-[11px] text-slate-100/70">
                Default bucket when overlaps exist without stronger deterministic escalation signals.
              </p>
            </article>
          </div>
          </div>
        </details>
      ) : null}

      {runDetectionReport ? (
        <details className="mt-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/50 [&>summary::-webkit-details-marker]:hidden">
          <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
            <div>
              <h2 className="text-lg font-semibold text-patriot-navy">Series progress & missing-issue rows</h2>
              <p className="mt-1 text-sm text-slate-600">
                Canonical series grouping, deterministic issue ordering, gaps by ownership / release visibility — tap to
                expand metrics.
              </p>
            </div>
          </summary>
          <div className="mt-4 border-t border-slate-100 pt-4">
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-7">
            <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Tracked series</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {runDetectionReport.summary.total_series_groups}
              </p>
            </article>
            <article className="rounded-2xl border border-amber-400/25 bg-amber-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-amber-100">Partial runs</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {runDetectionReport.summary.partial_run_groups}
              </p>
            </article>
            <article className="rounded-2xl border border-emerald-400/25 bg-emerald-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-emerald-100">
                Completed runs
              </p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {runDetectionReport.summary.complete_limited_series_groups}
              </p>
            </article>
            <article className="rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-rose-100">
                Incomplete limited
              </p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {runDetectionReport.summary.incomplete_limited_series_groups}
              </p>
            </article>
            <article className="rounded-2xl border border-cyan-400/25 bg-cyan-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-blue-800">Likely ongoing series</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {runDetectionReport.summary.probable_ongoing_series_groups}
              </p>
            </article>
            <article className="rounded-2xl border border-violet-400/25 bg-violet-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-violet-100">Missing issue rows</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {runDetectionReport.summary.total_missing_issue_rows}
              </p>
              <p className="mt-1 text-[11px] text-slate-100/70">
                Confirmed {runDetectionReport.summary.confirmed_missing_rows} · likely{" "}
                {runDetectionReport.summary.likely_missing_rows}
              </p>
            </article>
            <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-700">Future / unresolved</p>
              <p className="mt-2 text-2xl font-semibold text-patriot-navy">
                {runDetectionReport.summary.preorder_pending_rows +
                  runDetectionReport.summary.unreleased_future_issue_rows +
                  runDetectionReport.summary.unresolved_identity_gap_rows}
              </p>
              <p className="mt-1 text-[11px] text-slate-600">
                Preorder {runDetectionReport.summary.preorder_pending_rows} · unreleased{" "}
                {runDetectionReport.summary.unreleased_future_issue_rows} · identity{" "}
                {runDetectionReport.summary.unresolved_identity_gap_rows}
              </p>
            </article>
          </div>
          </div>
        </details>
      ) : null}

      {showPortfolioPerformance ? (
      !hasPerformanceData ? (
        <div className="mt-6">
          {dashboardWidgetErrors.portfolioPerformance ? (
            <StatusBanner tone="error">
              Portfolio performance: {dashboardWidgetErrors.portfolioPerformance}
            </StatusBanner>
          ) : (
            <EmptyState
              title="No performance data yet"
              description="Performance leaders appear after you create orders and start assigning FMV values to inventory copies."
              action={
                <div className="flex flex-col gap-3 sm:flex-row">
                  <Link
                    to="/connected-retailers/import"
                    className="rounded-2xl border border-slate-200 px-4 py-3 text-center text-sm font-semibold text-slate-100 transition hover:border-blue-400 hover:bg-white/5"
                  >
                    Import Retailer Order
                  </Link>
                  <Link
                    to="/orders/new"
                    className="rounded-2xl bg-patriot-blue px-4 py-3 text-center text-sm font-semibold text-white transition hover:bg-blue-900"
                  >
                    Add Your First Order
                  </Link>
                </div>
              }
            />
          )}
        </div>
      ) : (
        <details className="group mt-6 rounded-3xl border border-slate-200 bg-white p-4 shadow-xl shadow-slate-200/50 [&>summary::-webkit-details-marker]:hidden">
          <summary className="cursor-pointer list-none">
            <h2 className="text-lg font-semibold text-patriot-navy">Portfolio performance (FMV)</h2>
            <p className="mt-1 max-w-xl text-sm text-slate-600">
              Separate from deterministic intelligence lanes. Expand for gain / loss boards after FMV assignments.
            </p>
          </summary>
          <div className="mt-6 grid gap-4 border-t border-slate-100 pt-6 xl:grid-cols-3">
          {analyticsSections.map((section) => (
            <article
              key={section.title}
              className="rounded-3xl border border-slate-200 bg-white p-5 shadow-lg shadow-slate-200/60"
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-patriot-navy">{section.title}</h2>
                  <p className="mt-1 text-sm text-slate-600">
                    Premium portfolio analytics for your strongest signals.
                  </p>
                </div>
              </div>

              <div className="mt-5 space-y-3">
                {section.items.length ? (
                  section.items.map((item) => (
                    <Link
                      key={`${section.title}-${item.inventory_copy_id}`}
                      to={`/inventory/${item.inventory_copy_id}`}
                      className="block rounded-2xl border border-slate-200 bg-slate-50 p-4 transition hover:border-blue-400 hover:bg-blue-50"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-medium text-slate-900">{performanceLabel(item)}</p>
                          <p className="mt-1 text-sm text-slate-600">{item.publisher}</p>
                          <p className="mt-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                            {item.cover_name ?? "Standard cover"}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
                            {section.valueLabel}
                          </p>
                          <p
                            className={`mt-1 text-sm font-semibold ${
                              section.title === "Highest Value Books"
                                ? "text-blue-700"
                                : gainLossClass(section.valueFor(item))
                            }`}
                          >
                            {formatUsdCurrency(section.valueFor(item))}
                          </p>
                        </div>
                      </div>
                    </Link>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
                    {section.empty}
                  </div>
                )}
              </div>
            </article>
          ))}
          </div>
        </details>
      )
      ) : null}

      </>
      ) : null}

      {showInventoryGrid ? (
      <>
      <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/60">
          <div className="flex flex-col gap-4">
            <form className="grid gap-3 lg:grid-cols-[2fr_repeat(4,1fr)]" onSubmit={applySearch}>
              <input
                type="search"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Search by title, publisher, issue, or cover"
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-500 focus:border-blue-500"
              />
              <input
                type="text"
                value={publisher}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setPublisher(event.target.value);
                  })
                }
                placeholder="Publisher"
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-500 focus:border-blue-500"
              />
              <select
                value={holdStatus}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setHoldStatus(event.target.value);
                  })
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
              >
                <option value="">All hold statuses</option>
                <option value="hold">Hold</option>
                <option value="sell">Sell</option>
                <option value="sold">Sold</option>
              </select>
              <select
                value={gradeStatus}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setGradeStatus(event.target.value);
                  })
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
              >
                <option value="">All grade statuses</option>
                <option value="raw">Raw</option>
                <option value="submitted">Submitted</option>
                <option value="graded">Graded</option>
              </select>
              <button
                type="submit"
                className="rounded-2xl bg-patriot-blue px-4 py-3 text-sm font-semibold text-patriot-navy transition hover:bg-blue-900"
              >
                Search
              </button>
            </form>

            <div className="grid gap-3 md:grid-cols-3">
              <input
                type="number"
                min={1800}
                max={2999}
                value={releaseYearFilter}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setReleaseYearFilter(event.target.value);
                  })
                }
                placeholder="Release year (optional)"
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-500 focus:border-blue-500"
              />
              <select
                value={releaseCalendarFilter}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setReleaseCalendarFilter(
                      event.target.value as "" | InventoryReleaseCalendar,
                    );
                  })
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
              >
                <option value="">Any calendar release date state</option>
                <option value="present">Has exact calendar release date</option>
                <option value="missing">Missing calendar release date</option>
              </select>
              <select
                value={assetStateFilter}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setAssetStateFilter(event.target.value as "" | InventoryItem["asset_state"]);
                  })
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
              >
                <option value="">Any ownership / release state</option>
                <option value="preorder_not_released_yet">Upcoming preorder</option>
                <option value="ordered_not_received">Released / not received</option>
                <option value="in_hand">Received / in hand</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <select
                value={intelHealthFilter}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setIntelHealthFilter(
                      event.target.value as "" | InventoryIntelligenceHealthLevel | "not_healthy",
                    );
                  })
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
              >
                <option value="">Any inventory health bucket</option>
                <option value="not_healthy">Not healthy (review + incomplete + blocked)</option>
                <option value="healthy">Healthy</option>
                <option value="needs_review">Needs review</option>
                <option value="incomplete">Incomplete</option>
                <option value="blocked">Blocked</option>
              </select>
              <select
                value={ownershipIntelFilter}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setOwnershipIntelFilter(event.target.value as "" | InventoryOwnershipNormalized);
                  })
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
              >
                <option value="">Any normalized ownership (intel)</option>
                <option value="in_hand">Normalized: in_hand</option>
                <option value="preorder">Normalized: preorder</option>
                <option value="ordered_not_received">Normalized: ordered_not_received</option>
                <option value="cancelled">Normalized: cancelled</option>
                <option value="unknown_state">Normalized: unknown_state</option>
              </select>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <select
                value={valuationScopeFilter}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setValuationScopeFilter(event.target.value as "" | InventoryValuationScope);
                  })
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
              >
                <option value="">Any FMV scope</option>
                <option value="raw">Raw</option>
                <option value="graded">Graded</option>
                <option value="preorder_pending">Preorder pending</option>
                <option value="no_market_data">No market data</option>
                <option value="low_confidence">Low confidence</option>
                <option value="cancelled_excluded">Cancelled excluded</option>
              </select>
              <select
                value={confidenceBucketFilter}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setConfidenceBucketFilter(event.target.value as "" | MarketFmvConfidenceBucket);
                  })
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
              >
                <option value="">Any confidence</option>
                <option value="very_high">Very high</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
                <option value="very_low">Very low</option>
              </select>
            </div>

            <div className="grid gap-3 md:grid-cols-4">
              <select
                value={riskPriorityFilter}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setRiskPriorityFilter(event.target.value as "" | InventoryRiskPriority);
                  })
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
              >
                <option value="">Any risk priority</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
                <option value="info">Info</option>
              </select>
              <select
                value={riskTypeFilter}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setRiskTypeFilter(event.target.value as "" | InventoryRiskType);
                  })
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
              >
                <option value="">Any risk type</option>
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
              <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={needsAttentionFilter}
                  onChange={(event) =>
                    resetPageAndUpdate(() => {
                      setNeedsAttentionFilter(event.target.checked);
                    })
                  }
                />
                Needs attention only
              </label>
              <select
                value={arrivalClassificationFilter}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setArrivalClassificationFilter(event.target.value as "" | OrderArrivalClassification);
                  })
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
              >
                <option value="">Any order/arrival classification</option>
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
            </div>

            <div className="grid gap-3 md:grid-cols-4">
              <select
                value={actionCategoryFilter}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setActionCategoryFilter(event.target.value as "" | InventoryActionCenterCategory);
                  })
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
              >
                <option value="">Any action center category</option>
                <option value="review_relationship_conflict">{inventoryActionCenterCategoryUiLabel(
                  "review_relationship_conflict",
                )}</option>
                <option value="review_canonical_suggestion">
                  {inventoryActionCenterCategoryUiLabel("review_canonical_suggestion")}
                </option>
                <option value="review_duplicate_ownership">
                  {inventoryActionCenterCategoryUiLabel("review_duplicate_ownership")}
                </option>
                <option value="review_duplicate_scan">{inventoryActionCenterCategoryUiLabel(
                  "review_duplicate_scan",
                )}</option>
                <option value="review_variant_family">{inventoryActionCenterCategoryUiLabel(
                  "review_variant_family",
                )}</option>
                <option value="retry_ocr">{inventoryActionCenterCategoryUiLabel("retry_ocr")}</option>
                <option value="review_cover_processing">{inventoryActionCenterCategoryUiLabel(
                  "review_cover_processing",
                )}</option>
                <option value="scan_missing_cover">{inventoryActionCenterCategoryUiLabel(
                  "scan_missing_cover",
                )}</option>
                <option value="update_preorder_metadata">{inventoryActionCenterCategoryUiLabel(
                  "update_preorder_metadata",
                )}</option>
                <option value="review_run_gap">{inventoryActionCenterCategoryUiLabel("review_run_gap")}</option>
                <option value="review_high_confidence_match">{inventoryActionCenterCategoryUiLabel(
                  "review_high_confidence_match",
                )}</option>
              </select>
              <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-200 md:col-span-2">
                <input
                  type="checkbox"
                  checked={actionAttentionFilter}
                  onChange={(event) =>
                    resetPageAndUpdate(() => {
                      setActionAttentionFilter(event.target.checked);
                    })
                  }
                />
                Critical / high action lane only
              </label>
              <div className="hidden md:block" aria-hidden />
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <select
                value={sortBy}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setSortBy(event.target.value as SortBy);
                  })
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
              >
                {sortOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    Sort by {option.label}
                  </option>
                ))}
              </select>
              <select
                value={sortDir}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setSortDir(event.target.value as "asc" | "desc");
                  })
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
              >
                <option value="asc">Ascending</option>
                <option value="desc">Descending</option>
              </select>
              <button
                type="button"
                onClick={() => {
                  setSearch("");
                  setSearchInput("");
                  setPublisher("");
                  setHoldStatus("");
                  setGradeStatus("");
                  setReleaseYearFilter("");
                  setReleaseCalendarFilter("");
                  setAssetStateFilter("");
                  setRiskPriorityFilter("");
                  setRiskTypeFilter("");
                  setNeedsAttentionFilter(false);
                  setArrivalClassificationFilter("");
                  setSortBy("purchase_date");
                  setSortDir("asc");
                  setPage(1);
                }}
                className="rounded-2xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-blue-400 hover:bg-white/5"
              >
                Reset filters
              </button>
            </div>

            <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:flex-row md:items-center md:justify-between">
              <p className="text-sm text-slate-600">
                {selectedIds.length} selected for bulk updates
              </p>
              <div className="flex flex-col gap-3 sm:flex-row">
                <button
                  type="button"
                  disabled={!hasEligibleReceivingSelection || isSaving}
                  onClick={() => void applyBulkMarkReceived()}
                  className="rounded-2xl border border-emerald-400 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-900 transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Mark selected received
                </button>
                <select
                  value={bulkHoldStatus}
                  onChange={(event) =>
                    setBulkHoldStatus(event.target.value as "hold" | "sell" | "sold")
                  }
                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500"
                >
                  <option value="hold">Mark Hold</option>
                  <option value="sell">Mark Sell</option>
                  <option value="sold">Mark Sold</option>
                </select>
                <button
                  type="button"
                  disabled={!selectedIds.length || isSaving}
                  onClick={() => void applyBulkHoldUpdate()}
                  className="rounded-2xl bg-patriot-blue px-4 py-3 text-sm font-semibold text-patriot-navy transition hover:bg-blue-900 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Apply bulk update
                </button>
              </div>
            </div>
          </div>
      </section>

      {successMessage ? (
        <div className="mt-6">
          <StatusBanner tone="success">{successMessage}</StatusBanner>
        </div>
      ) : null}

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-slate-200 bg-white shadow-xl shadow-slate-200/60">
          <div className="border-b border-slate-200 px-5 py-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-patriot-navy">Inventory</h2>
                <p className="text-sm text-slate-600">
                  Page {page} of {pageCount} with {total} tracked copies
                </p>
              </div>
              {inventoryListLoading ? <p className="text-sm text-slate-600">Refreshing inventory...</p> : null}
            </div>
          </div>

          {!inventory.length ? (
            <div className="p-5">
              {dashboardWidgetErrors.inventoryList ? (
                <StatusBanner tone="error">
                  Inventory list: {dashboardWidgetErrors.inventoryList}
                </StatusBanner>
              ) : (
              <EmptyState
                title="No inventory yet"
                description="Create your first order to populate the dashboard with inventory copies, valuation controls, and detail pages."
                action={
                  <div className="flex flex-col gap-3 sm:flex-row">
                    <Link
                      to="/connected-retailers/import"
                      className="rounded-2xl border border-slate-200 px-4 py-3 text-center text-sm font-semibold text-slate-100 transition hover:border-blue-400 hover:bg-white/5"
                    >
                      Import Order
                    </Link>
                    <Link
                      to="/orders/new"
                      className="rounded-2xl bg-patriot-blue px-4 py-3 text-center text-sm font-semibold text-white transition hover:bg-blue-900"
                    >
                      Add Order
                    </Link>
                  </div>
                }
              />
              )}
            </div>
          ) : (
            <>
              <div className="flex items-center gap-3 border-b border-slate-200 px-4 py-2 text-xs text-slate-500">
                <input
                  type="checkbox"
                  checked={Boolean(inventory.length) && selectedIds.length === inventory.length}
                  onChange={toggleSelectAll}
                  aria-label="Select all on this page"
                />
                <span>Select all on this page</span>
              </div>
              <div
                className={
                  inventoryListLoading ? "pointer-events-none opacity-60 transition-opacity" : "transition-opacity"
                }
              >
              <PortfolioInventoryList
                inventory={inventory}
                selectedIds={selectedIds}
                isSaving={isSaving}
                fMvDrafts={fMvDrafts}
                gradeDrafts={gradeDrafts}
                holdDrafts={holdDrafts}
                starDrafts={starDrafts}
                normalizeDecimalInput={normalizeDecimalInput}
                onToggleSelection={toggleSelection}
                onFmvDraftChange={(id, value) =>
                  setFmvDrafts((current) => ({ ...current, [id]: value }))
                }
                onGradeDraftChange={(id, value) =>
                  setGradeDrafts((current) => ({ ...current, [id]: value }))
                }
                onHoldDraftChange={(id, value) =>
                  setHoldDrafts((current) => ({ ...current, [id]: value }))
                }
                onStarDraftChange={(id, value) =>
                  setStarDrafts((current) => ({ ...current, [id]: value }))
                }
                onSave={saveInventoryUpdate}
                onOpenNotes={(item) => {
                  setActiveNotesItem(item);
                  setNotesDraft(item.condition_notes ?? "");
                }}
                onOpenDetail={(item) => setDrawerInventoryCopyId(item.inventory_copy_id)}
                receivingCopyIds={receivingCopyIds}
                onMarkReceived={(id) => void markInventoryCopyReceived(id)}
              />
              </div>
            </>
          )}

          <div className="flex items-center justify-between border-t border-slate-200 px-5 py-4">
            <button
              type="button"
              disabled={page === 1 || inventoryListLoading}
              onClick={() => setPage((currentPage) => Math.max(1, currentPage - 1))}
              className="rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition hover:border-blue-500 hover:bg-slate-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400 disabled:opacity-100"
            >
              Previous
            </button>
            <span className="text-sm text-slate-600">
              Showing page {page} of {pageCount}
            </span>
            <button
              type="button"
              disabled={page >= pageCount || inventoryListLoading}
              onClick={() => setPage((currentPage) => Math.min(pageCount, currentPage + 1))}
              className="rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition hover:border-blue-500 hover:bg-slate-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400 disabled:opacity-100"
            >
              Next
            </button>
          </div>
      </section>
      </>
      ) : null}

      <PortfolioInventoryDetailDrawer
        inventoryCopyId={drawerInventoryCopyId}
        onClose={() => setDrawerInventoryCopyId(null)}
      />

      {activeNotesItem ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-white px-4">
          <div className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-slate-900 p-6 shadow-2xl shadow-black/30">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-semibold text-patriot-navy">Condition Notes</h3>
                <p className="mt-2 text-sm text-slate-600">
                  {activeNotesItem.title} #{activeNotesItem.issue_number}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setActiveNotesItem(null)}
                className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-100"
              >
                Close
              </button>
            </div>

            <textarea
              value={notesDraft}
              onChange={(event) => setNotesDraft(event.target.value)}
              maxLength={2000}
              rows={8}
              className="mt-6 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-500 focus:border-blue-500"
              placeholder="Add condition notes, grading observations, or sale prep notes."
            />

            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-slate-500">{notesDraft.length}/2000 characters</p>
              <button
                type="button"
                disabled={isSaving}
                onClick={async () => {
                  await saveInventoryUpdate(activeNotesItem.inventory_copy_id, {
                    condition_notes: notesDraft.trim() ? notesDraft : null,
                  });
                  setActiveNotesItem(null);
                }}
                className="rounded-2xl bg-patriot-blue px-4 py-3 text-sm font-semibold text-patriot-navy transition hover:bg-blue-900 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Save notes
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {showAutomationScanCards ? (
        <>
      <ScanIngestionSummaryCard />
      <ScanNormalizationSummaryCard />
      <ScanBoundarySummaryCard />
      <ScanOcrSummaryCard />
      <ScanReconciliationSummaryCard />
      <ScanDefectsSummaryCard />
      <ScanSpineTicksSummaryCard />
      <ScanCornerEdgesSummaryCard />
      <ScanSurfaceDefectsSummaryCard />
      <ScanStructuralDamageSummaryCard />
      <ScanDefectAggregationSummaryCard />
      <ScanGradingAssistanceSummaryCard />
      <ScanVisualEvidenceSummaryCard />
      <ScanReviewSummaryCard />
      <ScanHistoricalComparisonSummaryCard />
      <ScanAuthenticationSummaryCard />
      <ScanIntelligenceFeedSummaryCard />
      <ScanReplaySummaryCard />
      <AutomationBatchSummaryCard />
      <AutomationNotificationsSummaryCard />
      <AutomationAnalyticsSummaryCard />
      <AutomationOpsSummaryCard />
      <AutomationRulesSummaryCard />
      <AutomationJobsSummaryCard />
      <AutomationRecoverySummaryCard />
      <AutomationWorkersSummaryCard />
      <AutomationWorkflowsSummaryCard />
        </>
      ) : null}
    </AppShell>
  );
}
