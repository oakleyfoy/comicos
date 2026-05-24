import { useCallback, useEffect, useState } from "react";
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
  type InventoryRiskPriority,
  type InventoryRiskRead,
  type InventoryRiskType,
  type MetadataAlias,
  type MetadataAliasType,
  type OcrBatch,
  type OcrReplayRun,
  type OcrReplayType,
  type RelationshipReplayRun,
  type RelationshipReplayType,
  type OpsCanonicalCreatorRow,
  type OpsCanonicalSeriesRow,
  type OpsDashboardResponse,
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
  type RelationshipConflictDetectResponse,
  type RelationshipConflictListResponse,
  type RelationshipConflictSeverity,
  type RelationshipConflictStatus,
  type RelationshipConflictType,
  type RunDetectionListResponse,
  type RunDetectionSeries,
  type RunDetectionSeriesStatus,
  type VariantFamilyClassificationFilter,
  type VariantFamilyClustersListResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { LoadingState } from "../components/LoadingState";
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

  const [opsOrderArrivalReport, setOpsOrderArrivalReport] = useState<OrderArrivalIntelListResponse | null>(null);
  const [opsOrderArrivalCalendar, setOpsOrderArrivalCalendar] = useState<OrderArrivalIntelCalendarResponse | null>(
    null,
  );
  const [opsOrderArrivalClassification, setOpsOrderArrivalClassification] = useState<
    "" | OrderArrivalClassification
  >("");
  const [opsOrderArrivalError, setOpsOrderArrivalError] = useState<string | null>(null);

  const [opsCollectionSummary, setOpsCollectionSummary] = useState<CollectionAnalyticsSummary | null>(null);
  const [opsCollectionPublishers, setOpsCollectionPublishers] =
    useState<CollectionPublisherAnalyticsResponse | null>(null);
  const [opsCollectionQuality, setOpsCollectionQuality] = useState<CollectionQualityAnalyticsResponse | null>(null);
  const [opsCollectionComposition, setOpsCollectionComposition] =
    useState<CollectionCompositionResponse | null>(null);
  const [opsCollectionTimeline, setOpsCollectionTimeline] = useState<CollectionTimelineResponse | null>(null);
  const [opsCollectionAnalyticsError, setOpsCollectionAnalyticsError] = useState<string | null>(null);

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

  useEffect(() => {
    let ignore = false;

    async function loadDashboardAndAliases() {
      setIsLoading(true);
      setError(null);
      try {
        const [dashboardResponse, aliases] = await Promise.all([
          apiClient.getOpsDashboard(),
          apiClient.listMetadataAliases(),
        ]);
        if (!ignore) {
          setDashboard(dashboardResponse);
          setMetadataAliases(aliases);
          void apiClient.listRecentCoverLinkDecisionsForOps({ include_inactive: true, limit: 12 }).then(setCoverLinkDecisions);
        }
      } catch (loadError) {
        if (!ignore) {
          setError(
            loadError instanceof ApiError
              ? loadError.message
              : "Unable to load operations dashboard.",
          );
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
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

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

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
