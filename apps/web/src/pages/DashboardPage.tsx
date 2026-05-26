import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { describeHistoricalTimelineEvent, timelineDotClass } from "../lib/collectionHistoricalTimelineUi";
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
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../auth/AuthContext";

const sortOptions: Array<{ label: string; value: SortBy }> = [
  { label: "Purchase Date", value: "purchase_date" },
  { label: "Title", value: "title" },
  { label: "Acquisition Cost", value: "acquisition_cost" },
  { label: "Current FMV", value: "current_fmv" },
  { label: "Gain / Loss", value: "gain_loss" },
];

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
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
  }
}

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
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
      <p className="text-slate-400">{item.release_year ?? "—"}</p>
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
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
    case "cancelled":
      return "border-rose-400/30 bg-rose-400/10 text-rose-200";
    default:
      return "border-white/10 bg-white/5 text-slate-300";
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
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "blocked":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    default:
      return "border-white/10 bg-white/5 text-slate-300";
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
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
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
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
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
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
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
            <span className="inline-flex rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-300">
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
        <span className="inline-flex rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-300">
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
        <span className="inline-flex rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-300">
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
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "expected_to_ship_soon":
      return "border-violet-400/35 bg-violet-400/10 text-violet-100";
    case "received_recently":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "cancelled_order":
      return "border-white/15 bg-white/5 text-slate-300";
    default:
      return "border-white/15 bg-white/5 text-slate-300";
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
        <span className="inline-flex rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-300">
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
    return "text-slate-400";
  }

  const amount = Number(value);
  if (amount > 0) {
    return "text-emerald-300";
  }
  if (amount < 0) {
    return "text-rose-300";
  }
  return "text-slate-300";
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
    <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{caption}</p>
        <p className="text-[11px] text-slate-500">
          Row progress rollup:{" "}
          <span className="font-semibold text-slate-300">
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
                <tr key={row.id} className="border-t border-white/10">
                  <td className="py-2 pr-3 font-mono text-[11px] text-white">#{row.id}</td>
                  <td className="py-2 pr-3 capitalize text-slate-300">{formatScanSessionType(row.session_type)}</td>
                  <td className="py-2 pr-3 capitalize text-slate-300">{row.status.replace(/_/g, " ")}</td>
                  <td className="py-2 pr-3 text-slate-300">
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

export function DashboardPage() {
  const { user } = useAuth();

  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [performance, setPerformance] = useState<PortfolioPerformance | null>(null);
  const [portfolioValueSummary, setPortfolioValueSummary] = useState<PortfolioValueSummaryResponse | null>(null);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
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
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkHoldStatus, setBulkHoldStatus] = useState<"hold" | "sell" | "sold">("sell");
  const [fMvDrafts, setFmvDrafts] = useState<Record<number, string>>({});
  const [holdDrafts, setHoldDrafts] = useState<Record<number, InventoryItem["hold_status"]>>({});
  const [gradeDrafts, setGradeDrafts] = useState<Record<number, InventoryItem["grade_status"]>>({});
  const [starDrafts, setStarDrafts] = useState<Record<number, string>>({});
  const [activeNotesItem, setActiveNotesItem] = useState<InventoryItem | null>(null);
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
  const [opReportRollups, setOpReportRollups] = useState<OperationalReportingDashboardRollup | null>(null);
  const [opReportRollupsLoading, setOpReportRollupsLoading] = useState(true);
  const [opReportRollupsError, setOpReportRollupsError] = useState<string | null>(null);
  const [opReportBusy, setOpReportBusy] = useState(false);
  const [gradingDashSummary, setGradingDashSummary] = useState<GradingCandidateDashboardSummary | null>(null);
  const [gradingDashLoading, setGradingDashLoading] = useState(true);
  const [gradingDashError, setGradingDashError] = useState<string | null>(null);
  const [gradingSpreadSummary, setGradingSpreadSummary] = useState<GradingSpreadDashboardSummary | null>(null);
  const [gradingSpreadLoading, setGradingSpreadLoading] = useState(true);
  const [gradingSpreadError, setGradingSpreadError] = useState<string | null>(null);
  const [gradingRoiSummary, setGradingRoiSummary] = useState<GradingRoiDashboardSummary | null>(null);
  const [gradingRoiLoading, setGradingRoiLoading] = useState(true);
  const [gradingRoiError, setGradingRoiError] = useState<string | null>(null);
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
  const [gradingRiskSummary, setGradingRiskSummary] = useState<GradingRiskDashboardSummary | null>(null);
  const [gradingRiskLoading, setGradingRiskLoading] = useState(true);
  const [gradingRiskError, setGradingRiskError] = useState<string | null>(null);
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  const inventoryQuery = useMemo<InventoryQueryParams>(
    () => ({
      page,
      page_size: pageSize,
      search: search || undefined,
      publisher: publisher || undefined,
      hold_status: holdStatus || undefined,
      grade_status: gradeStatus || undefined,
      release_year: (() => {
        const n = Number(releaseYearFilter.trim());
        return Number.isInteger(n) ? n : undefined;
      })(),
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
    ],
  );

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
    const [
      summaryResponse,
      performanceResponse,
      portfolioValueSummaryResponse,
      inventoryResponse,
      riskSummaryResponse,
      workflowSummaryResponse,
      orderArrivalSummaryResponse,
      historicalTimelineResp,
      dupOwnershipInsight,
      runDetectionInsight,
      caSummary,
      caPublishers,
      caQuality,
      scanPipelineDashboard,
      physicalIntakeSummaryResponse,
    ] = await Promise.all([
      apiClient.getInventorySummary(),
      apiClient.getPortfolioPerformance(),
      apiClient.getPortfolioValueSummary({
        publisher: publisher || undefined,
        ownership_state: ownershipIntelFilter || undefined,
        valuation_scope: valuationScopeFilter || undefined,
        confidence_bucket: confidenceBucketFilter || undefined,
      }),
      apiClient.getInventory(query),
      apiClient.getInventoryRisksSummary(),
      apiClient.getInventoryActionCenterSummary(),
      apiClient.getOrderArrivalIntelligenceSummary(),
      apiClient.getCollectionHistoricalTimeline({ sort: "desc", limit: 40 }),
      apiClient.getDuplicateOwnershipList(),
      apiClient.getRunDetectionList(),
      apiClient.getCollectionAnalyticsSummary(),
      apiClient.getCollectionAnalyticsPublishers(),
      apiClient.getCollectionAnalyticsQuality(),
      apiClient.getScanPipelineDashboard(),
      apiClient.getPhysicalIntakeSummary(),
    ]);
    setSummary(summaryResponse);
    setPerformance(performanceResponse);
    setPortfolioValueSummary(portfolioValueSummaryResponse);
    setInventory(inventoryResponse.items);
    setTotal(inventoryResponse.total);
    setInventoryRiskSummary(riskSummaryResponse);
    setInventoryActionSummary(workflowSummaryResponse);
    setOrderArrivalSummary(orderArrivalSummaryResponse);
    setCollectionHistoricalTimeline(historicalTimelineResp);
    setDuplicateOwnershipReport(dupOwnershipInsight);
    setRunDetectionReport(runDetectionInsight);
    setCollectionAnalyticsSummary(caSummary);
    setCollectionAnalyticsPublishers(caPublishers);
    setCollectionAnalyticsQuality(caQuality);
    setScanPipelineDash(scanPipelineDashboard);
    setPhysicalIntakeSummary(physicalIntakeSummaryResponse);
    setSelectedIds((current) =>
      current.filter((id) => inventoryResponse.items.some((item) => item.inventory_copy_id === id)),
    );
  }

  useEffect(() => {
    let ignore = false;

    async function fetchData() {
      setIsLoading(true);
      setError(null);

      try {
        const [
          summaryResponse,
          performanceResponse,
          portfolioValueSummaryResponse,
          inventoryResponse,
          intelSummary,
          intelHealth,
          riskSummary,
          workflowSummary,
          orderArrivalSummaryResponse,
          historicalTimelineResp,
          dupOwnership,
          runDetection,
          caSummary,
          caPublishers,
          caQuality,
          scanPipelineDashboard,
          physicalIntakeSummaryResponse,
        ] =
          await Promise.all([
            apiClient.getInventorySummary(),
            apiClient.getPortfolioPerformance(),
            apiClient.getPortfolioValueSummary({
              publisher: publisher || undefined,
              ownership_state: ownershipIntelFilter || undefined,
              valuation_scope: valuationScopeFilter || undefined,
              confidence_bucket: confidenceBucketFilter || undefined,
            }),
            apiClient.getInventory(inventoryQuery),
            apiClient.getInventoryIntelligenceSummary(),
            apiClient.getInventoryIntelligenceHealth(),
            apiClient.getInventoryRisksSummary(),
            apiClient.getInventoryActionCenterSummary(),
            apiClient.getOrderArrivalIntelligenceSummary(),
            apiClient.getCollectionHistoricalTimeline({ sort: "desc", limit: 40 }),
            apiClient.getDuplicateOwnershipList(),
            apiClient.getRunDetectionList(),
            apiClient.getCollectionAnalyticsSummary(),
            apiClient.getCollectionAnalyticsPublishers(),
            apiClient.getCollectionAnalyticsQuality(),
            apiClient.getScanPipelineDashboard(),
            apiClient.getPhysicalIntakeSummary(),
          ]);

        if (ignore) {
          return;
        }

        setSummary(summaryResponse);
        setPerformance(performanceResponse);
        setPortfolioValueSummary(portfolioValueSummaryResponse);
        setInventory(inventoryResponse.items);
        setTotal(inventoryResponse.total);
        setInventoryIntelSummary(intelSummary);
        setInventoryIntelHealth(intelHealth);
        setInventoryRiskSummary(riskSummary);
        setInventoryActionSummary(workflowSummary);
        setOrderArrivalSummary(orderArrivalSummaryResponse);
        setCollectionHistoricalTimeline(historicalTimelineResp);
        setDuplicateOwnershipReport(dupOwnership);
        setRunDetectionReport(runDetection);
        setCollectionAnalyticsSummary(caSummary);
        setCollectionAnalyticsPublishers(caPublishers);
        setCollectionAnalyticsQuality(caQuality);
        setScanPipelineDash(scanPipelineDashboard);
        setPhysicalIntakeSummary(physicalIntakeSummaryResponse);
        setSelectedIds((current) =>
          current.filter((id) => inventoryResponse.items.some((item) => item.inventory_copy_id === id)),
        );
      } catch (loadError) {
        if (!ignore) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load dashboard.");
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    void fetchData();

    return () => {
      ignore = true;
    };
  }, [inventoryQuery]);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
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
  }, [user?.id]);

  useEffect(() => {
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
  }, [user?.id]);

  useEffect(() => {
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
  }, [user?.id]);

  useEffect(() => {
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
  }, [user?.id]);

  useEffect(() => {
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
  }, [user?.id]);

  useEffect(() => {
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
  }, [user?.id]);

  useEffect(() => {
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
  }, [user?.id]);

  useEffect(() => {
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
  }, [user?.id]);

  useEffect(() => {
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
  }, [user?.id]);

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
    conventionSummaryLoading ||
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
    Boolean(listingExportDash) ||
    dealerDashLoading ||
    dealerDashError ||
    dealerDashResp !== null;

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
    { label: "Cost Basis", value: formatCurrency(summary?.total_cost_basis ?? "0") },
    { label: "Current FMV", value: formatCurrency(summary?.total_current_fmv ?? "0") },
    {
      label: "Active Market Value",
      value: formatCurrencyWithCode(portfolioValue?.total_active_market_value ?? "0", portfolioValue?.currency_code ?? "USD"),
    },
    {
      label: "Raw Market Value",
      value: formatCurrencyWithCode(portfolioValue?.raw_market_value ?? "0", portfolioValue?.currency_code ?? "USD"),
    },
    {
      label: "Graded Market Value",
      value: formatCurrencyWithCode(portfolioValue?.graded_market_value ?? "0", portfolioValue?.currency_code ?? "USD"),
    },
    {
      label: "Low-Confidence Value",
      value: formatCurrencyWithCode(portfolioValue?.low_confidence_value ?? "0", portfolioValue?.currency_code ?? "USD"),
    },
    {
      label: "Preorder Informational",
      value: formatCurrencyWithCode(
        portfolioValue?.preorder_informational_value ?? "0",
        portfolioValue?.currency_code ?? "USD",
      ),
    },
    {
      label: "Stale Value",
      value: formatCurrencyWithCode(portfolioValue?.stale_value ?? "0", portfolioValue?.currency_code ?? "USD"),
    },
    { label: "No Market Data", value: portfolioValue?.no_market_data_count ?? 0 },
    { label: "Cancelled Excluded", value: portfolioValue?.cancelled_excluded_count ?? 0 },
    {
      label: "Unrealized P/L",
      value: formatCurrency(summary?.total_unrealized_gain_loss ?? "0"),
    },
  ];

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
  const isInitialLoad = isLoading && !summary && !performance && inventory.length === 0;

  if (isInitialLoad) {
    return (
      <AppShell>
        <PageHeader
          eyebrow="ComicOS Dashboard"
          title="Inventory Portfolio"
          description="Review cost basis, FMV, performance leaders, and book-level metadata from one premium workspace."
          actions={
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
              Signed in as <span className="font-medium text-white">{user?.email ?? "Loading..."}</span>
            </div>
          }
        />
        <div className="mt-6">
          <LoadingState
            title="Loading portfolio workspace"
            description="Refreshing summary cards, performance leaders, and inventory rows."
          />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="ComicOS Dashboard"
        title="Inventory Portfolio"
        description="Review cost basis, monitor held inventory, and manage book-level portfolio metadata from one dark-mode workspace."
        actions={
          <>
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
              Signed in as <span className="font-medium text-white">{user?.email ?? "Loading..."}</span>
            </div>
            <Link
              to="/orders/import"
              className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
            >
              Import Order
            </Link>
            <Link
              to="/scan-sessions"
              className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-teal-300/40 hover:bg-white/5"
            >
              Bulk scan ingest
            </Link>
            <Link
              to="/settings/scanner-profiles"
              className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-violet-300/35 hover:bg-white/5"
            >
              Scanner presets
            </Link>
            <Link
              to="/scan-sessions#scan-qa-and-routing"
              className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-amber-300/35 hover:bg-white/5"
            >
              QA &amp; routing
            </Link>
            <Link
              to="/dashboard#physical-intake"
              className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-emerald-300/35 hover:bg-white/5"
            >
              Receiving intake
            </Link>
            <Link
              to="/dashboard#market-intelligence"
              className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-emerald-300/35 hover:bg-white/5"
            >
              Market sales
            </Link>
            <Link
              to="/orders/new"
              className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
            >
              Add Order
            </Link>
          </>
        }
      />

      <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <article
            key={card.label}
            className="rounded-3xl border border-white/10 bg-slate-900/65 p-5 shadow-xl shadow-black/15"
          >
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-slate-500">{card.label}</p>
            <p className="mt-2 text-2xl font-semibold text-white sm:text-3xl">{card.value}</p>
          </article>
        ))}
      </section>
      {portfolioValue ? (
        <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/55 px-4 py-3 text-sm text-slate-300">
          Showing {portfolioValue.currency_code} market value.{" "}
          {portfolioHasMultipleCurrencies ? "Multiple currencies are kept separate." : "Single-currency summary."}{" "}
          Low-confidence and stale values are surfaced in the cards above without changing acquisition data.
        </div>
      ) : null}

      {physicalIntakeSummary || scanPipelineDash || marketWorkbenchRailsVisible || marketRegistryRailsVisible ? (
        <section className="mt-6 space-y-6" aria-label="Receiving, scan pipeline, and market intelligence">
          {physicalIntakeSummary ? (
            <section
              id="physical-intake"
              className="rounded-3xl border border-emerald-400/25 bg-emerald-950/20 p-5 shadow-xl shadow-black/15"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-emerald-200/70">Physical intake</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Receiving & scan placeholders</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
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
                <article className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Released, not received</p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {physicalIntakeSummary.counts.released_not_received}
                  </p>
                </article>
                <article className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Received, pending scan</p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {physicalIntakeSummary.counts.received_pending_scan}
                  </p>
                </article>
                <article className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                    Shipment overdue (expected ship)
                  </p>
                  <p className="mt-2 text-2xl font-semibold text-white">
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
              className="rounded-3xl border border-teal-400/25 bg-teal-950/15 p-5 shadow-xl shadow-black/15"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-teal-200/70">Bulk scan pipeline · read-only snapshot</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Session & queue visibility</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
                    Condensed aggregates (QA ledger, unresolved routing signals, queued high-res asks, presets, replay deltas).
                    Receiving placeholders stay in Physical intake above — avoids duplicating shipment vs scan semantics here.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <Link
                      to="/scan-sessions"
                      className="rounded-full border border-teal-400/35 px-3 py-1.5 font-semibold text-teal-100 transition hover:border-teal-300/55 hover:bg-teal-500/10"
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
                <p className="text-[11px] uppercase tracking-[0.16em] text-teal-200/70">
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
                  <article key={label} className="rounded-2xl border border-white/10 bg-slate-900/65 p-3">
                    <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-500">{label}</p>
                    <p className="mt-1 text-xl font-semibold text-white">{value}</p>
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
                  <article key={label} className="rounded-2xl border border-white/10 bg-slate-900/65 p-3">
                    <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-500">{label}</p>
                    <p className="mt-1 text-xl font-semibold text-white">{value}</p>
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
                    className="rounded-2xl border border-teal-500/15 bg-slate-900/65 p-3"
                  >
                    <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-500">{label}</p>
                    <p className="mt-1 text-xl font-semibold text-white">{value}</p>
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
              className="rounded-3xl border border-emerald-400/25 bg-emerald-950/12 p-5 shadow-xl shadow-black/15"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-emerald-200/70">Market sales foundation</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Read-only record preview</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
                    Deterministic sales records, source names, and normalization states from the new market-sales layer.
                    The dashboard stays read-only; see the ops panel for explicit import-upsert detail.
                  </p>
                </div>
                <Link
                  to="/ops"
                  className="rounded-full border border-emerald-400/35 px-3 py-1.5 text-xs font-semibold text-emerald-100 transition hover:border-emerald-300/60 hover:bg-emerald-500/10"
                >
                  Open ops view
                </Link>
              </div>
              {marketSalesLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading market sales preview…</p>
              ) : marketSalesError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{marketSalesError}</StatusBanner>
                </div>
              ) : marketSalesPreview.length === 0 ? (
                <p className="mt-4 text-sm text-slate-500">No market-sale records recorded yet.</p>
              ) : (
                <div className="mt-5 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
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
                    <tbody className="divide-y divide-white/10 text-slate-200">
                      {marketSalesPreview.slice(0, 6).map((row) => (
                        <tr key={row.id}>
                          <td className="p-3 align-top">
                            <div className="text-slate-100">{row.source_name}</div>
                            <div className="mt-1 text-[11px] text-slate-500">{row.source_type}</div>
                          </td>
                          <td className="p-3 align-top">
                            <div className="font-medium text-slate-100">{row.normalized_title ?? row.raw_title}</div>
                            <div className="mt-1 text-[11px] text-slate-400">
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

          {marketSaleReviewQueueSummaryLoading || marketSaleReviewQueueSummaryError || marketSaleReviewQueueSummary ? (
            <section className="mt-6 rounded-3xl border border-cyan-400/25 bg-cyan-950/12 p-5 shadow-xl shadow-black/15">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200/70">Market sale review queue</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Read-only review summary</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
                    Deterministic queue counts only. Operators can open the review workspace to update normalized fields
                    and log explicit review actions; the dashboard stays read-only.
                  </p>
                </div>
                <Link
                  to="/ops#market-sale-review-queue"
                  className="rounded-full border border-cyan-400/35 px-3 py-1.5 text-xs font-semibold text-cyan-100 transition hover:border-cyan-300/60 hover:bg-cyan-500/10"
                >
                  Open ops review queue
                </Link>
              </div>
              {marketSaleReviewQueueSummaryLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading market sale review summary…</p>
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
            <section className="mt-6 rounded-3xl border border-emerald-400/25 bg-emerald-950/12 p-5 shadow-xl shadow-black/15">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-emerald-200/70">Market comp eligibility</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Read-only readiness counts</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
                    Deterministic comp eligibility only. The dashboard stays read-only and shows lightweight readiness
                    counts; inspect the ops workspace for the full evidence drawer and filters.
                  </p>
                </div>
                <Link
                  to="/ops#market-comp-eligibility"
                  className="rounded-full border border-emerald-400/35 px-3 py-1.5 text-xs font-semibold text-emerald-100 transition hover:border-emerald-300/60 hover:bg-emerald-500/10"
                >
                  Open ops eligibility
                </Link>
              </div>
              {marketCompEligibilitySummaryLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading market comp eligibility summary…</p>
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
            <section className="mt-6 rounded-3xl border border-emerald-400/25 bg-emerald-950/12 p-5 shadow-xl shadow-black/15">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-emerald-200/70">Comparable sales</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Comp readiness overview</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
                    Lightweight grouped-comp summary. Open the ops explorer for full included and excluded sales evidence.
                  </p>
                </div>
                <Link
                  to="/ops#market-comps"
                  className="rounded-full border border-emerald-400/35 px-3 py-1.5 text-xs font-semibold text-emerald-100 transition hover:border-emerald-300/60 hover:bg-emerald-500/10"
                >
                  Open comp explorer
                </Link>
              </div>
              {marketCompsSummaryLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading comparable sales summary…</p>
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
            <section className="mt-6 rounded-3xl border border-cyan-400/25 bg-cyan-950/12 p-5 shadow-xl shadow-black/15">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200/70">Market FMV snapshots</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Deterministic valuation ledger</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
                    Snapshot-only FMV built from eligible comparable sales. This stays separate from manual inventory FMV edits
                    and never performs prediction, FX conversion, or automated portfolio mutation.
                  </p>
                </div>
                <Link
                  to="/ops#market-fmv"
                  className="rounded-full border border-cyan-400/35 px-3 py-1.5 text-xs font-semibold text-cyan-100 transition hover:border-cyan-300/60 hover:bg-cyan-500/10"
                >
                  Open ops FMV workspace
                </Link>
              </div>
              {marketFmvSummaryLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading market FMV snapshots…</p>
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
            <section className="mt-6 rounded-3xl border border-violet-400/25 bg-violet-950/12 p-5 shadow-xl shadow-black/15">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-violet-200/70">Market trend snapshots</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Deterministic trend signal strip</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
                    Compare FMV history over fixed windows to surface rising, falling, stable, and volatile movement without
                    forecasting, speculation scoring, or inventory mutation.
                  </p>
                </div>
                <Link
                  to="/ops#market-trends"
                  className="rounded-full border border-violet-400/35 px-3 py-1.5 text-xs font-semibold text-violet-100 transition hover:border-violet-300/60 hover:bg-violet-500/10"
                >
                  Open ops trend workspace
                </Link>
              </div>
              {marketTrendSummaryLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading market trend snapshots…</p>
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
            <section className="mt-6 rounded-3xl border border-violet-400/25 bg-violet-950/12 p-5 shadow-xl shadow-black/15">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-violet-200/70">Market match suggestions</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Read-only pending-count widget</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
                    Deterministic match suggestions only. Open the ops review workspace to inspect evidence and approve,
                    reject, or ignore suggestion artifacts without mutating canonical or inventory data.
                  </p>
                </div>
                <Link
                  to="/ops#market-match-suggestions"
                  className="rounded-full border border-violet-400/35 px-3 py-1.5 text-xs font-semibold text-violet-100 transition hover:border-violet-300/60 hover:bg-violet-500/10"
                >
                  Open ops match suggestions
                </Link>
              </div>
              {marketMatchSuggestionsPendingLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading market match suggestion count…</p>
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

          {user ? (
            <section
              id="dealer-command-dash"
              className="mt-6 rounded-3xl border border-lime-500/35 bg-slate-950/85 p-5 shadow-xl shadow-black/35"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-lime-200/85">Dealer command</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Operational cockpit · Bloomberg-style density</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
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
                <p className="mt-6 text-sm text-slate-400">Loading dealer rollups…</p>
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
                              value={snap ? `${formatCurrency(snap.gross_sales_30d)} / ${formatCurrency(snap.net_sales_30d)}` : "—"}
                            />
                          </div>
                          <p className="mt-2 text-[10px] text-slate-500">
                            *LOW bucket counts inventory rows flagged LOW / ILLIQUID minus ambiguous overlaps on the pinned snapshot_date.
                          </p>
                        </div>

                        <div className="grid gap-5 xl:grid-cols-2">
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">B · Alerts</p>
                            <div className="mt-2 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                              <table className="w-full border-collapse text-left text-xs">
                                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                                  <tr>
                                    <th className="p-3 font-medium">Severity</th>
                                    <th className="p-3 font-medium">Type</th>
                                    <th className="p-3 font-medium">Evidence</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-white/10 text-slate-200">
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
                                        <td className="p-3 text-slate-400">{a.message}</td>
                                      </tr>
                                    ))
                                  )}
                                </tbody>
                              </table>
                            </div>
                          </div>

                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">C · Operational feed</p>
                            <div className="mt-2 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                              <table className="w-full border-collapse text-left text-xs">
                                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                                  <tr>
                                    <th className="p-3 font-medium">Time</th>
                                    <th className="p-3 font-medium">Signal</th>
                                    <th className="p-3 font-medium">Summary</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-white/10 text-slate-200">
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
                                        <td className="p-3 text-slate-400">{evt.summary}</td>
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
                              <p className="mt-2 text-sm text-slate-400">Loading convention aggregates…</p>
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
                              <p className="mt-2 text-sm text-slate-400">Loading exporter rollups…</p>
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
                              <p className="mt-2 text-sm text-slate-400">Loading ledger summary…</p>
                            ) : salesLedgerSummaryError ? (
                              <StatusBanner tone="error">{salesLedgerSummaryError}</StatusBanner>
                            ) : salesLedgerSummary ? (
                              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                                <StatCard label="Gross 30d" value={snap ? formatCurrency(snap.gross_sales_30d) : formatCurrency(salesLedgerSummary.gross_sales_total)} />
                                <StatCard label="Net 30d" value={snap ? formatCurrency(snap.net_sales_30d) : formatCurrency(salesLedgerSummary.net_proceeds_total)} />
                                <StatCard label="Realized profit 30d" value={snap ? formatCurrency(snap.realized_profit_30d) : formatCurrency(salesLedgerSummary.realized_profit_total)} />
                                <StatCard label="Recent recorded rows" value={String(salesLedgerSummary.recent_sales.length)} />
                              </div>
                            ) : (
                              <p className="mt-2 text-sm text-slate-500">Ledger summary unavailable.</p>
                            )}
                          </div>

                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">G · Listing intelligence</p>
                            {listingIntelligenceSummaryLoading ? (
                              <p className="mt-2 text-sm text-slate-400">Loading intelligence rollup…</p>
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

          {user ? (
            <section
              id="grading-candidates-dash"
              className="mt-6 rounded-3xl border border-amber-400/35 bg-amber-950/15 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-amber-200/85">Grading operations</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">P37 grading candidate ledger</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
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
                <p className="mt-4 text-sm text-slate-400">Loading grading candidate rollup…</p>
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

          {user ? (
            <section
              id="grading-spreads-dash"
              className="mt-6 rounded-3xl border border-violet-400/35 bg-violet-950/15 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-violet-200/85">Grading economics</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">P37 raw-vs-graded spread engine</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
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
                <p className="mt-4 text-sm text-slate-400">Loading grading spread rollup…</p>
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

          {user ? (
            <section
              id="grading-roi-dash"
              className="mt-6 rounded-3xl border border-emerald-400/35 bg-emerald-950/15 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-emerald-200/85">Grading economics</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">P37 grading ROI engine</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
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
                <p className="mt-4 text-sm text-slate-400">Loading grading ROI rollup…</p>
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

          {user ? (
            <section
              id="grading-submission-dash"
              className="mt-6 rounded-3xl border border-sky-400/35 bg-sky-950/15 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-sky-200/85">Submission workflow</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">P37 submission batch operations</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
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
                <p className="mt-4 text-sm text-slate-400">Loading grading submissions…</p>
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

          {user ? (
            <section
              id="grading-reconciliation-dash"
              className="mt-6 rounded-3xl border border-cyan-400/35 bg-cyan-950/15 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200/85">Result reconciliation</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">P37 grading outcome reconciliation</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
                    Actual returned grades, ROI deltas, and grader performance snapshots without changing FMV,
                    pricing, or inventory automatically.
                  </p>
                </div>
                <Link
                  to="/ops#grading-reconciliation-ops"
                  className="rounded-xl border border-cyan-300/35 px-4 py-2 text-xs font-semibold text-cyan-100 transition hover:border-cyan-200/60 hover:bg-white/5"
                >
                  Ops reconciliation
                </Link>
              </div>
              {gradingReconciliationLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading grading reconciliation…</p>
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
                        <div key={`${row.grader}-${row.snapshot_date}`} className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                          <p className="text-sm font-semibold text-white">{row.grader}</p>
                          <p className="mt-1 text-xs text-slate-400">
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

          {user ? (
            <section
              id="grading-recommendation-dash"
              className="mt-6 rounded-3xl border border-fuchsia-400/35 bg-fuchsia-950/15 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-fuchsia-200/85">Recommendation engine</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">P37 grading decision support</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
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
                <p className="mt-4 text-sm text-slate-400">Loading grading recommendations…</p>
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

          {user ? (
            <section
              id="grading-risk-dash"
              className="mt-6 rounded-3xl border border-rose-400/35 bg-rose-950/12 p-5 shadow-xl shadow-black/18"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-rose-200/85">Risk and confidence</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">P37 grading uncertainty layer</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
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
                <p className="mt-4 text-sm text-slate-400">Loading grading risk snapshots…</p>
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

          {user ? (
            <section
              id="operational-reporting-dash"
              className="mt-6 rounded-3xl border border-sky-400/30 bg-slate-950/80 p-5 shadow-xl shadow-black/20"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-sky-200/80">Operational reporting</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">P36 closeout CSV registry</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
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
                <p className="mt-4 text-sm text-slate-400">Loading operational report fingerprints…</p>
              ) : opReportRollupsError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{opReportRollupsError}</StatusBanner>
                </div>
              ) : (
                <div className="mt-5 grid gap-4 xl:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Recent runs (14d)</p>
                    {opReportRollups && opReportRollups.recent_runs.length > 0 ? (
                      <ul className="mt-3 space-y-2 text-xs text-slate-200">
                        {opReportRollups.recent_runs.map((run) => (
                          <li key={run.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-2">
                            <div>
                              <p className="font-semibold text-white">{run.report_type}</p>
                              <p className="font-mono text-[10px] text-slate-500">
                                #{run.id} · {run.status} · rows {run.csv_row_count}
                              </p>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <span className="rounded-full border border-white/15 px-2 py-1 text-[10px] text-slate-300">
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

                  <div className="rounded-2xl border border-rose-400/35 bg-rose-950/20 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-rose-200/80">Failed reports</p>
                    {opReportRollups && opReportRollups.failed_runs.length > 0 ? (
                      <ul className="mt-3 space-y-2 text-xs text-rose-100">
                        {opReportRollups.failed_runs.map((run) => (
                          <li key={run.id} className="border-b border-white/10 pb-2">
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
              className="mt-6 rounded-3xl border border-amber-400/25 bg-amber-950/10 p-5 shadow-xl shadow-black/15"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-amber-200/80">Listing registry</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Canonical listing truth (manual + exports)</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
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
                <p className="mt-4 text-sm text-slate-400">Loading listing registry summary…</p>
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
                  <div className="mt-4 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
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
                        {listingRegistrySummary.recent_events.slice(0, 6).map((evt) => (
                          <tr key={evt.id}>
                            <td className="p-3 font-mono text-[11px] text-slate-300">#{evt.listing_id}</td>
                            <td className="p-3">{evt.event_type.replace(/_/g, " ")}</td>
                            <td className="p-3 text-slate-400">
                              {(evt.prior_status ?? "—")} → {(evt.new_status ?? "—")}
                            </td>
                            <td className="p-3 text-slate-400">{formatDateTime(evt.created_at)}</td>
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
              className="mt-6 rounded-3xl border border-fuchsia-400/25 bg-fuchsia-950/10 p-5 shadow-xl shadow-black/15"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-fuchsia-200/80">Listing intelligence</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Completeness, export readiness, and cleanup signals</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
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
                <p className="mt-4 text-sm text-slate-400">Loading listing intelligence summary…</p>
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
                  <div className="mt-4 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
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
                      <tbody className="divide-y divide-white/10 text-slate-200">
                        {listingIntelligenceSummary.recent_weak_or_incomplete.length === 0 ? (
                          <tr>
                            <td className="p-3 text-slate-400" colSpan={5}>
                              No weak or incomplete listings were found in the latest intelligence snapshot.
                            </td>
                          </tr>
                        ) : (
                          listingIntelligenceSummary.recent_weak_or_incomplete.slice(0, 6).map((row) => (
                            <tr key={row.id}>
                              <td className="p-3 font-mono text-[11px] text-slate-300">#{row.listing_id}</td>
                              <td className="p-3">{row.intelligence_status}</td>
                              <td className="p-3 text-slate-300">{row.completeness_score}</td>
                              <td className="p-3 text-slate-400">
                                {row.missing_required_fields_json.length > 0
                                  ? row.missing_required_fields_json.join(", ")
                                  : "—"}
                              </td>
                              <td className="p-3 text-slate-400">{row.stale_risk_flag ? "Yes" : "No"}</td>
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
              className="mt-6 rounded-3xl border border-sky-400/25 bg-sky-950/10 p-5 shadow-xl shadow-black/15"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-sky-200/80">Liquidity engine</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Evidence-backed inventory liquidity snapshot</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
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
                <p className="mt-4 text-sm text-slate-400">Loading liquidity summary…</p>
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
                        {liquiditySummary.recent_stale_events.length === 0 ? (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={4}>
                              No stale events recorded yet.
                            </td>
                          </tr>
                        ) : (
                          liquiditySummary.recent_stale_events.slice(0, 6).map((event) => (
                            <tr key={event.id}>
                              <td className="p-3 text-slate-200">{event.event_type.replace(/_/g, " ")}</td>
                              <td className="p-3 text-slate-300">{event.threshold_days}+ days</td>
                              <td className="p-3 text-slate-300">{event.days_active} days</td>
                              <td className="p-3 font-mono text-[11px] text-slate-300">#{event.listing_id}</td>
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
              className="mt-6 rounded-3xl border border-violet-400/25 bg-violet-950/10 p-5 shadow-xl shadow-black/15"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-violet-200/80">Convention ops</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Dealer workflow and show inventory snapshot</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
                    Deterministic convention assignments, movement history, temporary pricing, and active sale sessions.
                    This panel stays operational and never mutates inventory quantities or posts payments.
                  </p>
                </div>
                <Link
                  to="/ops#convention-ops"
                  className="rounded-full border border-violet-400/35 px-3 py-1.5 text-xs font-semibold text-violet-100 transition hover:border-violet-300/60 hover:bg-violet-500/10"
                >
                  Open ops convention
                </Link>
              </div>
              {conventionSummaryLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading convention summary…</p>
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
                        {conventionSummary.recent_events.length === 0 ? (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={4}>
                              No convention events recorded yet.
                            </td>
                          </tr>
                        ) : (
                          conventionSummary.recent_events.slice(0, 5).map((event) => (
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
            </section>
          ) : null}

          {salesLedgerSummaryLoading || salesLedgerSummaryError || salesLedgerSummary ? (
            <section
              id="sales-ledger-dash"
              className="mt-6 rounded-3xl border border-emerald-400/25 bg-emerald-950/10 p-5 shadow-xl shadow-black/15"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-emerald-200/80">Sales ledger</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Realized sale truth and profit snapshot</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
                    Recorded sales only. This ledger captures realized outcomes, linked listing transitions, and stable money
                    math without marketplace posting, inventory decrements, or hidden mutation.
                  </p>
                </div>
                <Link
                  to="/ops#sales-ledger-ops"
                  className="rounded-full border border-emerald-400/35 px-3 py-1.5 text-xs font-semibold text-emerald-100 transition hover:border-emerald-300/60 hover:bg-emerald-500/10"
                >
                  Open ops sales ledger
                </Link>
              </div>
              {salesLedgerSummaryLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading sales ledger summary…</p>
              ) : salesLedgerSummaryError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{salesLedgerSummaryError}</StatusBanner>
                </div>
              ) : salesLedgerSummary ? (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <StatCard label="Recorded sales" value={String(salesLedgerSummary.completed_sale_count)} />
                    <StatCard label="Gross sales" value={formatCurrency(salesLedgerSummary.gross_sales_total)} />
                    <StatCard label="Net proceeds" value={formatCurrency(salesLedgerSummary.net_proceeds_total)} />
                    <StatCard label="Realized profit" value={formatCurrency(salesLedgerSummary.realized_profit_total)} />
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {salesLedgerSummary.sales_count_by_channel.map((row) => (
                      <span
                        key={row.channel}
                        className="rounded-full border border-emerald-400/20 bg-emerald-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-100"
                      >
                        {row.channel.replace(/_/g, " ")} · {row.count}
                      </span>
                    ))}
                  </div>
                  <div className="mt-4 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
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
                      <tbody className="divide-y divide-white/10 text-slate-200">
                        {salesLedgerSummary.recent_sales.length === 0 ? (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={8}>
                              No recorded sales yet for this collector.
                            </td>
                          </tr>
                        ) : (
                          salesLedgerSummary.recent_sales.slice(0, 6).map((sale) => (
                            <tr key={sale.id}>
                              <td className="p-3 font-mono text-[11px] text-slate-300">#{sale.id}</td>
                              <td className="p-3 text-slate-200">{sale.channel.replace(/_/g, " ")}</td>
                              <td className="p-3 text-slate-200">{sale.status}</td>
                              <td className="p-3 text-slate-300">{formatCurrency(sale.gross_sale_amount)}</td>
                              <td className="p-3 text-slate-300">{formatCurrency(sale.net_proceeds_amount)}</td>
                              <td className="p-3 text-slate-300">{formatCurrency(sale.realized_profit_amount)}</td>
                              <td className="p-3 text-slate-400">{formatDate(sale.sale_date)}</td>
                              <td className="p-3 text-slate-400">{sale.listing_id ? `#${sale.listing_id}` : "—"}</td>
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
              className="mt-6 rounded-3xl border border-cyan-400/25 bg-cyan-950/12 p-5 shadow-xl shadow-black/15"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200/75">Marketplace exports</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">Deterministic CSV ledger (read-only)</h2>
                  <p className="mt-1 max-w-prose text-sm text-slate-400">
                    Channel-shaped listing files with checksums and append-only run history. Exports never post to marketplaces,
                    mutate listing status, or touch inventory balances. Bulk multi-select in the SPA is deferred; use the API for
                    batch <span className="font-mono text-[11px] text-cyan-100/90">POST /listing-export-runs</span> calls.
                  </p>
                </div>
                <Link
                  to="/ops#listing-export-ops"
                  className="rounded-full border border-cyan-400/35 px-3 py-1.5 text-xs font-semibold text-cyan-100 transition hover:border-cyan-300/60 hover:bg-cyan-500/10"
                >
                  Ops export runs
                </Link>
              </div>
              {listingExportDashLoading ? (
                <p className="mt-4 text-sm text-slate-400">Loading marketplace export summary…</p>
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
                  <div className="mt-4 overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
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
                      <tbody className="divide-y divide-white/10 text-slate-200">
                        {listingExportDash.recent_runs.length === 0 ? (
                          <tr>
                            <td className="p-4 text-slate-500" colSpan={7}>
                              No export attempts recorded yet for this collector.
                            </td>
                          </tr>
                        ) : (
                          listingExportDash.recent_runs.slice(0, 6).map((run) => (
                            <tr key={run.id}>
                              <td className="p-3 font-mono text-[11px] text-slate-300">#{run.id}</td>
                              <td className="p-3 text-slate-200">{run.channel}</td>
                              <td className="p-3 text-slate-200">{run.status}</td>
                              <td className="p-3 text-slate-300">{run.exported_listing_count}</td>
                              <td className="p-3 text-slate-300">{run.skipped_listing_count}</td>
                              <td className="p-3 font-mono text-[10px] text-slate-400">{shortenChecksum(run.checksum)}</td>
                              <td className="p-3 text-slate-400">
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
        <section className="mt-6 rounded-3xl border border-sky-400/25 bg-sky-950/12 p-5 shadow-xl shadow-black/15">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-[11px] uppercase tracking-[0.16em] text-sky-200/70">Market source registry</p>
              <h2 className="mt-1 text-lg font-semibold text-white">Registry and import-run summaries</h2>
              <p className="mt-1 max-w-prose text-sm text-slate-400">
                Deterministic source rows and append-only import-run history. The dashboard only reads these records;
                lifecycle changes remain in the ops API.
              </p>
            </div>
          </div>
          {marketSourcesLoading || marketImportRunsLoading ? (
            <p className="mt-4 text-sm text-slate-400">Loading market registry…</p>
          ) : marketSourcesError || marketImportRunsError ? (
            <div className="mt-4 space-y-3">
              {marketSourcesError ? <StatusBanner tone="error">{marketSourcesError}</StatusBanner> : null}
              {marketImportRunsError ? <StatusBanner tone="error">{marketImportRunsError}</StatusBanner> : null}
            </div>
          ) : (
            <div className="mt-5 grid gap-4 xl:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
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
                      <tbody className="text-slate-200">
                        {marketSources.slice(0, 8).map((row) => (
                          <tr key={row.id} className="border-t border-white/10">
                            <td className="py-2 pr-3 text-slate-100">{row.source_name}</td>
                            <td className="py-2 pr-3 text-slate-300">{row.source_type}</td>
                            <td className="py-2 pr-3 text-slate-300">{row.import_priority}</td>
                            <td className="py-2 text-slate-300">{row.enabled ? "Yes" : "No"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
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
                      <tbody className="text-slate-200">
                        {marketImportRuns.slice(0, 8).map((row) => (
                          <tr key={row.id} className="border-t border-white/10">
                            <td className="py-2 pr-3">
                              <div className="text-slate-100">{row.source_name}</div>
                              <div className="mt-1 text-[11px] text-slate-500">#{row.market_source_id}</div>
                            </td>
                            <td className="py-2 pr-3 text-slate-300">{row.status.replace(/_/g, " ")}</td>
                            <td className="py-2 pr-3 text-slate-300">
                              {row.imported_records}/{row.total_records} imported
                            </td>
                            <td className="py-2 text-slate-400">
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

      <details className="group mt-6 rounded-3xl border border-white/10 bg-slate-950/55 p-4 shadow-inner shadow-black/30 [&>summary::-webkit-details-marker]:hidden">
        <summary className="flex cursor-pointer list-none flex-wrap items-start justify-between gap-3 rounded-2xl border border-transparent p-3 transition hover:border-white/10 hover:bg-slate-950/40">
          <div>
            <h2 className="text-sm font-semibold text-white">Deterministic exports (CSV / JSON)</h2>
            <p className="mt-1 max-w-xl text-[11px] text-slate-400">
              Read-only snapshots aligned with risk, action center, order/arrival, run gaps, timeline, collection summary,
              and market intelligence (eligible comps, FMV/trend CSVs, inventory FMV subsets, deterministic JSON rollup).
              Filtered exports mirror the workbook controls below when exporting from filtered inventory grids.
            </p>
          </div>
          <span className="rounded-full border border-cyan-400/25 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/80">
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

      {inventoryRiskSummary ? (
        <section className="mt-4 rounded-3xl border border-white/10 bg-slate-900/60 p-5 shadow-xl shadow-black/15">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Inventory risk lanes</h2>
              <p className="mt-1 text-sm text-slate-400">
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
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryRiskSummary.critical_copies}</p>
            </article>
            <article className="rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-amber-100/80">High copies</p>
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryRiskSummary.high_copies}</p>
            </article>
            <article className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-cyan-100/80">Medium copies</p>
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryRiskSummary.medium_copies}</p>
            </article>
            <article className="rounded-2xl border border-violet-400/20 bg-violet-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-violet-100/80">Low copies</p>
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryRiskSummary.low_copies}</p>
            </article>
            <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Risk items</p>
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryRiskSummary.total_risk_items}</p>
            </article>
            <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Copies with risk</p>
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryRiskSummary.copies_with_risk}</p>
            </article>
          </div>
          <div className="mt-5 overflow-auto rounded-2xl border border-white/10 bg-slate-950/50 p-4">
            <h3 className="text-sm font-semibold text-white">Top action items</h3>
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
                    <tr key={item.inventory_copy_id} className="border-t border-white/5 align-top">
                      <td className="py-2 pr-3 font-medium text-white">
                        <Link to={`/inventory/${item.inventory_copy_id}`} className="hover:text-cyan-200">
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
                              className="inline-flex rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-200"
                            >
                              {inventoryRiskLabel(riskType)}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-2 text-slate-400">
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
        <section className="mt-4 rounded-3xl border border-white/10 bg-slate-900/60 p-5 shadow-xl shadow-black/15">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Workflow action center</h2>
              <p className="mt-1 text-sm text-slate-400">
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
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryActionSummary.critical_actions}</p>
            </article>
            <article className="rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-amber-100/80">High actions</p>
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryActionSummary.high_actions}</p>
            </article>
            <article className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-cyan-100/80">Medium actions</p>
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryActionSummary.medium_actions}</p>
            </article>
            <article className="rounded-2xl border border-violet-400/20 bg-violet-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-violet-100/80">Low actions</p>
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryActionSummary.low_actions}</p>
            </article>
            <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Copies with actions</p>
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryActionSummary.copies_with_actions}</p>
            </article>
            <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Total actions</p>
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryActionSummary.total_actions}</p>
            </article>
          </div>
          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/50 p-4">
              <h3 className="text-sm font-semibold text-white">Actions by category</h3>
              <ul className="mt-3 space-y-2 text-xs text-slate-300">
                {inventoryActionSummary.by_category
                  .filter((row) => row.count > 0)
                  .slice(0, 8)
                  .map((row) => (
                    <li key={row.key ?? "null"} className="flex justify-between gap-3 border-b border-white/5 pb-2">
                      <span className="text-slate-400">
                        {row.key ? inventoryActionCenterCategoryUiLabel(row.key as InventoryActionCenterCategory) : "—"}
                      </span>
                      <span className="font-semibold text-white">{row.count}</span>
                    </li>
                  ))}
              </ul>
            </div>
            <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/50 p-4">
              <h3 className="text-sm font-semibold text-white">Copies needing the most workflows</h3>
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
                      <tr key={item.inventory_copy_id} className="border-t border-white/5 align-top">
                        <td className="py-2 pr-3 font-medium text-white">
                          <Link to={`/inventory/${item.inventory_copy_id}`} className="hover:text-cyan-200">
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
                        <td className="py-2 pr-3 text-slate-400">{item.action_count}</td>
                        <td className="py-2 text-slate-400">
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
        <section className="mt-4 rounded-3xl border border-white/10 bg-slate-900/60 p-5 shadow-xl shadow-black/15">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Collection timeline (activity history)</h2>
              <p className="mt-1 text-sm text-slate-400">
                Persisted timestamps for purchases, arrivals, scans/OCR (and replays), link decisions, duplicate reviews,
                conflicts, variants — valuations never appear here.
              </p>
              <div className="mt-4 flex flex-wrap gap-2 border-t border-white/5 pt-3">
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
                      className="flex min-w-[10rem] flex-1 gap-3 rounded-2xl border border-cyan-400/25 bg-slate-950/50 p-3"
                    >
                      <span className={`mt-1 inline-block size-2.5 shrink-0 rounded-full ${timelineDotClass(event)}`} />
                      <div className="text-xs">
                        <p className="font-semibold text-cyan-100">{describeHistoricalTimelineEvent(event)}</p>
                        <p className="mt-1 text-[11px] text-slate-500">
                          {new Intl.DateTimeFormat("en-US", {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          }).format(new Date(event.occurred_at))}
                        </p>
                        <p className="mt-1 font-medium text-white">
                          {event.publisher} · {event.series_title} #{event.issue_number}
                        </p>
                        <Link
                          to={`/inventory/${event.inventory_copy_id}`}
                          className="mt-2 inline-flex text-[11px] font-semibold text-cyan-200 hover:text-cyan-100"
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
              <h3 className="text-sm font-semibold text-white">Recent reconciliation & reviews</h3>
              <div className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-950/50">
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
                        <tr key={`review-${event.stable_id}`} className="border-t border-white/5">
                          <td className="px-4 py-2 text-[11px] text-slate-400">
                            {new Intl.DateTimeFormat("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                              hour: "numeric",
                              minute: "2-digit",
                            }).format(new Date(event.occurred_at))}
                          </td>
                          <td className="px-4 py-2 font-semibold text-white">
                            {describeHistoricalTimelineEvent(event)}
                          </td>
                          <td className="px-4 py-2">
                            {event.publisher} · {event.series_title} #{event.issue_number}
                          </td>
                          <td className="px-4 py-2">
                            <Link
                              className="text-cyan-200 hover:text-cyan-50"
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
              <h3 className="text-sm font-semibold text-white">Latest collection activity</h3>
              <div className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-950/40">
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
                      <tr key={`all-${event.stable_id}`} className="border-t border-white/5 align-top">
                        <td className="px-4 py-2 text-[11px] text-slate-400 whitespace-nowrap">
                          {new Intl.DateTimeFormat("en-US", {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                            hour: "numeric",
                            minute: "2-digit",
                          }).format(new Date(event.occurred_at))}
                        </td>
                        <td className="px-4 py-2">
                          <p className="font-semibold text-white">{describeHistoricalTimelineEvent(event)}</p>
                          <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">{event.event_type}</p>
                        </td>
                        <td className="px-4 py-2">
                          <p>{event.publisher}</p>
                          <p className="text-[11px] text-slate-400">
                            {event.series_title} #{event.issue_number}
                          </p>
                        </td>
                        <td className="px-4 py-2">
                          <Link
                            className="text-cyan-200 hover:text-cyan-50"
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
        <section className="mt-4 rounded-3xl border border-white/10 bg-slate-900/60 p-5 shadow-xl shadow-black/15">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Order / arrival lanes</h2>
              <p className="mt-1 text-sm text-slate-400">
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
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-cyan-100/80">
                Releases this week
              </p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {orderArrivalBucketCount(orderArrivalSummary, "releases_this_week")}
              </p>
            </article>
            <article className="rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-amber-100/80">
                Released / not received
              </p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {orderArrivalBucketCount(orderArrivalSummary, "released_not_received")}
              </p>
            </article>
            <article className="rounded-2xl border border-violet-400/20 bg-violet-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-violet-100/80">Shipping soon</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {orderArrivalBucketCount(orderArrivalSummary, "expected_to_ship_soon")}
              </p>
            </article>
            <article className="rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-rose-100/80">Shipment overdue</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {orderArrivalBucketCount(orderArrivalSummary, "overdue_expected_ship")}
              </p>
            </article>
          </div>
          <div className="mt-5 overflow-auto rounded-2xl border border-white/10 bg-slate-950/50 p-4">
            <h3 className="text-sm font-semibold text-white">Upcoming preorder / arrivals</h3>
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
                    <tr key={item.inventory_copy_id} className="border-t border-white/5 align-top">
                      <td className="py-2 pr-3 font-medium text-white">
                        <Link to={`/inventory/${item.inventory_copy_id}`} className="hover:text-cyan-200">
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
                      <td className="py-2 text-slate-400">{item.evidence_preview.join(" · ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      ) : null}

      {((inventoryIntelSummary && inventoryIntelHealth) ||
        (collectionAnalyticsSummary && collectionAnalyticsQuality)) ? (
        <details className="mt-4 rounded-3xl border border-white/10 bg-slate-900/60 p-5 shadow-xl shadow-black/15 [&>summary::-webkit-details-marker]:hidden">
          <summary className="flex cursor-pointer list-none flex-wrap items-start justify-between gap-3 rounded-2xl border border-white/5 bg-slate-950/45 p-4">
            <div>
              <h2 className="text-lg font-semibold text-white">Coverage rollup & publishers</h2>
              <p className="mt-1 max-w-prose text-sm text-slate-400">
                Collapsed by default — ownership mix, health buckets, preorder exposure, OCR/canon coverage and
                deterministic publisher totals (mirrors Ops collection analytics wording).
              </p>
            </div>
          </summary>
          <div className="mt-8 space-y-12 border-t border-white/5 pt-8">
            {inventoryIntelSummary && inventoryIntelHealth ? (
              <div className="space-y-4">
                <div>
                  <h3 className="text-base font-semibold text-white">Inventory intelligence rollup</h3>
                  <p className="mt-1 text-sm text-slate-400">
                    Scans/OCR backlog, unresolved review workloads, deterministic duplicate/variant clustering touch —
                    read-only projections.
                  </p>
                </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-5">
            <article className="rounded-xl border border-white/10 bg-slate-950/55 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">In hand</p>
              <p className="mt-1 text-lg font-semibold text-white">{inventoryIntelSummary.ownership_in_hand}</p>
            </article>
            <article className="rounded-xl border border-white/10 bg-slate-950/55 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Preorder</p>
              <p className="mt-1 text-lg font-semibold text-white">{inventoryIntelSummary.ownership_preorder}</p>
            </article>
            <article className="rounded-xl border border-white/10 bg-slate-950/55 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Ordered (not recv)</p>
              <p className="mt-1 text-lg font-semibold text-white">
                {inventoryIntelSummary.ownership_ordered_not_received}
              </p>
            </article>
            <article className="rounded-xl border border-white/10 bg-slate-950/55 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Cancelled</p>
              <p className="mt-1 text-lg font-semibold text-white">{inventoryIntelSummary.ownership_cancelled}</p>
            </article>
            <article className="rounded-xl border border-white/10 bg-slate-950/55 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Unknown ops state</p>
              <p className="mt-1 text-lg font-semibold text-white">
                {inventoryIntelSummary.ownership_unknown_state}
              </p>
            </article>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Tracked copies</p>
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryIntelSummary.total_inventory_copies}</p>
            </article>
            <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Cover scans</p>
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryIntelSummary.scanned_copies}</p>
              <p className="mt-1 text-[11px] text-slate-500">
                {inventoryIntelSummary.unscanned_copies} still unscanned · OCR pending{" "}
                {inventoryIntelSummary.ocr_pending_copies}, complete {inventoryIntelSummary.ocr_complete_copies} · corrupt
                /failed cover processing {inventoryIntelSummary.cover_processing_failed_copies} · OCR failed{" "}
                {inventoryIntelSummary.ocr_failed_copies}
              </p>
            </article>
            <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Unresolved rollups</p>
              <p className="mt-2 text-2xl font-semibold text-white">
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
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryIntelHealth.healthy}</p>
            </article>
            <article className="rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-amber-100/80">Needs review</p>
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryIntelHealth.needs_review}</p>
            </article>
            <article className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-cyan-100/80">Incomplete</p>
              <p className="mt-2 text-2xl font-semibold text-white">{inventoryIntelHealth.incomplete}</p>
              <p className="mt-1 text-[11px] text-slate-400">
                Blocked copies: {inventoryIntelHealth.blocked} (normally cancelled/stranded workflows)
              </p>
            </article>
          </div>
              </div>
            ) : null}
            {collectionAnalyticsSummary && collectionAnalyticsQuality ? (
              <div className="space-y-4">
                <div>
                  <h3 className="text-base font-semibold text-white">Publisher & quality rollups</h3>
                  <p className="mt-1 text-sm text-slate-400">
                    As-of anchor:{" "}
                    <span className="font-semibold text-slate-200">
                      {collectionAnalyticsSummary.generated_as_of_date}
                    </span>
                  </p>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Preorder exposure</p>
              <p className="mt-2 text-2xl font-semibold text-white">{collectionAnalyticsSummary.preorder_copies}</p>
              <p className="mt-1 text-[11px] text-slate-500">
                Missing calendar cues: {collectionAnalyticsSummary.preorder_missing_calendar_copies}
              </p>
            </article>
            <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">In hand copies</p>
              <p className="mt-2 text-2xl font-semibold text-white">{collectionAnalyticsSummary.in_hand_copies}</p>
              <p className="mt-1 text-[11px] text-slate-500">Total tracked: {collectionAnalyticsSummary.total_copies}</p>
            </article>
            <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Unresolved review workload</p>
              <p className="mt-2 text-2xl font-semibold text-white">{collectionAnalyticsSummary.unresolved_review_copies}</p>
              <p className="mt-1 text-[11px] text-slate-500">Distinct copies in needs_review health bucket.</p>
            </article>
            <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Canonical-linked copies</p>
              <p className="mt-2 text-2xl font-semibold text-white">{collectionAnalyticsSummary.canonical_linked_copies}</p>
              <p className="mt-1 text-[11px] text-slate-500">Unscanned primaries: {collectionAnalyticsSummary.unscanned_primary_copies}</p>
            </article>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <article className="rounded-2xl border border-emerald-400/25 bg-emerald-400/5 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-200">OCR complete</p>
              <p className="mt-2 text-xl font-semibold text-white">
                {collectionAnalyticsQuality.inventory_quality.ocr_complete.percent}%{" "}
                <span className="text-[11px] text-slate-400">
                  ({collectionAnalyticsQuality.inventory_quality.ocr_complete.numerator}/
                  {collectionAnalyticsQuality.inventory_quality.ocr_complete.denominator})
                </span>
              </p>
            </article>
            <article className="rounded-2xl border border-cyan-400/25 bg-cyan-400/5 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-cyan-100">Canonical coverage</p>
              <p className="mt-2 text-xl font-semibold text-white">
                {collectionAnalyticsQuality.inventory_quality.canonical_linked.percent}%{" "}
                <span className="text-[11px] text-slate-400">
                  ({collectionAnalyticsQuality.inventory_quality.canonical_linked.numerator}/
                  {collectionAnalyticsQuality.inventory_quality.canonical_linked.denominator})
                </span>
              </p>
            </article>
            <article className="rounded-2xl border border-amber-400/25 bg-amber-400/5 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-100">Dup ownership touch</p>
              <p className="mt-2 text-xl font-semibold text-white">
                {collectionAnalyticsQuality.inventory_quality.duplicate_ownership_exposure_copies.percent}%{" "}
                <span className="text-[11px] text-slate-400">
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
              <p className="mt-2 text-xl font-semibold text-white">
                {
                  collectionAnalyticsQuality.inventory_quality.unresolved_open_conflict_copies.percent
                }%
                <span className="text-[11px] text-slate-400">
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
              <p className="mt-2 text-xl font-semibold text-white">
                {
                  collectionAnalyticsQuality.inventory_quality.primary_cover_failed_processing.percent
                }%
                <span className="text-[11px] text-slate-400">
                  {" "}
                  ({collectionAnalyticsQuality.inventory_quality.primary_cover_failed_processing.numerator}/
                  {collectionAnalyticsQuality.inventory_quality.primary_cover_failed_processing.denominator})
                </span>
              </p>
            </article>
            <article className="rounded-2xl border border-orange-400/25 bg-orange-400/5 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-orange-100">Latest OCR failures</p>
              <p className="mt-2 text-xl font-semibold text-white">
                {collectionAnalyticsQuality.inventory_quality.primary_cover_failed_ocr.percent}%
                <span className="text-[11px] text-slate-400">
                  {" "}
                  ({collectionAnalyticsQuality.inventory_quality.primary_cover_failed_ocr.numerator}/
                  {collectionAnalyticsQuality.inventory_quality.primary_cover_failed_ocr.denominator})
                </span>
              </p>
            </article>
          </div>
          {collectionAnalyticsPublishers && collectionAnalyticsPublishers.publishers.length ? (
            <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/50 p-4">
              <h3 className="text-sm font-semibold text-white">Publisher breakdown</h3>
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
              </div>
            ) : null}
          </div>
        </details>
      ) : null}

      {duplicateOwnershipReport ? (
        <details
          className="mt-4 rounded-3xl border border-white/10 bg-slate-900/65 p-5 shadow-xl shadow-black/15 [&>summary::-webkit-details-marker]:hidden"
          open={
            duplicateOwnershipReport.summary.probable_accidental_duplicate_groups > 0 ||
            duplicateOwnershipReport.summary.unresolved_duplicate_groups > 0
          }
        >
          <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white">Duplicate ownership clustering</h2>
                <p className="mt-1 text-sm text-slate-400">
                  Read-only owner overlap buckets (deterministic clustering — never auto-dedupe or silent metadata edits).
                  <span className="ml-1 text-[11px] text-slate-500"> Tap header to collapse.</span>
                </p>
              </div>
            </div>
          </summary>
          <div className="mt-4 border-t border-white/5 pt-4">
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-7">
            <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Overlap groups</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {duplicateOwnershipReport.summary.total_groups}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">Multi-copy groups only (&ge; two inventory IDs).</p>
            </article>
            <article className="rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-rose-100">
                Probable accidental
              </p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {duplicateOwnershipReport.summary.probable_accidental_duplicate_groups}
              </p>
              <p className="mt-1 text-[11px] text-slate-100/80">
                Heuristic raw-heavy clusters flagged by deterministic scan/canonical cues.
              </p>
            </article>
            <article className="rounded-2xl border border-cyan-400/25 bg-cyan-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-cyan-100">
                Preorder + received
              </p>
              <p className="mt-2 text-2xl font-semibold text-white">
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
              <p className="mt-2 text-2xl font-semibold text-white">
                {duplicateOwnershipReport.summary.duplicate_scan_only_groups}
              </p>
            </article>
            <article className="rounded-2xl border border-cyan-300/25 bg-white/5 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-cyan-100">Graded + raw</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {duplicateOwnershipReport.summary.graded_plus_raw_groups}
              </p>
            </article>
            <article className="rounded-2xl border border-amber-300/35 bg-amber-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-amber-100">
                Unresolved duplicates
              </p>
              <p className="mt-2 text-2xl font-semibold text-white">
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
              <p className="mt-2 text-2xl font-semibold text-white">
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
        <details className="mt-4 rounded-3xl border border-white/10 bg-slate-900/65 p-5 shadow-xl shadow-black/15 [&>summary::-webkit-details-marker]:hidden">
          <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
            <div>
              <h2 className="text-lg font-semibold text-white">Series progress & missing-issue rows</h2>
              <p className="mt-1 text-sm text-slate-400">
                Canonical series grouping, deterministic issue ordering, gaps by ownership / release visibility — tap to
                expand metrics.
              </p>
            </div>
          </summary>
          <div className="mt-4 border-t border-white/5 pt-4">
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-7">
            <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Tracked series</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {runDetectionReport.summary.total_series_groups}
              </p>
            </article>
            <article className="rounded-2xl border border-amber-400/25 bg-amber-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-amber-100">Partial runs</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {runDetectionReport.summary.partial_run_groups}
              </p>
            </article>
            <article className="rounded-2xl border border-emerald-400/25 bg-emerald-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-emerald-100">
                Completed runs
              </p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {runDetectionReport.summary.complete_limited_series_groups}
              </p>
            </article>
            <article className="rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-rose-100">
                Incomplete limited
              </p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {runDetectionReport.summary.incomplete_limited_series_groups}
              </p>
            </article>
            <article className="rounded-2xl border border-cyan-400/25 bg-cyan-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-cyan-100">Likely ongoing series</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {runDetectionReport.summary.probable_ongoing_series_groups}
              </p>
            </article>
            <article className="rounded-2xl border border-violet-400/25 bg-violet-400/10 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-violet-100">Missing issue rows</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {runDetectionReport.summary.total_missing_issue_rows}
              </p>
              <p className="mt-1 text-[11px] text-slate-100/70">
                Confirmed {runDetectionReport.summary.confirmed_missing_rows} · likely{" "}
                {runDetectionReport.summary.likely_missing_rows}
              </p>
            </article>
            <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-300">Future / unresolved</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {runDetectionReport.summary.preorder_pending_rows +
                  runDetectionReport.summary.unreleased_future_issue_rows +
                  runDetectionReport.summary.unresolved_identity_gap_rows}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Preorder {runDetectionReport.summary.preorder_pending_rows} · unreleased{" "}
                {runDetectionReport.summary.unreleased_future_issue_rows} · identity{" "}
                {runDetectionReport.summary.unresolved_identity_gap_rows}
              </p>
            </article>
          </div>
          </div>
        </details>
      ) : null}

      {!hasPerformanceData ? (
        <div className="mt-6">
          <EmptyState
            title="No performance data yet"
            description="Performance leaders appear after you create orders and start assigning FMV values to inventory copies."
            action={
              <div className="flex flex-col gap-3 sm:flex-row">
                <Link
                  to="/orders/import"
                  className="rounded-2xl border border-white/10 px-4 py-3 text-center text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
                >
                  Paste Receipt/Text
                </Link>
                <Link
                  to="/orders/new"
                  className="rounded-2xl bg-cyan-400 px-4 py-3 text-center text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
                >
                  Add Your First Order
                </Link>
              </div>
            }
          />
        </div>
      ) : (
        <details className="group mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-4 shadow-xl shadow-black/15 [&>summary::-webkit-details-marker]:hidden">
          <summary className="cursor-pointer list-none">
            <h2 className="text-lg font-semibold text-white">Portfolio performance (FMV)</h2>
            <p className="mt-1 max-w-xl text-sm text-slate-400">
              Separate from deterministic intelligence lanes. Expand for gain / loss boards after FMV assignments.
            </p>
          </summary>
          <div className="mt-6 grid gap-4 border-t border-white/5 pt-6 xl:grid-cols-3">
          {analyticsSections.map((section) => (
            <article
              key={section.title}
              className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-lg shadow-black/20"
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-white">{section.title}</h2>
                  <p className="mt-1 text-sm text-slate-400">
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
                      className="block rounded-2xl border border-white/10 bg-slate-950/70 p-4 transition hover:border-cyan-300/40 hover:bg-slate-950"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-medium text-white">{performanceLabel(item)}</p>
                          <p className="mt-1 text-sm text-slate-400">{item.publisher}</p>
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
                                ? "text-cyan-200"
                                : gainLossClass(section.valueFor(item))
                            }`}
                          >
                            {formatCurrency(section.valueFor(item))}
                          </p>
                        </div>
                      </div>
                    </Link>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-slate-950/50 p-4 text-sm text-slate-500">
                    {section.empty}
                  </div>
                )}
              </div>
            </article>
          ))}
          </div>
        </details>
      )}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
          <div className="flex flex-col gap-4">
            <form className="grid gap-3 lg:grid-cols-[2fr_repeat(4,1fr)]" onSubmit={applySearch}>
              <input
                type="search"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Search by title, publisher, issue, or cover"
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40"
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40"
              />
              <select
                value={holdStatus}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setHoldStatus(event.target.value);
                  })
                }
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
              >
                <option value="">All grade statuses</option>
                <option value="raw">Raw</option>
                <option value="submitted">Submitted</option>
                <option value="graded">Graded</option>
              </select>
              <button
                type="submit"
                className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40"
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
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
              <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-slate-200">
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
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
              <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-slate-200 md:col-span-2">
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
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
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
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
                className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
              >
                Reset filters
              </button>
            </div>

            <div className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-slate-950/50 p-4 md:flex-row md:items-center md:justify-between">
              <p className="text-sm text-slate-400">
                {selectedIds.length} selected for bulk updates
              </p>
              <div className="flex flex-col gap-3 sm:flex-row">
                <select
                  value={bulkHoldStatus}
                  onChange={(event) =>
                    setBulkHoldStatus(event.target.value as "hold" | "sell" | "sold")
                  }
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                >
                  <option value="hold">Mark Hold</option>
                  <option value="sell">Mark Sell</option>
                  <option value="sold">Mark Sold</option>
                </select>
                <button
                  type="button"
                  disabled={!selectedIds.length || isSaving}
                  onClick={() => void applyBulkHoldUpdate()}
                  className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Apply bulk update
                </button>
              </div>
            </div>
          </div>
      </section>

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 shadow-xl shadow-black/20">
          <div className="border-b border-white/10 px-5 py-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-white">Inventory</h2>
                <p className="text-sm text-slate-400">
                  Page {page} of {pageCount} with {total} tracked copies
                </p>
              </div>
              {isLoading ? <p className="text-sm text-slate-400">Refreshing inventory...</p> : null}
            </div>
          </div>

          {!inventory.length ? (
            <div className="p-5">
              <EmptyState
                title="No inventory yet"
                description="Create your first order to populate the dashboard with inventory copies, valuation controls, and detail pages."
                action={
                  <div className="flex flex-col gap-3 sm:flex-row">
                    <Link
                      to="/orders/import"
                      className="rounded-2xl border border-white/10 px-4 py-3 text-center text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
                    >
                      Import Order
                    </Link>
                    <Link
                      to="/orders/new"
                      className="rounded-2xl bg-cyan-400 px-4 py-3 text-center text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
                    >
                      Add Order
                    </Link>
                  </div>
                }
              />
            </div>
          ) : (
            <>
          <div className="hidden overflow-x-auto xl:block">
            <table className="min-w-full text-left text-sm text-slate-300">
              <thead className="border-b border-white/10 text-xs uppercase tracking-[0.16em] text-slate-500">
                <tr>
                  <th className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={Boolean(inventory.length) && selectedIds.length === inventory.length}
                      onChange={toggleSelectAll}
                    />
                  </th>
                  <th className="px-4 py-3">Title</th>
                  <th className="px-4 py-3">Issue</th>
                  <th className="px-4 py-3">Release meta</th>
                  <th className="px-4 py-3">Publisher</th>
                  <th className="px-4 py-3">Cover / Variant</th>
                  <th className="px-4 py-3">Retailer</th>
                  <th className="px-4 py-3">Order Date</th>
                  <th className="px-4 py-3">Acquisition</th>
                  <th className="px-4 py-3">Market FMV</th>
                  <th className="px-4 py-3">Valuation</th>
                  <th className="px-4 py-3">Manual FMV</th>
                  <th className="px-4 py-3">Gain / Loss</th>
                  <th className="px-4 py-3">Grade</th>
                  <th className="px-4 py-3">Hold</th>
                  <th className="px-4 py-3">Stars</th>
                  <th className="px-4 py-3">Notes</th>
                  <th className="px-4 py-3">Details</th>
                </tr>
              </thead>
              <tbody>
                {inventory.map((item) => (
                  <tr key={item.inventory_copy_id} className="border-b border-white/5 align-top">
                    <td className="px-4 py-3.5">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(item.inventory_copy_id)}
                        onChange={() => toggleSelection(item.inventory_copy_id)}
                      />
                    </td>
                    <td className="px-4 py-3.5 font-medium text-white">
                      <p>{item.title}</p>
                      <p className="mt-1 text-[11px]">
                        <span
                          className={`inline-flex rounded-full border px-2 py-1 font-semibold ${assetStateTone(
                            item.asset_state,
                          )}`}
                        >
                          {assetStateLabel(item.asset_state)}
                        </span>
                      </p>
                      <InventoryIntelBadges item={item} />
                      <InventoryRiskBadges risks={item.inventory_risks} />
                      <InventoryActionCenterBadges attachment={item.inventory_action_center} />
                      <OrderArrivalBadges classifications={item.order_arrival_classifications} />
                    </td>
                    <td className="px-4 py-3.5">#{item.issue_number}</td>
                    <td className="align-top">{inventoryReleaseChronologyCell(item)}</td>
                    <td className="px-4 py-3.5">{item.publisher}</td>
                    <td className="px-4 py-3.5 text-slate-300">
                      {variantLabel(item) || "Standard cover"}
                    </td>
                    <td className="px-4 py-3.5">{item.retailer}</td>
                    <td className="px-4 py-3.5">{formatDate(item.order_date)}</td>
                    <td className="px-4 py-3.5">{formatCurrency(item.acquisition_cost)}</td>
                    <td className="px-4 py-3.5">
                      <div className="space-y-1">
                        <p className="font-medium text-white">
                          {item.current_market_fmv
                            ? formatCurrencyWithCode(item.current_market_fmv, item.fmv_currency_code ?? "USD")
                            : "—"}
                        </p>
                        {item.fmv_stale_data ? (
                          <p className="text-[11px] text-amber-200">Stale data</p>
                        ) : null}
                        {!item.current_market_fmv || item.valuation_scope === "no_market_data" ? (
                          <p className="text-[11px] text-slate-500">No market data</p>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`inline-flex rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${
                          item.valuation_scope === "no_market_data"
                            ? "border-slate-400/30 bg-white/5 text-slate-300"
                            : item.valuation_scope === "cancelled_excluded"
                              ? "border-rose-400/35 bg-rose-400/10 text-rose-100"
                              : item.valuation_scope === "low_confidence"
                                ? "border-amber-400/35 bg-amber-400/10 text-amber-100"
                                : "border-cyan-400/35 bg-cyan-400/10 text-cyan-100"
                        }`}
                      >
                        {item.valuation_scope?.replace(/_/g, " ") ?? "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex gap-2">
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={fMvDrafts[item.inventory_copy_id] ?? ""}
                          onChange={(event) =>
                            setFmvDrafts((current) => ({
                              ...current,
                              [item.inventory_copy_id]: event.target.value,
                            }))
                          }
                          className="w-24 rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none transition focus:border-cyan-300/40"
                        />
                        <button
                          type="button"
                          disabled={isSaving}
                          onClick={() =>
                            void saveInventoryUpdate(item.inventory_copy_id, {
                              current_fmv: normalizeDecimalInput(
                                fMvDrafts[item.inventory_copy_id] ?? "",
                              ),
                            })
                          }
                          className="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
                        >
                          Save
                        </button>
                      </div>
                    </td>
                    <td className={`px-4 py-3.5 ${gainLossClass(item.gain_loss)}`}>
                      {formatCurrency(item.gain_loss)}
                    </td>
                    <td className="px-4 py-3.5">
                      <select
                        value={gradeDrafts[item.inventory_copy_id] ?? item.grade_status}
                        onChange={(event) =>
                          setGradeDrafts((current) => ({
                            ...current,
                            [item.inventory_copy_id]:
                              event.target.value as InventoryItem["grade_status"],
                          }))
                        }
                        onBlur={() =>
                          void saveInventoryUpdate(item.inventory_copy_id, {
                            grade_status: gradeDrafts[item.inventory_copy_id] ?? item.grade_status,
                          })
                        }
                        className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      >
                        <option value="raw">Raw</option>
                        <option value="submitted">Submitted</option>
                        <option value="graded">Graded</option>
                      </select>
                    </td>
                    <td className="px-4 py-3.5">
                      <select
                        value={holdDrafts[item.inventory_copy_id] ?? item.hold_status}
                        onChange={(event) =>
                          setHoldDrafts((current) => ({
                            ...current,
                            [item.inventory_copy_id]:
                              event.target.value as InventoryItem["hold_status"],
                          }))
                        }
                        onBlur={() =>
                          void saveInventoryUpdate(item.inventory_copy_id, {
                            hold_status: holdDrafts[item.inventory_copy_id] ?? item.hold_status,
                          })
                        }
                        className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      >
                        <option value="hold">Hold</option>
                        <option value="sell">Sell</option>
                        <option value="sold">Sold</option>
                      </select>
                    </td>
                    <td className="px-4 py-3.5">
                      <select
                        value={starDrafts[item.inventory_copy_id] ?? ""}
                        onChange={(event) =>
                          setStarDrafts((current) => ({
                            ...current,
                            [item.inventory_copy_id]: event.target.value,
                          }))
                        }
                        onBlur={() =>
                          void saveInventoryUpdate(item.inventory_copy_id, {
                            star_rating: starDrafts[item.inventory_copy_id]
                              ? Number(starDrafts[item.inventory_copy_id])
                              : null,
                          })
                        }
                        className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      >
                        <option value="">-</option>
                        <option value="1">1</option>
                        <option value="2">2</option>
                        <option value="3">3</option>
                        <option value="4">4</option>
                        <option value="5">5</option>
                      </select>
                    </td>
                    <td className="px-4 py-3.5">
                      <button
                        type="button"
                        onClick={() => {
                          setActiveNotesItem(item);
                          setNotesDraft(item.condition_notes ?? "");
                        }}
                        className="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
                      >
                        Notes
                      </button>
                    </td>
                    <td className="px-4 py-3.5">
                      <Link
                        to={`/inventory/${item.inventory_copy_id}`}
                        className="inline-flex rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-200 transition hover:border-cyan-300/50 hover:bg-cyan-400/20"
                      >
                        View Details
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="space-y-4 p-5 xl:hidden">
            {inventory.map((item) => (
              <article
                key={item.inventory_copy_id}
                className="rounded-3xl border border-white/10 bg-slate-950/70 p-4 shadow-lg shadow-black/10"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                      Inventory Copy #{item.inventory_copy_id}
                    </p>
                    <h3 className="mt-1 text-lg font-semibold text-white">
                      {item.title} #{item.issue_number}
                    </h3>
                    <p className="mt-1 text-sm text-slate-400">
                      {item.publisher} | {variantLabel(item) || "Standard cover"}
                    </p>
                    <p className="mt-2">
                      <span
                        className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold ${assetStateTone(
                          item.asset_state,
                        )}`}
                      >
                        {assetStateLabel(item.asset_state)}
                      </span>
                    </p>
                    <InventoryIntelBadges item={item} />
                    <InventoryRiskBadges risks={item.inventory_risks} />
                    <InventoryActionCenterBadges attachment={item.inventory_action_center} />
                    <OrderArrivalBadges classifications={item.order_arrival_classifications} />
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(item.inventory_copy_id)}
                      onChange={() => toggleSelection(item.inventory_copy_id)}
                    />
                    <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300">
                      {item.hold_status}
                    </span>
                  </div>
                </div>
                <div className="mt-4 grid gap-3 text-sm text-slate-300 sm:grid-cols-2">
                  <div>
                    <p className="text-slate-500">Retailer</p>
                    <p>{item.retailer}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Order Date</p>
                    <p>{formatDate(item.order_date)}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Release chronology</p>
                    {inventoryReleaseChronologyCell(item)}
                  </div>
                  <div>
                    <p className="text-slate-500">Acquisition</p>
                    <p>{formatCurrency(item.acquisition_cost)}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Gain / Loss</p>
                    <p className={gainLossClass(item.gain_loss)}>{formatCurrency(item.gain_loss)}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Current FMV</p>
                    <div className="mt-1 flex gap-2">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={fMvDrafts[item.inventory_copy_id] ?? ""}
                        onChange={(event) =>
                          setFmvDrafts((current) => ({
                            ...current,
                            [item.inventory_copy_id]: event.target.value,
                          }))
                        }
                        className="w-full rounded-xl border border-white/10 bg-slate-900/80 px-3 py-2 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          void saveInventoryUpdate(item.inventory_copy_id, {
                            current_fmv: normalizeDecimalInput(
                              fMvDrafts[item.inventory_copy_id] ?? "",
                            ),
                          })
                        }
                        className="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-100"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                  <div>
                    <p className="text-slate-500">Grade Status</p>
                    <select
                      value={gradeDrafts[item.inventory_copy_id] ?? item.grade_status}
                      onChange={(event) =>
                        setGradeDrafts((current) => ({
                          ...current,
                          [item.inventory_copy_id]:
                            event.target.value as InventoryItem["grade_status"],
                        }))
                      }
                      onBlur={() =>
                        void saveInventoryUpdate(item.inventory_copy_id, {
                          grade_status: gradeDrafts[item.inventory_copy_id] ?? item.grade_status,
                        })
                      }
                      className="mt-1 w-full rounded-xl border border-white/10 bg-slate-900/80 px-3 py-2 text-sm text-white outline-none"
                    >
                      <option value="raw">Raw</option>
                      <option value="submitted">Submitted</option>
                      <option value="graded">Graded</option>
                    </select>
                  </div>
                  <div>
                    <p className="text-slate-500">Hold Status</p>
                    <select
                      value={holdDrafts[item.inventory_copy_id] ?? item.hold_status}
                      onChange={(event) =>
                        setHoldDrafts((current) => ({
                          ...current,
                          [item.inventory_copy_id]:
                            event.target.value as InventoryItem["hold_status"],
                        }))
                      }
                      onBlur={() =>
                        void saveInventoryUpdate(item.inventory_copy_id, {
                          hold_status: holdDrafts[item.inventory_copy_id] ?? item.hold_status,
                        })
                      }
                      className="mt-1 w-full rounded-xl border border-white/10 bg-slate-900/80 px-3 py-2 text-sm text-white outline-none"
                    >
                      <option value="hold">Hold</option>
                      <option value="sell">Sell</option>
                      <option value="sold">Sold</option>
                    </select>
                  </div>
                  <div>
                    <p className="text-slate-500">Star Rating</p>
                    <select
                      value={starDrafts[item.inventory_copy_id] ?? ""}
                      onChange={(event) =>
                        setStarDrafts((current) => ({
                          ...current,
                          [item.inventory_copy_id]: event.target.value,
                        }))
                      }
                      onBlur={() =>
                        void saveInventoryUpdate(item.inventory_copy_id, {
                          star_rating: starDrafts[item.inventory_copy_id]
                            ? Number(starDrafts[item.inventory_copy_id])
                            : null,
                        })
                      }
                      className="mt-1 w-full rounded-xl border border-white/10 bg-slate-900/80 px-3 py-2 text-sm text-white outline-none"
                    >
                      <option value="">-</option>
                      <option value="1">1</option>
                      <option value="2">2</option>
                      <option value="3">3</option>
                      <option value="4">4</option>
                      <option value="5">5</option>
                    </select>
                  </div>
                  <div className="sm:col-span-2">
                    <div className="flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={() => {
                          setActiveNotesItem(item);
                          setNotesDraft(item.condition_notes ?? "");
                        }}
                        className="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-100"
                      >
                        Edit notes
                      </button>
                      <Link
                        to={`/inventory/${item.inventory_copy_id}`}
                        className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-200 transition hover:border-cyan-300/50 hover:bg-cyan-400/20"
                      >
                        View Details
                      </Link>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
            </>
          )}

          <div className="flex items-center justify-between border-t border-white/10 px-5 py-4">
            <button
              type="button"
              disabled={page === 1}
              onClick={() => setPage((currentPage) => Math.max(1, currentPage - 1))}
              className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-sm text-slate-400">
              Showing page {page} of {pageCount}
            </span>
            <button
              type="button"
              disabled={page >= pageCount}
              onClick={() => setPage((currentPage) => Math.min(pageCount, currentPage + 1))}
              className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          </div>
      </section>

      {activeNotesItem ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4">
          <div className="w-full max-w-2xl rounded-3xl border border-white/10 bg-slate-900 p-6 shadow-2xl shadow-black/30">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-semibold text-white">Condition Notes</h3>
                <p className="mt-2 text-sm text-slate-400">
                  {activeNotesItem.title} #{activeNotesItem.issue_number}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setActiveNotesItem(null)}
                className="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-100"
              >
                Close
              </button>
            </div>

            <textarea
              value={notesDraft}
              onChange={(event) => setNotesDraft(event.target.value)}
              maxLength={2000}
              rows={8}
              className="mt-6 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40"
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
                className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Save notes
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
