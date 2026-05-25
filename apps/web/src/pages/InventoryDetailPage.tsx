import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  resolveCoverImageOcrHeadline,
  scannerRecommendedUseLabel,
  type CoverLinkDecisionType,
  type CoverLinkRelationshipType,
  type CoverImageOcrHeadlineStatus,
  type CoverOcrCandidateReviewStatus,
  type InventoryDetail,
  type InventoryActionCenterAttachment,
  type InventoryActionCenterCategory,
  type InventoryCopyIntelligenceSignalsSummary,
  type InventoryOwnershipNormalized,
  type InventoryIntelligenceHealthLevel,
  type InventoryRiskPriority,
  type InventoryRiskRead,
  type InventoryRiskType,
  type InventoryFmvSnapshot,
  type MarketFmvSnapshotListResponse,
  type MarketFmvSnapshotRead,
  type MarketComparableListResponse,
  type OrderArrivalClassification,
  type InventoryUpdatePayload,
  type CoverRelationshipGraphEdge,
  type CoverRelationshipGraphRead,
  type DuplicateScanCandidatesResponse,
  type DuplicateScanClusterRead,
  type DuplicateScanDuplicatePeerRead,
  type DuplicateScanEvidenceFlags,
  type DuplicateScanSuppressedPairRead,
  type DuplicateOwnershipAttachment,
  type DuplicateOwnershipClassification,
  type RunDetectionAttachment,
  type RunDetectionSeriesStatus,
  type VariantFamilyCandidatesResponse,
  type VariantFamilyClusterRead,
  type VariantFamilyEvidenceFlags,
  type VariantFamilyPeerRead,
  type CanonicalIssueLinkSuggestionRead,
  type CollectionAnalyticsSummary,
  type RelationshipConflictListResponse,
  type RelationshipConflictRead,
  type CollectionHistoricalTimelineEventsResponse,
  type CollectionHistoricalTimelineGrouping,
  type InventoryScanQaPanelRead,
  type ScanSessionRoutingRead,
} from "../api/client";

import { describeHistoricalTimelineEvent, timelineDotClass } from "../lib/collectionHistoricalTimelineUi";

import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { HighResReviewInventorySection } from "../components/HighResReviewInventorySection";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function assetStateLabel(state: InventoryDetail["asset_state"]): string {
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

function assetStateTone(state: InventoryDetail["asset_state"]): string {
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

function normalizedOwnershipIntelLabelMini(state: InventoryOwnershipNormalized): string {
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

function inventoryIntelHealthClassMini(level: InventoryIntelligenceHealthLevel): string {
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

function InventoryDetailIntelStrip(props: { intel: InventoryCopyIntelligenceSignalsSummary }): JSX.Element {
  const { intel } = props;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      <span className="inline-flex rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-200">
        Ownership: {normalizedOwnershipIntelLabelMini(intel.ownership_state)}
      </span>
      <span
        className={`inline-flex rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${inventoryIntelHealthClassMini(
          intel.inventory_health,
        )}`}
      >
        Inventory health: {intel.inventory_health.replace(/_/g, " ")}
      </span>
      {!intel.has_cover_scan ? (
        <span className="inline-flex rounded-full border border-white/15 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-300">
          Cover scan missing
        </span>
      ) : null}
      {intel.preorder_missing_release_calendar ? (
        <span className="inline-flex rounded-full border border-amber-400/35 bg-amber-400/10 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-50">
          Preorder missing calendar
        </span>
      ) : null}
      {(intel.has_open_relationship_conflict ||
        intel.has_pending_canonical_suggestion ||
        intel.in_pending_duplicate_inventory_group ||
        intel.touches_probable_duplicate_scan_cluster ||
        intel.touches_probable_variant_family_cluster) ? (
        <span className="inline-flex rounded-full border border-violet-400/35 bg-violet-400/10 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-violet-50">
          Unresolved intelligence signals present
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

function orderArrivalClassificationLabel(value: OrderArrivalClassification): string {
  switch (value) {
    case "upcoming_preorder":
      return "Upcoming preorder";
    case "releases_this_week":
      return "Release scheduled this week";
    case "released_not_received":
      return "Released — not yet received";
    case "expected_to_ship_soon":
      return "Expected shipment in the next 14 days";
    case "overdue_expected_ship":
      return "Expected shipment date passed";
    case "received_recently":
      return "Received within the last 30 days";
    case "cancelled_order":
      return "Cancelled order line";
    case "missing_release_date":
      return "Preorder / unreleased without release date";
    case "missing_expected_ship_date":
      return "Awaiting expected ship date metadata";
    default:
      return value;
  }
}

function orderArrivalClassificationTone(value: OrderArrivalClassification): string {
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

function InventoryRunDetectionCallout(props: { attachment: RunDetectionAttachment }): JSX.Element {
  const { attachment } = props;
  const tone =
    attachment.series_status === "complete_limited_series"
      ? "border-emerald-400/35 bg-emerald-400/10"
      : attachment.series_status === "probable_ongoing_series"
        ? "border-cyan-400/35 bg-cyan-400/10"
        : attachment.series_status === "partial_run"
          ? "border-amber-400/35 bg-amber-400/10"
          : attachment.series_status === "incomplete_limited_series"
            ? "border-rose-400/40 bg-rose-400/10"
            : "border-white/15 bg-white/5";

  return (
    <div className={`mt-4 rounded-2xl border p-4 ${tone}`}>
      <p className="text-xs uppercase tracking-[0.16em] text-slate-200">Series progress</p>
      <p className="mt-2 text-lg font-semibold text-white">{runDetectionStatusLabel(attachment.series_status)}</p>
      <p className="mt-1 font-mono text-[11px] text-slate-300">{attachment.series_key}</p>
      <p className="mt-3 text-xs text-slate-200">
        Owned issues:{" "}
        {attachment.owned_issue_numbers.length ? attachment.owned_issue_numbers.join(", ") : "No deterministic issue list yet."}
      </p>
      {attachment.missing_issue_numbers.length ? (
        <p className="mt-2 text-xs text-rose-100">
          Missing issues: {attachment.missing_issue_numbers.join(", ")}
        </p>
      ) : null}
      {attachment.pending_issue_numbers.length ? (
        <p className="mt-2 text-xs text-cyan-100">
          Future / pending issues: {attachment.pending_issue_numbers.join(", ")}
        </p>
      ) : null}
      <p className="mt-3 text-[11px] text-slate-300">
        This panel is informational only and does not create wantlist entries or mutate canonical metadata.
      </p>
    </div>
  );
}

function InventoryDuplicateOwnershipCallout(props: { attachment: DuplicateOwnershipAttachment }): JSX.Element {
  const { attachment } = props;

  const tone =
    attachment.classification === "probable_accidental_duplicate" ||
    attachment.classification === "unresolved_duplicate"
      ? "border-rose-400/40 bg-rose-400/10"
      : attachment.classification === "duplicate_scan_only"
        ? "border-violet-400/35 bg-violet-400/10"
        : "border-cyan-400/35 bg-cyan-400/10";

  return (
    <div className={`mt-4 rounded-2xl border p-4 ${tone}`}>
      <p className="text-xs uppercase tracking-[0.16em] text-slate-200">Duplicate ownership group</p>
      <p className="mt-2 text-lg font-semibold text-white">{duplicateOwnershipClassificationLabel(attachment.classification)}</p>
      <p className="mt-1 font-mono text-[11px] text-slate-300">{attachment.group_key}</p>
      <p className="mt-3 text-xs text-slate-200">
        Peer copies in this deterministic cluster:{` `}
        {attachment.sibling_inventory_copy_ids.length ? (
          <span className="inline-flex flex-wrap gap-2">
            {attachment.sibling_inventory_copy_ids.map((peerId) => (
              <Link
                key={peerId}
                to={`/inventory/${peerId}`}
                className="rounded-full border border-white/20 px-2 py-0.5 text-[11px] font-semibold text-white transition hover:border-cyan-300/40"
              >
                #{peerId}
              </Link>
            ))}
          </span>
        ) : (
          <span className="text-slate-400">No additional siblings surfaced (unexpected for clusters).</span>
        )}
      </p>
      <p className="mt-3 text-[11px] text-slate-300">
        Signals are deterministic and recomputed live; they never mutate catalog metadata from this insight alone.
      </p>
    </div>
  );
}

function relationshipConflictTypeLabel(value: RelationshipConflictRead["conflict_type"]): string {
  return value.replace(/_/g, " ");
}

function relationshipConflictSeverityTone(value: RelationshipConflictRead["severity"]): string {
  switch (value) {
    case "critical":
      return "border-rose-400/30 bg-rose-400/10 text-rose-100";
    case "warning":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    default:
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
  }
}

function summarizeDuplicateEvidence(flags: DuplicateScanEvidenceFlags): string {
  const parts: string[] = [];



  if (flags.human_duplicate_scan_confirmed) {
    parts.push("human-confirmed duplicate scan");




  }



  if (flags.sha256_exact_match) {


    parts.push("exact SHA256");


  }



  if (flags.probable_duplicate_scan_match_group) {
    parts.push("duplicate-scan match group");


  }



  if (flags.fingerprint_similarity_probable) {
    parts.push("fingerprint similarity");


  }



  if (flags.supporting_shared_upcs.length) {
    parts.push(`UPC support: ${flags.supporting_shared_upcs.join(", ")}`);
  }




  return parts.length ? parts.join(" · ") : "linked by cluster topology only";


}



function summarizeVariantFamilyEvidence(flags: VariantFamilyEvidenceFlags): string {


  const parts: string[] = [];


  if (flags.human_variant_family) {


    parts.push("human-confirmed variant family");


  }


  if (flags.probable_variant_family_group) {


    parts.push("match candidate probable variant-family group");


  }


  if (flags.same_issue_divergent_fingerprint) {


    parts.push("same issue · divergent fingerprint");


  }


  if (flags.metadata_identity_normalized) {


    parts.push("normalized metadata identity match");


  }


  if (flags.ocr_title_issue_exact_pairwise) {


    parts.push("OCR title+issue pairwise exact");


  }


  if (flags.publisher_exact_pairwise) {


    parts.push("publisher exact");


  }


  if (flags.fingerprint_divergent_signal) {


    parts.push("divergent fingerprint signal");


  }


  if (flags.supporting_shared_upcs.length) {


    parts.push(`UPC support: ${flags.supporting_shared_upcs.join(", ")}`);


  }


  return parts.length ? parts.join(" · ") : "cluster-linked / transitive relation only";


}

function summarizeCanonicalIssueEvidence(evidence: Record<string, unknown>): string {
  const parts: string[] = [];
  if (typeof evidence.metadata_identity_key === "string" && evidence.metadata_identity_key) {
    parts.push(`identity ${evidence.metadata_identity_key}`);
  }
  if (typeof evidence.normalized_title === "string" && evidence.normalized_title) {
    parts.push(`title ${evidence.normalized_title}`);
  }
  if (typeof evidence.normalized_issue_number === "string" && evidence.normalized_issue_number) {
    parts.push(`#${evidence.normalized_issue_number}`);
  }
  if (typeof evidence.normalized_publisher === "string" && evidence.normalized_publisher) {
    parts.push(`publisher ${evidence.normalized_publisher}`);
  }
  if (typeof evidence.supporting_peer_count === "number") {
    parts.push(`${evidence.supporting_peer_count} related cover${evidence.supporting_peer_count === 1 ? "" : "s"}`);
  }
  return parts.join(" · ") || "review stored evidence";
}

function summarizeRelationshipConflictEvidence(evidence: Record<string, unknown>): string {
  const parts: string[] = [];
  if (Array.isArray(evidence.signals) && evidence.signals.length !== 0) {
    parts.push(`signals: ${evidence.signals.map((item) => String(item)).join(", ")}`);
  }
  if (Array.isArray(evidence.source_suggestion_targets) && evidence.source_suggestion_targets.length !== 0) {
    parts.push(`source: ${evidence.source_suggestion_targets.map((item) => String(item)).join(", ")}`);
  }
  if (Array.isArray(evidence.related_suggestion_targets) && evidence.related_suggestion_targets.length !== 0) {
    parts.push(`related: ${evidence.related_suggestion_targets.map((item) => String(item)).join(", ")}`);
  }
  if (typeof evidence.warning_type === "string") {
    parts.push(`warning: ${evidence.warning_type}`);
  }
  if (typeof evidence.ocr_reconciliation_warning_id === "number") {
    parts.push(`reconciliation warning #${evidence.ocr_reconciliation_warning_id}`);
  }
  if (Array.isArray(evidence.cycle_cover_image_ids) && evidence.cycle_cover_image_ids.length !== 0) {
    parts.push(`cycle covers: ${evidence.cycle_cover_image_ids.join(", ")}`);
  }
  return parts.join(" · ") || "deterministic conflict evidence recorded";
}


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

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
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

function marketFmvBucketTone(value: string): string {
  switch (value) {
    case "very_high":
    case "high":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "medium":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "volatile":
    case "low":
    case "very_low":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "moderate":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    default:
      return "border-white/10 bg-white/5 text-slate-300";
  }
}

function marketFmvScopeLabel(value: string): string {
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

function variantLabel(item: InventoryDetail): string {
  return [item.cover_name, item.printing, item.ratio, item.variant_type]
    .filter(Boolean)
    .join(" / ");
}

function coverProcessingTone(status: InventoryDetail["cover_images"][number]["processing_status"]): string {
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

function coverMatchingTone(status: InventoryDetail["cover_images"][number]["matching_status"]): string {
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

function coverImageOcrHeadlineTone(headline: CoverImageOcrHeadlineStatus): string {
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

function formatMaybeTimestamp(value: string | null): string {
  return value ? formatTimestamp(value) : "Not yet";
}

function ocrCandidateReviewCardClass(status: CoverOcrCandidateReviewStatus): string {
  switch (status) {
    case "approved":
      return "border-emerald-400/35 bg-emerald-500/5";
    case "rejected":
      return "border-rose-400/35 bg-rose-500/5";
    default:
      return "border-white/10 bg-slate-900/80";
  }
}

function barcodeCandidateReviewCardClass(
  status: InventoryDetail["cover_images"][number]["barcode_candidates"][number]["review_state"],
): string {
  switch (status) {
    case "approved":
      return "border-emerald-400/35 bg-emerald-500/5";
    case "rejected":
      return "border-rose-400/35 bg-rose-500/5";
    default:
      return "border-white/10 bg-slate-900/80";
  }
}

function shortFingerprint(value: string): string {
  if (value.length <= 16) {
    return value;
  }
  return `${value.slice(0, 8)}...${value.slice(-8)}`;
}

function matchCandidateTone(
  bucket: InventoryDetail["cover_images"][number]["match_candidates"][number]["confidence_bucket"],
): string {
  switch (bucket) {
    case "very_high":
      return "border-emerald-300/45 bg-emerald-400/15 text-emerald-50";
    case "high":
      return "border-emerald-400/35 bg-emerald-500/10 text-emerald-100";
    case "medium":
      return "border-amber-400/35 bg-amber-500/10 text-amber-100";
    case "low":
      return "border-cyan-400/30 bg-cyan-500/10 text-cyan-100";
    default:
      return "border-slate-500/30 bg-slate-500/10 text-slate-200";
  }
}

function matchGroupingTone(
  bucket: InventoryDetail["cover_images"][number]["match_candidates"][number]["grouping_confidence_bucket"],
): string {
  if (!bucket) {
    return "border-white/10 bg-white/5 text-slate-300";
  }
  return matchCandidateTone(bucket);
}

function formatGroupingType(
  value: InventoryDetail["cover_images"][number]["match_candidates"][number]["grouping_type"],
): string {
  return value ? value.replace(/_/g, " ") : "ungrouped";
}

function rankingReasonStrings(
  candidate: InventoryDetail["cover_images"][number]["match_candidates"][number],
  key: "conflicting_signals" | "missing_signals",
): string[] {
  const value = candidate.ranking_reason_json[key];
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function ocrQualitySeverityClass(
  severity: InventoryDetail["cover_images"][number]["ocr_quality_analyses"][number]["severity"],
): string {
  switch (severity) {
    case "critical":
      return "border-rose-400/35 bg-rose-500/10 text-rose-100";
    case "warning":
      return "border-amber-400/35 bg-amber-500/10 text-amber-100";
    default:
      return "border-cyan-400/30 bg-cyan-500/10 text-cyan-100";
  }
}

function ocrReconciliationSeverityClass(
  severity: InventoryDetail["cover_images"][number]["ocr_reconciliation_warnings"][number]["severity"],
): string {
  switch (severity) {
    case "critical":
      return "border-rose-400/35 bg-rose-500/10 text-rose-100";
    case "warning":
      return "border-amber-400/35 bg-amber-500/10 text-amber-100";
    default:
      return "border-cyan-400/30 bg-cyan-500/10 text-cyan-100";
  }
}

function ocrReconciliationStatusClass(
  status: InventoryDetail["cover_images"][number]["ocr_reconciliation_warnings"][number]["status"],
): string {
  switch (status) {
    case "acknowledged":
      return "border-cyan-400/30 text-cyan-100";
    case "dismissed":
      return "border-slate-500/40 text-slate-300";
    default:
      return "border-white/15 text-slate-100";
  }
}

const MANUAL_COVER_ASSIGN_INFO =
  "Manual assignment links the existing image record. It does not duplicate or analyze the image.";
const MANUAL_COVER_ASSIGN_MULTI_COPY =
  "Use this when an import created multiple inventory copies and the cover scan needs to be attached to the correct copy.";
const LINK_RELATIONSHIP_OPTIONS: CoverLinkRelationshipType[] = [
  "same_cover",
  "same_issue",
  "duplicate_scan",
  "variant_family",
  "unrelated",
];

function formatLinkRelationship(value: CoverLinkRelationshipType): string {
  return value.replace(/_/g, " ");
}

function linkDecisionTone(decisionType: CoverLinkDecisionType, relationshipType: CoverLinkRelationshipType): string {
  if (decisionType === "rejected_link" || relationshipType === "unrelated") {
    return "border-rose-400/30 bg-rose-500/10 text-rose-100";
  }
  if (decisionType === "approved_link") {
    return "border-emerald-400/30 bg-emerald-500/10 text-emerald-100";
  }
  return "border-amber-400/30 bg-amber-500/10 text-amber-100";
}

const GRAPH_LANE_SECTION_ORDER: CoverRelationshipGraphEdge["display_lane"][] = [
  "strong",
  "related",
  "needs_review",
  "blocked",
];

function graphLaneSectionTitle(lane: CoverRelationshipGraphEdge["display_lane"]): string {
  switch (lane) {
    case "strong":
      return "Strong ties (human-approved same-cover / duplicate-scan)";
    case "related":
      return "Related covers (human-approved same-issue / variant-family)";
    case "blocked":
      return "Blocked / rejected (human unrelated)";
    case "needs_review":
      return "Marked needs review";
    default:
      return lane;
  }
}

function edgesByLane(edges: CoverRelationshipGraphEdge[]): Map<CoverRelationshipGraphEdge["display_lane"], CoverRelationshipGraphEdge[]> {
  const map = new Map<CoverRelationshipGraphEdge["display_lane"], CoverRelationshipGraphEdge[]>();
  for (const lane of GRAPH_LANE_SECTION_ORDER) {
    map.set(lane, []);
  }
  for (const edge of edges) {
    const bucket = map.get(edge.display_lane) ?? [];
    bucket.push(edge);
    map.set(edge.display_lane, bucket);
  }
  for (const [lane, list] of map) {
    map.set(
      lane,
      [...list].sort(
        (a, b) =>
          a.source_cover_image_id - b.source_cover_image_id ||
          a.candidate_cover_image_id - b.candidate_cover_image_id ||
          a.decision_id - b.decision_id,
      ),
    );
  }
  return map;
}

export function InventoryDetailPage() {
  const { inventoryCopyId } = useParams<{ inventoryCopyId: string }>();
  const parsedInventoryCopyId = Number(inventoryCopyId);

  const [detail, setDetail] = useState<InventoryDetail | null>(null);
  const [history, setHistory] = useState<InventoryFmvSnapshot[]>([]);
  const [marketFmv, setMarketFmv] = useState<MarketFmvSnapshotListResponse | null>(null);
  const [marketFmvLoading, setMarketFmvLoading] = useState(false);
  const [marketFmvError, setMarketFmvError] = useState<string | null>(null);
  const [marketComps, setMarketComps] = useState<MarketComparableListResponse | null>(null);
  const [marketCompsLoading, setMarketCompsLoading] = useState(false);
  const [marketCompsError, setMarketCompsError] = useState<string | null>(null);
  const [selectedMarketFmvId, setSelectedMarketFmvId] = useState<number | null>(null);
  const [selectedMarketFmvDetail, setSelectedMarketFmvDetail] = useState<MarketFmvSnapshotRead | null>(null);
  const [selectedMarketFmvDetailLoading, setSelectedMarketFmvDetailLoading] = useState(false);
  const [selectedMarketFmvDetailError, setSelectedMarketFmvDetailError] = useState<string | null>(null);
  const [fMvDraft, setFmvDraft] = useState("");
  const [holdDraft, setHoldDraft] = useState<InventoryDetail["hold_status"]>("hold");
  const [gradeDraft, setGradeDraft] = useState<InventoryDetail["grade_status"]>("raw");
  const [starDraft, setStarDraft] = useState("");
  const [notesDraft, setNotesDraft] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const coverFileInputRef = useRef<HTMLInputElement>(null);
  const [coverThumbUrls, setCoverThumbUrls] = useState<string[]>([]);
  const [coverRegionPreviewUrls, setCoverRegionPreviewUrls] = useState<Record<string, string>>({});
  const [coverUploadBusy, setCoverUploadBusy] = useState(false);
  const [coverPrimaryBusyId, setCoverPrimaryBusyId] = useState<number | null>(null);
  const [coverProcessBusyId, setCoverProcessBusyId] = useState<number | null>(null);
  const [coverEvaluateBusyId, setCoverEvaluateBusyId] = useState<number | null>(null);
  const [coverOcrBusyId, setCoverOcrBusyId] = useState<number | null>(null);
  const [coverOcrCandidateReviewBusyId, setCoverOcrCandidateReviewBusyId] = useState<number | null>(null);
  const [coverBarcodeExtractBusyId, setCoverBarcodeExtractBusyId] = useState<number | null>(null);
  const [coverBarcodeReviewBusyId, setCoverBarcodeReviewBusyId] = useState<number | null>(null);
  const [coverFingerprintBusyId, setCoverFingerprintBusyId] = useState<number | null>(null);
  const [coverOcrQualityBusyId, setCoverOcrQualityBusyId] = useState<number | null>(null);
  const [coverMatchGenerateBusyId, setCoverMatchGenerateBusyId] = useState<number | null>(null);
  const [coverMatchReviewBusyId, setCoverMatchReviewBusyId] = useState<number | null>(null);
  const [coverLinkDecisionBusyId, setCoverLinkDecisionBusyId] = useState<number | null>(null);
  const [coverLinkDecisionRelationshipDrafts, setCoverLinkDecisionRelationshipDrafts] = useState<
    Record<number, CoverLinkRelationshipType>
  >({});
  const [coverLinkDecisionReasonDrafts, setCoverLinkDecisionReasonDrafts] = useState<Record<number, string>>({});
  const [coverOcrReconcileBusyId, setCoverOcrReconcileBusyId] = useState<number | null>(null);
  const [coverOcrWarningBusyId, setCoverOcrWarningBusyId] = useState<number | null>(null);
  const [coverOcrCandidateNoteDrafts, setCoverOcrCandidateNoteDrafts] = useState<Record<number, string>>({});
  const [linkExistingCoverIdDraft, setLinkExistingCoverIdDraft] = useState("");
  const [linkExistingCoverPrimary, setLinkExistingCoverPrimary] = useState(false);
  const [coverLinkExistingBusy, setCoverLinkExistingBusy] = useState(false);
  const [relationshipGraphByCoverId, setRelationshipGraphByCoverId] = useState<
    Partial<Record<number, CoverRelationshipGraphRead>>
  >({});
  const [relationshipGraphErrorByCoverId, setRelationshipGraphErrorByCoverId] = useState<Record<number, string>>({});
  const [relationshipGraphBusyId, setRelationshipGraphBusyId] = useState<number | null>(null);
  const [duplicateScanBusyId, setDuplicateScanBusyId] = useState<number | null>(null);
  const [duplicateScanByCoverId, setDuplicateScanByCoverId] = useState<
    Partial<Record<number, DuplicateScanCandidatesResponse>>
  >({});
  const [duplicateScanErrorByCoverId, setDuplicateScanErrorByCoverId] = useState<Record<number, string>>({});
  const [variantFamilyBusyId, setVariantFamilyBusyId] = useState<number | null>(null);
  const [variantFamilyByCoverId, setVariantFamilyByCoverId] = useState<
    Partial<Record<number, VariantFamilyCandidatesResponse>>
  >({});
  const [variantFamilyErrorByCoverId, setVariantFamilyErrorByCoverId] = useState<Record<number, string>>({});
  const [canonicalSuggestionBusyId, setCanonicalSuggestionBusyId] = useState<number | null>(null);
  const [canonicalSuggestionByCoverId, setCanonicalSuggestionByCoverId] = useState<
    Partial<Record<number, CanonicalIssueLinkSuggestionRead[]>>
  >({});
  const [canonicalSuggestionErrorByCoverId, setCanonicalSuggestionErrorByCoverId] = useState<Record<number, string>>({});
  const [canonicalSuggestionReviewBusyId, setCanonicalSuggestionReviewBusyId] = useState<number | null>(null);
  const [relationshipConflictBusyId, setRelationshipConflictBusyId] = useState<number | null>(null);
  const [relationshipConflictByCoverId, setRelationshipConflictByCoverId] = useState<
    Partial<Record<number, RelationshipConflictListResponse>>
  >({});
  const [relationshipConflictErrorByCoverId, setRelationshipConflictErrorByCoverId] = useState<
    Record<number, string>
  >({});
  const [relationshipConflictReviewBusyId, setRelationshipConflictReviewBusyId] = useState<number | null>(null);
  const [collectionPulseSummary, setCollectionPulseSummary] = useState<CollectionAnalyticsSummary | null>(null);
  const [collectionPulseError, setCollectionPulseError] = useState<string | null>(null);
  const [inventoryHistoricalTimeline, setInventoryHistoricalTimeline] =
    useState<CollectionHistoricalTimelineEventsResponse | null>(null);
  const [inventoryHistoricalTimelineGrouping, setInventoryHistoricalTimelineGrouping] =
    useState<CollectionHistoricalTimelineGrouping>("day");
  const [inventoryHistoricalTimelineBusy, setInventoryHistoricalTimelineBusy] = useState(false);
  const [inventoryHistoricalTimelineError, setInventoryHistoricalTimelineError] = useState<string | null>(null);
  const [inventoryScanQaPanel, setInventoryScanQaPanel] = useState<InventoryScanQaPanelRead | null>(null);
  const [inventoryScanQaError, setInventoryScanQaError] = useState<string | null>(null);
  const [inventoryScanQaBusy, setInventoryScanQaBusy] = useState(false);
  const [inventoryRoutingPanel, setInventoryRoutingPanel] = useState<ScanSessionRoutingRead | null>(null);
  const [inventoryRoutingError, setInventoryRoutingError] = useState<string | null>(null);
  const [inventoryRoutingBusy, setInventoryRoutingBusy] = useState(false);
  const [physicalReceiveBusy, setPhysicalReceiveBusy] = useState(false);
  const [physicalIntakeSessionBusy, setPhysicalIntakeSessionBusy] = useState(false);

  async function loadDetail(): Promise<void> {
    if (!Number.isInteger(parsedInventoryCopyId) || parsedInventoryCopyId <= 0) {
      setError("Invalid inventory copy id.");
      setIsLoading(false);
      return;
    }

    const [detailResponse, historyResponse] = await Promise.all([
      apiClient.getInventoryCopy(parsedInventoryCopyId),
      apiClient.getInventoryFmvHistory(parsedInventoryCopyId),
    ]);
    setDetail(detailResponse);
    setHistory(historyResponse);
    setFmvDraft(detailResponse.current_fmv ?? "");
    setHoldDraft(detailResponse.hold_status);
    setGradeDraft(detailResponse.grade_status);
    setStarDraft(detailResponse.star_rating ? String(detailResponse.star_rating) : "");
    setNotesDraft(detailResponse.condition_notes ?? "");
  }

  async function handlePhysicalMarkReceived(): Promise<void> {
    if (!detail) {
      return;
    }
    setPhysicalReceiveBusy(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.markInventoryPhysicallyReceived(detail.inventory_copy_id, {});
      await loadDetail();
      setSuccessMessage("Marked as physically received.");
    } catch (markErr) {
      setError(
        markErr instanceof ApiError ? markErr.message : "Unable to mark this copy as received.",
      );
    } finally {
      setPhysicalReceiveBusy(false);
    }
  }

  async function handleCreateIntakeScanSessionPlaceholder(): Promise<void> {
    if (!detail) {
      return;
    }
    setPhysicalIntakeSessionBusy(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const sess = await apiClient.createPhysicalIntakeScanSession({
        inventory_copy_ids: [detail.inventory_copy_id],
      });
      await loadDetail();
      setSuccessMessage(`Intake scan session #${sess.id} created (${sess.session_type.replace(/_/g, " ")})`);
    } catch (sessionErr) {
      setError(
        sessionErr instanceof ApiError ? sessionErr.message : "Unable to create intake receiving session.",
      );
    } finally {
      setPhysicalIntakeSessionBusy(false);
    }
  }

  useEffect(() => {
    let ignore = false;
    if (!detail?.metadata_identity_key) {
      setMarketFmv(null);
      setMarketFmvError(null);
      setMarketFmvLoading(false);
      setSelectedMarketFmvId(null);
      setMarketComps(null);
      setMarketCompsError(null);
      setMarketCompsLoading(false);
      return undefined;
    }
    void (async () => {
      setMarketFmvLoading(true);
      setMarketFmvError(null);
      try {
        const response = await apiClient.getMarketFmvByIdentity(detail.metadata_identity_key as string);
        if (!ignore) {
          setMarketFmv(response);
          const preferred =
            response.items.find((row) => row.snapshot_scope === "raw" && row.valuation_method === "median_recent_sales") ??
            response.items[0] ??
            null;
          setSelectedMarketFmvId(preferred?.id ?? null);
        }
      } catch (marketFmvLoadErr) {
        if (!ignore) {
          setMarketFmv(null);
          setSelectedMarketFmvId(null);
          setMarketFmvError(
            marketFmvLoadErr instanceof ApiError ? marketFmvLoadErr.message : "Unable to load market FMV snapshots.",
          );
        }
      } finally {
        if (!ignore) {
          setMarketFmvLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [detail?.metadata_identity_key]);

  useEffect(() => {
    let ignore = false;
    if (!detail?.metadata_identity_key) {
      return undefined;
    }
    void (async () => {
      setMarketCompsLoading(true);
      setMarketCompsError(null);
      try {
        const response = await apiClient.getMarketCompsByIdentity(detail.metadata_identity_key as string, {
          include_excluded: true,
        });
        if (!ignore) {
          setMarketComps(response);
        }
      } catch (marketCompsLoadErr) {
        if (!ignore) {
          setMarketComps(null);
          setMarketCompsError(
            marketCompsLoadErr instanceof ApiError ? marketCompsLoadErr.message : "Unable to load market comps.",
          );
        }
      } finally {
        if (!ignore) {
          setMarketCompsLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [detail?.metadata_identity_key]);

  useEffect(() => {
    let ignore = false;
    if (selectedMarketFmvId == null) {
      setSelectedMarketFmvDetail(null);
      setSelectedMarketFmvDetailError(null);
      setSelectedMarketFmvDetailLoading(false);
      return undefined;
    }
    void (async () => {
      setSelectedMarketFmvDetailLoading(true);
      setSelectedMarketFmvDetailError(null);
      try {
        const response = await apiClient.getMarketFmvSnapshot(selectedMarketFmvId);
        if (!ignore) {
          setSelectedMarketFmvDetail(response);
        }
      } catch (detailErr) {
        if (!ignore) {
          setSelectedMarketFmvDetail(null);
          setSelectedMarketFmvDetailError(
            detailErr instanceof ApiError ? detailErr.message : "Unable to load market FMV snapshot detail.",
          );
        }
      } finally {
        if (!ignore) {
          setSelectedMarketFmvDetailLoading(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [selectedMarketFmvId]);

  useEffect(() => {
    if (!detail?.cover_images) {
      return;
    }
    setCoverOcrCandidateNoteDrafts((prev) => {
      const next = { ...prev };
      for (const img of detail.cover_images) {
        for (const c of img.ocr_candidates) {
          if (next[c.id] === undefined) {
            next[c.id] = c.review_notes ?? "";
          }
        }
      }
      return next;
    });
    setCoverLinkDecisionRelationshipDrafts((prev) => {
      const next = { ...prev };
      for (const img of detail.cover_images) {
        for (const candidate of img.match_candidates) {
          if (next[candidate.id] === undefined) {
            next[candidate.id] =
              candidate.active_link_decision?.relationship_type ??
              (candidate.grouping_type === "probable_duplicate_scan"
                ? "duplicate_scan"
                : candidate.grouping_type === "probable_same_cover"
                  ? "same_cover"
                  : candidate.grouping_type === "probable_variant_family"
                    ? "variant_family"
                    : "same_issue");
          }
        }
      }
      return next;
    });
    setCoverLinkDecisionReasonDrafts((prev) => {
      const next = { ...prev };
      for (const img of detail.cover_images) {
        for (const candidate of img.match_candidates) {
          if (next[candidate.id] === undefined) {
            next[candidate.id] = candidate.active_link_decision?.decision_reason ?? "";
          }
        }
      }
      return next;
    });
  }, [detail]);

  useEffect(() => {
    let ignore = false;

    async function fetchDetail() {
      setIsLoading(true);
      setError(null);

      if (!Number.isInteger(parsedInventoryCopyId) || parsedInventoryCopyId <= 0) {
        setError("Invalid inventory copy id.");
        setIsLoading(false);
        return;
      }

      try {
        const [detailResponse, historyResponse] = await Promise.all([
          apiClient.getInventoryCopy(parsedInventoryCopyId),
          apiClient.getInventoryFmvHistory(parsedInventoryCopyId),
        ]);
        if (ignore) {
          return;
        }

        setDetail(detailResponse);
        setHistory(historyResponse);
        setFmvDraft(detailResponse.current_fmv ?? "");
        setHoldDraft(detailResponse.hold_status);
        setGradeDraft(detailResponse.grade_status);
        setStarDraft(detailResponse.star_rating ? String(detailResponse.star_rating) : "");
        setNotesDraft(detailResponse.condition_notes ?? "");
      } catch (loadError) {
        if (!ignore) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load inventory copy.");
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    void fetchDetail();

    return () => {
      ignore = true;
    };
  }, [parsedInventoryCopyId]);

  useEffect(() => {
    if (!detail?.inventory_copy_id) {
      setInventoryScanQaPanel(null);
      setInventoryScanQaError(null);
      setInventoryScanQaBusy(false);
      return;
    }
    let ignore = false;
    void (async () => {
      setInventoryScanQaBusy(true);
      setInventoryScanQaError(null);
      try {
        const panel = await apiClient.getInventoryCoverScanQa(detail.inventory_copy_id);
        if (!ignore) {
          setInventoryScanQaPanel(panel);
        }
      } catch (qaErr) {
        if (!ignore) {
          setInventoryScanQaPanel(null);
          setInventoryScanQaError(
            qaErr instanceof ApiError ? qaErr.message : "Unable to load cover scan QA routing.",
          );
        }
      } finally {
        if (!ignore) {
          setInventoryScanQaBusy(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [detail?.inventory_copy_id]);

  useEffect(() => {
    const originatingSessionId = detail?.originating_scan_session?.scan_session_id;
    if (!originatingSessionId) {
      setInventoryRoutingPanel(null);
      setInventoryRoutingError(null);
      setInventoryRoutingBusy(false);
      return;
    }
    let ignore = false;
    void (async () => {
      setInventoryRoutingBusy(true);
      setInventoryRoutingError(null);
      try {
        const routing = await apiClient.getScanSessionRouting(originatingSessionId);
        if (!ignore) {
          setInventoryRoutingPanel(routing);
        }
      } catch (routingErr) {
        if (!ignore) {
          setInventoryRoutingPanel(null);
          setInventoryRoutingError(
            routingErr instanceof ApiError ? routingErr.message : "Unable to load queue routing recommendations.",
          );
        }
      } finally {
        if (!ignore) {
          setInventoryRoutingBusy(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [detail?.originating_scan_session?.scan_session_id]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setCollectionPulseError(null);
      try {
        const summary = await apiClient.getCollectionAnalyticsSummary();
        if (!ignore) {
          setCollectionPulseSummary(summary);
        }
      } catch (pulseErr) {
        if (!ignore) {
          setCollectionPulseSummary(null);
          setCollectionPulseError(
            pulseErr instanceof ApiError ? pulseErr.message : "Unable to load collection analytics snapshot.",
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
    if (!Number.isInteger(parsedInventoryCopyId) || parsedInventoryCopyId <= 0) {
      setInventoryHistoricalTimeline(null);
      setInventoryHistoricalTimelineError(null);
      setInventoryHistoricalTimelineBusy(false);
      return undefined;
    }

    void (async () => {
      setInventoryHistoricalTimelineBusy(true);
      setInventoryHistoricalTimelineError(null);
      try {
        const res = await apiClient.getInventoryHistoricalTimeline(parsedInventoryCopyId, {
          grouping: inventoryHistoricalTimelineGrouping,
          sort: "asc",
          limit: 200,
        });
        if (!ignore) {
          setInventoryHistoricalTimeline(res);
        }
      } catch (timelineErr) {
        if (!ignore) {
          setInventoryHistoricalTimeline(null);
          setInventoryHistoricalTimelineError(
            timelineErr instanceof ApiError
              ? timelineErr.message
              : "Unable to load inventory timeline.",
          );
        }
      } finally {
        if (!ignore) {
          setInventoryHistoricalTimelineBusy(false);
        }
      }
    })();

    return () => {
      ignore = true;
    };
  }, [parsedInventoryCopyId, inventoryHistoricalTimelineGrouping]);

  useEffect(() => {
    const covers = detail?.cover_images ?? [];
    if (!covers.length) {
      setCoverThumbUrls([]);
      return undefined;
    }

    let cancelled = false;
    const objectUrls: string[] = [];

    async function loadThumbs(): Promise<void> {
      const next: string[] = [];
      for (const c of covers) {
        try {
          const blob = await apiClient.fetchCoverImageBlob(c.thumbnail_fetch_path ?? c.fetch_path);
          if (cancelled) {
            return;
          }
          const url = URL.createObjectURL(blob);
          objectUrls.push(url);
          next.push(url);
        } catch {
          /* skip failed thumbnail */
        }
      }
      if (!cancelled) {
        setCoverThumbUrls(next);
      }
    }

    void loadThumbs();

    return () => {
      cancelled = true;
      objectUrls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [
    detail?.inventory_copy_id,
    JSON.stringify(detail?.cover_images?.map((c) => [c.id, c.is_primary]) ?? []),
  ]);

  useEffect(() => {
    const covers = detail?.cover_images ?? [];
    if (!covers.length) {
      setCoverRegionPreviewUrls({});
      return undefined;
    }

    let cancelled = false;
    const objectUrls: string[] = [];

    async function loadRegionPreviews(): Promise<void> {
      const next: Record<string, string> = {};
      for (const cover of covers) {
        for (const region of cover.ocr_regions ?? []) {
          try {
            const blob = await apiClient.fetchCoverImageBlob(region.fetch_path);
            if (cancelled) {
              return;
            }
            const url = URL.createObjectURL(blob);
            objectUrls.push(url);
            next[`${cover.id}:${region.region_type}`] = url;
          } catch {
            /* skip failed OCR region preview */
          }
        }
      }
      if (!cancelled) {
        setCoverRegionPreviewUrls(next);
      }
    }

    void loadRegionPreviews();
    return () => {
      cancelled = true;
      objectUrls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [
    detail?.inventory_copy_id,
    JSON.stringify(
      detail?.cover_images?.map((c) => [c.id, ...(c.ocr_regions ?? []).map((r) => [r.id, r.sha256_hash])]) ?? [],
    ),
  ]);

  async function handleSetCoverPrimary(coverImageId: number): Promise<void> {
    if (!detail) {
      return;
    }

    setCoverPrimaryBusyId(coverImageId);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.setInventoryCoverPrimary(detail.inventory_copy_id, coverImageId);
      await loadDetail();
      setSuccessMessage("Primary cover updated.");
    } catch (primaryError) {
      if (primaryError instanceof ApiError) {
        setError(primaryError.message);
      } else {
        setError("Unable to set primary cover.");
      }
    } finally {
      setCoverPrimaryBusyId(null);
    }
  }

  async function handleLinkExistingCoverScan(): Promise<void> {
    if (!detail) {
      return;
    }
    const coverId = Number(linkExistingCoverIdDraft.trim());
    if (!Number.isInteger(coverId) || coverId < 1) {
      setError("Enter a valid cover image id.");
      setSuccessMessage(null);
      return;
    }

    const wantPrimary = linkExistingCoverPrimary;
    setCoverLinkExistingBusy(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.assignExistingCoverToInventory(detail.inventory_copy_id, {
        cover_image_id: coverId,
        set_primary: wantPrimary,
      });
      setLinkExistingCoverIdDraft("");
      setLinkExistingCoverPrimary(false);
      await loadDetail();
      setSuccessMessage(
        wantPrimary ? "Existing cover linked and set as primary." : "Existing cover linked.",
      );
    } catch (linkError) {
      if (linkError instanceof ApiError) {
        setError(linkError.message);
      } else {
        setError("Unable to link cover image.");
      }
    } finally {
      setCoverLinkExistingBusy(false);
    }
  }

  async function handleProcessCoverImage(coverImageId: number): Promise<void> {
    setCoverProcessBusyId(coverImageId);
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await apiClient.processCoverImage(coverImageId);
      await loadDetail();
      setSuccessMessage(
        response.status === "already_queued"
          ? "Cover image processing is already queued."
          : "Cover image metadata reprocessing queued.",
      );
    } catch (processError) {
      if (processError instanceof ApiError) {
        setError(processError.message);
      } else {
        setError("Unable to queue cover image processing.");
      }
    } finally {
      setCoverProcessBusyId(null);
    }
  }

  async function handleEvaluateCoverReadiness(coverImageId: number): Promise<void> {
    setCoverEvaluateBusyId(coverImageId);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.evaluateCoverImageMatchingReadiness(coverImageId);
      await loadDetail();
      setSuccessMessage("Cover matching readiness evaluated.");
    } catch (evaluateError) {
      if (evaluateError instanceof ApiError) {
        setError(evaluateError.message);
      } else {
        setError("Unable to evaluate cover readiness.");
      }
    } finally {
      setCoverEvaluateBusyId(null);
    }
  }

  async function handleRunCoverOcr(meta: InventoryDetail["cover_images"][number]): Promise<void> {
    setCoverOcrBusyId(meta.id);
    setError(null);
    setSuccessMessage(null);
    const headline = resolveCoverImageOcrHeadline({
      ocr_visibility: meta.ocr_visibility,
      latest_ocr_result: meta.latest_ocr_result,
    });
    const hasPriorResult = meta.latest_ocr_result !== null;
    const replayReason = headline === "failed" ? "retry-after-failure" : "manual-replay";
    try {
      const response = hasPriorResult
        ? await apiClient.replayCoverImageOcr(meta.id, { replay_reason: replayReason })
        : await apiClient.runCoverImageOcr(meta.id);
      await loadDetail();
      setSuccessMessage(
        response.status === "already_queued"
          ? "Cover OCR is already queued."
          : headline === "failed"
            ? "Cover OCR retry queued."
            : hasPriorResult
              ? "Cover OCR replay queued."
              : "Cover OCR queued.",
      );
    } catch (ocrError) {
      if (ocrError instanceof ApiError) {
        setError(ocrError.message);
      } else {
        setError(
          headline === "failed"
            ? "Unable to retry cover OCR."
            : hasPriorResult
              ? "Unable to replay cover OCR."
              : "Unable to queue cover OCR.",
        );
      }
    } finally {
      setCoverOcrBusyId(null);
    }
  }

  async function handleOcrCandidateApprove(candidateId: number): Promise<void> {
    setCoverOcrCandidateReviewBusyId(candidateId);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.approveOcrCandidate(candidateId);
      await loadDetail();
      setSuccessMessage("OCR candidate approved.");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to approve OCR candidate.");
      }
    } finally {
      setCoverOcrCandidateReviewBusyId(null);
    }
  }

  async function handleOcrCandidateReject(candidateId: number): Promise<void> {
    setCoverOcrCandidateReviewBusyId(candidateId);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.rejectOcrCandidate(candidateId);
      await loadDetail();
      setSuccessMessage("OCR candidate rejected.");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to reject OCR candidate.");
      }
    } finally {
      setCoverOcrCandidateReviewBusyId(null);
    }
  }

  async function handleOcrCandidateSaveNotes(candidateId: number): Promise<void> {
    setCoverOcrCandidateReviewBusyId(candidateId);
    setError(null);
    setSuccessMessage(null);
    const raw = coverOcrCandidateNoteDrafts[candidateId];
    try {
      await apiClient.patchOcrCandidateReviewNotes(candidateId, { review_notes: raw ?? "" });
      await loadDetail();
      setSuccessMessage("Review notes saved.");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to save review notes.");
      }
    } finally {
      setCoverOcrCandidateReviewBusyId(null);
    }
  }

  async function handleExtractCoverBarcodes(coverImageId: number): Promise<void> {
    setCoverBarcodeExtractBusyId(coverImageId);
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await apiClient.extractCoverImageBarcodes(coverImageId);
      await loadDetail();
      setSuccessMessage(
        response.candidate_count > 0
          ? `Barcode extraction refreshed (${response.candidate_count} candidates).`
          : "Barcode extraction refreshed with no candidates.",
      );
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to extract barcode candidates.");
      }
    } finally {
      setCoverBarcodeExtractBusyId(null);
    }
  }

  async function handleApproveBarcodeCandidate(barcodeCandidateId: number): Promise<void> {
    setCoverBarcodeReviewBusyId(barcodeCandidateId);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.approveBarcodeCandidate(barcodeCandidateId);
      await loadDetail();
      setSuccessMessage("Barcode candidate approved.");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to approve barcode candidate.");
      }
    } finally {
      setCoverBarcodeReviewBusyId(null);
    }
  }

  async function handleRejectBarcodeCandidate(barcodeCandidateId: number): Promise<void> {
    setCoverBarcodeReviewBusyId(barcodeCandidateId);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.rejectBarcodeCandidate(barcodeCandidateId);
      await loadDetail();
      setSuccessMessage("Barcode candidate rejected.");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to reject barcode candidate.");
      }
    } finally {
      setCoverBarcodeReviewBusyId(null);
    }
  }

  async function handleGenerateCoverFingerprints(coverImageId: number): Promise<void> {
    setCoverFingerprintBusyId(coverImageId);
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await apiClient.generateCoverImageFingerprints(coverImageId);
      await loadDetail();
      setSuccessMessage(
        response.fingerprint_count > 0
          ? `Fingerprint generation refreshed (${response.fingerprint_count} records).`
          : "Fingerprint generation refreshed with no records.",
      );
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to generate cover fingerprints.");
      }
    } finally {
      setCoverFingerprintBusyId(null);
    }
  }

  async function handleAnalyzeCoverOcrQuality(coverImageId: number): Promise<void> {
    setCoverOcrQualityBusyId(coverImageId);
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await apiClient.analyzeCoverImageOcrQuality(coverImageId);
      await loadDetail();
      setSuccessMessage(
        response.analysis_count > 0
          ? `OCR quality analysis refreshed (${response.analysis_count} records).`
          : "OCR quality analysis refreshed with no records.",
      );
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to analyze OCR quality.");
      }
    } finally {
      setCoverOcrQualityBusyId(null);
    }
  }

  async function handleGenerateCoverMatchCandidates(coverImageId: number): Promise<void> {
    setCoverMatchGenerateBusyId(coverImageId);
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await apiClient.generateCoverImageMatchCandidates(coverImageId);
      await loadDetail();
      setSuccessMessage(
        response.candidate_count > 0
          ? `Match candidates refreshed (${response.candidate_count} records).`
          : "Match candidate refresh produced no records.",
      );
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to generate cover match candidates.");
      }
    } finally {
      setCoverMatchGenerateBusyId(null);
    }
  }

  async function handleAcknowledgeCoverMatchCandidate(matchCandidateId: number): Promise<void> {
    setCoverMatchReviewBusyId(matchCandidateId);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.acknowledgeCoverMatchCandidate(matchCandidateId);
      await loadDetail();
      setSuccessMessage("Cover match candidate acknowledged.");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to acknowledge cover match candidate.");
      }
    } finally {
      setCoverMatchReviewBusyId(null);
    }
  }

  async function handleDismissCoverMatchCandidate(matchCandidateId: number): Promise<void> {
    setCoverMatchReviewBusyId(matchCandidateId);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.dismissCoverMatchCandidate(matchCandidateId);
      await loadDetail();
      setSuccessMessage("Cover match candidate dismissed.");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to dismiss cover match candidate.");
      }
    } finally {
      setCoverMatchReviewBusyId(null);
    }
  }

  async function loadDuplicateScanIfNeeded(coverImageId: number): Promise<void> {
    setDuplicateScanBusyId(coverImageId);
    setDuplicateScanErrorByCoverId((prev) => {
      const next = { ...prev };
      delete next[coverImageId];



      return next;
    });





    try {
      const dupSnapshot = await apiClient.getDuplicateScanCandidates(coverImageId);






      setDuplicateScanByCoverId((prevSnapshot) => ({ ...prevSnapshot, [coverImageId]: dupSnapshot }));


    } catch (lookupErrDup) {


      setDuplicateScanErrorByCoverId((prevSnapshotDup) => ({




        ...prevSnapshotDup,

        [coverImageId]:
          lookupErrDup instanceof ApiError ?
            lookupErrDup.message




            : "Unable to load duplicate scan intelligence.",




      }));

    } finally {
      setDuplicateScanBusyId(null);
    }



  }


  function clearDuplicateScanCachesForCoverIds(idsDupPiece: number[]): void {



    setDuplicateScanByCoverId((prevDup) => {
      const nextDup = { ...prevDup };


      for (const coverImageIdDup of idsDupPiece) {


        delete nextDup[coverImageIdDup];

      }



      return nextDup;


    });





    setDuplicateScanErrorByCoverId((previousErrDup) => {
      const nextErrDupPiece = { ...previousErrDup };
      for (const coverImageDup of idsDupPiece) {
        delete nextErrDupPiece[coverImageDup];
      }
      return nextErrDupPiece;
    });


  }



  async function loadVariantFamilyIfNeeded(coverImageId: number): Promise<void> {
    setVariantFamilyBusyId(coverImageId);
    setVariantFamilyErrorByCoverId((prevE) => {
      const next = { ...prevE };
      delete next[coverImageId];
      return next;
    });
    try {
      const vfSnap = await apiClient.getVariantFamilyCandidates(coverImageId);
      setVariantFamilyByCoverId((pv) => ({ ...pv, [coverImageId]: vfSnap }));
    } catch (vfErrV) {
      setVariantFamilyErrorByCoverId((pve) => ({
        ...pve,
        [coverImageId]:
          vfErrV instanceof ApiError ? vfErrV.message : "Unable to load variant-family intelligence.",
      }));
    } finally {
      setVariantFamilyBusyId(null);
    }
  }


  function clearVariantFamilyCachesForCoverIds(vfIdsPiece: number[]): void {
    setVariantFamilyByCoverId((prevVf) => {
      const nv = { ...prevVf };
      for (const cid of vfIdsPiece) {
        delete nv[cid];
      }
      return nv;
    });
    setVariantFamilyErrorByCoverId((pvErrVf) => {
      const ne = { ...pvErrVf };
      for (const cid of vfIdsPiece) {
        delete ne[cid];
      }
      return ne;
    });
  }

  async function loadCanonicalIssueSuggestionsIfNeeded(coverImageId: number): Promise<void> {
    setCanonicalSuggestionBusyId(coverImageId);
    setCanonicalSuggestionErrorByCoverId((prev) => {
      const next = { ...prev };
      delete next[coverImageId];
      return next;
    });
    try {
      const rows = await apiClient.getCanonicalIssueSuggestions(coverImageId);
      setCanonicalSuggestionByCoverId((prev) => ({ ...prev, [coverImageId]: rows }));
    } catch (err) {
      setCanonicalSuggestionErrorByCoverId((prev) => ({
        ...prev,
        [coverImageId]:
          err instanceof ApiError ? err.message : "Unable to load canonical issue suggestions.",
      }));
    } finally {
      setCanonicalSuggestionBusyId(null);
    }
  }

  async function handleGenerateCanonicalIssueSuggestions(coverImageId: number): Promise<void> {
    setCanonicalSuggestionBusyId(coverImageId);
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await apiClient.generateCanonicalIssueSuggestions(coverImageId);
      setCanonicalSuggestionByCoverId((prev) => ({ ...prev, [coverImageId]: response.suggestions }));
      setSuccessMessage(
        response.suggestion_count > 0
          ? `Canonical issue suggestions refreshed (${response.suggestion_count} records).`
          : "Canonical issue suggestion refresh produced no records.",
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to generate canonical issue suggestions.");
    } finally {
      setCanonicalSuggestionBusyId(null);
    }
  }

  function clearCanonicalIssueSuggestionCachesForCoverIds(coverIds: number[]): void {
    setCanonicalSuggestionByCoverId((prev) => {
      const next = { ...prev };
      for (const id of coverIds) {
        delete next[id];
      }
      return next;
    });
    setCanonicalSuggestionErrorByCoverId((prev) => {
      const next = { ...prev };
      for (const id of coverIds) {
        delete next[id];
      }
      return next;
    });
  }

  async function handleReviewCanonicalIssueSuggestion(
    coverImageId: number,
    suggestionId: number,
    action: "approve" | "reject" | "ignore",
  ): Promise<void> {
    setCanonicalSuggestionReviewBusyId(suggestionId);
    setError(null);
    setSuccessMessage(null);
    try {
      if (action === "approve") {
        await apiClient.approveCanonicalIssueSuggestion(suggestionId);
      } else if (action === "reject") {
        await apiClient.rejectCanonicalIssueSuggestion(suggestionId);
      } else {
        await apiClient.ignoreCanonicalIssueSuggestion(suggestionId);
      }
      const rows = await apiClient.getCanonicalIssueSuggestions(coverImageId);
      setCanonicalSuggestionByCoverId((prev) => ({ ...prev, [coverImageId]: rows }));
      setSuccessMessage(`Canonical issue suggestion ${action}d.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Unable to ${action} canonical issue suggestion.`);
    } finally {
      setCanonicalSuggestionReviewBusyId(null);
    }
  }

  async function loadRelationshipConflictsIfNeeded(coverImageId: number): Promise<void> {
    setRelationshipConflictBusyId(coverImageId);
    setRelationshipConflictErrorByCoverId((prev) => {
      const next = { ...prev };
      delete next[coverImageId];
      return next;
    });
    try {
      const rows = await apiClient.getRelationshipConflictsForCover(coverImageId);
      setRelationshipConflictByCoverId((prev) => ({ ...prev, [coverImageId]: rows }));
    } catch (err) {
      setRelationshipConflictErrorByCoverId((prev) => ({
        ...prev,
        [coverImageId]: err instanceof ApiError ? err.message : "Unable to load relationship conflicts.",
      }));
    } finally {
      setRelationshipConflictBusyId(null);
    }
  }

  async function handleDetectRelationshipConflicts(coverImageId: number): Promise<void> {
    setRelationshipConflictBusyId(coverImageId);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.detectRelationshipConflicts();
      const rows = await apiClient.getRelationshipConflictsForCover(coverImageId);
      setRelationshipConflictByCoverId((prev) => ({ ...prev, [coverImageId]: rows }));
      setSuccessMessage("Relationship conflicts refreshed.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to detect relationship conflicts.");
    } finally {
      setRelationshipConflictBusyId(null);
    }
  }

  async function handleReviewRelationshipConflict(
    coverImageId: number,
    conflictId: number,
    action: "acknowledge" | "dismiss" | "resolve",
  ): Promise<void> {
    setRelationshipConflictReviewBusyId(conflictId);
    setError(null);
    setSuccessMessage(null);
    try {
      if (action === "acknowledge") {
        await apiClient.acknowledgeRelationshipConflict(conflictId);
      } else if (action === "dismiss") {
        await apiClient.dismissRelationshipConflict(conflictId);
      } else {
        await apiClient.resolveRelationshipConflict(conflictId);
      }
      const rows = await apiClient.getRelationshipConflictsForCover(coverImageId);
      setRelationshipConflictByCoverId((prev) => ({ ...prev, [coverImageId]: rows }));
      setSuccessMessage(`Relationship conflict ${action}d.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Unable to ${action} relationship conflict.`);
    } finally {
      setRelationshipConflictReviewBusyId(null);
    }
  }


  async function loadRelationshipGraphIfNeeded(coverImageId: number): Promise<void> {





    setRelationshipGraphBusyId(coverImageId);




    setRelationshipGraphErrorByCoverId((prev) => {
      const next = { ...prev };
      delete next[coverImageId];
      return next;
    });
    try {
      const data = await apiClient.getCoverRelationshipGraph(coverImageId);
      setRelationshipGraphByCoverId((prev) => ({ ...prev, [coverImageId]: data }));
    } catch (e) {
      setRelationshipGraphErrorByCoverId((prev) => ({
        ...prev,
        [coverImageId]: e instanceof ApiError ? e.message : "Unable to load relationship graph.",
      }));
    } finally {
      setRelationshipGraphBusyId(null);
    }
  }

  function clearRelationshipGraphCacheForCoverIds(ids: number[]): void {
    setRelationshipGraphByCoverId((prev) => {
      const next = { ...prev };
      for (const id of ids) {
        delete next[id];
      }
      return next;
    });
    setRelationshipGraphErrorByCoverId((prev) => {
      const next = { ...prev };
      for (const id of ids) {
        delete next[id];
      }
      return next;
    });
  }

  async function handleCreateCoverLinkDecision(
    candidate: InventoryDetail["cover_images"][number]["match_candidates"][number],
    decisionType: CoverLinkDecisionType,
  ): Promise<void> {
    setCoverLinkDecisionBusyId(candidate.id);
    setError(null);
    setSuccessMessage(null);
    try {
      const relationshipType =
        coverLinkDecisionRelationshipDrafts[candidate.id] ??
        candidate.active_link_decision?.relationship_type ??
        "same_issue";
      await apiClient.createCoverLinkDecision({
        source_cover_image_id: candidate.source_cover_image_id,
        candidate_cover_image_id: candidate.candidate_cover_image_id,
        source_match_candidate_id: candidate.id,
        decision_type: decisionType,
        relationship_type: relationshipType,
        decision_reason: coverLinkDecisionReasonDrafts[candidate.id] ?? null,
      });
      await loadDetail();


      clearRelationshipGraphCacheForCoverIds([
        candidate.source_cover_image_id,
        candidate.candidate_cover_image_id,


      ]);


      clearDuplicateScanCachesForCoverIds([




        candidate.source_cover_image_id,
        candidate.candidate_cover_image_id,

      ]);



      clearVariantFamilyCachesForCoverIds([
        candidate.source_cover_image_id,
        candidate.candidate_cover_image_id,
      ]);
      clearCanonicalIssueSuggestionCachesForCoverIds([
        candidate.source_cover_image_id,
        candidate.candidate_cover_image_id,
      ]);


      setSuccessMessage(
        decisionType === "approved_link"
          ? "Human link decision saved as approved."
          : decisionType === "rejected_link"
            ? "Human link decision saved as unrelated/rejected."
            : "Human link decision saved as needs review.",
      );
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to save cover link decision.");
      }
    } finally {
      setCoverLinkDecisionBusyId(null);
    }
  }

  async function handleRevertCoverLinkDecision(decisionId: number): Promise<void> {
    setCoverLinkDecisionBusyId(decisionId);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.revertCoverLinkDecision(decisionId);
      await loadDetail();
      setRelationshipGraphByCoverId({});
      setRelationshipGraphErrorByCoverId({});
      setSuccessMessage("Cover link decision reverted.");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to revert cover link decision.");
      }
    } finally {
      setCoverLinkDecisionBusyId(null);
    }
  }

  async function handleReconcileCoverMetadata(coverImageId: number): Promise<void> {
    setCoverOcrReconcileBusyId(coverImageId);
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await apiClient.reconcileCoverImageOcrMetadata(coverImageId);
      await loadDetail();
      setSuccessMessage(
        response.warning_count > 0
          ? `OCR reconciliation refreshed (${response.warning_count} warnings).`
          : "OCR reconciliation refreshed with no warnings.",
      );
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to reconcile OCR metadata.");
      }
    } finally {
      setCoverOcrReconcileBusyId(null);
    }
  }

  async function handleAcknowledgeOcrWarning(warningId: number): Promise<void> {
    setCoverOcrWarningBusyId(warningId);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.acknowledgeOcrReconciliationWarning(warningId);
      await loadDetail();
      setSuccessMessage("OCR reconciliation warning acknowledged.");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to acknowledge OCR reconciliation warning.");
      }
    } finally {
      setCoverOcrWarningBusyId(null);
    }
  }

  async function handleDismissOcrWarning(warningId: number): Promise<void> {
    setCoverOcrWarningBusyId(warningId);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.dismissOcrReconciliationWarning(warningId);
      await loadDetail();
      setSuccessMessage("OCR reconciliation warning dismissed.");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Unable to dismiss OCR reconciliation warning.");
      }
    } finally {
      setCoverOcrWarningBusyId(null);
    }
  }

  async function handleCoverUpload(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !detail) {
      return;
    }

    setCoverUploadBusy(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiClient.uploadInventoryCoverImage(detail.inventory_copy_id, file);
      await loadDetail();
      setSuccessMessage("Cover image saved.");
    } catch (uploadError) {
      if (uploadError instanceof ApiError) {
        setError(uploadError.message);
      } else {
        setError("Unable to upload cover image.");
      }
    } finally {
      setCoverUploadBusy(false);
    }
  }

  async function saveDetail(): Promise<void> {
    if (!detail) {
      return;
    }

    const payload: InventoryUpdatePayload = {
      current_fmv: fMvDraft.trim() ? fMvDraft.trim() : null,
      hold_status: holdDraft,
      grade_status: gradeDraft,
      star_rating: starDraft ? Number(starDraft) : null,
      condition_notes: notesDraft.trim() ? notesDraft : null,
    };

    setError(null);
    setSuccessMessage(null);
    setIsSaving(true);

    try {
      await apiClient.updateInventoryCopy(detail.inventory_copy_id, payload);
      await loadDetail();
      setSuccessMessage("Asset profile updated.");
    } catch (saveError) {
      if (saveError instanceof ApiError) {
        setError(saveError.message);
      } else {
        setError("Unable to save inventory copy changes.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return (
      <AppShell>
        <LoadingState
          title="Loading asset profile"
          description="Refreshing valuation details, order metadata, and FMV history."
        />
      </AppShell>
    );
  }

  if (error && !detail) {
    return (
      <AppShell>
        <div className="max-w-4xl">
          <Link
            to="/dashboard"
            className="inline-flex rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:border-cyan-300/40 hover:bg-white/5"
          >
            Back to Dashboard
          </Link>
          <div className="mt-6">
            <StatusBanner tone="error">{error}</StatusBanner>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!detail) {
    return null;
  }

  const metrics = [
    { label: "Cost Basis", value: formatCurrency(detail.acquisition_cost) },
    { label: "Current FMV", value: formatCurrency(detail.current_fmv) },
    {
      label: "Gain / Loss",
      value: formatCurrency(detail.gain_loss),
      className: gainLossClass(detail.gain_loss),
    },
    { label: "Copy Number", value: `#${detail.copy_number}` },
  ];

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <PageHeader
          eyebrow="Asset Profile"
          title={`${detail.title} #${detail.issue_number}`}
          description={`Review valuation history, acquisition context, and copy-level metadata for ${detail.publisher}.`}
          actions={
            <>
              <Link
                to="/dashboard"
                className="inline-flex rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:border-cyan-300/40 hover:bg-white/5"
              >
                Back to Dashboard
              </Link>
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
                Inventory Copy <span className="font-medium text-white">#{detail.inventory_copy_id}</span>
              </div>
            </>
          }
        />

        {collectionPulseError ? (
          <div className="mt-4">
            <StatusBanner tone="error">{collectionPulseError}</StatusBanner>
          </div>
        ) : collectionPulseSummary ? (
          <section className="mt-4 rounded-2xl border border-cyan-400/20 bg-cyan-950/20 px-4 py-3 shadow-inner shadow-black/10">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-cyan-100">
                  Portfolio snapshot (read-only)
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  Same deterministic rollups shown on Dashboard; anchored{" "}
                  <span className="font-semibold text-slate-300">
                    {collectionPulseSummary.generated_as_of_date}
                  </span>
                </p>
              </div>
              <Link
                to="/dashboard"
                className="inline-flex shrink-0 rounded-full border border-white/15 bg-white/5 px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-white transition hover:border-cyan-300/35"
              >
                Open Dashboard analytics
              </Link>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-5">
              <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Tracked</p>
                <p className="mt-1 text-sm font-semibold text-white">{collectionPulseSummary.total_copies}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Preorder</p>
                <p className="mt-1 text-sm font-semibold text-white">{collectionPulseSummary.preorder_copies}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">In hand</p>
                <p className="mt-1 text-sm font-semibold text-white">{collectionPulseSummary.in_hand_copies}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Needs-review</p>
                <p className="mt-1 text-sm font-semibold text-white">
                  {collectionPulseSummary.unresolved_review_copies}
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Canon-linked</p>
                <p className="mt-1 text-sm font-semibold text-white">
                  {collectionPulseSummary.canonical_linked_copies}
                </p>
              </div>
            </div>
          </section>
        ) : null}

        {detail.originating_scan_session ? (
          <section className="mt-4 rounded-2xl border border-white/15 bg-slate-950/50 px-4 py-3 text-sm shadow-inner shadow-black/10">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              Originating scan session
            </p>
            <p className="mt-2 text-slate-200">
              Session{" "}
              <span className="font-mono text-xs font-semibold text-white">
                #{detail.originating_scan_session.scan_session_id}
              </span>{" "}
              · Item seq {detail.originating_scan_session.sequence_index} · Status{" "}
              <span className="capitalize">{detail.originating_scan_session.ingest_status.replace(/_/g, " ")}</span>
              {" · "}
              Session kind{" "}
              <span className="capitalize">{detail.originating_scan_session.session_type.replace(/_/g, " ")}</span>
            </p>
            {(detail.originating_scan_session.scanner_profile_snapshot ??
              detail.originating_scan_session.scanner_profile_label ??
              detail.originating_scan_session.scanner_profile_id) != null ? (
              <div className="mt-3 rounded-xl border border-cyan-400/25 bg-slate-900/65 px-3 py-2 text-xs text-slate-300">
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Capture preset</p>
                {detail.originating_scan_session.scanner_profile_snapshot ? (
                  <p className="mt-1 text-sm text-white">
                    {detail.originating_scan_session.scanner_profile_snapshot.profile_name}
                  </p>
                ) : (
                  <p className="mt-1 text-sm text-white">{detail.originating_scan_session.scanner_profile_label ?? "—"}</p>
                )}
                {detail.originating_scan_session.scanner_profile_snapshot ? (
                  <p className="mt-1 text-[11px] text-slate-400">
                    {scannerRecommendedUseLabel(detail.originating_scan_session.scanner_profile_snapshot.recommended_use)}
                    {detail.originating_scan_session.scanner_profile_snapshot.dpi !== null
                      ? ` · ${detail.originating_scan_session.scanner_profile_snapshot.dpi} dpi`
                      : ""}
                    {` · ${detail.originating_scan_session.scanner_profile_snapshot.file_format.toUpperCase()}`}
                  </p>
                ) : null}
                {detail.originating_scan_session.scanner_profile_id != null ? (
                  <p className="mt-1 font-mono text-[10px] text-slate-500">
                    profile id {detail.originating_scan_session.scanner_profile_id}
                  </p>
                ) : null}
              </div>
            ) : null}
          </section>
        ) : null}

        <section className="mt-4 rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900 via-slate-950 to-indigo-950/70 p-6 shadow-2xl shadow-cyan-950/20">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-4">
              <span className="inline-flex rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-cyan-200">
                Asset Profile
              </span>
              <div>
                <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                  {detail.title} #{detail.issue_number}
                </h1>
                <p className="mt-2 text-sm text-slate-300 sm:text-base">
                  {detail.publisher}
                  {variantLabel(detail) ? ` | ${variantLabel(detail)}` : " | Standard cover"}
                </p>
                <p className="mt-3">
                  <span
                    className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${assetStateTone(
                      detail.asset_state,
                    )}`}
                  >
                    {assetStateLabel(detail.asset_state)}
                  </span>
                </p>
                {detail.inventory_intelligence ? (
                  <InventoryDetailIntelStrip intel={detail.inventory_intelligence} />
                ) : null}
                {detail.run_detection ? (
                  <InventoryRunDetectionCallout attachment={detail.run_detection} />
                ) : null}
                {detail.duplicate_ownership ? (
                  <InventoryDuplicateOwnershipCallout attachment={detail.duplicate_ownership} />
                ) : null}
                {detail.inventory_risks &&
                detail.inventory_risks.length > 0 &&
                detail.inventory_action_center &&
                detail.inventory_action_center.action_categories.length > 0 ? (
                  <section className="mt-4 rounded-2xl border border-white/10 bg-slate-950/60 p-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Attention lanes</p>
                        <h3 className="mt-1 text-base font-semibold text-white">Risk lanes & workflow action center</h3>
                        <p className="mt-2 text-[11px] text-slate-500">
                          Same deterministic priority ladder as the Dashboard — read-only, no mutations.
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 grid gap-3">
                      {detail.inventory_risks.slice(0, 6).map((risk) => (
                        <article key={risk.risk_key} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                            <span
                              className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${inventoryRiskPriorityTone(
                                risk.priority,
                              )}`}
                            >
                              {inventoryRiskLabel(risk.risk_type)}
                            </span>
                            <span className="text-[11px] uppercase tracking-[0.14em] text-slate-500">{risk.priority}</span>
                          </div>
                          <p className="mt-3 text-xs text-slate-300">{inventoryRiskEvidenceSummary(risk)}</p>
                        </article>
                      ))}
                    </div>
                    <div className="mt-5 rounded-2xl border border-teal-400/20 bg-slate-950/40 p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-teal-200/90">
                          Workflow buckets
                        </p>
                        {detail.inventory_action_center.highest_lane_priority ? (
                          <span
                            className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${inventoryRiskPriorityTone(
                              detail.inventory_action_center.highest_lane_priority,
                            )}`}
                          >
                            Top lane: {detail.inventory_action_center.highest_lane_priority}
                          </span>
                        ) : null}
                        {detail.inventory_action_center.urgent_lane ? (
                          <span className="inline-flex rounded-full border border-rose-400/35 bg-rose-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-rose-100">
                            Critical / high lane
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {detail.inventory_action_center.action_categories.map((cat) => (
                          <span
                            key={cat}
                            className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                              detail.inventory_action_center?.urgent_lane
                                ? "border-rose-400/35 bg-rose-400/10 text-rose-100"
                                : "border-teal-400/30 bg-teal-400/10 text-teal-100"
                            }`}
                          >
                            {inventoryActionCenterCategoryUiLabel(cat)}
                          </span>
                        ))}
                      </div>
                      {detail.inventory_action_center.action_keys.length ? (
                        <details className="mt-3 rounded-xl border border-white/10 bg-black/30 p-3 font-mono text-[11px] leading-relaxed text-slate-400">
                          <summary className="cursor-pointer text-[10px] uppercase tracking-[0.14em] text-slate-500">
                            Stable action keys ({detail.inventory_action_center.action_keys.length})
                          </summary>
                          <ul className="mt-2 list-disc pl-4">
                            {detail.inventory_action_center.action_keys.slice(0, 12).map((key) => (
                              <li key={key}>{key}</li>
                            ))}
                          </ul>
                        </details>
                      ) : null}
                    </div>
                  </section>
                ) : (
                  <>
                    {detail.inventory_risks && detail.inventory_risks.length ? (
                      <section className="mt-4 rounded-2xl border border-white/10 bg-slate-950/60 p-4">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <div>
                            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Attention lanes</p>
                            <h3 className="mt-1 text-base font-semibold text-white">Risk lanes</h3>
                          </div>
                          <p className="text-xs text-slate-500">
                            {detail.inventory_risks.length} active risk{detail.inventory_risks.length === 1 ? "" : "s"}
                          </p>
                        </div>
                        <div className="mt-4 grid gap-3">
                          {detail.inventory_risks.slice(0, 6).map((risk) => (
                            <article key={risk.risk_key} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                                <span
                                  className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${inventoryRiskPriorityTone(
                                    risk.priority,
                                  )}`}
                                >
                                  {inventoryRiskLabel(risk.risk_type)}
                                </span>
                                <span className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                                  {risk.priority}
                                </span>
                              </div>
                              <p className="mt-3 text-xs text-slate-300">{inventoryRiskEvidenceSummary(risk)}</p>
                            </article>
                          ))}
                        </div>
                      </section>
                    ) : null}
                    {detail.inventory_action_center && detail.inventory_action_center.action_categories.length > 0 ? (
                      <section className="mt-4 rounded-2xl border border-teal-400/20 bg-slate-950/60 p-4">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <div>
                            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Attention lanes</p>
                            <h3 className="mt-1 text-base font-semibold text-white">Workflow action center</h3>
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            {detail.inventory_action_center.highest_lane_priority ? (
                              <span
                                className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${inventoryRiskPriorityTone(
                                  detail.inventory_action_center.highest_lane_priority,
                                )}`}
                              >
                                Top lane: {detail.inventory_action_center.highest_lane_priority}
                              </span>
                            ) : null}
                            {detail.inventory_action_center.urgent_lane ? (
                              <span className="inline-flex rounded-full border border-rose-400/35 bg-rose-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-rose-100">
                                Critical / high lane
                              </span>
                            ) : null}
                          </div>
                        </div>
                        <div className="mt-4 flex flex-wrap gap-2">
                          {detail.inventory_action_center.action_categories.map((cat) => (
                            <span
                              key={cat}
                              className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                                detail.inventory_action_center?.urgent_lane
                                  ? "border-rose-400/35 bg-rose-400/10 text-rose-100"
                                  : "border-teal-400/30 bg-teal-400/10 text-teal-100"
                              }`}
                            >
                              {inventoryActionCenterCategoryUiLabel(cat)}
                            </span>
                          ))}
                        </div>
                        {detail.inventory_action_center.action_keys.length ? (
                          <details className="mt-4 rounded-xl border border-white/10 bg-black/30 p-3 font-mono text-[11px] leading-relaxed text-slate-400">
                            <summary className="cursor-pointer text-[10px] uppercase tracking-[0.14em] text-slate-500">
                              Stable action keys
                            </summary>
                            <ul className="mt-2 list-disc pl-4">
                              {detail.inventory_action_center.action_keys.slice(0, 12).map((key) => (
                                <li key={key}>{key}</li>
                              ))}
                            </ul>
                          </details>
                        ) : null}
                      </section>
                    ) : null}
                  </>
                )}
                {detail.order_arrival_classifications && detail.order_arrival_classifications.length ? (
                  <section className="mt-4 rounded-2xl border border-white/10 bg-slate-950/60 p-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Order / arrival</p>
                        <h3 className="mt-1 text-base font-semibold text-white">Pipeline classification</h3>
                      </div>
                      <div className="text-xs text-slate-500">
                        <p>Release: {detail.release_date ? formatDate(detail.release_date) : "—"}</p>
                        <p>Expected ship: {detail.expected_ship_date ? formatDate(detail.expected_ship_date) : "—"}</p>
                        <p>Received: {detail.received_at ? formatDate(detail.received_at) : "—"}</p>
                      </div>
                    </div>
                    <div className="mt-4 grid gap-2">
                      {detail.order_arrival_classifications.map((c) => (
                        <article key={c} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                          <span
                            className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${orderArrivalClassificationTone(
                              c,
                            )}`}
                          >
                            {c.replace(/_/g, " ")}
                          </span>
                          <p className="mt-2 text-xs text-slate-300">{orderArrivalClassificationLabel(c)}</p>
                        </article>
                      ))}
                    </div>
                  </section>
                ) : null}
              </div>
              <div className="grid gap-3 text-sm text-slate-300 sm:grid-cols-2 lg:grid-cols-[repeat(auto-fit,minmax(10rem,1fr))]">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Retailer</p>
                  <p className="mt-2 font-medium text-white">{detail.retailer}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Purchase Date</p>
                  <p className="mt-2 font-medium text-white">
                    {detail.purchase_date ? formatDate(detail.purchase_date) : formatDate(detail.order_date)}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Release Year</p>
                  <p className="mt-2 font-medium text-slate-300">
                    {detail.release_year != null ? detail.release_year : "Not recorded"}
                  </p>
                </div>
                {detail.release_date ? (
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                      Exact Release Date
                    </p>
                    <p className="mt-2 text-xs font-normal text-slate-400">{formatDate(detail.release_date)}</p>
                  </div>
                ) : null}
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Release Status</p>
                  <p className="mt-2 font-medium text-white">{detail.release_status.replace(/_/g, " ")}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Order Status</p>
                  <p className="mt-2 font-medium text-white">{detail.order_status.replace(/_/g, " ")}</p>
                </div>
              </div>

              <section className="mt-4 w-full rounded-2xl border border-emerald-400/30 bg-emerald-950/25 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-emerald-200/70">Physical receiving</p>
                <div className="mt-2 space-y-1 text-xs text-slate-300">
                  <p>
                    <span className="text-slate-500">Received at:</span>{" "}
                    {detail.received_at ? formatDate(detail.received_at) : "—"}
                  </p>
                  <p className="text-slate-400">
                    Marking received only adjusts receipt fields (no OCR, ingest, canonical, or speculative metadata writes).
                  </p>
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  {(detail.order_status === "ordered" ||
                    detail.order_status === "preordered" ||
                    detail.order_status === "shipped") && (
                    <button
                      type="button"
                      disabled={physicalReceiveBusy}
                      onClick={() => void handlePhysicalMarkReceived()}
                      className="rounded-2xl border border-emerald-400/35 bg-emerald-500/15 px-4 py-2 text-xs font-semibold text-emerald-100 transition hover:border-emerald-300/60 hover:bg-emerald-500/25 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {physicalReceiveBusy ? "Marking…" : "Mark physically received"}
                    </button>
                  )}
                  {detail.order_status === "received" &&
                  (!detail.cover_images || detail.cover_images.length === 0) ? (
                    <>
                      <button
                        type="button"
                        disabled={physicalIntakeSessionBusy}
                        onClick={() => void handleCreateIntakeScanSessionPlaceholder()}
                        className="rounded-2xl border border-white/15 bg-white/5 px-4 py-2 text-xs font-semibold text-white transition hover:border-cyan-400/35 hover:bg-cyan-500/10 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {physicalIntakeSessionBusy ? "Creating…" : "Create intake receiving scan session"}
                      </button>
                      <Link
                        to="/scan-sessions"
                        className="rounded-2xl border border-white/15 px-4 py-2 text-xs font-semibold text-slate-200 transition hover:border-cyan-300/35 hover:text-white"
                      >
                        Open scan sessions
                      </Link>
                    </>
                  ) : null}
                </div>
              </section>
            </div>

            <div className="grid w-full gap-3 sm:grid-cols-2 lg:max-w-xl">
              {metrics.map((metric) => (
                <article
                  key={metric.label}
                  className="rounded-2xl border border-white/10 bg-slate-900/80 p-4"
                >
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    {metric.label}
                  </p>
                  <p className={`mt-3 text-2xl font-semibold text-white ${metric.className ?? ""}`}>
                    {metric.value}
                  </p>
                </article>
              ))}
            </div>
          </div>

          <section className="mt-8 rounded-3xl border border-cyan-400/20 bg-slate-950/45 p-5 shadow-xl shadow-black/15">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Inventory timeline — activity history</p>
                <h2 className="mt-1 text-lg font-semibold text-white">Preorder → fulfillment → reconciliation</h2>
                <p className="mt-2 max-w-prose text-sm text-slate-400">
                  Read-only audit trail from persisted fields and pipeline rows: dates, arrivals, scans, OCR (including
                  replays), link decisions / relationship replay, canonical reviews, conflicts, duplicates, and variant-family
                  detection. Ordering matches the API (deterministic, no speculative filling).
                </p>
              </div>
              <div className="flex flex-shrink-0 flex-col gap-2 sm:flex-row sm:items-center">
                <label className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Group by
                  <select
                    className="mt-1 block w-full min-w-[12rem] rounded-lg border border-white/15 bg-slate-950 px-3 py-2 text-xs text-white sm:mt-0 sm:ml-2 sm:inline-block sm:w-auto"
                    value={inventoryHistoricalTimelineGrouping}
                    onChange={(event) => {
                      setInventoryHistoricalTimelineGrouping(
                        event.target.value as CollectionHistoricalTimelineGrouping,
                      );
                    }}
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
                {inventoryHistoricalTimeline ? (
                  <p className="text-[11px] text-slate-500">
                    {inventoryHistoricalTimeline.summary.total_events_present} events stored · as of{" "}
                    {inventoryHistoricalTimeline.generated_as_of_date}
                  </p>
                ) : null}
              </div>
            </div>
            {inventoryHistoricalTimelineError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{inventoryHistoricalTimelineError}</StatusBanner>
              </div>
            ) : null}
            {inventoryHistoricalTimelineBusy && !inventoryHistoricalTimeline ? (
              <p className="mt-4 text-sm text-slate-400">Loading timeline…</p>
            ) : null}
            {inventoryHistoricalTimeline ? (
              <>
                {inventoryHistoricalTimelineBusy ? (
                  <p className="mt-4 text-[11px] text-slate-500">Refreshing timeline…</p>
                ) : null}
                <div className="mt-5 flex flex-wrap gap-3 border-t border-white/5 pt-4">
                  {inventoryHistoricalTimeline.events
                    .filter((event) =>
                      [
                        "inventory_added",
                        "preorder_created",
                        "release_day",
                        "expected_ship_window",
                        "inventory_received",
                        "scan_completed",
                      ].includes(event.event_type),
                    )
                    .map((event) => (
                      <article
                        key={`lifespan-${event.stable_id}`}
                        className="flex min-w-[9rem] max-w-[16rem] flex-1 gap-2 rounded-2xl border border-white/10 bg-slate-900/70 p-3"
                      >
                        <span
                          className={`mt-1 inline-block size-2.5 shrink-0 rounded-full ${timelineDotClass(event)}`}
                          aria-hidden
                        />
                        <div className="min-w-0 text-xs">
                          <p className="font-semibold text-cyan-100">{describeHistoricalTimelineEvent(event)}</p>
                          <p className="mt-1 text-[11px] text-slate-500">{formatTimestamp(event.occurred_at)}</p>
                          <p className="mt-2 text-[10px] uppercase tracking-[0.12em] text-slate-500">
                            {event.event_type.replace(/_/g, " ")}
                          </p>
                        </div>
                      </article>
                    ))}
                  {!inventoryHistoricalTimeline.events.some((e) =>
                    [
                      "inventory_added",
                      "preorder_created",
                      "release_day",
                      "expected_ship_window",
                      "inventory_received",
                      "scan_completed",
                    ].includes(e.event_type),
                  ) ? (
                    <p className="text-xs text-slate-500">
                      No preorder / release / fulfillment / scan entries yet — future pipeline activity will populate
                      this strip.
                    </p>
                  ) : null}
                </div>
                <div className="mt-6">
                  <h3 className="text-sm font-semibold text-white">
                    Historical events{" "}
                    {inventoryHistoricalTimeline.filters.grouping !== "none"
                      ? `(${inventoryHistoricalTimeline.filters.grouping})`
                      : null}
                  </h3>
                  {inventoryHistoricalTimeline.filters.grouping !== "none" &&
                  inventoryHistoricalTimeline.groups.length ? (
                    <div className="mt-4 space-y-6">
                      {inventoryHistoricalTimeline.groups.map((group) => (
                        <div key={`grp-${group.group_key}`}>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                            {group.group_key.replace(/__/g, " · ")}
                          </p>
                          <ul className="mt-2 space-y-2">
                            {group.events.map((event) => (
                              <li
                                key={`g-${event.stable_id}`}
                                className="flex gap-3 rounded-xl border border-white/5 bg-slate-950/40 px-3 py-2 text-xs text-slate-200"
                              >
                                <span
                                  className={`mt-1 inline-block size-2 shrink-0 rounded-full ${timelineDotClass(event)}`}
                                  aria-hidden
                                />
                                <div className="min-w-0 flex-1">
                                  <div className="flex flex-wrap items-baseline gap-2">
                                    <span className="font-semibold text-white">
                                      {describeHistoricalTimelineEvent(event)}
                                    </span>
                                    <span className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                                      {event.event_type.replace(/_/g, " ")}
                                    </span>
                                  </div>
                                  <p className="mt-1 text-[11px] text-slate-500">{formatTimestamp(event.occurred_at)}</p>
                                  <p className="mt-1 text-[11px] text-slate-400">
                                    Ownership snapshot:{" "}
                                    <span className="text-slate-200">{event.ownership_state_snapshot}</span>
                                    {" · "}Release status:{" "}
                                    <span className="text-slate-200">{event.release_status_snapshot}</span>
                                  </p>
                                </div>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <ul className="mt-4 space-y-2">
                      {inventoryHistoricalTimeline.events.map((event) => (
                        <li
                          key={`e-${event.stable_id}`}
                          className="flex gap-3 rounded-xl border border-white/5 bg-slate-950/40 px-3 py-2 text-xs text-slate-200"
                        >
                          <span
                            className={`mt-1 inline-block size-2 shrink-0 rounded-full ${timelineDotClass(event)}`}
                            aria-hidden
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-baseline gap-2">
                              <span className="font-semibold text-white">
                                {describeHistoricalTimelineEvent(event)}
                              </span>
                              <span className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                                {event.event_type.replace(/_/g, " ")}
                              </span>
                            </div>
                            <p className="mt-1 text-[11px] text-slate-500">{formatTimestamp(event.occurred_at)}</p>
                            <p className="mt-1 text-[11px] text-slate-400">
                              Ownership snapshot:{" "}
                              <span className="text-slate-200">{event.ownership_state_snapshot}</span>
                              {" · "}Release status:{" "}
                              <span className="text-slate-200">{event.release_status_snapshot}</span>
                            </p>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                  {!inventoryHistoricalTimeline.groups.length &&
                  inventoryHistoricalTimeline.events.length === 0 ? (
                    <p className="mt-4 text-sm text-slate-500">
                      No deterministic timeline rows for this copy yet (only derived from stored facts).
                    </p>
                  ) : null}
                </div>
              </>
            ) : null}
          </section>

          {detail ? <HighResReviewInventorySection inventoryCopyId={detail.inventory_copy_id} /> : null}

          {detail ? (
            (() => {
              const coverIds = new Set(detail.cover_images.map((cov) => cov.id));
              const routingRows = (inventoryRoutingPanel?.items ?? []).filter((row) =>
                row.cover_image_id ? coverIds.has(row.cover_image_id) : false,
              );
              return (
                <section className="mt-8 rounded-3xl border border-cyan-400/25 bg-cyan-950/10 p-6 shadow-inner shadow-black/10">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.16em] text-cyan-200/80">Queue routing recommendations</p>
                      <p className="mt-2 max-w-3xl text-sm text-slate-300">
                        Deterministic routing guidance for the linked scan images on this copy. Recommendations are read-only
                        until a user explicitly queues OCR, opens a high-res review request, or acknowledges the recommendation.
                      </p>
                    </div>
                    {inventoryRoutingBusy ? (
                      <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">Loading…</span>
                    ) : null}
                  </div>
                  {inventoryRoutingError ? (
                    <div className="mt-4">
                      <StatusBanner tone="error">{inventoryRoutingError}</StatusBanner>
                    </div>
                  ) : null}
                  {!inventoryRoutingBusy && routingRows.length === 0 ? (
                    <p className="mt-4 text-sm text-slate-500">No routing recommendations for this copy yet.</p>
                  ) : null}
                  {routingRows.length > 0 ? (
                    <ul className="mt-5 space-y-3">
                      {routingRows.map((row) => {
                        const reasons = Array.isArray(row.evidence_json?.reasons)
                          ? (row.evidence_json.reasons as string[])
                          : [];
                        const signals = Array.isArray(row.evidence_json?.signals)
                          ? (row.evidence_json.signals as { kind?: string }[])
                          : [];
                        const reasonLine = reasons.slice(0, 4).join(" · ");
                        const signalLine = signals
                          .slice(0, 4)
                          .map((sig) => sig.kind ?? "signal")
                          .join(" · ");
                        return (
                          <li key={row.id ?? `${row.scan_session_item_id}-${row.cover_image_id}`} className="rounded-2xl border border-white/10 bg-slate-950/55 px-4 py-3 text-sm text-slate-200">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-mono text-xs text-white">
                                Cover #{row.cover_image_id ?? row.scan_session_item_id ?? "—"}
                              </span>
                              <div className="flex flex-wrap gap-2">
                                <span className="inline-flex rounded-full border border-cyan-400/35 bg-cyan-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-cyan-100">
                                  {row.recommendation_type.replace(/_/g, " ")}
                                </span>
                                <span className="inline-flex rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-200">
                                  {row.priority}
                                </span>
                                <span className="inline-flex rounded-full border border-amber-400/35 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-amber-50">
                                  {row.routing_status.replace(/_/g, " ")}
                                </span>
                              </div>
                            </div>
                            <p className="mt-2 text-xs text-slate-400">
                              Reasons: <span className="text-slate-200">{reasonLine || "—"}</span>
                            </p>
                            <p className="mt-1 text-xs text-slate-400">
                              Signals: <span className="text-slate-200">{signalLine || "—"}</span>
                            </p>
                          </li>
                        );
                      })}
                    </ul>
                  ) : null}
                </section>
              );
            })()
          ) : null}

          {detail ? (
            <section className="mt-8 rounded-3xl border border-emerald-400/25 bg-emerald-950/10 p-6 shadow-inner shadow-black/10">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-emerald-200/80">Cover scan QA (routing)</p>
                  <p className="mt-2 max-w-3xl text-sm text-slate-300">
                    Deterministic read of format, dimensions, ingest-style signals, and OCR quality analysis when present.
                    Recommendations are visibility only — they do not queue OCR or change metadata.
                  </p>
                </div>
                {inventoryScanQaBusy ? (
                  <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">Loading…</span>
                ) : null}
              </div>
              {inventoryScanQaError ? (
                <div className="mt-4">
                  <StatusBanner tone="error">{inventoryScanQaError}</StatusBanner>
                </div>
              ) : null}
              {!inventoryScanQaBusy && inventoryScanQaPanel && inventoryScanQaPanel.covers.length === 0 ? (
                <p className="mt-4 text-sm text-slate-500">No cover images on this copy yet.</p>
              ) : null}
              {inventoryScanQaPanel && inventoryScanQaPanel.covers.length > 0 ? (
                <ul className="mt-5 space-y-3">
                  {inventoryScanQaPanel.covers.map((row) => {
                    const signals = Array.isArray(row.evidence_json?.signals)
                      ? (row.evidence_json?.signals as { kind?: string }[])
                      : [];
                    const headline = signals
                      .slice(0, 4)
                      .map((s) => s.kind ?? "signal")
                      .join(" · ");
                    return (
                      <li
                        key={row.cover_image_id}
                        className="rounded-2xl border border-white/10 bg-slate-950/55 px-4 py-3 text-sm text-slate-200"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-mono text-xs text-white">Cover #{row.cover_image_id}</span>
                          <div className="flex flex-wrap gap-2">
                            <span className="inline-flex rounded-full border border-violet-400/35 bg-violet-400/15 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-violet-100">
                              {row.qa_classification.replace(/_/g, " ")}
                            </span>
                            <span className="inline-flex rounded-full border border-cyan-400/35 bg-cyan-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-cyan-100">
                              {row.routing_recommendation.replace(/_/g, " ")}
                            </span>
                            <span className="inline-flex rounded-full border border-amber-400/35 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-amber-50">
                              {row.severity}
                            </span>
                          </div>
                        </div>
                        <p className="mt-2 text-xs text-slate-400">
                          Signals (first 4): <span className="text-slate-200">{headline || "—"}</span>
                        </p>
                      </li>
                    );
                  })}
                </ul>
              ) : null}
            </section>
          ) : null}

          <div className="mt-8 border-t border-white/10 pt-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Cover scans</p>
                <p className="mt-2 text-sm text-slate-400">
                  {detail.is_in_hand
                    ? "Lightweight reference thumbnails for this copy only. Uploads replace nothing in catalog metadata."
                    : "This asset is not yet in hand, so scans are optional. Nothing here forces cover upload, OCR, or reconciliation before receipt."}
                </p>
              </div>
              <div className="flex shrink-0 flex-col gap-2 sm:items-end">
                <input
                  ref={coverFileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  className="hidden"
                  onChange={(event) => void handleCoverUpload(event)}
                />
                <button
                  type="button"
                  disabled={coverUploadBusy}
                  onClick={() => coverFileInputRef.current?.click()}
                  className="inline-flex items-center justify-center rounded-full border border-cyan-400/30 bg-cyan-400/10 px-5 py-2 text-sm font-semibold text-cyan-100 transition hover:border-cyan-300/60 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {coverUploadBusy ? "Uploading…" : "Upload scan"}
                </button>
              </div>
            </div>
            <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/50 p-4">
              {!detail.is_in_hand ? (
                <div className="mb-4">
                  <StatusBanner tone="info">
                    {assetStateLabel(detail.asset_state)}. Scan upload is optional until the book is physically received.
                  </StatusBanner>
                </div>
              ) : null}
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Manual link</p>
              <p className="mt-2 text-xs text-slate-400">{MANUAL_COVER_ASSIGN_INFO}</p>
              <p className="mt-2 text-xs text-slate-400">{MANUAL_COVER_ASSIGN_MULTI_COPY}</p>
              <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
                <label className="flex min-w-[10rem] flex-1 flex-col gap-1">
                  <span className="text-xs font-medium text-slate-400">Existing cover image id</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={linkExistingCoverIdDraft}
                    disabled={coverLinkExistingBusy || coverUploadBusy}
                    onChange={(event) => setLinkExistingCoverIdDraft(event.target.value)}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40"
                    placeholder="Cover image #"
                  />
                </label>
                <label className="flex cursor-pointer items-center gap-2 pb-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={linkExistingCoverPrimary}
                    disabled={coverLinkExistingBusy || coverUploadBusy}
                    onChange={(event) => setLinkExistingCoverPrimary(event.target.checked)}
                    className="rounded border-white/30 bg-slate-950 accent-cyan-400"
                  />
                  Set as primary
                </label>
                <button
                  type="button"
                  disabled={coverLinkExistingBusy || coverUploadBusy}
                  onClick={() => void handleLinkExistingCoverScan()}
                  className="inline-flex items-center justify-center rounded-full border border-cyan-400/35 bg-cyan-400/10 px-5 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {coverLinkExistingBusy ? "Linking…" : "Link existing cover"}
                </button>
              </div>
            </div>
            {detail.cover_images.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500">
                No uploaded scans linked to this inventory copy yet.
              </p>
            ) : (
              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {detail.cover_images.map((meta, index) => {
                  const thumb = coverThumbUrls[index];
                  const label = meta.original_filename ?? `Cover ${meta.id}`;
                  const busy = coverPrimaryBusyId === meta.id;
                  const ocrHeadline = resolveCoverImageOcrHeadline({
                    ocr_visibility: meta.ocr_visibility,
                    latest_ocr_result: meta.latest_ocr_result,
                  });
                  const ocrRunCount = meta.ocr_visibility?.ocr_run_count ?? 0;
                  const priorRuns = meta.ocr_visibility?.prior_run_created_ats ?? [];
                  return (
                    <div
                      key={meta.id}
                      className={`rounded-2xl border bg-slate-950/60 p-4 text-sm text-slate-300 ${
                        meta.is_primary
                          ? "border-amber-400/40 shadow-lg shadow-amber-500/10"
                          : "border-white/10"
                      }`}
                    >
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        {meta.is_primary ? (
                          <span className="rounded-full border border-amber-400/35 bg-amber-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-100">
                            Primary
                          </span>
                        ) : (
                          <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                            Alternate
                          </span>
                        )}
                      </div>
                      {thumb ? (
                        <button
                          type="button"
                          className="mb-3 block w-full overflow-hidden rounded-xl border border-white/10 bg-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
                          title="Open full image"
                          onClick={() => window.open(thumb, "_blank", "noopener,noreferrer")}
                        >
                          <img
                            src={thumb}
                            alt={`Uploaded comic cover thumbnail for ${label}`}
                            className="h-40 w-full object-cover"
                          />
                        </button>
                      ) : (
                        <div className="mb-3 flex h-40 items-center justify-center rounded-xl border border-dashed border-white/15 bg-slate-950/50 text-xs text-slate-500">
                          Loading preview…
                        </div>
                      )}
                      <p className="font-medium text-white">{label}</p>
                      <div className="mt-3 space-y-2 text-xs">
                        <div className="flex flex-wrap gap-2">
                          <span
                            className={`inline-flex rounded-full border px-2 py-1 font-semibold uppercase tracking-wide ${coverProcessingTone(meta.processing_status)}`}
                          >
                            {meta.processing_status}
                          </span>
                          <span
                            className={`inline-flex rounded-full border px-2 py-1 font-semibold uppercase tracking-wide ${coverMatchingTone(meta.matching_status)}`}
                          >
                            matching {meta.matching_status}
                          </span>
                          <span
                            className={`inline-flex rounded-full border px-2 py-1 font-semibold uppercase tracking-wide ${coverImageOcrHeadlineTone(ocrHeadline)}`}
                          >
                            ocr {ocrHeadline}
                          </span>
                        </div>
                        <p className="text-slate-400">
                          Latest OCR processed:{" "}
                          {formatMaybeTimestamp(meta.latest_ocr_result?.processed_at ?? null)}
                          {meta.latest_ocr_result?.confidence_score != null ? (
                            <span className="text-slate-500">
                              {" "}
                              · confidence {meta.latest_ocr_result.confidence_score}
                            </span>
                          ) : null}
                          {typeof meta.ocr_visibility?.retry_available === "boolean" ? (
                            <span className="text-slate-500">
                              {" "}
                              · retry{" "}
                              {meta.ocr_visibility.retry_available ? "available" : "blocked"}
                            </span>
                          ) : null}
                        </p>
                        {ocrRunCount > 0 ? (
                          <p className="text-slate-500">
                            OCR runs recorded: {ocrRunCount}
                            {priorRuns.length > 0
                              ? ` · prior timestamps (newest-first): ${priorRuns
                                  .slice(0, 3)
                                  .map((ts: string) => formatTimestamp(ts))
                                  .join(", ")}${priorRuns.length > 3 ? "…" : ""}`
                              : ""}
                          </p>
                        ) : null}
                        {meta.latest_ocr_result?.replay_of_ocr_result_id != null ? (
                          <p className="text-slate-500">
                            Latest OCR replayed from #{meta.latest_ocr_result.replay_of_ocr_result_id}
                            {meta.latest_ocr_result.replay_reason
                              ? ` · reason: ${meta.latest_ocr_result.replay_reason}`
                              : ""}
                          </p>
                        ) : null}
                        {meta.latest_ocr_result?.source_cover_image_sha256 ? (
                          <p className="text-slate-500">
                            OCR snapshot img {meta.latest_ocr_result.source_cover_image_sha256.slice(0, 12)}...
                            {meta.latest_ocr_result.source_processing_version
                              ? ` · ${meta.latest_ocr_result.source_processing_version}`
                              : ""}
                            {meta.latest_ocr_result.normalization_version
                              ? ` · ${meta.latest_ocr_result.normalization_version}`
                              : ""}
                          </p>
                        ) : null}
                        <p className="text-slate-400">
                          Metadata refreshed: {formatMaybeTimestamp(meta.metadata_refreshed_at)}
                        </p>
                        <p className="text-slate-400">
                          Ready for matching: {formatMaybeTimestamp(meta.ready_for_matching_at)}
                        </p>
                        {meta.processing_error ? (
                          <p className="text-rose-300">{meta.processing_error}</p>
                        ) : null}
                        {meta.matching_notes ? <p className="text-amber-100/90">{meta.matching_notes}</p> : null}
                        {meta.latest_ocr_result?.processing_error ? (
                          <p className="text-rose-300">{meta.latest_ocr_result.processing_error}</p>
                        ) : null}
                      </div>
                      {meta.latest_ocr_result?.raw_text ? (
                        <div className="mt-3 rounded-xl border border-white/10 bg-slate-950/80 p-3">
                          <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">OCR raw text</p>
                          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-words text-[11px] leading-5 text-slate-300">
                            {meta.latest_ocr_result.raw_text}
                          </pre>
                        </div>
                      ) : null}
                      <details className="mt-3 rounded-xl border border-white/10 bg-slate-950/70 p-3">
                        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                          OCR Regions ({meta.ocr_regions.length})
                        </summary>
                        {meta.ocr_regions.length === 0 ? (
                          <p className="mt-3 text-xs text-slate-500">No OCR regions extracted yet.</p>
                        ) : (
                          <div className="mt-3 grid grid-cols-2 gap-3">
                            {meta.ocr_regions.map((region) => {
                              const previewUrl = coverRegionPreviewUrls[`${meta.id}:${region.region_type}`];
                              return (
                                <a
                                  key={region.id}
                                  href={previewUrl ?? region.fetch_path}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="rounded-lg border border-white/10 bg-slate-900/80 p-2"
                                >
                                  <p className="truncate text-[10px] uppercase tracking-[0.14em] text-slate-500">
                                    {region.region_type}
                                  </p>
                                  {previewUrl ? (
                                    <img
                                      src={previewUrl}
                                      alt={`${region.region_type} OCR region`}
                                      className="mt-2 h-20 w-full rounded object-cover"
                                    />
                                  ) : (
                                    <div className="mt-2 flex h-20 items-center justify-center rounded bg-slate-950 text-[11px] text-slate-500">
                                      Loading…
                                    </div>
                                  )}
                                </a>
                              );
                            })}
                          </div>
                        )}
                      </details>
                      <details
                        className="mt-3 rounded-xl border border-cyan-400/30 bg-slate-950/70 p-3"
                        onToggle={(evtCanon) => {
                          if (evtCanon.currentTarget.open) {
                            void loadCanonicalIssueSuggestionsIfNeeded(meta.id);
                          }
                        }}
                      >
                        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-100">
                          Canonical issue suggestions (cover #{meta.id})
                        </summary>
                        <div className="mt-3 space-y-3 text-xs text-slate-200">
                          <p className="text-[11px] text-slate-500">
                            Deterministic, human-review-only assistance. Approving or rejecting a suggestion updates the
                            review artifact only; it does not mutate canonical metadata, aliases, identity keys, or
                            inventory linkage.
                          </p>
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              disabled={canonicalSuggestionBusyId === meta.id}
                              onClick={() => void handleGenerateCanonicalIssueSuggestions(meta.id)}
                              className="inline-flex rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-2 py-1 text-[10px] font-semibold text-cyan-100"
                            >
                              {canonicalSuggestionBusyId === meta.id ? "Refreshing…" : "Generate / refresh suggestions"}
                            </button>
                          </div>
                          {canonicalSuggestionErrorByCoverId[meta.id] ? (
                            <p className="text-rose-200">{canonicalSuggestionErrorByCoverId[meta.id]}</p>
                          ) : null}
                          {canonicalSuggestionBusyId === meta.id ? (
                            <p className="text-slate-400">Loading canonical issue suggestions…</p>
                          ) : null}
                          {(() => {
                            const rows = canonicalSuggestionByCoverId[meta.id];
                            if (!rows && canonicalSuggestionBusyId !== meta.id && !canonicalSuggestionErrorByCoverId[meta.id]) {
                              return <p className="text-slate-500">Expand to load current suggestion rows for this cover.</p>;
                            }
                            if (!rows) {
                              return null;
                            }
                            if (rows.length === 0) {
                              return <p className="text-slate-500">No canonical issue suggestions for this cover.</p>;
                            }
                            return (
                              <div className="space-y-2">
                                {rows.map((row) => (
                                  <div key={row.id} className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <p>
                                        <span className="font-semibold text-slate-50">{row.suggestion_type.replace(/_/g, " ")}</span>
                                        {" · "}
                                        <span className="text-cyan-100">{row.confidence_bucket}</span>
                                        {" · "}
                                        issue #{row.canonical_issue_id ?? "?"}
                                      </p>
                                      <p className="text-[11px] text-slate-400">
                                        state {row.review_state} · score {row.deterministic_score.toFixed(2)}
                                      </p>
                                    </div>
                                    <p className="mt-1 text-slate-300">
                                      {row.suggested_metadata_identity_key ? row.suggested_metadata_identity_key : "No identity key suggestion"}
                                    </p>
                                    <p className="mt-1 text-slate-500">{summarizeCanonicalIssueEvidence(row.evidence_json)}</p>
                                    {row.suppression_reason ? (
                                      <p className="mt-1 text-amber-200">Suppression: {row.suppression_reason}</p>
                                    ) : null}
                                    <div className="mt-2 flex flex-wrap gap-2">
                                      <button
                                        type="button"
                                        disabled={canonicalSuggestionReviewBusyId === row.id}
                                        onClick={() => void handleReviewCanonicalIssueSuggestion(meta.id, row.id, "approve")}
                                        className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold text-emerald-100 disabled:opacity-40"
                                      >
                                        Approve
                                      </button>
                                      <button
                                        type="button"
                                        disabled={canonicalSuggestionReviewBusyId === row.id}
                                        onClick={() => void handleReviewCanonicalIssueSuggestion(meta.id, row.id, "reject")}
                                        className="rounded-lg border border-rose-400/30 bg-rose-500/10 px-2 py-1 text-[10px] font-semibold text-rose-100 disabled:opacity-40"
                                      >
                                        Reject
                                      </button>
                                      <button
                                        type="button"
                                        disabled={canonicalSuggestionReviewBusyId === row.id}
                                        onClick={() => void handleReviewCanonicalIssueSuggestion(meta.id, row.id, "ignore")}
                                        className="rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold text-slate-100 disabled:opacity-40"
                                      >
                                        Ignore
                                      </button>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            );
                          })()}
                        </div>
                      </details>
                      <details className="mt-3 rounded-xl border border-white/10 bg-slate-950/70 p-3">
                        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                          Barcode Candidates ({meta.barcode_candidates.length})
                        </summary>
                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            disabled={coverBarcodeExtractBusyId === meta.id}
                            onClick={() => void handleExtractCoverBarcodes(meta.id)}
                            className="inline-flex rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-2 py-1 text-[10px] font-semibold text-cyan-100"
                          >
                            {coverBarcodeExtractBusyId === meta.id ? "Refreshing…" : "Refresh barcodes"}
                          </button>
                          <span className="text-[11px] text-slate-500">
                            Pending{" "}
                            {meta.barcode_candidates.filter((candidate) => candidate.review_state === "pending").length}
                          </span>
                        </div>
                        {meta.barcode_candidates.length === 0 ? (
                          <p className="mt-3 text-xs text-slate-500">
                            No persisted barcode candidates yet. Refresh to normalize barcode OCR values safely.
                          </p>
                        ) : (
                          <div className="mt-3 space-y-2">
                            {meta.barcode_candidates.map((candidate) => {
                              const reviewBusy = coverBarcodeReviewBusyId === candidate.id;
                              const sourceLabel =
                                candidate.source_ocr_candidate_id != null
                                  ? `OCR candidate #${candidate.source_ocr_candidate_id}`
                                  : candidate.source_ocr_result_id != null
                                    ? `OCR result #${candidate.source_ocr_result_id}`
                                    : "derived";
                              return (
                                <div
                                  key={candidate.id}
                                  className={`rounded-lg border p-3 text-xs ${barcodeCandidateReviewCardClass(candidate.review_state)}`}
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <span className="rounded-full border border-white/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-100">
                                        {candidate.barcode_type}
                                      </span>
                                      <span className="rounded-full border border-white/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-100">
                                        {candidate.review_state}
                                      </span>
                                    </div>
                                    <span className="text-[10px] text-slate-500">
                                      Updated {formatTimestamp(candidate.updated_at)}
                                    </span>
                                  </div>
                                  <p className="mt-2 text-slate-100">Raw value: {candidate.raw_barcode_value}</p>
                                  <p className="mt-1 text-slate-300">
                                    Normalized UPC: {candidate.normalized_upc_value}
                                  </p>
                                  <p className="mt-1 text-slate-500">
                                    Source {sourceLabel}
                                    {candidate.confidence != null ? ` · confidence ${candidate.confidence}` : ""}
                                    {candidate.reviewed_at ? ` · reviewed ${formatTimestamp(candidate.reviewed_at)}` : ""}
                                  </p>
                                  <div className="mt-2 flex flex-wrap gap-2">
                                    <button
                                      type="button"
                                      disabled={reviewBusy}
                                      onClick={() => void handleApproveBarcodeCandidate(candidate.id)}
                                      className="inline-flex rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold text-emerald-100 disabled:opacity-50"
                                    >
                                      Approve
                                    </button>
                                    <button
                                      type="button"
                                      disabled={reviewBusy}
                                      onClick={() => void handleRejectBarcodeCandidate(candidate.id)}
                                      className="inline-flex rounded-lg border border-rose-400/30 bg-rose-500/10 px-2 py-1 text-[10px] font-semibold text-rose-100 disabled:opacity-50"
                                    >
                                      Reject
                                    </button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </details>
                      <details className="mt-3 rounded-xl border border-white/10 bg-slate-950/70 p-3">
                        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                          Cover Fingerprints ({meta.fingerprints.length})
                        </summary>
                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            disabled={coverFingerprintBusyId === meta.id}
                            onClick={() => void handleGenerateCoverFingerprints(meta.id)}
                            className="inline-flex rounded-lg border border-violet-400/30 bg-violet-500/10 px-2 py-1 text-[10px] font-semibold text-violet-100"
                          >
                            {coverFingerprintBusyId === meta.id ? "Generating…" : "Generate fingerprints"}
                          </button>
                        </div>
                        {meta.fingerprints.length === 0 ? (
                          <p className="mt-3 text-xs text-slate-500">
                            No fingerprint records yet. Generate hashes to prepare deterministic similarity infrastructure.
                          </p>
                        ) : (
                          <div className="mt-3 space-y-2">
                            {meta.fingerprints.map((fingerprint) => (
                              <div
                                key={fingerprint.id}
                                className="rounded-lg border border-white/10 bg-slate-900/80 p-3 text-xs text-slate-300"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="rounded-full border border-white/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-100">
                                      {fingerprint.fingerprint_type}
                                    </span>
                                    <span className="rounded-full border border-white/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-100">
                                      {fingerprint.derivative_type}
                                    </span>
                                  </div>
                                  <span className="text-[10px] text-slate-500">
                                    Updated {formatTimestamp(fingerprint.updated_at)}
                                  </span>
                                </div>
                                <p className="mt-2 text-slate-100" title={fingerprint.fingerprint_value}>
                                  Fingerprint: {shortFingerprint(fingerprint.fingerprint_value)}
                                </p>
                                <p className="mt-1 text-slate-500">
                                  {fingerprint.extraction_version} · {fingerprint.image_width ?? "—"} ×{" "}
                                  {fingerprint.image_height ?? "—"}
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </details>
                      <details className="mt-3 rounded-xl border border-white/10 bg-slate-950/70 p-3">
                        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                          OCR Quality Analysis ({meta.ocr_quality_analyses.length})
                        </summary>
                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            disabled={coverOcrQualityBusyId === meta.id}
                            onClick={() => void handleAnalyzeCoverOcrQuality(meta.id)}
                            className="inline-flex rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-2 py-1 text-[10px] font-semibold text-cyan-100"
                          >
                            {coverOcrQualityBusyId === meta.id ? "Analyzing…" : "Analyze quality"}
                          </button>
                        </div>
                        {meta.ocr_quality_analyses.length === 0 ? (
                          <p className="mt-3 text-xs text-slate-500">
                            No OCR quality analyses persisted yet. Analyze quality to score blur,
                            resolution, contrast, OCR readability, and crop heuristics deterministically.
                          </p>
                        ) : (
                          <div className="mt-3 space-y-2">
                            {meta.ocr_quality_analyses.map((analysis) => (
                              <div
                                key={analysis.id}
                                className={`rounded-lg border p-3 text-xs ${ocrQualitySeverityClass(analysis.severity)}`}
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="rounded-full border border-current/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                                      {analysis.severity}
                                    </span>
                                    <span className="rounded-full border border-current/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                                      {analysis.quality_type.replace(/_/g, " ")}
                                    </span>
                                  </div>
                                  <span className="text-[10px] text-slate-400">
                                    Score {analysis.deterministic_score.toFixed(2)}
                                  </span>
                                </div>
                                <p className="mt-2 text-slate-100">
                                  {analysis.extraction_version}
                                  {analysis.source_ocr_result_id != null
                                    ? ` · OCR result #${analysis.source_ocr_result_id}`
                                    : ""}
                                </p>
                                <div className="mt-2 flex flex-wrap gap-2">
                                  {Object.entries(analysis.detail_json).map(([key, value]) => (
                                    <span
                                      key={key}
                                      className="rounded-full border border-white/15 px-2 py-1 text-[10px] text-slate-100"
                                    >
                                      {key.replace(/_/g, " ")}:{" "}
                                      {typeof value === "object" && value !== null
                                        ? JSON.stringify(value)
                                        : String(value)}
                                    </span>
                                  ))}
                                </div>
                                <p className="mt-2 text-slate-400">
                                  Updated {formatTimestamp(analysis.updated_at)}
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </details>
                      <details
                        className="mt-3 rounded-xl border border-white/10 bg-slate-950/70 p-3"
                        onToggle={(event) => {
                          if (event.currentTarget.open) {
                            void loadRelationshipGraphIfNeeded(meta.id);
                          }
                        }}
                      >
                        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                          Human-approved relationship graph (cover #{meta.id})
                        </summary>
                        <div className="mt-3 space-y-3 text-xs text-slate-300">
                          <p className="text-[11px] text-slate-500">
                            One-hop subgraph from persisted human cover link decisions only (active rows). Ignores
                            match confidence, fingerprints, OCR, and grouping heuristics.
                          </p>
                          {relationshipGraphBusyId === meta.id ? (
                            <p className="text-slate-400">Loading graph…</p>
                          ) : null}
                          {relationshipGraphErrorByCoverId[meta.id] ? (
                            <p className="text-rose-200">{relationshipGraphErrorByCoverId[meta.id]}</p>
                          ) : null}
                          {(() => {
                            const graph = relationshipGraphByCoverId[meta.id];
                            if (!graph) {
                              return (
                                <p className="text-slate-500">
                                  Expand this section to load current human decisions for this cover image.
                                </p>
                              );
                            }
                            if (graph.edges.length === 0) {
                              return <p className="text-slate-500">No active human link decisions touching this cover.</p>;
                            }
                            const grouped = edgesByLane(graph.edges);
                            return GRAPH_LANE_SECTION_ORDER.map((lane) => {
                              const laneEdges = grouped.get(lane) ?? [];
                              if (laneEdges.length === 0) {
                                return null;
                              }
                              return (
                                <div key={lane} className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
                                  <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                    {graphLaneSectionTitle(lane)}
                                  </p>
                                  <ul className="mt-2 space-y-2">
                                    {laneEdges.map((edge) => (
                                      <li
                                        key={`${edge.decision_id}-${edge.source_cover_image_id}-${edge.candidate_cover_image_id}`}
                                        className="rounded-md border border-white/10 px-3 py-2 text-[11px] text-slate-200"
                                      >
                                        <p>
                                          #{edge.source_cover_image_id} → #{edge.candidate_cover_image_id} ·{" "}
                                          {edge.decision_type.replace(/_/g, " ")} ·{" "}
                                          {formatLinkRelationship(edge.relationship_type)}
                                        </p>
                                        <p className="mt-1 text-slate-500">
                                          Decision #{edge.decision_id} · {formatTimestamp(edge.created_at)}
                                          {edge.decision_reason ? ` · "${edge.decision_reason}"` : ""}
                                        </p>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              );
                            });
                          })()}
                        </div>
                      </details>
                      <details
                        className="mt-3 rounded-xl border border-amber-400/30 bg-slate-950/70 p-3"
                        onToggle={(evtDup) => {
                          if (evtDup.currentTarget.open) {
                            void loadDuplicateScanIfNeeded(meta.id);
                          }
                        }}
                      >
                        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.16em] text-amber-100">
                          Duplicate scan intelligence (cover #{meta.id})
                        </summary>
                        <div className="mt-3 space-y-3 text-xs text-slate-200">
                          <p className="text-[11px] text-slate-500">
                            Deterministic duplicate-scan visibility (SHA256, fingerprints, probable duplicate-scan groups,
                            human duplicate-scan links). Unrelated link decisions can suppress pairwise cues. Read-only: no
                            automatic dedupe, merge, or metadata writes.
                          </p>
                          {duplicateScanBusyId === meta.id ? <p className="text-slate-400">Loading duplicate scan…</p> : null}
                          {duplicateScanErrorByCoverId[meta.id] ? (
                            <p className="text-rose-200">{duplicateScanErrorByCoverId[meta.id]}</p>
                          ) : null}
                          {(() => {
                            const dup = duplicateScanByCoverId[meta.id];
                            if (!dup && duplicateScanBusyId !== meta.id && !duplicateScanErrorByCoverId[meta.id]) {
                              return (
                                <p className="text-slate-500">Expand to load duplicate-scan candidates for this cover.</p>
                              );
                            }
                            if (!dup) {
                              return null;
                            }
                            const hasSignal =
                              dup.duplicate_peers.length > 0 || dup.suppressed_pairs_touching_focal.length > 0;
                            return (
                              <div className="space-y-3">
                                {!hasSignal ? (
                                  <p className="text-slate-500">No duplicate-scan signals for this cover.</p>
                                ) : (
                                  <StatusBanner tone="warning">
                                    Likely duplicate scan cluster — review evidence below. This panel never deletes or
                                    merges records.
                                  </StatusBanner>
                                )}
                                {dup.touching_clusters.length > 0 ? (
                                  <div className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
                                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                      Clusters touching this cover
                                    </p>
                                    <ul className="mt-2 space-y-2 text-[11px]">
                                      {dup.touching_clusters.map((c: DuplicateScanClusterRead) => (
                                        <li key={c.cluster_key} className="rounded-md border border-white/10 px-2 py-2">
                                          <p>
                                            #{c.cover_image_ids.join(", #")} · {c.classification} ·{" "}
                                            {c.evidence_strength.replace(/_/g, " ")} · size {c.cluster_size}
                                          </p>
                                          <p className="mt-1 font-mono text-[10px] text-slate-500">{c.cluster_key}</p>
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                ) : null}
                                {dup.duplicate_peers.length > 0 ? (
                                  <div className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
                                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                      Peers
                                    </p>
                                    <ul className="mt-2 space-y-2">
                                      {dup.duplicate_peers.map((pPeer: DuplicateScanDuplicatePeerRead) => {
                                        const bridging = Boolean(
                                          (pPeer.evidence_detail as Record<string, unknown>)
                                            ?.cluster_transitive_duplicate_scan,
                                        );
                                        return (
                                          <li key={pPeer.pair_key} className="rounded-md border border-white/10 px-2 py-2">
                                            <p>
                                              Cover #{pPeer.peer_cover_image_id} ·{" "}
                                              <span
                                                className={
                                                  pPeer.classification === "confirmed"
                                                    ? "text-emerald-200"
                                                    : "text-amber-100"
                                                }
                                              >
                                                {pPeer.classification}
                                              </span>
                                              {" · "}
                                              {summarizeDuplicateEvidence(pPeer.evidences)}
                                            </p>
                                            <p className="mt-1 text-slate-500">
                                              Human decision:{" "}
                                              {pPeer.human_duplicate_scan_decision_id != null
                                                ? `#${pPeer.human_duplicate_scan_decision_id}`
                                                : "—"}
                                              {bridging ? " · cluster-linked peer" : ""}
                                            </p>
                                          </li>
                                        );
                                      })}
                                    </ul>
                                  </div>
                                ) : null}
                                {dup.suppressed_pairs_touching_focal.length > 0 ? (
                                  <div className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
                                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                      Suppressed by unrelated link decisions
                                    </p>
                                    <ul className="mt-2 space-y-1 text-[11px] text-slate-300">
                                      {dup.suppressed_pairs_touching_focal.map((s) => (
                                        <li key={s.pair_key}>
                                          {s.pair_key}: {s.suppressed_signal_labels.join(", ") || "(no labels)"}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                ) : null}
                              </div>
                            );
                          })()}
                        </div>
                      </details>
                      <details
                        className="mt-3 rounded-xl border border-violet-400/35 bg-slate-950/70 p-3"
                        onToggle={(evtVf) => {
                          if (evtVf.currentTarget.open) {
                            void loadVariantFamilyIfNeeded(meta.id);
                          }
                        }}
                      >
                        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.16em] text-violet-100">
                          Variant family intelligence (cover #{meta.id})
                        </summary>
                        <div className="mt-3 space-y-3 text-xs text-slate-200">
                          <p className="text-[11px] text-slate-500">
                            Read-only deterministic variant-family clustering (probable grouping, same-issue divergence,
                            normalized metadata identity, supporting UPC overlaps, human-approved variant_family links).
                            Duplicate-scan approvals exclude pairwise variant exploration. Uses existing Cover Link Decision
                            workflow for human actions — nothing here auto-links inventory.
                          </p>
                          {variantFamilyBusyId === meta.id ? (
                            <p className="text-slate-400">Loading variant family…</p>
                          ) : null}
                          {variantFamilyErrorByCoverId[meta.id] ? (
                            <p className="text-rose-200">{variantFamilyErrorByCoverId[meta.id]}</p>
                          ) : null}
                          {(() => {
                            const vf = variantFamilyByCoverId[meta.id];
                            if (!vf && variantFamilyBusyId !== meta.id && !variantFamilyErrorByCoverId[meta.id]) {
                              return (
                                <p className="text-slate-500">Expand to load variant-family context for this cover.</p>
                              );
                            }
                            if (!vf) {
                              return null;
                            }
                            const hasSig =
                              vf.variant_peers.length > 0 || vf.suppressed_pairs_touching_focal.length > 0;
                            return (
                              <div className="space-y-3">
                                {!hasSig ? (
                                  <p className="text-slate-500">No variant-family visibility for this cover.</p>
                                ) : (
                                  <StatusBanner tone="info">
                                    Variant-family clustering nearby — probable vs confirmed is labeled per peer/cluster.
                                  </StatusBanner>
                                )}
                                {vf.touching_clusters.length > 0 ? (
                                  <div className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
                                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                      Clusters touching this cover
                                    </p>
                                    <ul className="mt-2 space-y-2 text-[11px]">
                                      {vf.touching_clusters.map((c: VariantFamilyClusterRead) => (
                                        <li key={c.cluster_key} className="rounded-md border border-white/10 px-2 py-2">
                                          <p>
                                            #{c.cover_image_ids.join(", #")} · {c.classification} ·{" "}
                                            {c.evidence_strength.replace(/_/g, " ")} · size {c.cluster_size}
                                          </p>
                                          <p className="mt-1 font-mono text-[10px] text-slate-500">{c.cluster_key}</p>
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                ) : null}
                                {vf.variant_peers.length > 0 ? (
                                  <div className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
                                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                      Likely variants (peers)
                                    </p>
                                    <ul className="mt-2 space-y-2">
                                      {vf.variant_peers.map((pVf: VariantFamilyPeerRead) => {
                                        const bridging = Boolean(
                                          (pVf.evidence_detail as Record<string, unknown>)
                                            ?.cluster_transitive_variant_family,
                                        );
                                        return (
                                          <li key={pVf.pair_key} className="rounded-md border border-white/10 px-2 py-2">
                                            <p>
                                              Cover #{pVf.peer_cover_image_id} ·{" "}
                                              <span
                                                className={
                                                  pVf.classification === "confirmed"
                                                    ? "text-emerald-200"
                                                    : "text-violet-200"
                                                }
                                              >
                                                {pVf.classification}
                                              </span>
                                              {" · "}
                                              {summarizeVariantFamilyEvidence(pVf.evidences)}
                                            </p>
                                            <p className="mt-1 text-slate-500">
                                              Human decision:{" "}
                                              {pVf.human_variant_family_decision_id != null
                                                ? `#${pVf.human_variant_family_decision_id}`
                                                : "—"}
                                              {bridging ? " · cluster-linked peer" : ""}
                                            </p>
                                          </li>
                                        );
                                      })}
                                    </ul>
                                  </div>
                                ) : null}
                                {vf.suppressed_pairs_touching_focal.length > 0 ? (
                                  <div className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
                                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                      Suppressed (unrelated link decisions)
                                    </p>
                                    <ul className="mt-2 space-y-1 text-[11px] text-slate-300">
                                      {vf.suppressed_pairs_touching_focal.map((s) => (
                                        <li key={s.pair_key}>
                                          {s.pair_key}: {s.suppressed_signal_labels.join(", ") || "(no labels)"}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                ) : null}
                              </div>
                            );
                          })()}
                        </div>
                      </details>
                      <details
                        className="mt-3 rounded-xl border border-amber-400/35 bg-slate-950/70 p-3"
                        onToggle={(evtConflict) => {
                          if (evtConflict.currentTarget.open) {
                            void loadRelationshipConflictsIfNeeded(meta.id);
                          }
                        }}
                      >
                        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.16em] text-amber-100">
                          Relationship conflicts (cover #{meta.id})
                        </summary>
                        <div className="mt-3 space-y-3 text-xs text-slate-200">
                          <p className="text-[11px] text-slate-500">
                            Deterministic conflict visibility only. Detects contradictions across relationship decisions,
                            graph edges, duplicate-scan / variant-family signals, canonical suggestions, stale ranking
                            context, and preorder reconciliation warnings. Nothing here auto-corrects, unlinks, or mutates
                            metadata.
                          </p>
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              disabled={relationshipConflictBusyId === meta.id}
                              onClick={() => void handleDetectRelationshipConflicts(meta.id)}
                              className="rounded-lg border border-amber-300/30 bg-amber-400/10 px-3 py-2 text-[11px] font-semibold text-amber-100 transition hover:border-amber-200/60 hover:bg-amber-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {relationshipConflictBusyId === meta.id ? "Detecting…" : "Detect / Refresh conflicts"}
                            </button>
                          </div>
                          {relationshipConflictBusyId === meta.id ? (
                            <p className="text-slate-400">Loading relationship conflicts…</p>
                          ) : null}
                          {relationshipConflictErrorByCoverId[meta.id] ? (
                            <p className="text-rose-200">{relationshipConflictErrorByCoverId[meta.id]}</p>
                          ) : null}
                          {(() => {
                            const conflictData = relationshipConflictByCoverId[meta.id];
                            if (
                              !conflictData &&
                              relationshipConflictBusyId !== meta.id &&
                              !relationshipConflictErrorByCoverId[meta.id]
                            ) {
                              return (
                                <p className="text-slate-500">Expand to load conflict context for this cover.</p>
                              );
                            }
                            if (!conflictData) {
                              return null;
                            }
                            if (conflictData.conflicts.length === 0) {
                              return <p className="text-slate-500">No relationship conflicts for this cover.</p>;
                            }
                            return (
                              <div className="space-y-2">
                                {conflictData.conflicts.map((row) => (
                                  <div key={row.id} className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <span
                                        className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${relationshipConflictSeverityTone(
                                          row.severity,
                                        )}`}
                                      >
                                        {row.severity}
                                      </span>
                                      <span className="text-[11px] font-semibold text-white">
                                        {relationshipConflictTypeLabel(row.conflict_type)}
                                      </span>
                                      <span className="text-[10px] uppercase tracking-wide text-slate-500">
                                        {row.status}
                                      </span>
                                    </div>
                                    <p className="mt-2 text-[11px] text-slate-300">
                                      {summarizeRelationshipConflictEvidence(row.evidence_json)}
                                    </p>
                                    <div className="mt-3 flex flex-wrap gap-2">
                                      <button
                                        type="button"
                                        disabled={relationshipConflictReviewBusyId === row.id}
                                        onClick={() => void handleReviewRelationshipConflict(meta.id, row.id, "acknowledge")}
                                        className="rounded-md border border-cyan-400/30 bg-cyan-400/10 px-2 py-1 text-[10px] font-semibold text-cyan-100 transition hover:border-cyan-300/50 hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                                      >
                                        Acknowledge
                                      </button>
                                      <button
                                        type="button"
                                        disabled={relationshipConflictReviewBusyId === row.id}
                                        onClick={() => void handleReviewRelationshipConflict(meta.id, row.id, "dismiss")}
                                        className="rounded-md border border-amber-400/30 bg-amber-400/10 px-2 py-1 text-[10px] font-semibold text-amber-100 transition hover:border-amber-300/50 hover:bg-amber-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                                      >
                                        Dismiss
                                      </button>
                                      <button
                                        type="button"
                                        disabled={relationshipConflictReviewBusyId === row.id}
                                        onClick={() => void handleReviewRelationshipConflict(meta.id, row.id, "resolve")}
                                        className="rounded-md border border-emerald-400/30 bg-emerald-400/10 px-2 py-1 text-[10px] font-semibold text-emerald-100 transition hover:border-emerald-300/50 hover:bg-emerald-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                                      >
                                        Resolve
                                      </button>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            );
                          })()}
                        </div>
                      </details>
                      <details className="mt-3 rounded-xl border border-white/10 bg-slate-950/70 p-3">
                        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                          Cover Match Candidates ({meta.match_candidates.length})
                        </summary>
                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            disabled={coverMatchGenerateBusyId === meta.id}
                            onClick={() => void handleGenerateCoverMatchCandidates(meta.id)}
                            className="inline-flex rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold text-emerald-100"
                          >
                            {coverMatchGenerateBusyId === meta.id ? "Refreshing…" : "Refresh candidates"}
                          </button>
                          <span className="text-[11px] text-slate-500">
                            Open{" "}
                            {
                              meta.match_candidates.filter(
                                (candidate) =>
                                  candidate.dismissed_at === null && candidate.acknowledged_at === null,
                              ).length
                            }
                          </span>
                        </div>
                        {meta.match_candidates.length === 0 ? (
                          <p className="mt-3 text-xs text-slate-500">
                            No match candidates persisted yet. Refresh to compare barcode, OCR, and fingerprint
                            signals deterministically.
                          </p>
                        ) : (
                          <div className="mt-3 space-y-2">
                            {[...meta.match_candidates]
                              .sort((a, b) => {
                                const aOpen = a.dismissed_at === null && a.acknowledged_at === null ? 0 : 1;
                                const bOpen = b.dismissed_at === null && b.acknowledged_at === null ? 0 : 1;
                                if (aOpen !== bOpen) {
                                  return aOpen - bOpen;
                                }
                                return (
                                  a.candidate_rank - b.candidate_rank ||
                                  b.ranking_score - a.ranking_score ||
                                  b.normalized_confidence_score - a.normalized_confidence_score
                                );
                              })
                              .map((candidate) => {
                              const reviewBusy = coverMatchReviewBusyId === candidate.id;
                              const linkBusy =
                                coverLinkDecisionBusyId === candidate.id ||
                                coverLinkDecisionBusyId === candidate.active_link_decision?.id;
                              const isDismissed = candidate.dismissed_at !== null;
                              const isAcknowledged = candidate.acknowledged_at !== null;
                              const conflictingSignals = rankingReasonStrings(candidate, "conflicting_signals");
                              const missingSignals = rankingReasonStrings(candidate, "missing_signals");
                              return (
                                <div
                                  key={candidate.id}
                                  className={`rounded-lg border p-3 text-xs ${matchCandidateTone(candidate.confidence_bucket)}`}
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <span className="rounded-full border border-current/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                                        rank #{candidate.candidate_rank}
                                      </span>
                                      <span className="rounded-full border border-current/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                                        {candidate.confidence_bucket}
                                      </span>
                                      <span className="rounded-full border border-current/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                                        {candidate.candidate_type.replace(/_/g, " ")}
                                      </span>
                                      {candidate.grouping_type ? (
                                        <span
                                          className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${matchGroupingTone(candidate.grouping_confidence_bucket)}`}
                                        >
                                          {formatGroupingType(candidate.grouping_type)}
                                        </span>
                                      ) : null}
                                      {isAcknowledged ? (
                                        <span className="rounded-full border border-cyan-400/30 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-cyan-100">
                                          acknowledged
                                        </span>
                                      ) : null}
                                      {isDismissed ? (
                                        <span className="rounded-full border border-slate-500/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-300">
                                          dismissed
                                        </span>
                                      ) : null}
                                      {candidate.active_link_decision ? (
                                        <span
                                          className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${linkDecisionTone(
                                            candidate.active_link_decision.decision_type,
                                            candidate.active_link_decision.relationship_type,
                                          )}`}
                                        >
                                          {candidate.active_link_decision.decision_type.replace(/_/g, " ")} ·{" "}
                                          {formatLinkRelationship(candidate.active_link_decision.relationship_type)}
                                        </span>
                                      ) : null}
                                    </div>
                                    <div className="text-right text-[10px] text-slate-300">
                                      <p>
                                        Confidence {(candidate.normalized_confidence_score * 100).toFixed(0)}% · raw{" "}
                                        {candidate.deterministic_score.toFixed(2)}
                                      </p>
                                      <p className="text-slate-400">
                                        candidate cover #{candidate.candidate_cover_image_id}
                                      </p>
                                    </div>
                                  </div>
                                  <div className="mt-2 text-slate-100">
                                    <p className="text-[11px] text-slate-100">
                                      {candidate.confidence_explanation_summary ?? "No confidence explanation recorded."}
                                    </p>
                                    <p className="mt-1 text-[11px] text-slate-300">
                                      {String(
                                        candidate.ranking_reason_json.ranking_explanation_summary ??
                                          "No ranking explanation recorded.",
                                      )}
                                    </p>
                                    {candidate.grouping_type ? (
                                      <div className="mt-2 rounded-lg border border-white/10 bg-slate-950/50 p-2 text-[11px] text-slate-200">
                                        <p className="font-semibold text-slate-100">
                                          Why grouped: {formatGroupingType(candidate.grouping_type)}
                                        </p>
                                        <p className="mt-1 text-slate-300">
                                          {candidate.grouping_reason_summary ?? "No grouping explanation recorded."}
                                        </p>
                                        <p className="mt-1 text-slate-500">
                                          Group key {candidate.grouping_key} · bucket{" "}
                                          {candidate.grouping_confidence_bucket ?? "n/a"}
                                        </p>
                                      </div>
                                    ) : null}
                                    {candidate.active_link_decision ? (
                                      <div className="mt-2 rounded-lg border border-white/10 bg-slate-950/50 p-2 text-[11px] text-slate-200">
                                        <p className="font-semibold text-slate-100">Human link decision</p>
                                        <p className="mt-1 text-slate-300">
                                          {candidate.active_link_decision.decision_type.replace(/_/g, " ")} ·{" "}
                                          {formatLinkRelationship(candidate.active_link_decision.relationship_type)} ·{" "}
                                          {candidate.active_link_decision.decision_state}
                                        </p>
                                        {candidate.active_link_decision.reviewer_user_email ? (
                                          <p className="mt-1 text-slate-400">
                                            Reviewer {candidate.active_link_decision.reviewer_user_email}
                                          </p>
                                        ) : null}
                                        {candidate.active_link_decision.decision_reason ? (
                                          <p className="mt-1 text-slate-400">
                                            {candidate.active_link_decision.decision_reason}
                                          </p>
                                        ) : null}
                                      </div>
                                    ) : null}
                                    <div className="mt-2 grid gap-2 md:grid-cols-2">
                                      <div>
                                        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                                          Signals
                                        </p>
                                        {candidate.contributing_signals.length === 0 ? (
                                          <p className="text-[11px] text-slate-400">No contributing signals.</p>
                                        ) : (
                                          <div className="space-y-1">
                                            {candidate.contributing_signals.map((signal, index) => (
                                              <div
                                                key={`${candidate.id}-signal-${index}`}
                                                className="rounded border border-white/10 px-2 py-1 text-[10px]"
                                              >
                                                <p className="font-semibold text-slate-100">
                                                  {String(signal.label ?? signal.signal ?? "signal")}
                                                </p>
                                                <p className="text-slate-300">{String(signal.detail ?? "")}</p>
                                              </div>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                      <div>
                                        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                                          Penalties
                                        </p>
                                        {candidate.penalties.length === 0 ? (
                                          <p className="text-[11px] text-slate-400">No penalties applied.</p>
                                        ) : (
                                          <div className="space-y-1">
                                            {candidate.penalties.map((penalty, index) => (
                                              <div
                                                key={`${candidate.id}-penalty-${index}`}
                                                className="rounded border border-rose-400/20 px-2 py-1 text-[10px]"
                                              >
                                                <p className="font-semibold text-rose-100">
                                                  {String(penalty.label ?? penalty.signal ?? "penalty")}
                                                </p>
                                                <p className="text-slate-300">{String(penalty.detail ?? "")}</p>
                                              </div>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                    {conflictingSignals.length > 0 || missingSignals.length > 0 ? (
                                      <div className="mt-2 grid gap-2 md:grid-cols-2">
                                        <div>
                                          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                                            Conflicting signals
                                          </p>
                                          {conflictingSignals.length === 0 ? (
                                            <p className="text-[11px] text-slate-400">No conflicts recorded.</p>
                                          ) : (
                                            <div className="flex flex-wrap gap-2">
                                              {conflictingSignals.map((value) => (
                                                <span
                                                  key={`${candidate.id}-conflict-${value}`}
                                                  className="rounded-full border border-rose-400/20 px-2 py-1 text-[10px] text-rose-100"
                                                >
                                                  {value.replace(/_/g, " ")}
                                                </span>
                                              ))}
                                            </div>
                                          )}
                                        </div>
                                        <div>
                                          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                                            Missing signals
                                          </p>
                                          {missingSignals.length === 0 ? (
                                            <p className="text-[11px] text-slate-400">No missing signals recorded.</p>
                                          ) : (
                                            <div className="flex flex-wrap gap-2">
                                              {missingSignals.map((value) => (
                                                <span
                                                  key={`${candidate.id}-missing-${value}`}
                                                  className="rounded-full border border-slate-500/40 px-2 py-1 text-[10px] text-slate-300"
                                                >
                                                  {value.replace(/_/g, " ")}
                                                </span>
                                              ))}
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    ) : null}
                                    <div className="mt-2 flex flex-wrap gap-2">
                                      {candidate.matched_fields.map((field) => (
                                        <span
                                          key={`${candidate.id}-matched-${field}`}
                                          className="rounded-full border border-emerald-400/25 px-2 py-1 text-[10px] text-emerald-100"
                                        >
                                          matched {field.replace(/_/g, " ")}
                                        </span>
                                      ))}
                                      {candidate.failed_fields.map((field) => (
                                        <span
                                          key={`${candidate.id}-failed-${field}`}
                                          className="rounded-full border border-slate-500/40 px-2 py-1 text-[10px] text-slate-300"
                                        >
                                          failed {field.replace(/_/g, " ")}
                                        </span>
                                      ))}
                                    </div>
                                  </div>
                                  <p className="mt-2 text-slate-400">
                                    Updated {formatTimestamp(candidate.updated_at)} · {candidate.extraction_version} ·{" "}
                                    {candidate.confidence_version} · {candidate.ranking_version}
                                  </p>
                                  <div className="mt-2 flex flex-wrap gap-2">
                                    <button
                                      type="button"
                                      disabled={reviewBusy || isDismissed}
                                      onClick={() => void handleAcknowledgeCoverMatchCandidate(candidate.id)}
                                      className="inline-flex rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-2 py-1 text-[10px] font-semibold text-cyan-100 disabled:opacity-50"
                                    >
                                      Acknowledge
                                    </button>
                                    <button
                                      type="button"
                                      disabled={reviewBusy || isDismissed}
                                      onClick={() => void handleDismissCoverMatchCandidate(candidate.id)}
                                      className="inline-flex rounded-lg border border-rose-400/30 bg-rose-500/10 px-2 py-1 text-[10px] font-semibold text-rose-100 disabled:opacity-50"
                                    >
                                      Dismiss
                                    </button>
                                  </div>
                                  <div className="mt-3 rounded-lg border border-white/10 bg-slate-950/60 p-2">
                                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                                      Human link decision
                                    </p>
                                    <div className="mt-2 grid gap-2 md:grid-cols-[minmax(0,12rem)_minmax(0,1fr)]">
                                      <label className="text-[11px] text-slate-300">
                                        <span className="mb-1 block text-[10px] uppercase tracking-wide text-slate-500">
                                          Relationship
                                        </span>
                                        <select
                                          value={coverLinkDecisionRelationshipDrafts[candidate.id] ?? "same_issue"}
                                          disabled={linkBusy}
                                          onChange={(event) =>
                                            setCoverLinkDecisionRelationshipDrafts((prev) => ({
                                              ...prev,
                                              [candidate.id]: event.target.value as CoverLinkRelationshipType,
                                            }))
                                          }
                                          className="w-full rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-[11px] text-slate-100"
                                        >
                                          {LINK_RELATIONSHIP_OPTIONS.map((option) => (
                                            <option key={option} value={option}>
                                              {formatLinkRelationship(option)}
                                            </option>
                                          ))}
                                        </select>
                                      </label>
                                      <label className="text-[11px] text-slate-300">
                                        <span className="mb-1 block text-[10px] uppercase tracking-wide text-slate-500">
                                          Reason (optional)
                                        </span>
                                        <input
                                          type="text"
                                          value={coverLinkDecisionReasonDrafts[candidate.id] ?? ""}
                                          disabled={linkBusy}
                                          onChange={(event) =>
                                            setCoverLinkDecisionReasonDrafts((prev) => ({
                                              ...prev,
                                              [candidate.id]: event.target.value,
                                            }))
                                          }
                                          className="w-full rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-[11px] text-slate-100"
                                        />
                                      </label>
                                    </div>
                                    <div className="mt-2 flex flex-wrap gap-2">
                                      <button
                                        type="button"
                                        disabled={linkBusy}
                                        onClick={() => void handleCreateCoverLinkDecision(candidate, "approved_link")}
                                        className="inline-flex rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold text-emerald-100 disabled:opacity-50"
                                      >
                                        Approve link
                                      </button>
                                      <button
                                        type="button"
                                        disabled={linkBusy}
                                        onClick={() => {
                                          setCoverLinkDecisionRelationshipDrafts((prev) => ({
                                            ...prev,
                                            [candidate.id]: "unrelated",
                                          }));
                                          void handleCreateCoverLinkDecision(candidate, "rejected_link");
                                        }}
                                        className="inline-flex rounded-lg border border-rose-400/30 bg-rose-500/10 px-2 py-1 text-[10px] font-semibold text-rose-100 disabled:opacity-50"
                                      >
                                        Reject as unrelated
                                      </button>
                                      <button
                                        type="button"
                                        disabled={linkBusy}
                                        onClick={() => void handleCreateCoverLinkDecision(candidate, "needs_review")}
                                        className="inline-flex rounded-lg border border-amber-400/30 bg-amber-500/10 px-2 py-1 text-[10px] font-semibold text-amber-100 disabled:opacity-50"
                                      >
                                        Needs review
                                      </button>
                                      {candidate.active_link_decision ? (
                                        <button
                                          type="button"
                                          disabled={linkBusy}
                                          onClick={() =>
                                            void handleRevertCoverLinkDecision(candidate.active_link_decision!.id)
                                          }
                                          className="inline-flex rounded-lg border border-white/15 px-2 py-1 text-[10px] font-semibold text-slate-100 disabled:opacity-50"
                                        >
                                          Revert decision
                                        </button>
                                      ) : null}
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </details>
                      <details className="mt-3 rounded-xl border border-white/10 bg-slate-950/70 p-3">
                        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                          OCR Candidates ({meta.ocr_candidates.length})
                        </summary>
                        {meta.ocr_candidates.length === 0 ? (
                          <p className="mt-3 text-xs text-slate-500">No OCR candidates extracted yet.</p>
                        ) : (
                          <div className="mt-3 space-y-4">
                            {Array.from(
                              meta.ocr_candidates.reduce((acc, c) => {
                                const arr = acc.get(c.candidate_type) ?? [];
                                arr.push(c);
                                acc.set(c.candidate_type, arr);
                                return acc;
                              }, new Map<string, typeof meta.ocr_candidates>()),
                            )
                              .sort(([a], [b]) => a.localeCompare(b))
                              .map(([candidateType, candidatesOfType]) => (
                                <div key={candidateType}>
                                  <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                                    {candidateType}
                                  </p>
                                  <div className="space-y-2">
                                    {[...candidatesOfType]
                                      .sort((x, y) => x.id - y.id)
                                      .map((candidate) => {
                                        const reviewBusy = coverOcrCandidateReviewBusyId === candidate.id;
                                        return (
                                          <div
                                            key={candidate.id}
                                            className={`rounded-lg border p-2 text-xs ${ocrCandidateReviewCardClass(candidate.review_status)}`}
                                          >
                                            <div className="flex flex-wrap items-center justify-between gap-2">
                                              <span
                                                className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                                                  candidate.review_status === "approved"
                                                    ? "border-emerald-400/40 text-emerald-200"
                                                    : candidate.review_status === "rejected"
                                                      ? "border-rose-400/40 text-rose-200"
                                                      : "border-white/15 text-slate-300"
                                                }`}
                                              >
                                                {candidate.review_status}
                                              </span>
                                              {candidate.reviewed_at ? (
                                                <span className="text-[10px] text-slate-500">
                                                  Reviewed {formatTimestamp(candidate.reviewed_at)}
                                                </span>
                                              ) : null}
                                            </div>
                                            <p className="mt-2 text-slate-200">{candidate.raw_candidate_text}</p>
                                            <p className="mt-1 text-slate-500">
                                              normalized {candidate.normalized_candidate_text ?? "—"} · source{" "}
                                              {candidate.extraction_source}
                                              {candidate.confidence_score != null
                                                ? ` · confidence ${candidate.confidence_score}`
                                                : ""}
                                            </p>
                                            <label className="mt-2 block text-[10px] uppercase tracking-[0.14em] text-slate-500">
                                              Review notes
                                            </label>
                                            <textarea
                                              className="mt-1 w-full rounded border border-white/10 bg-slate-950/80 px-2 py-1 text-[11px] text-slate-200"
                                              rows={2}
                                              disabled={reviewBusy}
                                              value={
                                                coverOcrCandidateNoteDrafts[candidate.id] ??
                                                candidate.review_notes ??
                                                ""
                                              }
                                              onChange={(event) =>
                                                setCoverOcrCandidateNoteDrafts((prev) => ({
                                                  ...prev,
                                                  [candidate.id]: event.target.value,
                                                }))
                                              }
                                            />
                                            <div className="mt-2 flex flex-wrap gap-2">
                                              <button
                                                type="button"
                                                disabled={reviewBusy}
                                                onClick={() => void handleOcrCandidateApprove(candidate.id)}
                                                className="inline-flex rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold text-emerald-100"
                                              >
                                                Approve
                                              </button>
                                              <button
                                                type="button"
                                                disabled={reviewBusy}
                                                onClick={() => void handleOcrCandidateReject(candidate.id)}
                                                className="inline-flex rounded-lg border border-rose-400/30 bg-rose-500/10 px-2 py-1 text-[10px] font-semibold text-rose-100"
                                              >
                                                Reject
                                              </button>
                                              <button
                                                type="button"
                                                disabled={reviewBusy}
                                                onClick={() => void handleOcrCandidateSaveNotes(candidate.id)}
                                                className="inline-flex rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold text-slate-200"
                                              >
                                                Save notes
                                              </button>
                                            </div>
                                          </div>
                                        );
                                      })}
                                  </div>
                                </div>
                              ))}
                          </div>
                        )}
                      </details>
                      <details className="mt-3 rounded-xl border border-white/10 bg-slate-950/70 p-3">
                        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                          OCR Reconciliation Warnings ({meta.ocr_reconciliation_warnings.length})
                        </summary>
                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            disabled={coverOcrReconcileBusyId === meta.id}
                            onClick={() => void handleReconcileCoverMetadata(meta.id)}
                            className="inline-flex rounded-lg border border-amber-400/30 bg-amber-500/10 px-2 py-1 text-[10px] font-semibold text-amber-100"
                          >
                            {coverOcrReconcileBusyId === meta.id ? "Refreshing…" : "Refresh warnings"}
                          </button>
                          <span className="text-[11px] text-slate-500">
                            Open{" "}
                            {meta.ocr_reconciliation_warnings.filter((warning) => warning.status === "open").length}
                          </span>
                        </div>
                        {meta.ocr_reconciliation_warnings.length === 0 ? (
                          <p className="mt-3 text-xs text-slate-500">
                            No reconciliation warnings recorded yet. Run refresh to compare OCR candidates against the
                            current metadata snapshot.
                          </p>
                        ) : (
                          <div className="mt-3 space-y-2">
                            {meta.ocr_reconciliation_warnings.map((warning) => {
                              const warningBusy = coverOcrWarningBusyId === warning.id;
                              return (
                                <div
                                  key={warning.id}
                                  className={`rounded-lg border p-3 text-xs ${ocrReconciliationSeverityClass(warning.severity)}`}
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <span className="rounded-full border border-current/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                                        {warning.severity}
                                      </span>
                                      <span
                                        className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${ocrReconciliationStatusClass(warning.status)}`}
                                      >
                                        {warning.status}
                                      </span>
                                      <span className="text-[10px] uppercase tracking-[0.14em] text-slate-300">
                                        {warning.warning_type.replace(/_/g, " ")}
                                      </span>
                                    </div>
                                    <span className="text-[10px] text-slate-400">
                                      {warning.resolved_at
                                        ? `Resolved ${formatTimestamp(warning.resolved_at)}`
                                        : `Created ${formatTimestamp(warning.created_at)}`}
                                    </span>
                                  </div>
                                  <p className="mt-2 text-slate-100">{warning.message}</p>
                                  <p className="mt-2 text-slate-300">
                                    Current metadata: {warning.current_metadata_value ?? "—"}
                                  </p>
                                  <p className="mt-1 text-slate-300">OCR candidate: {warning.candidate_value ?? "—"}</p>
                                  <div className="mt-2 flex flex-wrap gap-2">
                                    <button
                                      type="button"
                                      disabled={warningBusy || warning.status === "acknowledged"}
                                      onClick={() => void handleAcknowledgeOcrWarning(warning.id)}
                                      className="inline-flex rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-2 py-1 text-[10px] font-semibold text-cyan-100 disabled:opacity-50"
                                    >
                                      Acknowledge
                                    </button>
                                    <button
                                      type="button"
                                      disabled={warningBusy || warning.status === "dismissed"}
                                      onClick={() => void handleDismissOcrWarning(warning.id)}
                                      className="inline-flex rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold text-slate-200 disabled:opacity-50"
                                    >
                                      Dismiss
                                    </button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </details>
                      {meta.is_primary ? (
                        <p className="mt-2 text-xs text-amber-200/90">Primary display image for this copy.</p>
                      ) : (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void handleSetCoverPrimary(meta.id)}
                          className="mt-3 inline-flex rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-white transition hover:border-cyan-300/40 hover:bg-cyan-300/10 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {busy ? "Updating…" : "Set primary"}
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={coverProcessBusyId === meta.id}
                        onClick={() => void handleProcessCoverImage(meta.id)}
                        className="mt-3 inline-flex rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-white transition hover:border-cyan-300/40 hover:bg-cyan-300/10 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {coverProcessBusyId === meta.id ? "Queueing…" : "Reprocess metadata"}
                      </button>
                      <button
                        type="button"
                        disabled={coverEvaluateBusyId === meta.id}
                        onClick={() => void handleEvaluateCoverReadiness(meta.id)}
                        className="mt-3 inline-flex rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-white transition hover:border-cyan-300/40 hover:bg-cyan-300/10 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {coverEvaluateBusyId === meta.id ? "Evaluating…" : "Evaluate readiness"}
                      </button>
                      <button
                        type="button"
                        disabled={coverOcrBusyId === meta.id}
                        onClick={() => void handleRunCoverOcr(meta)}
                        className="mt-3 inline-flex rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-white transition hover:border-cyan-300/40 hover:bg-cyan-300/10 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {coverOcrBusyId === meta.id
                          ? "Queueing…"
                          : ocrHeadline === "failed"
                            ? "Retry OCR"
                            : meta.latest_ocr_result
                              ? "Replay OCR"
                              : "Run OCR"}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        {error ? <div className="mt-6"><StatusBanner tone="error">{error}</StatusBanner></div> : null}

        {successMessage ? (
          <div className="mt-6">
            <StatusBanner tone="success">{successMessage}</StatusBanner>
          </div>
        ) : null}

        <section className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <article className="rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-white">Investment Snapshot</h2>
                <p className="mt-2 text-sm text-slate-400">
                  Review asset identity, copy-level valuation, and acquisition metadata in one view.
                </p>
              </div>
              <span
                className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${
                  detail.hold_status === "hold"
                    ? "border-cyan-400/30 bg-cyan-400/10 text-cyan-200"
                    : detail.hold_status === "sell"
                      ? "border-amber-400/30 bg-amber-400/10 text-amber-200"
                      : "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
                }`}
              >
                {detail.hold_status}
              </span>
            </div>

            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Cover Profile</p>
                <div className="mt-3 space-y-2 text-sm text-slate-300">
                  <p>Cover: {detail.cover_name ?? "Standard"}</p>
                  <p>Printing: {detail.printing ?? "Standard"}</p>
                  <p>Ratio: {detail.ratio ?? "Open order"}</p>
                  <p>Variant Type: {detail.variant_type ?? "Primary"}</p>
                  <p>Cover Artist: {detail.cover_artist ?? "Unknown"}</p>
                </div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                  Acquisition Metadata
                </p>
                <div className="mt-3 space-y-2 text-sm text-slate-300">
                  <p>Source Type: {detail.source_type ?? "Unspecified"}</p>
                  <p>Asset State: {assetStateLabel(detail.asset_state)}</p>
                  <p>Purchase Date: {detail.purchase_date ? formatDate(detail.purchase_date) : formatDate(detail.order_date)}</p>
                  <p>Release Year: {detail.release_year ?? "Unknown"}</p>
                  <p>Release Date: {detail.release_date ? formatDate(detail.release_date) : "Unknown"}</p>
                  <p>Release Status: {detail.release_status.replace(/_/g, " ")}</p>
                  <p>Order Status: {detail.order_status.replace(/_/g, " ")}</p>
                  <p>
                    Expected Ship: {detail.expected_ship_date ? formatDate(detail.expected_ship_date) : "Unknown"}
                  </p>
                  <p>Received: {detail.received_at ? formatTimestamp(detail.received_at) : "Not received"}</p>
                  <p>Order ID: #{detail.order_id}</p>
                  <p>Order Item ID: #{detail.order_item_id}</p>
                  <p>Variant ID: #{detail.variant_id}</p>
                  <p>Created: {formatTimestamp(detail.created_at)}</p>
                </div>
              </div>
            </div>

            <div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/70 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Condition Notes</p>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-300">
                {detail.condition_notes || "No condition notes added yet."}
              </p>
            </div>
          </article>

          <article className="rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
            <h2 className="text-xl font-semibold text-white">Manage Copy</h2>
            <p className="mt-2 text-sm text-slate-400">
              Adjust live FMV, portfolio intent, rating, grading status, and notes for this single
              asset.
            </p>

            <div className="mt-6 space-y-5">
              <label className="block">
                <span className="text-sm font-medium text-slate-300">Current FMV</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={fMvDraft}
                  onChange={(event) => setFmvDraft(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  placeholder="Enter current fair market value"
                />
              </label>

              <div className="grid gap-5 sm:grid-cols-2">
                <label className="block">
                  <span className="text-sm font-medium text-slate-300">Hold Status</span>
                  <select
                    value={holdDraft}
                    onChange={(event) =>
                      setHoldDraft(event.target.value as InventoryDetail["hold_status"])
                    }
                    className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  >
                    <option value="hold">Hold</option>
                    <option value="sell">Sell</option>
                    <option value="sold">Sold</option>
                  </select>
                </label>

                <label className="block">
                  <span className="text-sm font-medium text-slate-300">Grade Status</span>
                  <select
                    value={gradeDraft}
                    onChange={(event) =>
                      setGradeDraft(event.target.value as InventoryDetail["grade_status"])
                    }
                    className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  >
                    <option value="raw">Raw</option>
                    <option value="submitted">Submitted</option>
                    <option value="graded">Graded</option>
                  </select>
                </label>
              </div>

              <label className="block">
                <span className="text-sm font-medium text-slate-300">Star Rating</span>
                <select
                  value={starDraft}
                  onChange={(event) => setStarDraft(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                >
                  <option value="">No rating</option>
                  <option value="1">1</option>
                  <option value="2">2</option>
                  <option value="3">3</option>
                  <option value="4">4</option>
                  <option value="5">5</option>
                </select>
              </label>

              <label className="block">
                <span className="text-sm font-medium text-slate-300">Condition Notes</span>
                <textarea
                  rows={8}
                  maxLength={2000}
                  value={notesDraft}
                  onChange={(event) => setNotesDraft(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  placeholder="Add grading observations, defects, press notes, or exit-strategy context."
                />
              </label>

              <div className="flex items-center justify-between gap-4">
                <p className="text-sm text-slate-500">{notesDraft.length}/2000 characters</p>
                <button
                  type="button"
                  disabled={isSaving}
                  onClick={() => void saveDetail()}
                  className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSaving ? "Saving..." : "Save Asset Profile"}
                </button>
              </div>
            </div>
          </article>
        </section>

        <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white">FMV History</h2>
              <p className="mt-2 text-sm text-slate-400">
                Every manual FMV change is preserved as a dated valuation snapshot.
              </p>
            </div>
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
              {history.length} snapshots
            </span>
          </div>

          {history.length ? (
            <div className="mt-6 overflow-x-auto">
              <table className="min-w-full text-left text-sm text-slate-300">
                <thead className="border-b border-white/10 text-xs uppercase tracking-[0.16em] text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Changed</th>
                    <th className="px-4 py-3">Previous FMV</th>
                    <th className="px-4 py-3">New FMV</th>
                    <th className="px-4 py-3">Delta</th>
                    <th className="px-4 py-3">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((snapshot) => {
                    const delta =
                      snapshot.previous_fmv === null
                        ? null
                        : (Number(snapshot.new_fmv) - Number(snapshot.previous_fmv)).toFixed(2);

                    return (
                      <tr key={snapshot.id} className="border-b border-white/5">
                        <td className="px-4 py-4 text-slate-300">
                          {formatTimestamp(snapshot.changed_at)}
                        </td>
                        <td className="px-4 py-4 text-slate-400">
                          {formatCurrency(snapshot.previous_fmv)}
                        </td>
                        <td className="px-4 py-4 font-medium text-white">
                          {formatCurrency(snapshot.new_fmv)}
                        </td>
                        <td className={`px-4 py-4 ${gainLossClass(delta)}`}>
                          {delta === null ? "Initial mark" : formatCurrency(delta)}
                        </td>
                        <td className="px-4 py-4">
                          <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs uppercase tracking-[0.14em] text-cyan-200">
                            {snapshot.source}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="mt-6">
              <EmptyState
                title="No FMV history yet"
                description="The first manual FMV change will create the opening snapshot for this inventory copy."
              />
            </div>
          )}
        </section>

        <section className="mt-6 rounded-3xl border border-cyan-400/25 bg-cyan-950/10 p-6 shadow-xl shadow-black/20">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white">Market FMV Snapshots</h2>
              <p className="mt-2 text-sm text-slate-400">
                Deterministic market-derived FMV is shown here as a read-only snapshot ledger. It never overwrites the
                manual `Current FMV` field above.
              </p>
            </div>
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
              {marketFmv?.total ?? 0} snapshots
            </span>
          </div>

          {!detail.metadata_identity_key ? (
            <div className="mt-6">
              <EmptyState
                title="No metadata identity key"
                description="This inventory copy does not have a metadata identity key yet, so no market FMV snapshots can be mapped."
              />
            </div>
          ) : marketFmvLoading ? (
            <p className="mt-6 text-sm text-slate-400">Loading market FMV snapshots…</p>
          ) : marketFmvError ? (
            <div className="mt-6">
              <StatusBanner tone="error">{marketFmvError}</StatusBanner>
            </div>
          ) : !marketFmv || marketFmv.items.length === 0 ? (
            <div className="mt-6">
              <EmptyState
                title="No FMV snapshots yet"
                description="Ops generation has not produced any deterministic market FMV snapshots for this metadata identity."
              />
            </div>
          ) : (
            <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.9fr)]">
              <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3 font-medium">Inspect</th>
                      <th className="p-3 font-medium">Scope / method</th>
                      <th className="p-3 font-medium">FMV</th>
                      <th className="p-3 font-medium">Comps</th>
                      <th className="p-3 font-medium">Confidence</th>
                      <th className="p-3 font-medium">Liquidity</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {marketFmv.items.map((row) => {
                      const isSelected = selectedMarketFmvId === row.id;
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
                              onClick={() => setSelectedMarketFmvId((cur) => (cur === row.id ? null : row.id))}
                            >
                              {isSelected ? "Hide" : "View"}
                            </button>
                          </td>
                          <td className="p-3 align-top">
                            <div className="font-medium text-slate-100">{marketFmvScopeLabel(row.snapshot_scope)}</div>
                            <div className="mt-1 text-[11px] text-slate-400">{row.valuation_method.replace(/_/g, " ")}</div>
                            <div className="mt-1 text-[11px] text-slate-500">
                              {row.snapshot_date} · {row.currency_code}
                            </div>
                          </td>
                          <td className="p-3 align-top font-medium text-white">{formatCurrency(row.estimated_fmv)}</td>
                          <td className="p-3 align-top text-slate-300">{row.comp_count}</td>
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
                {selectedMarketFmvDetailLoading ? (
                  <p className="text-sm text-slate-400">Loading FMV snapshot evidence…</p>
                ) : selectedMarketFmvDetailError ? (
                  <StatusBanner tone="error">{selectedMarketFmvDetailError}</StatusBanner>
                ) : selectedMarketFmvDetail ? (
                  <>
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-cyan-100">
                        Snapshot #{selectedMarketFmvDetail.id}
                      </p>
                      <h3 className="mt-1 text-lg font-semibold text-white">
                        {formatCurrency(selectedMarketFmvDetail.estimated_fmv)} ·{" "}
                        {marketFmvScopeLabel(selectedMarketFmvDetail.snapshot_scope)}
                      </h3>
                      <p className="mt-2 text-sm text-slate-400">
                        {selectedMarketFmvDetail.valuation_method.replace(/_/g, " ")} from {selectedMarketFmvDetail.comp_count} comps.
                      </p>
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-3">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Confidence</p>
                        <p className="mt-2 text-sm text-slate-100">{selectedMarketFmvDetail.confidence_bucket}</p>
                      </div>
                      <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-3">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Liquidity</p>
                        <p className="mt-2 text-sm text-slate-100">{selectedMarketFmvDetail.liquidity_bucket}</p>
                      </div>
                      <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-3">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Volatility</p>
                        <p className="mt-2 text-sm text-slate-100">{selectedMarketFmvDetail.volatility_bucket}</p>
                      </div>
                      <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-3">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Stale</p>
                        <p className="mt-2 text-sm text-slate-100">{selectedMarketFmvDetail.stale_data ? "Yes" : "No"}</p>
                      </div>
                    </div>
                    <div className="mt-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Recent comp preview</p>
                      <div className="mt-3 space-y-2">
                        {selectedMarketFmvDetail.comp_references.slice(0, 5).map((ref) => (
                          <div key={ref.id} className="rounded-2xl border border-white/10 bg-slate-900/60 p-3 text-sm text-slate-300">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <div className="font-medium text-slate-100">
                                  {ref.market_sale_record?.normalized_title ?? ref.market_sale_record?.raw_title ?? `Sale #${ref.market_sale_record_id}`}
                                </div>
                                <div className="mt-1 text-[11px] text-slate-400">
                                  {ref.market_sale_record?.sale_date ? formatDate(ref.market_sale_record.sale_date) : "Unknown date"} ·{" "}
                                  {formatCurrency(ref.market_sale_record?.total_price ?? ref.market_sale_record?.sale_price ?? null)}
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
                  <EmptyState
                    title="No snapshot selected"
                    description="Pick a deterministic FMV snapshot row to inspect the comp references used to produce it."
                  />
                )}
              </div>
            </div>
          )}
        </section>

        <section className="mt-6 rounded-3xl border border-emerald-400/20 bg-emerald-950/10 p-6 shadow-xl shadow-black/20">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white">Comparable Sales</h2>
              <p className="mt-2 text-sm text-slate-400">
                Deterministic comp analysis only. This panel surfaces the exact market-sale records that support the
                current identity, scope, and FMV context without mutating inventory, metadata, or pricing.
              </p>
            </div>
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
              {marketComps?.total_comps ?? 0} records · {marketComps?.total_groups ?? 0} groups
            </span>
          </div>

          {!detail.metadata_identity_key ? (
            <div className="mt-6">
              <EmptyState
                title="No metadata identity key"
                description="Comparable sales need a metadata identity key before records can be grouped deterministically."
              />
            </div>
          ) : marketCompsLoading ? (
            <p className="mt-6 text-sm text-slate-400">Loading comparable sales…</p>
          ) : marketCompsError ? (
            <div className="mt-6">
              <StatusBanner tone="error">{marketCompsError}</StatusBanner>
            </div>
          ) : !marketComps || marketComps.items.length === 0 ? (
            <div className="mt-6">
              <EmptyState
                title="No comparable sales"
                description="No grouped comps matched this identity yet."
              />
            </div>
          ) : (
            <div className="mt-6 space-y-4">
              {marketComps.items.map((group) => (
                <details key={group.group_key} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4" open>
                  <summary className="cursor-pointer list-none">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.16em] text-emerald-100/70">Comp group</p>
                        <h3 className="mt-1 text-base font-semibold text-white">{group.group_label}</h3>
                        <p className="mt-1 text-xs text-slate-400">
                          {group.comp_count} included · {group.excluded_count} excluded · {group.quality_signals.sale_recency_bucket}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${compQualityTone(group.quality_signals.sale_recency_bucket)}`}>
                          {group.quality_signals.sale_recency_bucket}
                        </span>
                        <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${compQualityTone(group.quality_signals.price_spread_bucket)}`}>
                          spread {group.quality_signals.price_spread_bucket}
                        </span>
                        <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${compQualityTone(group.quality_signals.volatility_signal)}`}>
                          {group.quality_signals.volatility_signal}
                        </span>
                      </div>
                    </div>
                  </summary>

                  <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Included comps</p>
                      <div className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-900/50">
                        <table className="w-full border-collapse text-left text-xs">
                          <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                            <tr>
                              <th className="p-3 font-medium">Sale</th>
                              <th className="p-3 font-medium">Source</th>
                              <th className="p-3 font-medium">Scope</th>
                              <th className="p-3 font-medium">Price</th>
                              <th className="p-3 font-medium">Signals</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-white/10 text-slate-200">
                            {group.included_comps.map((comp) => (
                              <tr key={comp.id}>
                                <td className="p-3 align-top">
                                  <div className="font-medium text-slate-100">
                                    {comp.normalized_title ?? comp.raw_title}
                                  </div>
                                  <div className="mt-1 text-[11px] text-slate-400">
                                    Issue {comp.normalized_issue ?? comp.raw_issue}
                                    {comp.sale_date ? ` · ${formatDate(comp.sale_date)}` : ""}
                                  </div>
                                  <div className="mt-2 flex flex-wrap gap-1.5">
                                    <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketComparableTone(comp.comp_classification)}`}>
                                      {marketComparableClassificationLabel(comp.comp_classification)}
                                    </span>
                                    {comp.eligibility_classification ? (
                                      <span className="inline-flex rounded-full border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-200">
                                        {comp.eligibility_classification.replace(/_/g, " ")}
                                      </span>
                                    ) : null}
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
                                <td className="p-3 align-top">
                                  <div className="flex flex-wrap gap-1.5">
                                    <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${compQualityTone(group.quality_signals.source_diversity_bucket)}`}>
                                      {group.quality_signals.source_diversity_bucket}
                                    </span>
                                    <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${compQualityTone(group.quality_signals.grade_consistency_bucket)}`}>
                                      {group.quality_signals.grade_consistency_bucket}
                                    </span>
                                  </div>
                                  <p className="mt-2 text-[11px] text-slate-500">
                                    {comp.comp_reason}
                                  </p>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Excluded comps</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {group.excluded_comps.length} record{group.excluded_comps.length === 1 ? "" : "s"} hidden by default
                      </p>
                      <div className="mt-3 space-y-2">
                        {group.excluded_comps.length === 0 ? (
                          <p className="text-sm text-slate-400">No excluded comps for this group.</p>
                        ) : (
                          group.excluded_comps.map((comp) => (
                            <div key={comp.id} className="rounded-xl border border-white/10 bg-white/5 p-3">
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="font-medium text-slate-100">{comp.normalized_title ?? comp.raw_title}</p>
                                  <p className="mt-1 text-[11px] text-slate-400">
                                    {comp.source_name} · {comp.comp_scope.replace(/_/g, " ")}
                                  </p>
                                </div>
                                <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${marketComparableTone(comp.comp_classification)}`}>
                                  {marketComparableClassificationLabel(comp.comp_classification)}
                                </span>
                              </div>
                              <p className="mt-2 text-xs text-slate-500">{comp.comp_reason}</p>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </details>
              ))}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
