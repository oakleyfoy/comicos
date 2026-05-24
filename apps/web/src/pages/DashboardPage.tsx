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

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
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

export function DashboardPage() {
  const { user } = useAuth();

  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [performance, setPerformance] = useState<PortfolioPerformance | null>(null);
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
    ] = await Promise.all([
      apiClient.getInventorySummary(),
      apiClient.getPortfolioPerformance(),
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
    ]);
    setSummary(summaryResponse);
    setPerformance(performanceResponse);
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
        ] =
          await Promise.all([
            apiClient.getInventorySummary(),
            apiClient.getPortfolioPerformance(),
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
          ]);

        if (ignore) {
          return;
        }

        setSummary(summaryResponse);
        setPerformance(performanceResponse);
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

  const cards = [
    { label: "Copies", value: summary?.total_copies ?? 0 },
    { label: "In Hand", value: summary?.in_hand_copies ?? 0 },
    { label: "Ordered", value: summary?.ordered_not_received_copies ?? 0 },
    { label: "Preordered", value: summary?.preordered_copies ?? 0 },
    { label: "Cancelled", value: summary?.cancelled_copies ?? 0 },
    { label: "Cost Basis", value: formatCurrency(summary?.total_cost_basis ?? "0") },
    { label: "Current FMV", value: formatCurrency(summary?.total_current_fmv ?? "0") },
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
              to="/orders/new"
              className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
            >
              Add Order
            </Link>
          </>
        }
      />

      <section className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {cards.map((card) => (
            <article
              key={card.label}
              className="rounded-2xl border border-white/10 bg-slate-900/70 p-4 shadow-lg shadow-black/20"
            >
              <p className="text-xs font-medium uppercase tracking-[0.16em] text-slate-500">
                {card.label}
              </p>
              <p className="mt-2 text-2xl font-semibold text-white sm:text-3xl">{card.value}</p>
            </article>
          ))}
      </section>

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-950/55 p-4 shadow-inner shadow-black/30">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Deterministic exports</h2>
            <p className="mt-1 max-w-xl text-[11px] text-slate-400">
              Read-only CSV/JSON snapshots aligned with Intelligence surfaces. Outputs omit FMV/speculation paths and reflect
              the same filters applied to inventory reports when exporting the filtered workbook.
            </p>
          </div>
          <span className="rounded-full border border-cyan-400/25 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/80">
            Owner scope
          </span>
        </div>
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
            onClick={() => void runInventoryExport(() => apiClient.downloadOwnerReportsCollectionSummaryJson())}
          >
            Collection summary JSON
          </button>
        </div>
      </section>

      {inventoryRiskSummary ? (
        <section className="mt-4 rounded-3xl border border-white/10 bg-slate-900/60 p-5 shadow-xl shadow-black/15">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Inventory risk</h2>
              <p className="mt-1 text-sm text-slate-400">
                Deterministic attention surface derived from existing conflicts, canonical review, scan/OCR quality,
                preorder gaps, duplicate uncertainty, and run-detection signals. No pricing, speculation, or automated
                fixes.
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
              <h2 className="text-lg font-semibold text-white">Inventory action center</h2>
              <p className="mt-1 text-sm text-slate-400">
                Workflow-facing rollup of deterministic inventory attention items (risk lanes, duplicate and variant
                intelligence, preorder gaps where not already covered elsewhere, and arrivals). Same priority scale as
                inventory risk — read-only, no mutations.
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
                  .sort((a, b) => b.count - a.count)
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
              <h2 className="text-lg font-semibold text-white">Collection timeline & activity</h2>
              <p className="mt-1 text-sm text-slate-400">
                Deterministic timestamps from purchases, arrivals, scans, OCR, link decisions, replays, duplicate
                reviews, conflicts, and variant-family signals — no valuations, summaries, or hidden inference.
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
              <h2 className="text-lg font-semibold text-white">Order pipeline & arrivals</h2>
              <p className="mt-1 text-sm text-slate-400">
                Derived from purchase/release/ship timestamps and normalized order statuses. Read-only logistics
                overlay (no FMV/pricing/speculation/automatic receiving).
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

      {inventoryIntelSummary && inventoryIntelHealth ? (
        <section className="mt-4 rounded-3xl border border-white/10 bg-slate-900/60 p-5 shadow-xl shadow-black/15">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Inventory intelligence</h2>
              <p className="mt-1 text-sm text-slate-400">
                Read-only deterministic signals derived from scans, preorder calendar coverage, OCR and cover
                processing state, unresolved conflicts/suggestions/duplicate-groups, plus probable clustering for
                dedupe and variant surfaces. Nothing here modifies records.
              </p>
            </div>
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
        </section>
      ) : null}

      {collectionAnalyticsSummary && collectionAnalyticsQuality ? (
        <section className="mt-4 rounded-3xl border border-white/10 bg-slate-900/60 p-5 shadow-xl shadow-black/15">
          <div>
            <h2 className="text-lg font-semibold text-white">Collection analytics</h2>
            <p className="mt-1 text-sm text-slate-400">
              Deterministic portfolio rollups across publishers, fulfillment, scans, OCR, canonical linkage, preorder
              calendar exposure, and duplicate-ownership clustering. Reporting only (no mutations, pricing, or AI scoring).
              As-of anchor:{" "}
              <span className="font-semibold text-slate-200">{collectionAnalyticsSummary.generated_as_of_date}</span>
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
        </section>
      ) : null}

      {duplicateOwnershipReport ? (
        <section className="mt-4 rounded-3xl border border-white/10 bg-slate-900/65 p-5 shadow-xl shadow-black/15">
          <div>
            <h2 className="text-lg font-semibold text-white">Duplicate ownership intelligence</h2>
            <p className="mt-1 text-sm text-slate-400">
              Read-only rollup that clusters copies you personally own using metadata identity overlap, deterministic
              duplicate-scan intelligence, canonical edges, duplicate reviews, preorder + in-hand overlaps, graded vs raw
              pairings, and approved human duplicate/same-cover links. There is never automatic dedupe, deletion, or
              silent metadata rewriting from this lane.
            </p>
          </div>
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
        </section>
      ) : null}

      {runDetectionReport ? (
        <section className="mt-4 rounded-3xl border border-white/10 bg-slate-900/65 p-5 shadow-xl shadow-black/15">
          <div>
            <h2 className="text-lg font-semibold text-white">Run detection</h2>
            <p className="mt-1 text-sm text-slate-400">
              Read-only series progress computed from canonical series identity, deterministic issue ordering,
              registry-backed known issues, ownership state, and future release visibility. This lane never creates a
              wantlist or mutates metadata.
            </p>
          </div>
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
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-cyan-100">Probable ongoing</p>
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
        </section>
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
        <section className="mt-6 grid gap-4 xl:grid-cols-3">
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
        </section>
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
                  <th className="px-4 py-3">Current FMV</th>
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
