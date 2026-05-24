import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type BulkMutationResult,
  type CoverLinkRelationshipType,
  type CoverRelationshipGraphEdge,
  type CoverRelationshipGraphRead,
  type DuplicateScanCandidatesResponse,
  type DuplicateScanEvidenceFlags,
  type CanonicalIssueLinkSuggestionRead,
  type RelationshipConflictListResponse,
  type RelationshipConflictRead,
  type VariantFamilyCandidatesResponse,
  type VariantFamilyEvidenceFlags,
  type OcrReviewItemKindLiteral,
  type OcrReviewQueueItem,
  type OcrReviewQueueQueryParams,
  type OcrReviewSummaryResponse,
} from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { StatusBanner } from "../StatusBanner";

const ITEM_KIND_OPTIONS: Array<{ value: OcrReviewItemKindLiteral; label: string }> = [
  { value: "ocr_candidate", label: "OCR candidates" },
  { value: "reconciliation_warning", label: "Reconciliation warnings" },
  { value: "barcode_candidate", label: "Barcode candidates" },
  { value: "match_candidate", label: "Match candidates" },
  { value: "ocr_quality_analysis", label: "OCR quality" },
];

type MatchCandidateDetail = Awaited<ReturnType<typeof apiClient.getCoverImageMatchCandidatesForOps>>[number];
const MATCH_LINK_RELATIONSHIP_OPTIONS: CoverLinkRelationshipType[] = [
  "same_cover",
  "same_issue",
  "duplicate_scan",
  "variant_family",
  "unrelated",
];

function formatLinkRelationship(value: CoverLinkRelationshipType): string {
  return value.replace(/_/g, " ");
}

function selectionKey(item: OcrReviewQueueItem): string {
  return `${item.item_kind}:${item.entity_id}`;
}

function formatQueueCell(item: OcrReviewQueueItem): string {
  switch (item.item_kind) {
    case "ocr_candidate":
      return item.candidate_type ?? "candidate";
    case "reconciliation_warning":
      return item.warning_type ?? "warning";
    case "barcode_candidate":
      return item.barcode_candidate?.barcode_type ?? "barcode";
    case "match_candidate":
      return item.match_candidate?.candidate_type ?? "match";
    case "ocr_quality_analysis":
      return item.quality_type ?? "quality";
    default:
      return item.item_kind;
  }
}

function formatReviewConfidence(item: OcrReviewQueueItem): string {
  if (item.item_kind === "match_candidate" && item.match_candidate) {
    return `#${item.match_candidate.candidate_rank} · ${(item.match_candidate.normalized_confidence_score * 100).toFixed(0)}% · ${
      item.match_candidate.confidence_bucket
    }`;
  }
  if (typeof item.norm_score === "number" && item.item_kind !== "reconciliation_warning") {
    return item.norm_score.toFixed(2);
  }
  return item.severity || item.confidence_bucket || "—";
}

function formatGroupingType(value: MatchCandidateDetail["grouping_type"]): string {
  return value ? value.replace(/_/g, " ") : "ungrouped";
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
    parts.push("probable variant-family grouping");
  }
  if (flags.same_issue_divergent_fingerprint) {
    parts.push("same-issue · divergent fingerprint");
  }
  if (flags.metadata_identity_normalized) {
    parts.push("normalized metadata identity");
  }
  if (flags.ocr_title_issue_exact_pairwise) {
    parts.push("OCR title+issue pairwise exact");
  }
  if (flags.publisher_exact_pairwise) {
    parts.push("publisher exact");
  }
  if (flags.fingerprint_divergent_signal) {
    parts.push("divergent fingerprints");
  }
  if (flags.supporting_shared_upcs.length) {
    parts.push(`UPC support: ${flags.supporting_shared_upcs.join(", ")}`);
  }
  return parts.length ? parts.join(" · ") : "cluster-linked only";
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
  if (typeof evidence.supporting_peer_count === "number") {
    parts.push(`${evidence.supporting_peer_count} related cover${evidence.supporting_peer_count === 1 ? "" : "s"}`);
  }
  return parts.join(" · ") || "review stored evidence";
}

function summarizeRelationshipConflictEvidence(evidence: Record<string, unknown>): string {
  const parts: string[] = [];
  if (Array.isArray(evidence.signals) && evidence.signals.length) {
    parts.push(`signals: ${evidence.signals.map((item) => String(item)).join(", ")}`);
  }
  if (Array.isArray(evidence.cycle_cover_image_ids) && evidence.cycle_cover_image_ids.length) {
    parts.push(`cycle covers: ${evidence.cycle_cover_image_ids.join(", ")}`);
  }
  if (typeof evidence.warning_type === "string") {
    parts.push(`warning: ${evidence.warning_type}`);
  }
  return parts.join(" · ") || "deterministic conflict evidence";
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

function rankingReasonStrings(
  candidate: MatchCandidateDetail,
  key: "conflicting_signals" | "missing_signals",
): string[] {
  const value = candidate.ranking_reason_json[key];
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

const OCR_GRAPH_LANES: CoverRelationshipGraphEdge["display_lane"][] = ["strong", "related", "needs_review", "blocked"];

function ocrGraphLaneLabel(lane: CoverRelationshipGraphEdge["display_lane"]): string {
  switch (lane) {
    case "strong":
      return "Strong";
    case "related":
      return "Related";
    case "blocked":
      return "Blocked";
    case "needs_review":
      return "Needs review";
    default:
      return lane;
  }
}

function groupMatchCandidates(candidates: MatchCandidateDetail[]): Array<{
  id: string;
  label: string;
  reason: string | null;
  bucket: MatchCandidateDetail["grouping_confidence_bucket"];
  candidates: MatchCandidateDetail[];
}> {
  const groups = new Map<
    string,
    {
      id: string;
      label: string;
      reason: string | null;
      bucket: MatchCandidateDetail["grouping_confidence_bucket"];
      candidates: MatchCandidateDetail[];
    }
  >();
  [...candidates]
    .sort(
      (a, b) =>
        a.candidate_rank - b.candidate_rank ||
        b.ranking_score - a.ranking_score ||
        b.normalized_confidence_score - a.normalized_confidence_score,
    )
    .forEach((candidate) => {
      const key = candidate.grouping_key ?? `ungrouped:${candidate.id}`;
      const existing = groups.get(key);
      if (existing) {
        existing.candidates.push(candidate);
        return;
      }
      groups.set(key, {
        id: key,
        label: candidate.grouping_type ? formatGroupingType(candidate.grouping_type) : "ungrouped candidate",
        reason: candidate.grouping_reason_summary,
        bucket: candidate.grouping_confidence_bucket,
        candidates: [candidate],
      });
    });
  return Array.from(groups.values());
}

async function revokeObjectUrlSoon(url: string | undefined): Promise<void> {
  if (!url?.startsWith("blob:")) {
    return;
  }
  URL.revokeObjectURL(url);
}

export function OcrReviewWorkspace(): JSX.Element | null {
  const { isOpsAdmin } = useAuth();
  const [summary, setSummary] = useState<OcrReviewSummaryResponse | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const [queue, setQueue] = useState<OcrReviewQueueItem[]>([]);
  const [queueTotal, setQueueTotal] = useState(0);
  const [queuePage, setQueuePage] = useState(1);
  const [queuePageSize, setQueuePageSize] = useState(25);
  const [queueScope, setQueueScope] = useState<"attention" | "all">("attention");
  const [itemKinds, setItemKinds] = useState<OcrReviewItemKindLiteral[]>([]);
  const [queueLoading, setQueueLoading] = useState(true);
  const [queueError, setQueueError] = useState<string | null>(null);

  const [selectedKeys, setSelectedKeys] = useState<Record<string, true>>({});
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [bulkMessage, setBulkMessage] = useState<string | null>(null);
  const [bulkError, setBulkError] = useState<string | null>(null);

  const [detailThumbUrl, setDetailThumbUrl] = useState<string | undefined>();
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [linkBusyCandidateId, setLinkBusyCandidateId] = useState<number | null>(null);
  const [linkRelationshipDrafts, setLinkRelationshipDrafts] = useState<Record<number, CoverLinkRelationshipType>>({});
  const [detailContext, setDetailContext] = useState<{
    ocrResults: Awaited<ReturnType<typeof apiClient.getCoverImageOcrResultsForOps>>;
    warnings: Awaited<ReturnType<typeof apiClient.getCoverImageOcrReconciliationWarningsForOps>>;
    barcodes: Awaited<ReturnType<typeof apiClient.getCoverImageBarcodeCandidatesForOps>>;
    fingerprints: Awaited<ReturnType<typeof apiClient.getCoverImageFingerprintsForOps>>;
    matchCandidates: Awaited<ReturnType<typeof apiClient.getCoverImageMatchCandidatesForOps>>;
    quality: Awaited<ReturnType<typeof apiClient.getCoverImageOcrQualityAnalysisForOps>>;
    relationshipGraph: CoverRelationshipGraphRead | null;
    duplicateScan: DuplicateScanCandidatesResponse;
    variantFamily: VariantFamilyCandidatesResponse;
    canonicalIssueSuggestions: CanonicalIssueLinkSuggestionRead[];
    relationshipConflicts: RelationshipConflictListResponse | null;
  } | null>(null);
  const [canonicalSuggestionBusyId, setCanonicalSuggestionBusyId] = useState<number | null>(null);
  const [relationshipConflictBusyId, setRelationshipConflictBusyId] = useState<number | null>(null);

  const fetchRelationshipGraphQuiet = useCallback(async (coverImageId: number): Promise<CoverRelationshipGraphRead | null> => {
    try {
      return await apiClient.getCoverRelationshipGraphForOps(coverImageId);
    } catch {
      return null;
    }
  }, []);

  const refreshSummary = useCallback(async () => {
    setSummaryError(null);
    try {
      const row = await apiClient.getOcrReviewSummaryForOps();
      setSummary(row);
    } catch (error) {
      setSummary(null);
      setSummaryError(error instanceof ApiError ? error.message : "Unable to load OCR review summary.");
    }
  }, []);

  const refreshQueue = useCallback(async () => {
    setQueueLoading(true);
    setQueueError(null);
    try {
      const params: OcrReviewQueueQueryParams = {
        queue_scope: queueScope,
        page: queuePage,
        page_size: queuePageSize,
        item_kind: itemKinds.length > 0 ? itemKinds : undefined,
      };
      const response = await apiClient.getOcrReviewQueueForOps(params);
      setQueue(response.items);
      setQueueTotal(response.total);
    } catch (error) {
      setQueue([]);
      setQueueTotal(0);
      setQueueError(error instanceof ApiError ? error.message : "Unable to load OCR review queue.");
    } finally {
      setQueueLoading(false);
    }
  }, [itemKinds, queuePage, queuePageSize, queueScope]);

  useEffect(() => {
    void refreshSummary();
  }, [refreshSummary]);

  useEffect(() => {
    if (!isOpsAdmin) {
      return;
    }
    void refreshQueue();
  }, [isOpsAdmin, refreshQueue]);

  const activeItem = useMemo(() => {
    if (!activeKey) {
      return undefined;
    }
    return queue.find((row) => selectionKey(row) === activeKey);
  }, [activeKey, queue]);

  const focalInventoryCopyId = useMemo(() => {
    if (!activeItem?.cover_image_id) {
      return null;
    }
    const nodes = detailContext?.relationshipGraph?.nodes;
    if (!nodes?.length) {
      return null;
    }
    const node = nodes.find((n) => n.cover_image_id === activeItem.cover_image_id);
    return node?.inventory?.inventory_copy_id ?? null;
  }, [activeItem, detailContext?.relationshipGraph?.nodes]);

  useEffect(() => {
    if (!detailContext?.matchCandidates) {
      return;
    }
    setLinkRelationshipDrafts((prev) => {
      const next = { ...prev };
      for (const candidate of detailContext.matchCandidates) {
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
      return next;
    });
  }, [detailContext]);

  const runLinkDecision = useCallback(
    async (candidate: MatchCandidateDetail, relationshipType: CoverLinkRelationshipType, decisionType: "approved_link" | "rejected_link") => {
      setLinkBusyCandidateId(candidate.id);
      setDetailError(null);
      try {
        await apiClient.createCoverLinkDecisionForOps({
          source_cover_image_id: candidate.source_cover_image_id,
          candidate_cover_image_id: candidate.candidate_cover_image_id,
          source_match_candidate_id: candidate.id,
          decision_type: decisionType,
          relationship_type: relationshipType,
        });
        await Promise.all([refreshQueue(), refreshSummary()]);
        if (activeItem) {
          const coverImageId = activeItem.cover_image_id;
          const [
            ocrResults,
            warnings,
            barcodes,
            fingerprints,
            matchCandidates,
            quality,
            relationshipGraph,
            duplicateScan,
            variantFamily,
            canonicalIssueSuggestions,
            relationshipConflicts,
          ] = await Promise.all([
            apiClient.getCoverImageOcrResultsForOps(coverImageId),
            apiClient.getCoverImageOcrReconciliationWarningsForOps(coverImageId),
            apiClient.getCoverImageBarcodeCandidatesForOps(coverImageId),
            apiClient.getCoverImageFingerprintsForOps(coverImageId),
            apiClient.getCoverImageMatchCandidatesForOps(coverImageId),
            apiClient.getCoverImageOcrQualityAnalysisForOps(coverImageId),
            fetchRelationshipGraphQuiet(coverImageId),
            apiClient.getDuplicateScanCandidatesForOps(coverImageId),
            apiClient.getVariantFamilyCandidatesForOps(coverImageId),
            apiClient.getCanonicalIssueSuggestionsForOps(coverImageId),
            apiClient.getRelationshipConflictsForCoverOps(coverImageId),
          ]);
          setDetailContext({
            ocrResults,
            warnings,
            barcodes,
            fingerprints,
            matchCandidates,
            quality,
            relationshipGraph,
            duplicateScan,
            variantFamily,
            canonicalIssueSuggestions,
            relationshipConflicts,
          });
        }
      } catch (error) {
        setDetailError(error instanceof ApiError ? error.message : "Unable to persist cover link decision.");
      } finally {
        setLinkBusyCandidateId(null);
      }
    },
    [activeItem, fetchRelationshipGraphQuiet, refreshQueue, refreshSummary],
  );

  const reviewCanonicalIssueSuggestion = useCallback(
    async (suggestionId: number, action: "approve" | "reject" | "ignore") => {
      if (!activeItem) {
        return;
      }
      setCanonicalSuggestionBusyId(suggestionId);
      setDetailError(null);
      try {
        if (action === "approve") {
          await apiClient.approveCanonicalIssueSuggestionForOps(suggestionId);
        } else if (action === "reject") {
          await apiClient.rejectCanonicalIssueSuggestionForOps(suggestionId);
        } else {
          await apiClient.ignoreCanonicalIssueSuggestionForOps(suggestionId);
        }
        const canonicalIssueSuggestions = await apiClient.getCanonicalIssueSuggestionsForOps(activeItem.cover_image_id);
        setDetailContext((prev) =>
          prev
            ? {
                ...prev,
                canonicalIssueSuggestions,
              }
            : prev,
        );
      } catch (error) {
        setDetailError(error instanceof ApiError ? error.message : "Unable to review canonical issue suggestion.");
      } finally {
        setCanonicalSuggestionBusyId(null);
      }
    },
    [activeItem],
  );

  const reviewRelationshipConflict = useCallback(
    async (conflictId: number, action: "acknowledge" | "dismiss" | "resolve") => {
      if (!activeItem) {
        return;
      }
      setRelationshipConflictBusyId(conflictId);
      setDetailError(null);
      try {
        if (action === "acknowledge") {
          await apiClient.acknowledgeRelationshipConflictForOps(conflictId);
        } else if (action === "dismiss") {
          await apiClient.dismissRelationshipConflictForOps(conflictId);
        } else {
          await apiClient.resolveRelationshipConflictForOps(conflictId);
        }
        const relationshipConflicts = await apiClient.getRelationshipConflictsForCoverOps(activeItem.cover_image_id);
        setDetailContext((prev) =>
          prev
            ? {
                ...prev,
                relationshipConflicts,
              }
            : prev,
        );
      } catch (error) {
        setDetailError(error instanceof ApiError ? error.message : "Unable to review relationship conflict.");
      } finally {
        setRelationshipConflictBusyId(null);
      }
    },
    [activeItem],
  );

  useEffect(() => {
    let ignore = false;
    void revokeObjectUrlSoon(detailThumbUrl);

    if (!activeItem || !isOpsAdmin) {
      setDetailThumbUrl(undefined);
      setDetailContext(null);
      setDetailError(null);
      setDetailLoading(false);
      return () => {
        ignore = true;
      };
    }

    const coverImageId = activeItem.cover_image_id;
    const thumbPath = `/files/cover-images/${coverImageId}/derivatives/thumb`;

    setDetailLoading(true);
    setDetailError(null);

    void (async (): Promise<void> => {
      try {
        const [
          blob,
          ocrResults,
          warnings,
          barcodes,
          fingerprints,
          matchCandidates,
          quality,
          duplicateScan,
          variantFamily,
          canonicalIssueSuggestions,
          relationshipConflicts,
        ] = await Promise.all([
          apiClient.fetchCoverImageBlob(thumbPath),
          apiClient.getCoverImageOcrResultsForOps(coverImageId),
          apiClient.getCoverImageOcrReconciliationWarningsForOps(coverImageId),
          apiClient.getCoverImageBarcodeCandidatesForOps(coverImageId),
          apiClient.getCoverImageFingerprintsForOps(coverImageId),
          apiClient.getCoverImageMatchCandidatesForOps(coverImageId),
          apiClient.getCoverImageOcrQualityAnalysisForOps(coverImageId),
          apiClient.getDuplicateScanCandidatesForOps(coverImageId),
          apiClient.getVariantFamilyCandidatesForOps(coverImageId),
          apiClient.getCanonicalIssueSuggestionsForOps(coverImageId),
          apiClient.getRelationshipConflictsForCoverOps(coverImageId),
        ]);

        const objectUrl = URL.createObjectURL(blob);
        const relationshipGraph = await fetchRelationshipGraphQuiet(coverImageId);
        if (ignore) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        setDetailThumbUrl((prev) => {
          void revokeObjectUrlSoon(prev);
          return objectUrl;
        });
        setDetailContext({
          ocrResults,
          warnings,
          barcodes,
          fingerprints,
          matchCandidates,
          quality,
          relationshipGraph,
          duplicateScan,
          variantFamily,
          canonicalIssueSuggestions,
          relationshipConflicts,
        });
      } catch (error) {
        if (!ignore) {
          setDetailError(
            error instanceof ApiError ? error.message : "Unable to load cover review context.",
          );
          setDetailContext(null);
        }
      } finally {
        if (!ignore) {
          setDetailLoading(false);
        }
      }
    })();

    return () => {
      ignore = true;
    };
  }, [activeItem, fetchRelationshipGraphQuiet, isOpsAdmin]);

  useEffect(() => {
    return () => {
      void revokeObjectUrlSoon(detailThumbUrl);
    };
  }, [detailThumbUrl]);

  function toggleKind(value: OcrReviewItemKindLiteral): void {
    setItemKinds((current) =>
      current.includes(value) ? current.filter((k) => k !== value) : [...current, value],
    );
    setQueuePage(1);
  }

  function toggleRow(item: OcrReviewQueueItem): void {
    const key = selectionKey(item);
    setSelectedKeys((prev) => {
      const next = { ...prev };
      if (next[key]) {
        delete next[key];
      } else {
        next[key] = true;
      }
      return next;
    });
  }

  function selectAllVisible(): void {
    const next: Record<string, true> = {};
    queue.forEach((row) => {
      next[selectionKey(row)] = true;
    });
    setSelectedKeys(next);
  }

  function clearSelection(): void {
    setSelectedKeys({});
  }

  const selectedItems = useMemo(
    () => queue.filter((row) => selectedKeys[selectionKey(row)]),
    [queue, selectedKeys],
  );

  const bulkKind = useMemo(() => {
    const kinds = new Set(selectedItems.map((row) => row.item_kind));
    if (kinds.size !== 1) {
      return null;
    }
    return selectedItems[0]?.item_kind ?? null;
  }, [selectedItems]);

  function summarizeBulkResult(label: string, result: BulkMutationResult): string {
    const skipped = Object.keys(result.skipped ?? {}).length;
    const ok = result.succeeded.length;
    return `${label}: updated ${ok} row(s)${skipped > 0 ? `, skipped ${skipped}` : ""}.`;
  }

  async function runBulk(
    runner: () => Promise<BulkMutationResult>,
    label: string,
  ): Promise<void> {
    setBulkError(null);
    setBulkMessage(null);
    try {
      const outcome = await runner();
      setBulkMessage(summarizeBulkResult(label, outcome));
      clearSelection();
      await Promise.all([refreshQueue(), refreshSummary()]);
    } catch (error) {
      setBulkError(error instanceof ApiError ? error.message : `${label} failed.`);
    }
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent): void {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
        return;
      }
      if (queue.length === 0 || (event.key !== "j" && event.key !== "k")) {
        return;
      }
      event.preventDefault();

      if (!activeKey) {
        const first = queue[0];
        if (first) {
          setActiveKey(selectionKey(first));
        }
        return;
      }

      let idx = queue.findIndex((row) => selectionKey(row) === activeKey);
      if (idx < 0) {
        idx = 0;
      }
      if (event.key === "j") {
        idx = Math.min(queue.length - 1, idx + 1);
      } else {
        idx = Math.max(0, idx - 1);
      }
      const nextItem = queue[idx];
      if (nextItem) {
        setActiveKey(selectionKey(nextItem));
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeKey, queue]);

  const pageCount = Math.max(1, Math.ceil(queueTotal / queuePageSize));

  if (!isOpsAdmin) {
    return null;
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-col gap-3 border-b border-white/10 pb-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">OCR Review Queue</h2>
          <p className="mt-2 text-sm text-slate-400">
            Centralized ops queue for OCR candidates, reconciliation warnings, barcodes, match signals,
            and quality flags. Bulk actions wrap existing acknowledgement paths only (no automated
            metadata writes). Keyboard: <kbd className="text-slate-200">j</kbd> /
            <kbd className="text-slate-200">k</kbd> move highlight.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={queueLoading}
            onClick={() => {
              void Promise.all([refreshQueue(), refreshSummary()]);
            }}
            className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:opacity-50"
          >
            {queueLoading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      {summaryError ? (
        <div className="mt-4">
          <StatusBanner tone="info">{summaryError}</StatusBanner>
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {summary ? (
          <>
            <span className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-slate-200">
              Pending OCR candidates: {summary.pending_ocr_candidates}
            </span>
            <span className="rounded-full border border-amber-400/25 bg-amber-400/5 px-3 py-1 text-xs text-amber-100">
              Open reconciliation warnings: {summary.open_reconciliation_warnings}
            </span>
            <span className="rounded-full border border-rose-400/25 bg-rose-500/5 px-3 py-1 text-xs text-rose-100">
              Critical OCR quality: {summary.critical_ocr_quality_analyses}
            </span>
            <span className="rounded-full border border-violet-400/25 bg-violet-500/5 px-3 py-1 text-xs text-violet-100">
              Pending high bucket matches: {summary.pending_high_bucket_match_candidates}
            </span>
            <span className="rounded-full border border-cyan-400/25 bg-cyan-500/5 px-3 py-1 text-xs text-cyan-100">
              Batches w/ failures: {summary.batches_with_failed_items}
            </span>
          </>
        ) : (
          <p className="text-xs text-slate-500">Summary loading…</p>
        )}
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)_minmax(0,1fr)] lg:items-end">
        <label className="flex flex-col gap-2 text-sm text-slate-300">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Queue scope</span>
          <select
            value={queueScope}
            onChange={(event) => {
              setQueueScope(event.target.value as "attention" | "all");
              setQueuePage(1);
            }}
            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
          >
            <option value="attention">Attention (recommended)</option>
            <option value="all">Everything</option>
          </select>
        </label>
        <label className="flex flex-col gap-2 text-sm text-slate-300">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Kinds</span>
          <div className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-200">
            <div className="flex flex-wrap gap-2">
              {ITEM_KIND_OPTIONS.map((opt) => (
                <label key={opt.value} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={itemKinds.includes(opt.value)}
                    onChange={() => toggleKind(opt.value)}
                  />
                  {opt.label}
                </label>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-slate-500">Leave empty for all kinds.</p>
          </div>
        </label>
        <label className="flex flex-col gap-2 text-sm text-slate-300">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Page size</span>
          <select
            value={queuePageSize}
            onChange={(event) => {
              setQueuePageSize(Number(event.target.value));
              setQueuePage(1);
            }}
            className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white"
          >
            {[25, 50, 100].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => selectAllVisible()}
          className="rounded-xl border border-white/15 px-3 py-2 text-xs font-semibold text-slate-100 transition hover:border-cyan-300/35"
        >
          Select visible
        </button>
        <button
          type="button"
          onClick={() => clearSelection()}
          className="rounded-xl border border-white/15 px-3 py-2 text-xs font-semibold text-slate-100 transition hover:border-white/30"
        >
          Clear selection
        </button>
        <button
          type="button"
          disabled={bulkKind !== "reconciliation_warning" || selectedItems.length === 0}
          onClick={() =>
            void runBulk(
              () =>
                apiClient.bulkAcknowledgeOcrReconciliationWarningsForOps({
                  ids: selectedItems.map((item) => item.entity_id),
                }),
              "Acknowledge warnings",
            )
          }
          className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-100 transition hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Bulk acknowledge warnings
        </button>
        <button
          type="button"
          disabled={bulkKind !== "reconciliation_warning" || selectedItems.length === 0}
          onClick={() =>
            void runBulk(
              () =>
                apiClient.bulkDismissOcrReconciliationWarningsForOps({
                  ids: selectedItems.map((item) => item.entity_id),
                }),
              "Dismiss warnings",
            )
          }
          className="rounded-xl border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs font-semibold text-amber-100 transition hover:bg-amber-400/15 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Bulk dismiss warnings
        </button>
        <button
          type="button"
          disabled={bulkKind !== "barcode_candidate" || selectedItems.length === 0}
          onClick={() =>
            void runBulk(
              () =>
                apiClient.bulkApproveBarcodeCandidatesForOps({
                  ids: selectedItems.map((item) => item.entity_id),
                }),
              "Approve barcodes",
            )
          }
          className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-400/15 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Bulk approve barcode candidates
        </button>
        <button
          type="button"
          disabled={bulkKind !== "barcode_candidate" || selectedItems.length === 0}
          onClick={() =>
            void runBulk(
              () =>
                apiClient.bulkRejectBarcodeCandidatesForOps({
                  ids: selectedItems.map((item) => item.entity_id),
                }),
              "Reject barcodes",
            )
          }
          className="rounded-xl border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-xs font-semibold text-rose-100 transition hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Bulk reject barcode candidates
        </button>
      </div>
      {bulkError ? (
        <div className="mt-3">
          <StatusBanner tone="error">{bulkError}</StatusBanner>
        </div>
      ) : null}
      {bulkMessage ? (
        <div className="mt-3">
          <StatusBanner tone="success">{bulkMessage}</StatusBanner>
        </div>
      ) : null}
      <p className="mt-2 text-[11px] text-slate-500">
        Bulk actions require every selected row to share the same kind (warnings vs barcodes).
      </p>

      {queueError ? (
        <div className="mt-4">
          <StatusBanner tone="error">{queueError}</StatusBanner>
        </div>
      ) : null}

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
        <div className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-950/50">
          {queueLoading ? (
            <div className="px-6 py-12 text-center text-sm text-slate-400">Loading queue…</div>
          ) : queue.length === 0 ? (
            <div className="px-6 py-12 text-center text-sm text-slate-400">Queue is empty.</div>
          ) : (
            <table className="min-w-full text-left text-sm text-slate-200">
              <thead className="border-b border-white/10 bg-slate-950/80 text-[11px] uppercase tracking-[0.14em] text-slate-500">
                <tr>
                  <th className="px-4 py-3">Sel</th>
                  <th className="px-4 py-3">Kind</th>
                  <th className="px-4 py-3">Cover</th>
                  <th className="px-4 py-3">Detail</th>
                  <th className="px-4 py-3">Confidence / severity</th>
                  <th className="px-4 py-3">Created</th>
                </tr>
              </thead>
              <tbody>
                {queue.map((item) => {
                  const sk = selectionKey(item);
                  const isActive = activeKey === sk;
                  return (
                    <tr
                      key={sk}
                      className={`cursor-pointer border-b border-white/5 ${isActive ? "bg-cyan-500/5" : "hover:bg-white/5"}`}
                      onClick={() => setActiveKey(sk)}
                    >
                      <td className="px-4 py-2">
                        <input
                          type="checkbox"
                          checked={Boolean(selectedKeys[sk])}
                          onChange={(event) => {
                            event.stopPropagation();
                            toggleRow(item);
                          }}
                          onClick={(event) => event.stopPropagation()}
                        />
                      </td>
                      <td className="px-4 py-2 text-xs text-slate-300">{item.item_kind}</td>
                      <td className="px-4 py-2 text-xs text-slate-200">#{item.cover_image_id}</td>
                      <td className="px-4 py-2 text-xs text-slate-200">{formatQueueCell(item)}</td>
                      <td className="px-4 py-2 text-xs text-slate-300">{formatReviewConfidence(item)}</td>
                      <td className="px-4 py-2 text-[11px] text-slate-500">
                        {new Date(item.created_at).toLocaleString()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
          {!activeItem ? (
            <p className="text-sm text-slate-500">Select a row to inspect OCR context snapshots.</p>
          ) : (
            <>
              <div className="flex flex-col gap-3 md:flex-row">
                <div className="w-full max-w-[12rem]">
                  {detailThumbUrl ? (
                    <img
                      src={detailThumbUrl}
                      alt={`Cover ${activeItem.cover_image_id}`}
                      className="w-full rounded-xl border border-white/10 object-cover"
                    />
                  ) : (
                    <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-white/15 text-xs text-slate-500">
                      {detailLoading ? "Loading thumbnail…" : "No thumbnail"}
                    </div>
                  )}
                </div>
                <div className="flex-1 text-sm text-slate-200">
                  <p className="font-semibold text-white">
                    Cover #{activeItem.cover_image_id} · {activeItem.item_kind}
                  </p>
                  <p className="mt-2 text-xs text-slate-400">
                    Active entity #{activeItem.entity_id} ({formatQueueCell(activeItem)})
                  </p>
                </div>
              </div>

              {detailError ? (
                <div className="mt-3">
                  <StatusBanner tone="error">{detailError}</StatusBanner>
                </div>
              ) : null}
              {detailLoading ? (
                <p className="mt-4 text-xs text-slate-500">Loading OCR context payloads…</p>
              ) : detailContext ? (
                <div className="mt-4 space-y-4 text-xs text-slate-300">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      OCR results ({detailContext.ocrResults.length})
                    </p>
                    <ul className="mt-2 space-y-1">
                      {detailContext.ocrResults.slice(0, 6).map((row) => (
                        <li key={row.id} className="rounded-lg border border-white/10 px-3 py-2">
                          #{row.id} · {row.ocr_engine} · {row.processing_status}{" "}
                          {typeof row.confidence_score === "number"
                            ? `· conf ${row.confidence_score}`
                            : ""}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-lg border border-amber-400/25 bg-slate-950/55 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-100">
                      Relationship conflicts · focal cover #{activeItem.cover_image_id}
                    </p>
                    <p className="mt-1 text-[11px] text-slate-500">
                      Deterministic conflict visibility only. Contradictions are surfaced here for review and lifecycle
                      tracking; nothing auto-corrects links, canonical targets, or metadata.
                    </p>
                    {detailContext.relationshipConflicts &&
                    detailContext.relationshipConflicts.conflicts.length === 0 ? (
                      <p className="mt-2 text-xs text-slate-500">No relationship conflicts for this cover.</p>
                    ) : detailContext.relationshipConflicts ? (
                      <div className="mt-3 space-y-2">
                        {detailContext.relationshipConflicts.conflicts.map((row) => (
                          <div key={row.id} className="rounded-md border border-white/10 px-2 py-2 text-[11px]">
                            <p>
                              <span
                                className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${relationshipConflictSeverityTone(
                                  row.severity,
                                )}`}
                              >
                                {row.severity}
                              </span>
                              <span className="ml-2 font-semibold text-slate-100">
                                {row.conflict_type.replace(/_/g, " ")}
                              </span>
                              <span className="ml-2 text-slate-400">state {row.status}</span>
                            </p>
                            <p className="mt-1 text-slate-500">
                              {summarizeRelationshipConflictEvidence(row.evidence_json)}
                            </p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <button
                                type="button"
                                disabled={relationshipConflictBusyId === row.id}
                                onClick={() => void reviewRelationshipConflict(row.id, "acknowledge")}
                                className="rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-2 py-1 text-[10px] font-semibold text-cyan-100 disabled:opacity-40"
                              >
                                Acknowledge
                              </button>
                              <button
                                type="button"
                                disabled={relationshipConflictBusyId === row.id}
                                onClick={() => void reviewRelationshipConflict(row.id, "dismiss")}
                                className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-2 py-1 text-[10px] font-semibold text-amber-100 disabled:opacity-40"
                              >
                                Dismiss
                              </button>
                              <button
                                type="button"
                                disabled={relationshipConflictBusyId === row.id}
                                onClick={() => void reviewRelationshipConflict(row.id, "resolve")}
                                className="rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-2 py-1 text-[10px] font-semibold text-emerald-100 disabled:opacity-40"
                              >
                                Resolve
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      Reconciliation warnings ({detailContext.warnings.length})
                    </p>
                    <ul className="mt-2 space-y-1">
                      {detailContext.warnings.slice(0, 6).map((w) => (
                        <li key={w.id} className="rounded-lg border border-amber-400/25 px-3 py-2">
                          {w.warning_type} · {w.status} · {w.message}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      Barcode candidates ({detailContext.barcodes.length})
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      Fingerprints ({detailContext.fingerprints.length})
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      Human-approved relationship graph (focal cover #{activeItem.cover_image_id})
                    </p>
                    <p className="mt-1 text-[11px] text-slate-500">
                      One-hop subgraph from persisted CoverImageLinkDecision rows — active only. Confidence, grouping,
                      OCR, fingerprints, or barcodes are not consulted here.
                    </p>
                    {detailContext.relationshipGraph && detailContext.relationshipGraph.edges.length > 0 ? (
                      <div className="mt-2 space-y-2">
                        {OCR_GRAPH_LANES.map((lane) => {
                          const laneEdges = detailContext.relationshipGraph!.edges.filter(
                            (edge) => edge.display_lane === lane,
                          );
                          if (laneEdges.length === 0) {
                            return null;
                          }
                          return (
                            <div key={lane} className="rounded-lg border border-cyan-400/25 bg-slate-950/65 px-3 py-2">
                              <p className="text-[11px] font-semibold text-cyan-100">
                                {ocrGraphLaneLabel(lane)} ({laneEdges.length})
                              </p>
                              <ul className="mt-1 space-y-1">
                                {laneEdges.map((edge) => (
                                  <li key={edge.decision_id} className="text-[11px] text-slate-300">
                                    #{edge.source_cover_image_id} → #{edge.candidate_cover_image_id} · decision #
                                    {edge.decision_id} · {edge.created_at.slice(0, 10)}{" "}
                                    {edge.decision_reason ? `· ${edge.decision_reason}` : ""}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          );
                        })}
                      </div>
                    ) : detailContext.relationshipGraph ? (
                      <p className="mt-2 text-xs text-slate-600">No active human edges for this cover.</p>
                    ) : (
                      <p className="mt-2 text-xs text-slate-600">Relationship graph unavailable for this drill-down.</p>
                    )}
                  </div>
                  <div className="rounded-lg border border-amber-400/25 bg-slate-950/50 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-100">
                      Duplicate scan intelligence · focal cover #{activeItem.cover_image_id}
                    </p>
                    <p className="mt-1 text-[11px] text-slate-500">
                      Read-only deterministic view (SHA256, fingerprints, probable duplicate-scan groups, human duplicate-scan
                      links). Unrelated decisions can suppress pairwise cues. Never merges or modifies records.
                    </p>
                    {(() => {
                      const dup = detailContext.duplicateScan;
                      const hasSignal =
                        dup.duplicate_peers.length > 0 || dup.suppressed_pairs_touching_focal.length > 0;
                      return (
                        <div className="mt-3 space-y-3">
                          {!hasSignal ? (
                            <p className="text-xs text-slate-500">No duplicate-scan signals for this cover.</p>
                          ) : (
                            <StatusBanner tone="warning">
                              Likely duplicate-scan cluster nearby — inspect peers and suppressed pairs below.
                            </StatusBanner>
                          )}
                          {dup.touching_clusters.length > 0 ? (
                            <div>
                              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                Clusters touching this cover
                              </p>
                              <ul className="mt-2 space-y-2 text-[11px]">
                                {dup.touching_clusters.map((c) => (
                                  <li key={c.cluster_key} className="rounded-md border border-white/10 px-2 py-2">
                                    <p>
                                      {c.cover_image_ids.map((idNum) => (
                                        <span key={idNum} className="mr-2 font-mono text-slate-200">
                                          #{idNum}
                                        </span>
                                      ))}
                                      · {c.classification} · {c.evidence_strength.replace(/_/g, " ")} · size{" "}
                                      {c.cluster_size}
                                    </p>
                                    <p className="mt-1 font-mono text-[10px] text-slate-600">{c.cluster_key}</p>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                          {dup.duplicate_peers.length > 0 ? (
                            <div>
                              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Peers</p>
                              <ul className="mt-2 space-y-2 text-[11px]">
                                {dup.duplicate_peers.map((pPeer) => {
                                  const bridging = Boolean(
                                    (pPeer.evidence_detail as Record<string, unknown>)
                                      ?.cluster_transitive_duplicate_scan,
                                  );
                                  return (
                                    <li key={pPeer.pair_key} className="rounded-md border border-white/10 px-2 py-2">
                                      <p>
                                        <span className="font-mono text-slate-100">
                                          Peer cover #{pPeer.peer_cover_image_id}
                                        </span>
                                        {" · "}
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
                                        <span className="text-slate-300">{summarizeDuplicateEvidence(pPeer.evidences)}</span>
                                      </p>
                                      <p className="mt-1 text-slate-500">
                                        Human decision:{" "}
                                        {pPeer.human_duplicate_scan_decision_id != null
                                          ? `#${pPeer.human_duplicate_scan_decision_id}`
                                          : "—"}
                                        {bridging ? " · cluster-linked peer" : null}
                                      </p>
                                    </li>
                                  );
                                })}
                              </ul>
                            </div>
                          ) : null}
                          {dup.suppressed_pairs_touching_focal.length > 0 ? (
                            <div>
                              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                Suppressed by unrelated link decisions
                              </p>
                              <ul className="mt-2 space-y-1 text-[11px] text-slate-300">
                                {dup.suppressed_pairs_touching_focal.map((sup) => (
                                  <li key={sup.pair_key}>
                                    {sup.pair_key}: {sup.suppressed_signal_labels.join(", ") || "(no labels)"}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                        </div>
                      );
                    })()}
                  </div>
                  <div className="rounded-lg border border-violet-400/30 bg-slate-950/55 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-violet-100">
                      Variant family intelligence · focal cover #{activeItem.cover_image_id}
                    </p>
                    <p className="mt-1 text-[11px] text-slate-500">
                      Confirmed (human-approved variant_family links) versus probable deterministic clusters. Navigate using
                      monospaced cover ids. Duplicate-scan pairs are excluded upstream.
                    </p>
                    {(() => {
                      const vfCtx = detailContext.variantFamily;
                      const has =
                        vfCtx.variant_peers.length > 0 || vfCtx.suppressed_pairs_touching_focal.length > 0;
                      return (
                        <div className="mt-3 space-y-3">
                          {!has ? (
                            <p className="text-xs text-slate-500">No variant-family context for this cover.</p>
                          ) : (
                            <StatusBanner tone="info">
                              Variant-family clustering — probable vs confirmed is labeled explicitly per peer.
                            </StatusBanner>
                          )}
                          {vfCtx.touching_clusters.length > 0 ? (
                            <div>
                              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Clusters</p>
                              <ul className="mt-2 space-y-2 text-[11px]">
                                {vfCtx.touching_clusters.map((cv) => (
                                  <li key={cv.cluster_key} className="rounded-md border border-white/10 px-2 py-2">
                                    <p>
                                      {cv.cover_image_ids.map((idNumV) => (
                                        <span key={idNumV} className="mr-2 font-mono text-slate-200">
                                          #{idNumV}
                                        </span>
                                      ))}
                                      · {cv.classification} · {cv.evidence_strength.replace(/_/g, " ")}
                                    </p>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                          {vfCtx.variant_peers.length > 0 ? (
                            <div>
                              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Peers</p>
                              <ul className="mt-2 space-y-2 text-[11px]">
                                {vfCtx.variant_peers.map((pvp) => {
                                  const bridgingVf = Boolean(
                                    (pvp.evidence_detail as Record<string, unknown>)
                                      ?.cluster_transitive_variant_family,
                                  );
                                  return (
                                    <li key={pvp.pair_key} className="rounded-md border border-white/10 px-2 py-2">
                                      <p>
                                        <span className="font-mono text-slate-50">Cover #{pvp.peer_cover_image_id}</span>
                                        {" · "}
                                        <span
                                          className={
                                            pvp.classification === "confirmed"
                                              ? "text-emerald-200"
                                              : "text-violet-200"
                                          }
                                        >
                                          {pvp.classification}
                                        </span>
                                        {" · "}
                                        <span className="text-slate-300">
                                          {summarizeVariantFamilyEvidence(pvp.evidences)}
                                        </span>
                                      </p>
                                      <p className="mt-1 text-slate-500">
                                        Human decision{" "}
                                        {pvp.human_variant_family_decision_id != null
                                          ? `#${pvp.human_variant_family_decision_id}`
                                          : "—"}
                                        {bridgingVf ? " · cluster-linked" : ""}
                                      </p>
                                    </li>
                                  );
                                })}
                              </ul>
                            </div>
                          ) : null}
                          {vfCtx.suppressed_pairs_touching_focal.length > 0 ? (
                            <div>
                              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                Suppressed (unrelated decisions)
                              </p>
                              <ul className="mt-2 space-y-1 text-[11px] text-slate-300">
                                {vfCtx.suppressed_pairs_touching_focal.map((sv) => (
                                  <li key={sv.pair_key}>
                                    {sv.pair_key}: {sv.suppressed_signal_labels.join(", ") || "(no labels)"}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                        </div>
                      );
                    })()}
                  </div>
                  <div className="rounded-lg border border-cyan-400/25 bg-slate-950/55 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-100">
                      Canonical issue suggestions · focal cover #{activeItem.cover_image_id}
                    </p>
                    <p className="mt-1 text-[11px] text-slate-500">
                      Deterministic review-only suggestions. Approvals and rejections stay on the suggestion artifact and do
                      not mutate canonical metadata, aliases, or inventory links.
                    </p>
                    {detailContext.canonicalIssueSuggestions.length === 0 ? (
                      <p className="mt-2 text-xs text-slate-500">No canonical issue suggestions for this cover.</p>
                    ) : (
                      <div className="mt-3 space-y-2">
                        {detailContext.canonicalIssueSuggestions.map((row) => (
                          <div key={row.id} className="rounded-md border border-white/10 px-2 py-2 text-[11px]">
                            <p>
                              <span className="font-semibold text-slate-100">{row.suggestion_type.replace(/_/g, " ")}</span>
                              {" · "}
                              <span className="text-cyan-100">{row.confidence_bucket}</span>
                              {" · "}
                              issue #{row.canonical_issue_id ?? "?"}
                              {" · "}
                              state {row.review_state}
                            </p>
                            <p className="mt-1 text-slate-500">{summarizeCanonicalIssueEvidence(row.evidence_json)}</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <button
                                type="button"
                                disabled={canonicalSuggestionBusyId === row.id}
                                onClick={() => void reviewCanonicalIssueSuggestion(row.id, "approve")}
                                className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold text-emerald-100 disabled:opacity-40"
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                disabled={canonicalSuggestionBusyId === row.id}
                                onClick={() => void reviewCanonicalIssueSuggestion(row.id, "reject")}
                                className="rounded-lg border border-rose-400/30 bg-rose-500/10 px-2 py-1 text-[10px] font-semibold text-rose-100 disabled:opacity-40"
                              >
                                Reject
                              </button>
                              <button
                                type="button"
                                disabled={canonicalSuggestionBusyId === row.id}
                                onClick={() => void reviewCanonicalIssueSuggestion(row.id, "ignore")}
                                className="rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-[10px] font-semibold text-slate-100 disabled:opacity-40"
                              >
                                Ignore
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      Match candidates ({detailContext.matchCandidates.length})
                    </p>
                    <div className="mt-2 space-y-2">
                      {groupMatchCandidates(detailContext.matchCandidates.slice(0, 12)).map((group) => (
                        <details
                          key={group.id}
                          className="rounded-lg border border-white/10 bg-slate-950/60 px-3 py-2"
                          open={group.candidates.length <= 2}
                        >
                          <summary className="cursor-pointer list-none">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="font-semibold text-slate-100">
                                {group.label} · {group.candidates.length} candidate
                                {group.candidates.length === 1 ? "" : "s"}
                              </p>
                              <p className="text-slate-300">
                                {group.bucket ?? "n/a"} · top rank #{group.candidates[0]?.candidate_rank ?? "?"}
                              </p>
                            </div>
                            <p className="mt-1 text-slate-400">
                              {group.reason ?? "No grouping explanation recorded for this candidate set."}
                            </p>
                          </summary>
                          <div className="mt-2 space-y-2">
                            {group.candidates.map((candidate) => {
                              const conflictingSignals = rankingReasonStrings(candidate, "conflicting_signals");
                              const missingSignals = rankingReasonStrings(candidate, "missing_signals");
                              const relationshipDraft =
                                linkRelationshipDrafts[candidate.id] ?? candidate.active_link_decision?.relationship_type ?? "same_issue";
                              return (
                                <div key={candidate.id} className="rounded-lg border border-white/10 px-3 py-2">
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <p className="font-semibold text-slate-100">
                                      #{candidate.candidate_rank} · {candidate.candidate_type.replace(/_/g, " ")} ·{" "}
                                      {candidate.confidence_bucket}
                                    </p>
                                    <p className="text-slate-300">
                                      {(candidate.normalized_confidence_score * 100).toFixed(0)}% · raw{" "}
                                      {candidate.deterministic_score.toFixed(2)}
                                    </p>
                                  </div>
                                  <p className="mt-1 text-slate-300">
                                    {candidate.confidence_explanation_summary ?? "No confidence explanation recorded."}
                                  </p>
                                  <p className="mt-1 text-slate-400">
                                    {String(
                                      candidate.ranking_reason_json.ranking_explanation_summary ??
                                        "No ranking explanation recorded.",
                                    )}
                                  </p>
                                  {candidate.active_link_decision ? (
                                    <p className="mt-1 text-slate-300">
                                      Human decision: {candidate.active_link_decision.decision_type.replace(/_/g, " ")} ·{" "}
                                      {formatLinkRelationship(candidate.active_link_decision.relationship_type)}
                                    </p>
                                  ) : null}
                                  {(() => {
                                    const graph = detailContext.relationshipGraph;
                                    if (!graph) {
                                      return null;
                                    }
                                    const pair = graph.edges.find(
                                      (edge) =>
                                        edge.source_cover_image_id === candidate.source_cover_image_id &&
                                        edge.candidate_cover_image_id === candidate.candidate_cover_image_id,
                                    );
                                    if (!pair) {
                                      return (
                                        <p className="mt-1 text-[11px] text-slate-600">
                                          No matching active human graph edge for this directional pair yet.
                                        </p>
                                      );
                                    }
                                    return (
                                      <p className="mt-1 text-[11px] text-cyan-200">
                                        Matching active graph edge: {ocrGraphLaneLabel(pair.display_lane)} lane · #
                                        {pair.decision_id} · {pair.decision_type.replace(/_/g, " ")} ·{" "}
                                        {formatLinkRelationship(pair.relationship_type)}
                                      </p>
                                    );
                                  })()}
                                  {candidate.contributing_signals.length > 0 ? (
                                    <p className="mt-1 text-slate-400">
                                      Signals:{" "}
                                      {candidate.contributing_signals
                                        .slice(0, 3)
                                        .map((item) => String(item.label ?? item.signal ?? "signal"))
                                        .join(", ")}
                                    </p>
                                  ) : null}
                                  {candidate.penalties.length > 0 ? (
                                    <p className="mt-1 text-slate-400">
                                      Penalties:{" "}
                                      {candidate.penalties
                                        .slice(0, 2)
                                        .map((item) => String(item.label ?? item.signal ?? "penalty"))
                                        .join(", ")}
                                    </p>
                                  ) : null}
                                  {conflictingSignals.length > 0 ? (
                                    <p className="mt-1 text-slate-400">
                                      Conflicts: {conflictingSignals.slice(0, 3).join(", ")}
                                    </p>
                                  ) : null}
                                  {missingSignals.length > 0 ? (
                                    <p className="mt-1 text-slate-500">
                                      Missing: {missingSignals.slice(0, 3).join(", ")}
                                    </p>
                                  ) : null}
                                  <div className="mt-2 flex flex-wrap items-center gap-2">
                                    <select
                                      value={relationshipDraft}
                                      disabled={linkBusyCandidateId === candidate.id}
                                      onChange={(event) =>
                                        setLinkRelationshipDrafts((prev) => ({
                                          ...prev,
                                          [candidate.id]: event.target.value as CoverLinkRelationshipType,
                                        }))
                                      }
                                      className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-[11px] text-slate-100"
                                    >
                                      {MATCH_LINK_RELATIONSHIP_OPTIONS.map((option) => (
                                        <option key={option} value={option}>
                                          {formatLinkRelationship(option)}
                                        </option>
                                      ))}
                                    </select>
                                    <button
                                      type="button"
                                      disabled={linkBusyCandidateId === candidate.id}
                                      onClick={() =>
                                        void runLinkDecision(candidate, relationshipDraft, "approved_link")
                                      }
                                      className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[11px] font-semibold text-emerald-100 disabled:opacity-40"
                                    >
                                      Quick approve link
                                    </button>
                                    <button
                                      type="button"
                                      disabled={linkBusyCandidateId === candidate.id}
                                      onClick={() =>
                                        void runLinkDecision(candidate, "unrelated", "rejected_link")
                                      }
                                      className="rounded-lg border border-rose-400/30 bg-rose-500/10 px-2 py-1 text-[11px] font-semibold text-rose-100 disabled:opacity-40"
                                    >
                                      Quick reject unrelated
                                    </button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </details>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      OCR quality ({detailContext.quality.length})
                    </p>
                    {activeItem.item_kind === "ocr_quality_analysis" ? (
                      <div className="mt-2 rounded-lg border border-amber-400/30 bg-amber-500/5 p-3 text-[11px] text-slate-200">
                        <p className="font-semibold text-amber-100">High-resolution review escalation</p>
                        <p className="mt-1 text-slate-300">
                          Owners file these from the inventory workspace (ops cannot POST the owner escalate endpoint).
                          Reference{" "}
                          <code className="rounded bg-slate-950/80 px-1 font-mono text-[10px] text-cyan-200">
                            source_ocr_quality_analysis_id
                          </code>{" "}
                          <span className="font-mono text-cyan-100">#{activeItem.entity_id}</span> when creating the request.
                        </p>
                        {focalInventoryCopyId != null ? (
                          <Link
                            to={`/inventory/${focalInventoryCopyId}`}
                            className="mt-2 inline-block font-semibold text-cyan-200 underline-offset-4 hover:underline"
                          >
                            Open inventory #{focalInventoryCopyId}
                          </Link>
                        ) : (
                          <p className="mt-2 text-slate-500">
                            No inventory copy surfaced on this relationship graph snapshot — match the owner's copy manually.
                          </p>
                        )}
                      </div>
                    ) : null}
                    <ul className="mt-2 space-y-1">
                      {detailContext.quality.slice(0, 8).map((row) => (
                        <li key={row.id} className="rounded-lg border border-white/10 px-3 py-2">
                          #{row.id} · {row.quality_type} · {row.severity} · score {row.deterministic_score}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : (
                !detailError && (
                  <p className="mt-4 text-xs text-slate-500">Nothing to preview for this selection.</p>
                )
              )}
            </>
          )}
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
        <p>
          Page {queuePage} of {pageCount} · {queueTotal} total matches
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={queuePage <= 1 || queueLoading}
            onClick={() => setQueuePage((p) => Math.max(1, p - 1))}
            className="rounded-xl border border-white/15 px-3 py-1 font-semibold text-slate-100 transition hover:bg-white/5 disabled:opacity-40"
          >
            Prev
          </button>
          <button
            type="button"
            disabled={queuePage >= pageCount || queueLoading}
            onClick={() => setQueuePage((p) => Math.min(pageCount, p + 1))}
            className="rounded-xl border border-white/15 px-3 py-1 font-semibold text-slate-100 transition hover:bg-white/5 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}
