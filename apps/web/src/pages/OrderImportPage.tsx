import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  resolveCoverImageOcrHeadline,
  type AiDraftOrderItem,
  type AiParseOrderResponse,
  type CoverImageOcrHeadlineStatus,
  type CoverOcrCandidateReviewStatus,
  type DraftImport,
  type DraftSourceType,
  type ImportParseJobStatus,
  type InventoryCoverImage,
} from "../api/client";
import { MetadataReviewDraftCard } from "../components/MetadataReviewDraftCard";
import { ImportReviewCard } from "../components/imports/ImportReviewCard";
import { useAuth } from "../auth/AuthContext";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import {
  creatorAliasRowKey,
  hasCreatorMetadataWarningNotes,
  hasMalformedReleaseDateNote,
  zipCreatorSlots,
  CREATOR_ROLE_LABELS,
} from "./metadataReviewPresentation";
import {
  effectiveReleaseStatusForForm,
  importLifecyclePresentation,
  sortDraftItemsByLifecycle,
} from "../lib/importReleaseLifecycle";

interface OrderItemDraft {
  publisher: string;
  title: string;
  releaseDate: string;
  releaseStatus: "" | "released" | "not_released_yet" | "unknown";
  orderStatus: "" | "ordered" | "preordered" | "shipped" | "received" | "cancelled";
  issueNumber: string;
  coverName: string;
  printing: string;
  ratio: string;
  variantType: string;
  coverArtist: string;
  writers: string[];
  artists: string[];
  coverArtists: string[];
  quantity: string;
  rawItemPrice: string;
  releaseLifecycleStatus?: AiDraftOrderItem["release_lifecycle_status"];
  lifecycleDisplayLabel?: string;
  lifecycleDisplayDetail?: string;
  lifecycleSortBucket?: number;
  catalogReleaseSourceText?: string;
  catalogMatchPossible?: boolean;
  coverImageUrl?: string;
  coverThumbnailUrl?: string;
  hasCoverImage?: boolean;
}

interface ItemFieldErrors {
  publisher?: string;
  title?: string;
  issueNumber?: string;
  quantity?: string;
  rawItemPrice?: string;
}

interface FormErrors {
  retailer?: string;
  orderDate?: string;
  shippingAmount?: string;
  taxAmount?: string;
  items: Record<number, ItemFieldErrors>;
}

const emptyItem = (): OrderItemDraft => ({
  publisher: "",
  title: "",
  releaseDate: "",
  releaseStatus: "",
  orderStatus: "",
  issueNumber: "",
  coverName: "",
  printing: "",
  ratio: "",
  variantType: "",
  coverArtist: "",
  writers: [],
  artists: [],
  coverArtists: [],
  quantity: "1",
  rawItemPrice: "0.00",
});

function emptyFormErrors(): FormErrors {
  return { items: {} };
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

function formatImportCoverDimensions(width: number | null, height: number | null): string {
  if (width != null && height != null) {
    return `${width} × ${height} px`;
  }
  return "—";
}

function formatImportCoverFileSize(bytes: number | null): string {
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

function formatImportCoverTimestamp(value: string | null): string {
  if (!value) {
    return "Not yet";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function ocrCandidateReviewCardClassImport(status: CoverOcrCandidateReviewStatus): string {
  switch (status) {
    case "approved":
      return "border-emerald-400/35 bg-emerald-500/5";
    case "rejected":
      return "border-rose-400/35 bg-rose-500/5";
    default:
      return "border-white/10 bg-slate-900/80";
  }
}

function barcodeCandidateReviewCardClassImport(
  status: InventoryCoverImage["barcode_candidates"][number]["review_state"],
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

function importOcrReconciliationSeverityClass(
  severity: InventoryCoverImage["ocr_reconciliation_warnings"][number]["severity"],
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

function importOcrReconciliationStatusClass(
  status: InventoryCoverImage["ocr_reconciliation_warnings"][number]["status"],
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

function importCoverProcessingTone(
  status: InventoryCoverImage["processing_status"],
): string {
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

function importCoverMatchingTone(status: InventoryCoverImage["matching_status"]): string {
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

function importCoverOcrHeadlineTone(headline: CoverImageOcrHeadlineStatus): string {
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


function normalizeOptional(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function normalizeReleaseStatus(
  value: OrderItemDraft["releaseStatus"],
): AiDraftOrderItem["release_status"] {
  return value || null;
}

function normalizeOrderStatus(
  value: OrderItemDraft["orderStatus"],
): AiDraftOrderItem["order_status"] {
  return value || null;
}

function mapAiDraftToForm(draft: AiParseOrderResponse) {
  return {
    retailer: draft.retailer ?? "",
    orderDate: draft.order_date ?? "",
    sourceType: draft.source_type,
    shippingAmount: draft.shipping_amount,
    taxAmount: draft.tax_amount,
    items:
      draft.items.length > 0
        ? sortDraftItemsByLifecycle(
            draft.items.map<OrderItemDraft>((item) => ({
              publisher: item.publisher ?? "",
              title: item.title ?? "",
              releaseDate:
                item.parsed_release_date ?? item.release_date ?? item.raw_release_date ?? "",
              releaseStatus: effectiveReleaseStatusForForm(item) || item.release_status || "",
              orderStatus: item.order_status ?? "",
              issueNumber: item.issue_number ?? "",
              coverName: item.cover_name ?? "",
              printing: item.printing ?? "",
              ratio: item.ratio ?? "",
              variantType: item.variant_type ?? "",
              coverArtist: item.cover_artist ?? "",
              writers: item.writers ?? item.canonical_writers ?? [],
              artists: item.artists ?? item.canonical_artists ?? [],
              coverArtists:
                item.cover_artists ??
                item.canonical_cover_artists ??
                (item.cover_artist ? [item.cover_artist] : []),
              quantity: item.quantity === null ? "" : String(item.quantity),
              rawItemPrice: item.raw_item_price ?? "",
              releaseLifecycleStatus: item.release_lifecycle_status ?? undefined,
              lifecycleDisplayLabel: item.lifecycle_display_label ?? undefined,
              lifecycleDisplayDetail: item.lifecycle_display_detail ?? undefined,
              lifecycleSortBucket: item.lifecycle_sort_bucket ?? undefined,
              catalogReleaseSourceText: item.catalog_release_source_text ?? undefined,
              catalogMatchPossible: item.catalog_match_possible ?? undefined,
              coverImageUrl: item.cover_image_url ?? undefined,
              coverThumbnailUrl: item.cover_thumbnail_url ?? undefined,
              hasCoverImage: item.has_cover_image ?? undefined,
            })),
          )
        : [emptyItem()],
  };
}

function displayValue(value: string | null | undefined): string {
  const trimmed = value?.trim();
  return trimmed ? trimmed : "Not provided";
}

function itemLifecycleBadge(item: OrderItemDraft): { label: string; detail: string | null; className: string } | null {
  const presentation = importLifecyclePresentation({
    release_lifecycle_status: item.releaseLifecycleStatus ?? null,
    lifecycle_display_label: item.lifecycleDisplayLabel ?? null,
    lifecycle_display_detail: item.lifecycleDisplayDetail ?? null,
    lifecycle_sort_bucket: item.lifecycleSortBucket ?? null,
    is_preorder: item.releaseLifecycleStatus === "PREORDER",
    is_overdue: item.releaseLifecycleStatus === "OVERDUE",
    is_released_not_received: item.releaseLifecycleStatus === "RELEASED_NOT_RECEIVED",
    release_status: item.releaseStatus || null,
    parsed_release_date: item.releaseDate || null,
    release_date: item.releaseDate || null,
    order_status: item.orderStatus || null,
  });
  if (presentation) {
    return {
      label: presentation.label,
      detail: presentation.detail || null,
      className: presentation.badgeClassName,
    };
  }
  const legacy = itemPreorderLabel(item);
  if (!legacy) {
    return null;
  }
  return {
    label: legacy,
    detail: null,
    className: "border-cyan-400/30 bg-cyan-500/10 text-cyan-100",
  };
}

function itemCardSurfaceClass(item: OrderItemDraft): string {
  const presentation = importLifecyclePresentation({
    release_lifecycle_status: item.releaseLifecycleStatus ?? null,
    lifecycle_display_label: item.lifecycleDisplayLabel ?? null,
    lifecycle_display_detail: item.lifecycleDisplayDetail ?? null,
    lifecycle_sort_bucket: item.lifecycleSortBucket ?? null,
    is_preorder: item.releaseLifecycleStatus === "PREORDER",
    is_overdue: item.releaseLifecycleStatus === "OVERDUE",
    is_released_not_received: item.releaseLifecycleStatus === "RELEASED_NOT_RECEIVED",
    release_status: item.releaseStatus || null,
    parsed_release_date: item.releaseDate || null,
    release_date: item.releaseDate || null,
    order_status: item.orderStatus || null,
  });
  return presentation?.cardClassName ?? "border-white/10 bg-slate-900/70 shadow-black/20";
}

function itemPreorderLabel(item: OrderItemDraft): string | null {
  const trimmedReleaseDate = item.releaseDate.trim();
  const exactDateMatch = /^\d{4}-\d{2}-\d{2}$/.test(trimmedReleaseDate);
  const inferredFutureRelease =
    exactDateMatch && new Date(`${trimmedReleaseDate}T00:00:00`).getTime() > Date.now();
  if (item.orderStatus === "cancelled") {
    return "Cancelled";
  }
  if (item.orderStatus === "received") {
    return "Owned / In Hand";
  }
  if (
    item.releaseStatus === "not_released_yet" ||
    item.orderStatus === "preordered" ||
    inferredFutureRelease
  ) {
    return "Preorder / Not Released Yet";
  }
  if (item.orderStatus === "ordered" || item.orderStatus === "shipped") {
    return "Ordered / Not Received";
  }
  return null;
}

function metadataReviewItemsFromDraft(
  draft: AiParseOrderResponse | null,
): Array<{ index: number; item: AiDraftOrderItem }> {
  if (!draft) {
    return [];
  }

  return draft.items.flatMap((item, index) =>
    item.metadata_review_required ? [{ index, item }] : [],
  );
}

function needsPublisherAliasHelp(item: AiDraftOrderItem): boolean {
  const rawPublisher = item.raw_publisher?.trim();
  if (!rawPublisher) {
    return false;
  }

  return (
    item.metadata_review_notes?.some((note) =>
      note.includes("Review canonical publisher"),
    ) ?? false
  );
}

function needsSeriesAliasHelp(item: AiDraftOrderItem): boolean {
  return Boolean(item.raw_title?.trim());
}

function buildCreatorAliasInputSeeds(draft: AiParseOrderResponse): Record<string, string> {
  const seeds: Record<string, string> = {};
  draft.items.forEach((item, index) => {
    (["writers", "artists", "cover_artists"] as const).forEach((role) => {
      zipCreatorSlots(item, role).forEach(({ slot, raw, canonical }) => {
        if (!raw.trim() && !canonical.trim()) {
          return;
        }
        seeds[creatorAliasRowKey(index, role, slot)] = canonical;
      });
    });
  });
  return seeds;
}

function metadataReviewPassesFilters(
  item: AiDraftOrderItem,
  filters: { releaseOnly: boolean; creatorOnly: boolean },
): boolean {
  if (filters.releaseOnly && !hasMalformedReleaseDateNote(item)) {
    return false;
  }
  if (filters.creatorOnly && !hasCreatorMetadataWarningNotes(item)) {
    return false;
  }
  return true;
}

function buildMissingPublisherErrors(
  draftItems: AiParseOrderResponse["items"],
): Record<number, ItemFieldErrors> {
  return draftItems.reduce<Record<number, ItemFieldErrors>>((errors, item, index) => {
    if (!item.publisher?.trim()) {
      errors[index] = {
        publisher:
          "Publisher could not be inferred from the draft text. Fill it in before confirming.",
      };
    }
    return errors;
  }, {});
}

const PARSE_JOB_POLL_INTERVAL_MS = 1500;

type ParseJobUiStatus = "idle" | "queued" | "started" | "finished" | "failed";
type DraftEditorMode = "ai" | "manual";

function normalizeParseJobStatus(status: ImportParseJobStatus): ParseJobUiStatus {
  if (status === "scheduled" || status === "deferred") {
    return "queued";
  }

  return status;
}

function parseJobStatusLabel(status: ParseJobUiStatus): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "started":
      return "Started / Running";
    case "finished":
      return "Finished";
    case "failed":
      return "Failed";
    default:
      return "Idle";
  }
}

function parseJobStatusTone(status: ParseJobUiStatus): "info" | "success" | "error" {
  if (status === "finished") {
    return "success";
  }

  if (status === "failed") {
    return "error";
  }

  return "info";
}

function parseJobStatusMessage(status: ParseJobUiStatus, error: string | null): string {
  switch (status) {
    case "queued":
      return "Parse job queued. Waiting for the background worker to start parsing.";
    case "started":
      return "Parse job running. No order or inventory will be created until you confirm the draft.";
    case "finished":
      return "Parse job finished. Review the editable draft below before confirming.";
    case "failed":
      return error ?? "Parse job failed. Review the error and try again.";
    default:
      return "";
  }
}

const MANUAL_COVER_ASSIGN_INFO =
  "Manual assignment links the existing image record. It does not duplicate or analyze the image.";
const MANUAL_COVER_ASSIGN_MULTI_COPY =
  "Use this when an import created multiple inventory copies and the cover scan needs to be attached to the correct copy.";

function ImportCoverManualAssignPanel({
  coverImageId,
  disabled,
  onAssigned,
}: {
  coverImageId: number;
  disabled: boolean;
  onAssigned: () => Promise<void>;
}) {
  const [invIdDraft, setInvIdDraft] = useState("");
  const [assignPrimary, setAssignPrimary] = useState(false);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [localOk, setLocalOk] = useState<string | null>(null);

  async function submitAssign(): Promise<void> {
    const parsed = Number(invIdDraft.trim());
    if (!Number.isInteger(parsed) || parsed < 1) {
      setLocalError("Enter a valid inventory copy id.");
      setLocalOk(null);
      return;
    }
    setBusy(true);
    setLocalError(null);
    setLocalOk(null);
    try {
      await apiClient.assignExistingCoverToInventory(parsed, {
        cover_image_id: coverImageId,
        set_primary: assignPrimary,
      });
      setLocalOk(`Cover linked to inventory copy #${parsed}.`);
      await onAssigned();
    } catch (err) {
      setLocalError(err instanceof ApiError ? err.message : "Assignment failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3 space-y-2 border-t border-white/10 pt-3">
      <p className="text-[11px] leading-relaxed text-slate-400">
        Assign this scan to one inventory copy from this confirmed order when multiple copies exist.
      </p>
      <label className="flex flex-col gap-1">
        <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Inventory copy id</span>
        <input
          type="text"
          inputMode="numeric"
          value={invIdDraft}
          disabled={disabled || busy}
          onChange={(event) => setInvIdDraft(event.target.value)}
          className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40"
          placeholder="e.g. 12345"
        />
      </label>
      <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-300">
        <input
          type="checkbox"
          checked={assignPrimary}
          disabled={disabled || busy}
          onChange={(event) => setAssignPrimary(event.target.checked)}
          className="rounded border-white/30 bg-slate-950 accent-cyan-400"
        />
        Set as primary for that copy
      </label>
      <button
        type="button"
        disabled={disabled || busy}
        onClick={() => void submitAssign()}
        className="inline-flex w-full justify-center rounded-xl border border-cyan-400/35 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy ? "Linking…" : "Assign to inventory copy"}
      </button>
      {localError ? <p className="text-[11px] text-rose-300">{localError}</p> : null}
      {localOk ? <p className="text-[11px] text-emerald-200/90">{localOk}</p> : null}
    </div>
  );
}

export function OrderImportPage() {
  const { isOpsAdmin } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [editorMode, setEditorMode] = useState<DraftEditorMode>("ai");
  const [rawText, setRawText] = useState("");
  const [retailer, setRetailer] = useState("");
  const [orderDate, setOrderDate] = useState("");
  const [sourceType, setSourceType] = useState<DraftSourceType>("ai_draft");
  const [shippingAmount, setShippingAmount] = useState("0.00");
  const [taxAmount, setTaxAmount] = useState("0.00");
  const [items, setItems] = useState<OrderItemDraft[]>([emptyItem()]);
  const [expandedItemIndexes, setExpandedItemIndexes] = useState<Record<number, boolean>>({});
  const [formErrors, setFormErrors] = useState<FormErrors>(emptyFormErrors());
  const [error, setError] = useState<string | null>(null);
  const [parseWarnings, setParseWarnings] = useState<string[]>([]);
  const [confidenceScore, setConfidenceScore] = useState<number | null>(null);
  const [draftPayload, setDraftPayload] = useState<AiParseOrderResponse | null>(null);
  const [publisherAliasInputs, setPublisherAliasInputs] = useState<Record<number, string>>({});
  const [seriesAliasInputs, setSeriesAliasInputs] = useState<Record<number, string>>({});
  const [creatorAliasInputs, setCreatorAliasInputs] = useState<Record<string, string>>({});
  const [metadataAliasError, setMetadataAliasError] = useState<string | null>(null);
  const [metadataAliasSuccess, setMetadataAliasSuccess] = useState<string | null>(null);
  const [activeAliasKey, setActiveAliasKey] = useState<string | null>(null);
  const [hasDraft, setHasDraft] = useState(false);
  const [savedImportId, setSavedImportId] = useState<number | null>(null);
  const [importStatus, setImportStatus] = useState<"draft" | "confirmed" | "discarded" | null>(null);
  const [isLoadingImport, setIsLoadingImport] = useState(false);
  const [isEnqueueingParseJob, setIsEnqueueingParseJob] = useState(false);
  const [parseJobId, setParseJobId] = useState<string | null>(null);
  const [parseJobStatus, setParseJobStatus] = useState<ParseJobUiStatus>("idle");
  const [parseJobError, setParseJobError] = useState<string | null>(null);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState<{
    orderId: number;
    importId: number;
    totalCopiesCreated: number;
    allInTotal: string;
    notices: string[];
  } | null>(null);

  const importCoverInputRef = useRef<HTMLInputElement>(null);
  const [importCoverImages, setImportCoverImages] = useState<InventoryCoverImage[]>([]);
  const [importCoverThumbUrls, setImportCoverThumbUrls] = useState<string[]>([]);
  const [importCoverRegionPreviewUrls, setImportCoverRegionPreviewUrls] = useState<Record<string, string>>({});
  const [importCoverUploadBusy, setImportCoverUploadBusy] = useState(false);
  const [importCoverUploadError, setImportCoverUploadError] = useState<string | null>(null);
  const [importCoverActionMessage, setImportCoverActionMessage] = useState<string | null>(null);
  const [importCoverPrimaryBusyId, setImportCoverPrimaryBusyId] = useState<number | null>(null);
  const [importCoverProcessBusyId, setImportCoverProcessBusyId] = useState<number | null>(null);
  const [importCoverEvaluateBusyId, setImportCoverEvaluateBusyId] = useState<number | null>(null);
  const [importCoverOcrBusyId, setImportCoverOcrBusyId] = useState<number | null>(null);
  const [importCoverOcrCandidateReviewBusyId, setImportCoverOcrCandidateReviewBusyId] =
    useState<number | null>(null);
  const [importCoverBarcodeExtractBusyId, setImportCoverBarcodeExtractBusyId] =
    useState<number | null>(null);
  const [importCoverBarcodeReviewBusyId, setImportCoverBarcodeReviewBusyId] =
    useState<number | null>(null);
  const [importCoverOcrReconcileBusyId, setImportCoverOcrReconcileBusyId] =
    useState<number | null>(null);
  const [importCoverOcrWarningBusyId, setImportCoverOcrWarningBusyId] = useState<number | null>(null);
  const [importCoverOcrCandidateNoteDrafts, setImportCoverOcrCandidateNoteDrafts] = useState<
    Record<number, string>
  >({});

  const subtotal = useMemo(
    () =>
      items.reduce((sum, item) => {
        const quantity = Number(item.quantity || 0);
        const rawItemPrice = Number(item.rawItemPrice || 0);
        return sum + quantity * rawItemPrice;
      }, 0),
    [items],
  );
  const estimatedAllInTotal = subtotal + Number(shippingAmount || 0) + Number(taxAmount || 0);
  const isParseJobActive =
    parseJobId !== null && parseJobStatus !== "finished" && parseJobStatus !== "failed";
  const shouldShowDraftEditor = hasDraft || editorMode === "manual";
  const missingPublisherItems = useMemo(
    () =>
      items.flatMap((item, index) =>
        item.publisher.trim()
          ? []
          : [
              {
                index,
                label: item.issueNumber.trim()
                  ? `${item.title.trim() || "Untitled item"} #${item.issueNumber.trim()}`
                  : item.title.trim() || `Item ${index + 1}`,
              },
            ],
      ),
    [items],
  );
  const metadataReviewItems = useMemo(
    () => metadataReviewItemsFromDraft(draftPayload),
    [draftPayload],
  );
  const [releaseDateReviewOnlyFilter, setReleaseDateReviewOnlyFilter] = useState(false);
  const [creatorReviewOnlyFilter, setCreatorReviewOnlyFilter] = useState(false);
  const displayedMetadataReviewItems = useMemo(() => {
    const filters = {
      releaseOnly: releaseDateReviewOnlyFilter,
      creatorOnly: creatorReviewOnlyFilter,
    };

    const needsFiltering =
      filters.releaseOnly || filters.creatorOnly;

    return needsFiltering
      ? metadataReviewItems.filter(({ item }) => metadataReviewPassesFilters(item, filters))
      : metadataReviewItems;
  }, [
    metadataReviewItems,
    releaseDateReviewOnlyFilter,
    creatorReviewOnlyFilter,
  ]);
  function applyImportToForm(savedImport: DraftImport): void {
    const mapped = mapAiDraftToForm(savedImport.parsed_payload_json);
    setEditorMode(mapped.sourceType === "manual_draft" ? "manual" : "ai");
    setRawText(savedImport.raw_text);
    setRetailer(mapped.retailer);
    setOrderDate(mapped.orderDate);
    setSourceType(mapped.sourceType);
    setShippingAmount(mapped.shippingAmount);
    setTaxAmount(mapped.taxAmount);
    setItems(mapped.items);
    setExpandedItemIndexes({});
    setParseWarnings(savedImport.parsed_payload_json.warnings);
    setDraftPayload(savedImport.parsed_payload_json);
    setPublisherAliasInputs(
      Object.fromEntries(
        savedImport.parsed_payload_json.items.map((item, index) => [
          index,
          item.canonical_publisher ?? item.publisher ?? "",
        ]),
      ),
    );
    setSeriesAliasInputs(
      Object.fromEntries(
        savedImport.parsed_payload_json.items.map((item, index) => [
          index,
          item.canonical_title ?? item.title ?? "",
        ]),
      ),
    );
    setCreatorAliasInputs(buildCreatorAliasInputSeeds(savedImport.parsed_payload_json));
    setConfidenceScore(Number(savedImport.confidence_score));
    setHasDraft(true);
    setSavedImportId(savedImport.id);
    setImportStatus(savedImport.status);
    setImportCoverImages(savedImport.cover_images ?? []);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
  }

  async function refreshLoadedImportFromServer(): Promise<void> {
    if (savedImportId == null) {
      return;
    }
    const updated = await apiClient.getImport(savedImportId);
    applyImportToForm(updated);
  }

  useEffect(() => {
    setImportCoverOcrCandidateNoteDrafts((prev) => {
      const next = { ...prev };
      for (const img of importCoverImages) {
        for (const c of img.ocr_candidates) {
          if (next[c.id] === undefined) {
            next[c.id] = c.review_notes ?? "";
          }
        }
      }
      return next;
    });
  }, [importCoverImages]);

  function clearLoadedDraftState(): void {
    setRetailer("");
    setOrderDate("");
    setSourceType(editorMode === "manual" ? "manual_draft" : "ai_draft");
    setShippingAmount("0.00");
    setTaxAmount("0.00");
    setItems([emptyItem()]);
    setExpandedItemIndexes({});
    setFormErrors(emptyFormErrors());
    setParseWarnings([]);
    setDraftPayload(null);
    setPublisherAliasInputs({});
    setSeriesAliasInputs({});
    setCreatorAliasInputs({});
    setMetadataAliasError(null);
    setMetadataAliasSuccess(null);
    setActiveAliasKey(null);
    setConfidenceScore(null);
    setHasDraft(false);
    setSavedImportId(null);
    setReleaseDateReviewOnlyFilter(false);
    setCreatorReviewOnlyFilter(false);
    setImportStatus(null);
    setSuccess(null);
    setImportCoverImages([]);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
    setImportCoverPrimaryBusyId(null);
    setImportCoverProcessBusyId(null);
  }

  function buildParsedPayload(): AiParseOrderResponse {
    return {
      retailer: retailer.trim() || null,
      order_date: orderDate || null,
      source_type: sourceType,
      shipping_amount: shippingAmount || "0.00",
      tax_amount: taxAmount || "0.00",
      items: items.map((item) => ({
        publisher: item.publisher.trim() || null,
        title: item.title.trim() || null,
        release_date: normalizeOptional(item.releaseDate),
        release_status: normalizeReleaseStatus(item.releaseStatus),
        order_status: normalizeOrderStatus(item.orderStatus),
        issue_number: item.issueNumber.trim() || null,
        cover_name: normalizeOptional(item.coverName),
        printing: normalizeOptional(item.printing),
        ratio: normalizeOptional(item.ratio),
        variant_type: normalizeOptional(item.variantType),
        cover_artist: normalizeOptional(item.coverArtist),
        writers: item.writers.length ? item.writers : null,
        artists: item.artists.length ? item.artists : null,
        cover_artists: item.coverArtists.length ? item.coverArtists : null,
        quantity: item.quantity.trim() ? Number(item.quantity) : null,
        raw_item_price: item.rawItemPrice.trim() ? item.rawItemPrice : null,
      })),
      warnings: parseWarnings,
      confidence_score: confidenceScore ?? (sourceType === "manual_draft" ? 1 : 0),
    };
  }

  async function createManualDraft(): Promise<void> {
    setIsSavingDraft(true);
    setError(null);
    setSuccess(null);
    try {
      const created = await apiClient.createManualImport({
        raw_text: rawText.trim() || null,
        ...buildParsedPayload(),
        source_type: "manual_draft",
        confidence_score: confidenceScore ?? 1,
      });
      applyImportToForm(created);
      setSearchParams({ importId: String(created.id) });
    } catch (saveError) {
      if (saveError instanceof ApiError) {
        setError(saveError.message);
      } else {
        setError("Unable to create manual draft.");
      }
    } finally {
      setIsSavingDraft(false);
    }
  }

  function resetForm(): void {
    setRawText("");
    clearLoadedDraftState();
    setError(null);
    setIsEnqueueingParseJob(false);
    setParseJobId(null);
    setParseJobStatus("idle");
    setParseJobError(null);
    setSearchParams({});
  }

  function switchEditorMode(nextMode: DraftEditorMode): void {
    setEditorMode(nextMode);
    setSourceType(nextMode === "manual" ? "manual_draft" : "ai_draft");
    setParseJobId(null);
    setParseJobStatus("idle");
    setParseJobError(null);
    if (!savedImportId) {
      setParseWarnings([]);
      setConfidenceScore(nextMode === "manual" ? 1 : null);
      setError(null);
    }
  }

  function updateItem(index: number, field: keyof OrderItemDraft, value: string): void {
    setItems((current) =>
      current.map((item, itemIndex) =>
        itemIndex === index
          ? {
              ...item,
              [field]: value,
            }
          : item,
      ),
    );
  }

  function clearItemError(index: number, field: keyof ItemFieldErrors): void {
    setFormErrors((current) => ({
      ...current,
      items: {
        ...current.items,
        [index]: {
          ...current.items[index],
          [field]: undefined,
        },
      },
    }));
  }

  function addItem(): void {
    setItems((current) => [...current, emptyItem()]);
    setExpandedItemIndexes({});
  }

  function removeItem(index: number): void {
    setItems((current) => current.filter((_, itemIndex) => itemIndex !== index));
    setExpandedItemIndexes({});
  }

  function toggleItemDetails(index: number): void {
    setExpandedItemIndexes((current) => ({
      ...current,
      [index]: !current[index],
    }));
  }

  function validate(): FormErrors {
    const nextErrors = emptyFormErrors();

    if (!retailer.trim()) {
      nextErrors.retailer = "Retailer is required.";
    }

    if (!orderDate) {
      nextErrors.orderDate = "Order date is required.";
    }

    if (Number(shippingAmount) < 0) {
      nextErrors.shippingAmount = "Shipping amount must be 0 or greater.";
    }

    if (Number(taxAmount) < 0) {
      nextErrors.taxAmount = "Tax amount must be 0 or greater.";
    }

    if (!items.length) {
      nextErrors.items[0] = { title: "At least one order item is required." };
    }

    for (const [index, item] of items.entries()) {
      const itemErrors: ItemFieldErrors = {};
      if (!item.title.trim()) {
        itemErrors.title = "Title is required.";
      }
      if (!item.issueNumber.trim()) {
        itemErrors.issueNumber = "Issue number is required.";
      }
      if (Number(item.quantity) < 1) {
        itemErrors.quantity = "Quantity must be at least 1.";
      }
      if (Number(item.rawItemPrice) < 0) {
        itemErrors.rawItemPrice = "Raw item price must be 0 or greater.";
      }
      if (Object.keys(itemErrors).length) {
        nextErrors.items[index] = itemErrors;
      }
    }

    return nextErrors;
  }

  function hasValidationErrors(nextErrors: FormErrors): boolean {
    return Boolean(
      nextErrors.retailer ||
        nextErrors.orderDate ||
        nextErrors.shippingAmount ||
        nextErrors.taxAmount ||
        Object.values(nextErrors.items).some((itemErrors) =>
          Object.values(itemErrors).some(Boolean),
        ),
    );
  }

  useEffect(() => {
    const importIdParam = searchParams.get("importId");
    if (!importIdParam) {
      return;
    }

    const importId = Number(importIdParam);
    if (!Number.isInteger(importId) || importId < 1) {
      setError("Invalid import draft identifier.");
      return;
    }

    let ignore = false;
    setIsLoadingImport(true);
    setError(null);

    void apiClient
      .getImport(importId)
      .then((savedImport) => {
        if (ignore) {
          return;
        }
        applyImportToForm(savedImport);
      })
      .catch((loadError) => {
        if (ignore) {
          return;
        }
        if (loadError instanceof ApiError) {
          setError(loadError.message);
        } else {
          setError("Unable to load saved import draft.");
        }
      })
      .finally(() => {
        if (!ignore) {
          setIsLoadingImport(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [searchParams]);

  useEffect(() => {
    if (!parseJobId) {
      return;
    }

    let isCancelled = false;
    let timeoutId: number | null = null;

    const pollJobStatus = async () => {
      try {
        const job = await apiClient.getImportParseJobStatus(parseJobId);
        if (isCancelled) {
          return;
        }

        const nextStatus = normalizeParseJobStatus(job.status);
        setParseJobStatus(nextStatus);

        if (nextStatus === "failed") {
          setParseJobError(job.error ?? "Parse job failed. Try again.");
          return;
        }

        if (nextStatus === "finished") {
          if (!job.import_record) {
            setParseJobStatus("failed");
            setParseJobError("Parse job finished but no draft import was returned.");
            return;
          }

          setParseJobError(null);
          applyImportToForm(job.import_record);
          setSearchParams({ importId: String(job.import_record.id) });
          return;
        }

        timeoutId = window.setTimeout(() => {
          void pollJobStatus();
        }, PARSE_JOB_POLL_INTERVAL_MS);
      } catch (pollError) {
        if (isCancelled) {
          return;
        }

        setParseJobStatus("failed");
        if (pollError instanceof ApiError) {
          setParseJobError(pollError.message);
        } else {
          setParseJobError("Unable to refresh parse job status.");
        }
      }
    };

    timeoutId = window.setTimeout(() => {
      void pollJobStatus();
    }, PARSE_JOB_POLL_INTERVAL_MS);

    return () => {
      isCancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [parseJobId, setSearchParams]);

  useEffect(() => {
    if (!importCoverImages.length) {
      setImportCoverThumbUrls([]);
      return undefined;
    }

    let cancelled = false;
    const objectUrls: string[] = [];

    async function loadThumbs(): Promise<void> {
      const next: string[] = [];
      for (const meta of importCoverImages) {
        try {
          const blob = await apiClient.fetchCoverImageBlob(
            meta.thumbnail_fetch_path ?? meta.fetch_path,
          );
          if (cancelled) {
            return;
          }
          const url = URL.createObjectURL(blob);
          objectUrls.push(url);
          next.push(url);
        } catch {
          /* skip thumbnails that failed to decode */
        }
      }
      if (!cancelled) {
        setImportCoverThumbUrls(next);
      }
    }

    void loadThumbs();

    return () => {
      cancelled = true;
      objectUrls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [savedImportId, JSON.stringify(importCoverImages.map((c) => [c.id, c.is_primary]))]);

  useEffect(() => {
    if (!importCoverImages.length) {
      setImportCoverRegionPreviewUrls({});
      return undefined;
    }

    let cancelled = false;
    const objectUrls: string[] = [];

    async function loadRegionPreviews(): Promise<void> {
      const next: Record<string, string> = {};
      for (const meta of importCoverImages) {
        for (const region of meta.ocr_regions ?? []) {
          try {
            const blob = await apiClient.fetchCoverImageBlob(region.fetch_path);
            if (cancelled) {
              return;
            }
            const url = URL.createObjectURL(blob);
            objectUrls.push(url);
            next[`${meta.id}:${region.region_type}`] = url;
          } catch {
            /* skip OCR region previews that failed */
          }
        }
      }
      if (!cancelled) {
        setImportCoverRegionPreviewUrls(next);
      }
    }

    void loadRegionPreviews();
    return () => {
      cancelled = true;
      objectUrls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [
    savedImportId,
    JSON.stringify(
      importCoverImages.map((c) => [c.id, ...(c.ocr_regions ?? []).map((r) => [r.id, r.sha256_hash])]),
    ),
  ]);

  async function handleImportCoverUpload(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const picked = event.target.files?.[0];
    event.target.value = "";
    if (!picked || savedImportId === null) {
      return;
    }

    if (importStatus !== "draft") {
      setImportCoverUploadError("Cover uploads stay open only while this import is a draft.");
      return;
    }

    const matchesName = /\.(jpe?g|png|gif|webp)$/i.test(picked.name);
    const matchesType =
      picked.type.trim() !== "" &&
      /^image\/(jpeg|png|gif|webp)$/i.test(picked.type.trim());
    if (!(matchesName || matchesType)) {
      setImportCoverUploadError("Use JPG, PNG, WebP, or GIF files.");
      return;
    }

    setImportCoverUploadBusy(true);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
    try {
      await apiClient.uploadImportCoverImage(savedImportId, picked);
      const refreshed = await apiClient.getImport(savedImportId);
      applyImportToForm(refreshed);
    } catch (coverError) {
      if (coverError instanceof ApiError) {
        setImportCoverUploadError(coverError.message);
      } else {
        setImportCoverUploadError("Cover upload failed. Try another file.");
      }
    } finally {
      setImportCoverUploadBusy(false);
    }
  }

  async function handleImportCoverPrimary(coverImageId: number): Promise<void> {
    if (savedImportId === null || importStatus !== "draft") {
      return;
    }
    setImportCoverPrimaryBusyId(coverImageId);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
    try {
      await apiClient.setImportCoverPrimary(savedImportId, coverImageId);
      const refreshed = await apiClient.getImport(savedImportId);
      applyImportToForm(refreshed);
    } catch (primaryError) {
      if (primaryError instanceof ApiError) {
        setImportCoverUploadError(primaryError.message);
      } else {
        setImportCoverUploadError("Unable to set primary cover.");
      }
    } finally {
      setImportCoverPrimaryBusyId(null);
    }
  }

  async function handleImportCoverProcess(coverImageId: number): Promise<void> {
    setImportCoverProcessBusyId(coverImageId);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
    try {
      const response = await apiClient.processCoverImage(coverImageId);
      await refreshLoadedImportFromServer();
      setImportCoverActionMessage(
        response.status === "already_queued"
          ? "Cover image processing is already queued."
          : "Cover image metadata reprocessing queued.",
      );
    } catch (processError) {
      if (processError instanceof ApiError) {
        setImportCoverUploadError(processError.message);
      } else {
        setImportCoverUploadError("Unable to queue cover image processing.");
      }
    } finally {
      setImportCoverProcessBusyId(null);
    }
  }

  async function handleImportCoverEvaluate(coverImageId: number): Promise<void> {
    setImportCoverEvaluateBusyId(coverImageId);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
    try {
      await apiClient.evaluateCoverImageMatchingReadiness(coverImageId);
      await refreshLoadedImportFromServer();
      setImportCoverActionMessage("Cover matching readiness evaluated.");
    } catch (evaluateError) {
      if (evaluateError instanceof ApiError) {
        setImportCoverUploadError(evaluateError.message);
      } else {
        setImportCoverUploadError("Unable to evaluate cover readiness.");
      }
    } finally {
      setImportCoverEvaluateBusyId(null);
    }
  }

  async function handleImportCoverOcr(meta: InventoryCoverImage): Promise<void> {
    setImportCoverOcrBusyId(meta.id);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
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
      await refreshLoadedImportFromServer();
      setImportCoverActionMessage(
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
        setImportCoverUploadError(ocrError.message);
      } else {
        setImportCoverUploadError(
          headline === "failed"
            ? "Unable to retry cover OCR."
            : hasPriorResult
              ? "Unable to replay cover OCR."
              : "Unable to queue cover OCR.",
        );
      }
    } finally {
      setImportCoverOcrBusyId(null);
    }
  }

  async function handleImportOcrCandidateApprove(candidateId: number): Promise<void> {
    setImportCoverOcrCandidateReviewBusyId(candidateId);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
    try {
      await apiClient.approveOcrCandidate(candidateId);
      await refreshLoadedImportFromServer();
      setImportCoverActionMessage("OCR candidate approved.");
    } catch (e) {
      if (e instanceof ApiError) {
        setImportCoverUploadError(e.message);
      } else {
        setImportCoverUploadError("Unable to approve OCR candidate.");
      }
    } finally {
      setImportCoverOcrCandidateReviewBusyId(null);
    }
  }

  async function handleImportOcrCandidateReject(candidateId: number): Promise<void> {
    setImportCoverOcrCandidateReviewBusyId(candidateId);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
    try {
      await apiClient.rejectOcrCandidate(candidateId);
      await refreshLoadedImportFromServer();
      setImportCoverActionMessage("OCR candidate rejected.");
    } catch (e) {
      if (e instanceof ApiError) {
        setImportCoverUploadError(e.message);
      } else {
        setImportCoverUploadError("Unable to reject OCR candidate.");
      }
    } finally {
      setImportCoverOcrCandidateReviewBusyId(null);
    }
  }

  async function handleImportOcrCandidateSaveNotes(candidateId: number): Promise<void> {
    setImportCoverOcrCandidateReviewBusyId(candidateId);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
    const raw = importCoverOcrCandidateNoteDrafts[candidateId];
    try {
      await apiClient.patchOcrCandidateReviewNotes(candidateId, { review_notes: raw ?? "" });
      await refreshLoadedImportFromServer();
      setImportCoverActionMessage("Review notes saved.");
    } catch (e) {
      if (e instanceof ApiError) {
        setImportCoverUploadError(e.message);
      } else {
        setImportCoverUploadError("Unable to save review notes.");
      }
    } finally {
      setImportCoverOcrCandidateReviewBusyId(null);
    }
  }

  async function handleImportCoverBarcodeExtract(coverImageId: number): Promise<void> {
    setImportCoverBarcodeExtractBusyId(coverImageId);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
    try {
      const response = await apiClient.extractCoverImageBarcodes(coverImageId);
      await refreshLoadedImportFromServer();
      setImportCoverActionMessage(
        response.candidate_count > 0
          ? `Barcode extraction refreshed (${response.candidate_count} candidates).`
          : "Barcode extraction refreshed with no candidates.",
      );
    } catch (e) {
      if (e instanceof ApiError) {
        setImportCoverUploadError(e.message);
      } else {
        setImportCoverUploadError("Unable to extract barcode candidates.");
      }
    } finally {
      setImportCoverBarcodeExtractBusyId(null);
    }
  }

  async function handleImportBarcodeApprove(barcodeCandidateId: number): Promise<void> {
    setImportCoverBarcodeReviewBusyId(barcodeCandidateId);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
    try {
      await apiClient.approveBarcodeCandidate(barcodeCandidateId);
      await refreshLoadedImportFromServer();
      setImportCoverActionMessage("Barcode candidate approved.");
    } catch (e) {
      if (e instanceof ApiError) {
        setImportCoverUploadError(e.message);
      } else {
        setImportCoverUploadError("Unable to approve barcode candidate.");
      }
    } finally {
      setImportCoverBarcodeReviewBusyId(null);
    }
  }

  async function handleImportBarcodeReject(barcodeCandidateId: number): Promise<void> {
    setImportCoverBarcodeReviewBusyId(barcodeCandidateId);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
    try {
      await apiClient.rejectBarcodeCandidate(barcodeCandidateId);
      await refreshLoadedImportFromServer();
      setImportCoverActionMessage("Barcode candidate rejected.");
    } catch (e) {
      if (e instanceof ApiError) {
        setImportCoverUploadError(e.message);
      } else {
        setImportCoverUploadError("Unable to reject barcode candidate.");
      }
    } finally {
      setImportCoverBarcodeReviewBusyId(null);
    }
  }

  async function handleImportCoverReconcile(coverImageId: number): Promise<void> {
    setImportCoverOcrReconcileBusyId(coverImageId);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
    try {
      const response = await apiClient.reconcileCoverImageOcrMetadata(coverImageId);
      await refreshLoadedImportFromServer();
      setImportCoverActionMessage(
        response.warning_count > 0
          ? `OCR reconciliation refreshed (${response.warning_count} warnings).`
          : "OCR reconciliation refreshed with no warnings.",
      );
    } catch (e) {
      if (e instanceof ApiError) {
        setImportCoverUploadError(e.message);
      } else {
        setImportCoverUploadError("Unable to reconcile OCR metadata.");
      }
    } finally {
      setImportCoverOcrReconcileBusyId(null);
    }
  }

  async function handleImportOcrWarningAcknowledge(warningId: number): Promise<void> {
    setImportCoverOcrWarningBusyId(warningId);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
    try {
      await apiClient.acknowledgeOcrReconciliationWarning(warningId);
      await refreshLoadedImportFromServer();
      setImportCoverActionMessage("OCR reconciliation warning acknowledged.");
    } catch (e) {
      if (e instanceof ApiError) {
        setImportCoverUploadError(e.message);
      } else {
        setImportCoverUploadError("Unable to acknowledge OCR reconciliation warning.");
      }
    } finally {
      setImportCoverOcrWarningBusyId(null);
    }
  }

  async function handleImportOcrWarningDismiss(warningId: number): Promise<void> {
    setImportCoverOcrWarningBusyId(warningId);
    setImportCoverUploadError(null);
    setImportCoverActionMessage(null);
    try {
      await apiClient.dismissOcrReconciliationWarning(warningId);
      await refreshLoadedImportFromServer();
      setImportCoverActionMessage("OCR reconciliation warning dismissed.");
    } catch (e) {
      if (e instanceof ApiError) {
        setImportCoverUploadError(e.message);
      } else {
        setImportCoverUploadError("Unable to dismiss OCR reconciliation warning.");
      }
    } finally {
      setImportCoverOcrWarningBusyId(null);
    }
  }

  async function handleParse(): Promise<void> {
    if (isEnqueueingParseJob || isParseJobActive) {
      return;
    }

    setError(null);
    setParseJobError(null);
    setSuccess(null);
    setFormErrors(emptyFormErrors());

    if (!rawText.trim()) {
      setError("Paste receipt or order text before running the AI parser.");
      return;
    }

    clearLoadedDraftState();
    setSearchParams({});
    setIsEnqueueingParseJob(true);
    setParseJobId(null);
    setParseJobStatus("idle");
    try {
      const job = await apiClient.enqueueImportParseJob({ raw_text: rawText });
      setParseJobId(job.job_id);
      setParseJobStatus(normalizeParseJobStatus(job.status));
    } catch (parseError) {
      if (parseError instanceof ApiError) {
        setError(parseError.message);
      } else {
        setError("Unable to parse order text right now.");
      }
    } finally {
      setIsEnqueueingParseJob(false);
    }
  }

  async function saveDraftChanges(): Promise<void> {
    const validationErrors = validate();
    if (hasValidationErrors(validationErrors)) {
      setFormErrors(validationErrors);
      setError(
        savedImportId
          ? "Fix the draft fields below before saving your changes."
          : "Fix the manual draft fields below before creating the draft.",
      );
      return;
    }

    if (!savedImportId) {
      if (editorMode === "manual") {
        await createManualDraft();
        return;
      }
      setError("Parse and save a draft before updating it.");
      return;
    }

    setIsSavingDraft(true);
    setError(null);
    try {
      const updated = await apiClient.updateImport(savedImportId, {
        raw_text: rawText,
        parsed_payload_json: buildParsedPayload(),
        confidence_score: confidenceScore ?? 0,
      });
      applyImportToForm(updated);
      setFormErrors(emptyFormErrors());
    } catch (saveError) {
      if (saveError instanceof ApiError) {
        setError(saveError.message);
      } else {
        setError("Unable to save draft changes.");
      }
    } finally {
      setIsSavingDraft(false);
    }
  }

  async function clearMetadataReviewForItem(
    itemIndex: number,
    mode: "accept" | "ignore",
  ): Promise<void> {
    setDraftPayload((current) => {
      if (!current) {
        return current;
      }
      const items = current.items.map((draftItem, idx) =>
        idx === itemIndex
          ? {
              ...draftItem,
              metadata_review_required: false,
              metadata_review_notes: mode === "ignore" ? draftItem.metadata_review_notes : [],
            }
          : draftItem,
      );
      return { ...current, items };
    });
    setMetadataAliasSuccess(
      mode === "accept"
        ? "Marked as reviewed. Save draft to persist this change."
        : "Warning ignored for this session. Save draft to persist.",
    );
    setMetadataAliasError(null);
  }

  async function handleCreateMetadataAlias(
    index: number,
    item: AiDraftOrderItem,
    aliasType: "publisher" | "series",
  ): Promise<void> {
    const aliasKey = `${aliasType}-${index}`;
    const aliasValue =
      aliasType === "publisher" ? item.raw_publisher?.trim() : item.raw_title?.trim();
    const canonicalValue =
      aliasType === "publisher"
        ? publisherAliasInputs[index]?.trim()
        : seriesAliasInputs[index]?.trim();

    if (!aliasValue || !canonicalValue) {
      setMetadataAliasError(
        aliasType === "publisher"
          ? "Both the raw publisher and canonical publisher are required."
          : "Both the raw title and canonical series title are required.",
      );
      return;
    }

    setActiveAliasKey(aliasKey);
    setMetadataAliasError(null);
    setMetadataAliasSuccess(null);
    try {
      await apiClient.createMetadataAlias({
        alias_type: aliasType,
        alias_value: aliasValue,
        canonical_value: canonicalValue,
      });
      if (savedImportId) {
        const refreshed = await apiClient.getImport(savedImportId);
        applyImportToForm(refreshed);
      }
      setMetadataAliasSuccess(
        `Saved ${aliasType} alias "${aliasValue}" -> "${canonicalValue}" and refreshed draft metadata.`,
      );
    } catch (aliasError) {
      if (aliasError instanceof ApiError) {
        setMetadataAliasError(aliasError.message);
      } else {
        setMetadataAliasError(
          aliasType === "publisher"
            ? "Unable to save publisher alias."
            : "Unable to save series alias.",
        );
      }
    } finally {
      setActiveAliasKey(null);
    }
  }

  async function handleCreateCreatorAlias(
    aliasRowKey: string,
    aliasValue: string,
    canonicalValue: string,
  ): Promise<void> {
    const trimmedAlias = aliasValue.trim();
    const trimmedCanonical = canonicalValue.trim();

    if (!trimmedAlias || !trimmedCanonical) {
      setMetadataAliasError(
        "Both the raw creator name and canonical creator name are required for a creator alias.",
      );
      return;
    }

    setActiveAliasKey(`creator:${aliasRowKey}`);
    setMetadataAliasError(null);
    setMetadataAliasSuccess(null);
    try {
      await apiClient.createMetadataAlias({
        alias_type: "creator",
        alias_value: trimmedAlias,
        canonical_value: trimmedCanonical,
      });
      if (savedImportId) {
        const refreshed = await apiClient.getImport(savedImportId);
        applyImportToForm(refreshed);
      }
      setMetadataAliasSuccess(
        `Saved creator alias "${trimmedAlias}" → "${trimmedCanonical}" and refreshed draft metadata. Creator aliases affect future normalization only; Comic OS does not perform automatic fuzzy merges.`,
      );
    } catch (aliasError) {
      if (aliasError instanceof ApiError) {
        setMetadataAliasError(aliasError.message);
      } else {
        setMetadataAliasError("Unable to save creator alias.");
      }
    } finally {
      setActiveAliasKey(null);
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    setError(null);
    setFormErrors(emptyFormErrors());

    const validationErrors = validate();
    if (hasValidationErrors(validationErrors)) {
      setFormErrors(validationErrors);
      setError("Fix the draft fields below before confirming the order.");
      return;
    }

    setIsSubmitting(true);
    try {
      if (!savedImportId) {
        throw new ApiError(
          editorMode === "manual"
            ? "Create and save a manual draft before confirming it."
            : "Parse and save a draft before confirming it.",
          400,
        );
      }

      const updated = await apiClient.updateImport(savedImportId, {
        raw_text: rawText,
        parsed_payload_json: buildParsedPayload(),
        confidence_score: confidenceScore ?? 0,
      });
      applyImportToForm(updated);

      const missingPublisherErrors = buildMissingPublisherErrors(updated.parsed_payload_json.items);
      if (Object.keys(missingPublisherErrors).length > 0) {
        setFormErrors({
          ...emptyFormErrors(),
          items: missingPublisherErrors,
        });
        setError(
          "Some items still need publishers before confirming. The server only auto-fills obvious titles.",
        );
        return;
      }

      const response = await apiClient.confirmImport(savedImportId);
      setImportStatus(response.status);
      setSuccess({
        orderId: response.order_id,
        importId: savedImportId,
        totalCopiesCreated: response.total_copies_created,
        allInTotal: response.all_in_total,
        notices: response.notices ?? [],
      });
    } catch (submissionError) {
      if (submissionError instanceof ApiError) {
        setError(submissionError.message);
      } else {
        setError("Unable to create order right now.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  if (success) {
    return (
      <AppShell>
        <div className="mx-auto max-w-4xl">
          <section className="rounded-3xl border border-emerald-400/20 bg-gradient-to-br from-slate-900 via-slate-950 to-emerald-950/40 p-6 shadow-2xl shadow-emerald-950/20">
            <span className="inline-flex rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-emerald-200">
              Draft Confirmed
            </span>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Draft converted into a real order
            </h1>
            <p className="mt-3 text-sm leading-6 text-slate-300 sm:text-base">
              Order #{success.orderId} created {success.totalCopiesCreated} inventory copies with an
              all-in total of {formatCurrency(Number(success.allInTotal))}.
            </p>

            {success.notices.length > 0 ? (
              <div className="mt-6 rounded-2xl border border-cyan-400/25 bg-slate-950/50 p-4 text-sm text-cyan-100/90">
                <p className="font-semibold text-cyan-50">Heads-up</p>
                <ul className="mt-2 list-disc space-y-2 pl-5 text-slate-300">
                  {success.notices.map((note, index) => (
                    <li key={`${index}-${note.slice(0, 48)}`}>{note}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {success.totalCopiesCreated > 1 ||
            success.notices.some((note) =>
              note.toLowerCase().includes("multiple inventory copies"),
            ) ? (
              <div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/50 p-4 text-sm text-slate-300">
                <p className="font-medium text-white">Cover scans on this import</p>
                <p className="mt-2 text-slate-400">{MANUAL_COVER_ASSIGN_INFO}</p>
                <p className="mt-2 text-slate-400">{MANUAL_COVER_ASSIGN_MULTI_COPY}</p>
              </div>
            ) : null}

            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <Link
                to={`/orders/import?importId=${success.importId}`}
                className="rounded-2xl border border-cyan-400/30 bg-cyan-400/10 px-5 py-3 text-center text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/20"
              >
                Open import to attach cover scans
              </Link>
              <Link
                to={`/orders/${success.orderId}`}
                className="rounded-2xl bg-cyan-400 px-5 py-3 text-center text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
              >
                View Order
              </Link>
              <button
                type="button"
                onClick={resetForm}
                className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
              >
                Start Another Draft
              </button>
              <Link
                to="/dashboard"
                className="rounded-2xl border border-white/10 px-5 py-3 text-center text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
              >
                Back to Dashboard
              </Link>
            </div>
          </section>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Import Draft Workspace"
        title="Import Order Draft"
        description="Use AI parsing or build a manual draft directly. In both modes, you review, edit, and confirm before any order or inventory is created."
        actions={
          <Link
            to="/orders/new"
            className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
          >
            Manual Entry
          </Link>
        }
      />

      <div className="mx-auto max-w-7xl">
        {isLoadingImport ? (
          <div className="mt-6">
            <StatusBanner tone="info">Loading saved import draft...</StatusBanner>
          </div>
        ) : null}

        <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
          <div className="mb-5 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => switchEditorMode("ai")}
              className={`rounded-2xl px-4 py-3 text-sm font-semibold transition ${
                editorMode === "ai"
                  ? "bg-cyan-400 text-slate-950"
                  : "border border-white/10 text-slate-100 hover:border-cyan-300/40 hover:bg-white/5"
              }`}
            >
              AI Parse Mode
            </button>
            <button
              type="button"
              onClick={() => switchEditorMode("manual")}
              className={`rounded-2xl px-4 py-3 text-sm font-semibold transition ${
                editorMode === "manual"
                  ? "bg-cyan-400 text-slate-950"
                  : "border border-white/10 text-slate-100 hover:border-cyan-300/40 hover:bg-white/5"
              }`}
            >
              Manual Draft Mode
            </button>
          </div>

          <div className="grid gap-5 lg:grid-cols-[1.4fr_0.6fr]">
            <div>
              <label className="block">
                <span className="text-sm font-medium text-slate-300">
                  {editorMode === "manual" ? "Source notes or pasted text (optional)" : "Raw receipt or order text"}
                </span>
                <textarea
                  rows={12}
                  value={rawText}
                  onChange={(event) => setRawText(event.target.value)}
                  placeholder={
                    editorMode === "manual"
                      ? "Optional notes, invoice snippets, or source text for this manual draft."
                      : "Paste a Whatnot receipt, eBay receipt, retailer invoice, or arbitrary order text here."
                  }
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40"
                />
              </label>
            </div>

            <div className="space-y-4">
              <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4 text-sm text-cyan-100">
                {editorMode === "manual"
                  ? "Manual drafts also stop at the same confirm boundary. Saving a draft never creates inventory directly."
                  : "AI never creates inventory directly. It only prepares a draft order for your review."}
              </div>
              {parseJobId ? (
                <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4 text-sm text-slate-300">
                  <p className="font-medium text-slate-200">Parse job status</p>
                  <p className="mt-1">{parseJobStatusLabel(parseJobStatus)}</p>
                  <p className="mt-2 break-all text-xs text-slate-500">Job ID: {parseJobId}</p>
                </div>
              ) : null}
              {savedImportId ? (
                <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4 text-sm text-slate-300">
                  Saved import #{savedImportId}
                  {importStatus ? ` · ${importStatus}` : ""}
                </div>
              ) : null}
              {confidenceScore !== null ? (
                <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                  <p className="text-sm font-medium text-slate-400">
                    {editorMode === "manual" ? "Draft Confidence" : "Parser Confidence"}
                  </p>
                  <p className="mt-2 text-3xl font-semibold text-white">
                    {Math.round(confidenceScore * 100)}%
                  </p>
                </div>
              ) : null}
              <button
                type="button"
                disabled={
                  editorMode === "ai"
                    ? isEnqueueingParseJob || isParseJobActive
                    : isSavingDraft || isSubmitting || importStatus === "confirmed"
                }
                onClick={() =>
                  editorMode === "ai" ? void handleParse() : void saveDraftChanges()
                }
                className="w-full rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {editorMode === "ai"
                  ? isEnqueueingParseJob
                    ? "Queueing parse job..."
                    : isParseJobActive
                      ? "Parse job running..."
                      : "Parse and Save Draft"
                  : savedImportId
                    ? isSavingDraft
                      ? "Saving draft..."
                      : "Save Draft Changes"
                    : isSavingDraft
                      ? "Creating manual draft..."
                      : "Create Manual Draft"}
              </button>
              <button
                type="button"
                disabled={isEnqueueingParseJob || isSubmitting}
                onClick={resetForm}
                className="w-full rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Clear
              </button>
            </div>
          </div>
        </section>

        {error ? (
          <div className="mt-6">
            <StatusBanner tone="error">{error}</StatusBanner>
          </div>
        ) : null}

        {editorMode === "ai" && parseJobStatus !== "idle" ? (
          <div className="mt-6">
            <StatusBanner tone={parseJobStatusTone(parseJobStatus)}>
              {parseJobStatusMessage(parseJobStatus, parseJobError)}
            </StatusBanner>
          </div>
        ) : null}

        {parseWarnings.length ? (
          <div className="mt-6">
            <StatusBanner tone="info">
              <div className="space-y-2">
                <p className="font-semibold text-cyan-50">
                  {editorMode === "manual" ? "Draft notes" : "Parser warnings"}
                </p>
                <ul className="list-disc space-y-1 pl-5">
                  {parseWarnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            </StatusBanner>
          </div>
        ) : null}

        <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Cover images</p>
              <p className="mt-2 text-sm text-slate-400">
                Optional reference scans for this import only. Saves do not remap covers to catalog
                issues or change confirm semantics.
              </p>
              {!savedImportId ? (
                <p className="mt-2 text-sm text-slate-500">
                  Save a draft first so uploads can attach to that import record.
                </p>
              ) : null}
              {savedImportId && importStatus !== "draft" ? (
                <p className="mt-2 text-sm text-slate-500">
                  This import is {importStatus}. Earlier uploads remain visible below; uploads are
                  paused.
                </p>
              ) : null}
            </div>
            <div className="flex shrink-0 flex-col gap-2 sm:items-end">
              <input
                ref={importCoverInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif,.jpg,.jpeg,.png,.webp,.gif"
                className="hidden"
                onChange={(event) => void handleImportCoverUpload(event)}
              />
              <button
                type="button"
                disabled={
                  !savedImportId || importStatus !== "draft" || importCoverUploadBusy || isSubmitting
                }
                onClick={() => importCoverInputRef.current?.click()}
                className="inline-flex items-center justify-center rounded-full border border-cyan-400/30 bg-cyan-400/10 px-5 py-2 text-sm font-semibold text-cyan-100 transition hover:border-cyan-300/60 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {importCoverUploadBusy ? "Uploading…" : "Upload cover scan"}
              </button>
            </div>
          </div>

          {importCoverUploadError ? (
            <div className="mt-4">
              <StatusBanner tone="error">{importCoverUploadError}</StatusBanner>
            </div>
          ) : null}

          {importCoverActionMessage ? (
            <div className="mt-4">
              <StatusBanner tone="success">{importCoverActionMessage}</StatusBanner>
            </div>
          ) : null}

          {importStatus === "confirmed" &&
          importCoverImages.some((c) => c.draft_import_id != null) ? (
            <div className="mt-4 space-y-2 rounded-2xl border border-amber-400/25 bg-amber-400/5 p-4 text-sm text-amber-100/90">
              <p className="font-medium text-white">Manual cover assignment</p>
              <p className="text-slate-300">{MANUAL_COVER_ASSIGN_INFO}</p>
              <p className="text-slate-300">{MANUAL_COVER_ASSIGN_MULTI_COPY}</p>
            </div>
          ) : null}

          {importCoverImages.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No scans attached to this import yet.</p>
          ) : (
            <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {importCoverImages.map((meta, index) => {
                const thumb = importCoverThumbUrls[index];
                const label = meta.original_filename ?? `Cover ${meta.id}`;
                const busy = importCoverPrimaryBusyId === meta.id;
                const canSetPrimary = savedImportId !== null && importStatus === "draft";
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
                          alt={`Cover thumbnail for ${label}`}
                          className="h-40 w-full object-cover"
                        />
                      </button>
                    ) : (
                      <div className="mb-3 flex h-40 items-center justify-center rounded-xl border border-dashed border-white/15 bg-slate-950/50 text-xs text-slate-500">
                        Loading preview…
                      </div>
                    )}
                    <p className="font-medium text-white">{label}</p>
                    <dl className="mt-3 space-y-1 text-xs text-slate-400">
                      <div className="flex justify-between gap-2">
                        <dt>MIME</dt>
                        <dd className="text-right">{meta.mime_type}</dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt>Dimensions</dt>
                        <dd className="text-right">
                          {formatImportCoverDimensions(meta.image_width, meta.image_height)}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt>Size</dt>
                        <dd className="text-right">
                          {formatImportCoverFileSize(meta.file_size ?? null)}
                        </dd>
                      </div>
                    </dl>
                    <div className="mt-3 space-y-2 text-xs">
                      <div className="flex flex-wrap gap-2">
                        <span
                          className={`inline-flex rounded-full border px-2 py-1 font-semibold uppercase tracking-wide ${importCoverProcessingTone(meta.processing_status)}`}
                        >
                          {meta.processing_status}
                        </span>
                        <span
                          className={`inline-flex rounded-full border px-2 py-1 font-semibold uppercase tracking-wide ${importCoverMatchingTone(meta.matching_status)}`}
                        >
                          matching {meta.matching_status}
                        </span>
                        <span
                          className={`inline-flex rounded-full border px-2 py-1 font-semibold uppercase tracking-wide ${importCoverOcrHeadlineTone(ocrHeadline)}`}
                        >
                          ocr {ocrHeadline}
                        </span>
                      </div>
                      <p className="text-slate-400">
                        Latest OCR processed:{" "}
                        {formatImportCoverTimestamp(meta.latest_ocr_result?.processed_at ?? null)}
                        {meta.latest_ocr_result?.confidence_score != null ? (
                          <span className="text-slate-500">
                            {" "}
                            · confidence {meta.latest_ocr_result.confidence_score}
                          </span>
                        ) : null}
                        {typeof meta.ocr_visibility?.retry_available === "boolean" ? (
                          <span className="text-slate-500">
                            {" "}
                            · retry {meta.ocr_visibility.retry_available ? "available" : "blocked"}
                          </span>
                        ) : null}
                      </p>
                      {ocrRunCount > 0 ? (
                        <p className="text-slate-500">
                          OCR runs recorded: {ocrRunCount}
                          {priorRuns.length > 0
                            ? ` · prior timestamps (newest-first): ${priorRuns
                                .slice(0, 3)
                                .map((ts: string) => formatImportCoverTimestamp(ts))
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
                        Metadata refreshed: {formatImportCoverTimestamp(meta.metadata_refreshed_at)}
                      </p>
                      <p className="text-slate-400">
                        Ready for matching: {formatImportCoverTimestamp(meta.ready_for_matching_at)}
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
                            const previewUrl = importCoverRegionPreviewUrls[`${meta.id}:${region.region_type}`];
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
                    <details className="mt-3 rounded-xl border border-white/10 bg-slate-950/70 p-3">
                      <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                        Barcode Candidates ({meta.barcode_candidates.length})
                      </summary>
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          disabled={importCoverBarcodeExtractBusyId === meta.id}
                          onClick={() => void handleImportCoverBarcodeExtract(meta.id)}
                          className="inline-flex rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-2 py-1 text-[10px] font-semibold text-cyan-100"
                        >
                          {importCoverBarcodeExtractBusyId === meta.id ? "Refreshing…" : "Refresh barcodes"}
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
                            const reviewBusy = importCoverBarcodeReviewBusyId === candidate.id;
                            const sourceLabel =
                              candidate.source_ocr_candidate_id != null
                                ? `OCR candidate #${candidate.source_ocr_candidate_id}`
                                : candidate.source_ocr_result_id != null
                                  ? `OCR result #${candidate.source_ocr_result_id}`
                                  : "derived";
                            return (
                              <div
                                key={candidate.id}
                                className={`rounded-lg border p-3 text-xs ${barcodeCandidateReviewCardClassImport(candidate.review_state)}`}
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
                                    Updated {formatImportCoverTimestamp(candidate.updated_at)}
                                  </span>
                                </div>
                                <p className="mt-2 text-slate-100">Raw value: {candidate.raw_barcode_value}</p>
                                <p className="mt-1 text-slate-300">
                                  Normalized UPC: {candidate.normalized_upc_value}
                                </p>
                                <p className="mt-1 text-slate-500">
                                  Source {sourceLabel}
                                  {candidate.confidence != null ? ` · confidence ${candidate.confidence}` : ""}
                                  {candidate.reviewed_at
                                    ? ` · reviewed ${formatImportCoverTimestamp(candidate.reviewed_at)}`
                                    : ""}
                                </p>
                                <div className="mt-2 flex flex-wrap gap-2">
                                  <button
                                    type="button"
                                    disabled={reviewBusy}
                                    onClick={() => void handleImportBarcodeApprove(candidate.id)}
                                    className="inline-flex rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold text-emerald-100 disabled:opacity-50"
                                  >
                                    Approve
                                  </button>
                                  <button
                                    type="button"
                                    disabled={reviewBusy}
                                    onClick={() => void handleImportBarcodeReject(candidate.id)}
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
                                      const reviewBusy = importCoverOcrCandidateReviewBusyId === candidate.id;
                                      return (
                                        <div
                                          key={candidate.id}
                                          className={`rounded-lg border p-2 text-xs ${ocrCandidateReviewCardClassImport(candidate.review_status)}`}
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
                                                Reviewed {formatImportCoverTimestamp(candidate.reviewed_at)}
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
                                              importCoverOcrCandidateNoteDrafts[candidate.id] ??
                                              candidate.review_notes ??
                                              ""
                                            }
                                            onChange={(event) =>
                                              setImportCoverOcrCandidateNoteDrafts((prev) => ({
                                                ...prev,
                                                [candidate.id]: event.target.value,
                                              }))
                                            }
                                          />
                                          <div className="mt-2 flex flex-wrap gap-2">
                                            <button
                                              type="button"
                                              disabled={reviewBusy}
                                              onClick={() => void handleImportOcrCandidateApprove(candidate.id)}
                                              className="inline-flex rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold text-emerald-100"
                                            >
                                              Approve
                                            </button>
                                            <button
                                              type="button"
                                              disabled={reviewBusy}
                                              onClick={() => void handleImportOcrCandidateReject(candidate.id)}
                                              className="inline-flex rounded-lg border border-rose-400/30 bg-rose-500/10 px-2 py-1 text-[10px] font-semibold text-rose-100"
                                            >
                                              Reject
                                            </button>
                                            <button
                                              type="button"
                                              disabled={reviewBusy}
                                              onClick={() => void handleImportOcrCandidateSaveNotes(candidate.id)}
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
                          disabled={importCoverOcrReconcileBusyId === meta.id}
                          onClick={() => void handleImportCoverReconcile(meta.id)}
                          className="inline-flex rounded-lg border border-amber-400/30 bg-amber-500/10 px-2 py-1 text-[10px] font-semibold text-amber-100"
                        >
                          {importCoverOcrReconcileBusyId === meta.id ? "Refreshing…" : "Refresh warnings"}
                        </button>
                        <span className="text-[11px] text-slate-500">
                          Open{" "}
                          {meta.ocr_reconciliation_warnings.filter((warning) => warning.status === "open").length}
                        </span>
                      </div>
                      {meta.ocr_reconciliation_warnings.length === 0 ? (
                        <p className="mt-3 text-xs text-slate-500">
                          No reconciliation warnings recorded yet. Refresh to compare OCR candidates against the
                          current draft metadata snapshot when available.
                        </p>
                      ) : (
                        <div className="mt-3 space-y-2">
                          {meta.ocr_reconciliation_warnings.map((warning) => {
                            const warningBusy = importCoverOcrWarningBusyId === warning.id;
                            return (
                              <div
                                key={warning.id}
                                className={`rounded-lg border p-3 text-xs ${importOcrReconciliationSeverityClass(warning.severity)}`}
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="rounded-full border border-current/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                                      {warning.severity}
                                    </span>
                                    <span
                                      className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${importOcrReconciliationStatusClass(warning.status)}`}
                                    >
                                      {warning.status}
                                    </span>
                                    <span className="text-[10px] uppercase tracking-[0.14em] text-slate-300">
                                      {warning.warning_type.replace(/_/g, " ")}
                                    </span>
                                  </div>
                                  <span className="text-[10px] text-slate-400">
                                    {warning.resolved_at
                                      ? `Resolved ${formatImportCoverTimestamp(warning.resolved_at)}`
                                      : `Created ${formatImportCoverTimestamp(warning.created_at)}`}
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
                                    onClick={() => void handleImportOcrWarningAcknowledge(warning.id)}
                                    className="inline-flex rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-2 py-1 text-[10px] font-semibold text-cyan-100 disabled:opacity-50"
                                  >
                                    Acknowledge
                                  </button>
                                  <button
                                    type="button"
                                    disabled={warningBusy || warning.status === "dismissed"}
                                    onClick={() => void handleImportOcrWarningDismiss(warning.id)}
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
                      <p className="mt-3 text-xs text-amber-200/90">Primary display image for this draft.</p>
                    ) : canSetPrimary ? (
                      <button
                        type="button"
                        disabled={busy || importCoverUploadBusy || isSubmitting}
                        onClick={() => void handleImportCoverPrimary(meta.id)}
                        className="mt-3 inline-flex rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-white transition hover:border-cyan-300/40 hover:bg-cyan-300/10 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {busy ? "Updating…" : "Set primary"}
                      </button>
                    ) : null}
                    <button
                      type="button"
                      disabled={importCoverProcessBusyId === meta.id}
                      onClick={() => void handleImportCoverProcess(meta.id)}
                      className="mt-3 inline-flex rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-white transition hover:border-cyan-300/40 hover:bg-cyan-300/10 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {importCoverProcessBusyId === meta.id ? "Queueing…" : "Reprocess metadata"}
                    </button>
                    <button
                      type="button"
                      disabled={importCoverEvaluateBusyId === meta.id}
                      onClick={() => void handleImportCoverEvaluate(meta.id)}
                      className="mt-3 inline-flex rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-white transition hover:border-cyan-300/40 hover:bg-cyan-300/10 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {importCoverEvaluateBusyId === meta.id ? "Evaluating…" : "Evaluate readiness"}
                    </button>
                    <button
                      type="button"
                      disabled={importCoverOcrBusyId === meta.id}
                      onClick={() => void handleImportCoverOcr(meta)}
                      className="mt-3 inline-flex rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-white transition hover:border-cyan-300/40 hover:bg-cyan-300/10 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {importCoverOcrBusyId === meta.id
                        ? "Queueing…"
                        : ocrHeadline === "failed"
                          ? "Retry OCR"
                          : meta.latest_ocr_result
                            ? "Replay OCR"
                            : "Run OCR"}
                    </button>
                    {importStatus === "confirmed" && meta.draft_import_id != null ? (
                      <ImportCoverManualAssignPanel
                        coverImageId={meta.id}
                        disabled={isSubmitting || importCoverUploadBusy}
                        onAssigned={refreshLoadedImportFromServer}
                      />
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {shouldShowDraftEditor && missingPublisherItems.length ? (
          <div className="mt-6">
            <StatusBanner tone="info">
              <div className="space-y-2">
                <p className="font-semibold text-cyan-50">Publisher review needed</p>
                <p>
                  Saving the draft will auto-fill only obvious publisher matches server-side. Any
                  item still blank after save needs manual review before confirm.
                </p>
                <ul className="list-disc space-y-1 pl-5">
                  {missingPublisherItems.map((item) => (
                    <li key={`${item.index}-${item.label}`}>
                      Item {item.index + 1}: {item.label}
                    </li>
                  ))}
                </ul>
              </div>
            </StatusBanner>
          </div>
        ) : null}

        {shouldShowDraftEditor && metadataReviewItems.length ? (
          <section className="mt-6 rounded-3xl border border-amber-400/20 bg-amber-400/10 p-5 shadow-xl shadow-black/20">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-white">Needs Metadata Review</h2>
                <p className="mt-2 text-sm text-amber-100/80">
                  Each flagged item starts with a Review Required summary (issue, severity, and recommended
                  action). Open Advanced Details only when you need raw canonical troubleshooting data.
                </p>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:flex-wrap">
                <label className="flex cursor-pointer items-center gap-3 rounded-2xl border border-rose-400/25 bg-slate-950/60 px-4 py-2.5 text-xs font-medium text-rose-100">
                  <input
                    type="checkbox"
                    checked={releaseDateReviewOnlyFilter}
                    onChange={(event) => setReleaseDateReviewOnlyFilter(event.target.checked)}
                    className="h-4 w-4 rounded border-white/20 bg-slate-950 text-rose-400 focus:ring-rose-300/40"
                  />
                  Show release date warnings only
                </label>
                <label className="flex cursor-pointer items-center gap-3 rounded-2xl border border-fuchsia-400/25 bg-slate-950/60 px-4 py-2.5 text-xs font-medium text-fuchsia-50">
                  <input
                    type="checkbox"
                    checked={creatorReviewOnlyFilter}
                    onChange={(event) => setCreatorReviewOnlyFilter(event.target.checked)}
                    className="h-4 w-4 rounded border-white/20 bg-slate-950 text-fuchsia-300 focus:ring-fuchsia-300/40"
                  />
                  Show creator warnings only
                </label>
                <span className="inline-flex whitespace-nowrap rounded-full border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-amber-100">
                  {releaseDateReviewOnlyFilter || creatorReviewOnlyFilter
                    ? `${displayedMetadataReviewItems.length} of ${metadataReviewItems.length} shown`
                    : `${metadataReviewItems.length} flagged`}
                </span>
              </div>
            </div>

            {isOpsAdmin ? (
              <div className="mt-4">
                <StatusBanner tone="info">
                  Creator aliases mapped here steer future deterministic normalization only. Comic OS never
                  auto-merges similar creator strings or rewires existing inventory identities from this
                  panel.
                </StatusBanner>
              </div>
            ) : null}

            {metadataAliasError ? (
              <div className="mt-4">
                <StatusBanner tone="error">{metadataAliasError}</StatusBanner>
              </div>
            ) : null}

            {metadataAliasSuccess ? (
              <div className="mt-4">
                <StatusBanner tone="success">{metadataAliasSuccess}</StatusBanner>
              </div>
            ) : null}

            {(releaseDateReviewOnlyFilter || creatorReviewOnlyFilter) &&
            displayedMetadataReviewItems.length === 0 ? (
              <div className="mt-4">
                <StatusBanner tone="info">
                  No flagged items match the active review filters right now — clear filters to restore
                  the full metadata review list.
                </StatusBanner>
              </div>
            ) : null}

            <div className="mt-4 space-y-6">
              {displayedMetadataReviewItems.map(({ index, item }) => (
                <div key={`metadata-review-${index}`} className="space-y-4">
                  <p className="text-sm font-semibold text-white">
                    Item {index + 1}
                    <span className="ml-2 font-normal text-slate-400">
                      {displayValue(item.title)} #{displayValue(item.issue_number)}
                    </span>
                  </p>
                  <MetadataReviewDraftCard
                    index={index}
                    item={item}
                    actionsDisabled={isSavingDraft || isSubmitting}
                    onLooksGood={() => void clearMetadataReviewForItem(index, "accept")}
                    onIgnoreWarning={() => void clearMetadataReviewForItem(index, "ignore")}
                    onCreateAlias={() => {
                      document
                        .getElementById(`metadata-review-aliases-${index}`)
                        ?.scrollIntoView({ behavior: "smooth", block: "start" });
                    }}
                  />

                  <div id={`metadata-review-aliases-${index}`} className="space-y-4">
                  {isOpsAdmin && needsPublisherAliasHelp(item) ? (
                    <div className="mt-4 rounded-2xl border border-emerald-400/20 bg-emerald-400/10 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-100">
                        Create Publisher Alias
                      </p>
                      <p className="mt-2 text-sm text-emerald-100/80">
                        Save a manual alias for future imports, then refresh this draft with the new
                        canonical publisher.
                      </p>
                      <div className="mt-4 grid gap-3 md:grid-cols-[1fr_1fr_auto]">
                        <input
                          value={item.raw_publisher ?? ""}
                          readOnly
                          className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-slate-300"
                        />
                        <input
                          value={publisherAliasInputs[index] ?? ""}
                          onChange={(event) =>
                            setPublisherAliasInputs((current) => ({
                              ...current,
                              [index]: event.target.value,
                            }))
                          }
                          placeholder="Canonical publisher"
                          className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-emerald-300/40"
                        />
                        <button
                          type="button"
                          disabled={activeAliasKey === `publisher-${index}`}
                          onClick={() => void handleCreateMetadataAlias(index, item, "publisher")}
                          className="rounded-2xl bg-emerald-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {activeAliasKey === `publisher-${index}` ? "Saving..." : "Save Alias"}
                        </button>
                      </div>
                    </div>
                  ) : null}

                  {isOpsAdmin && needsSeriesAliasHelp(item) ? (
                    <div className="mt-4 rounded-2xl border border-violet-400/20 bg-violet-400/10 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-violet-100">
                        Create Series Alias
                      </p>
                      <p className="mt-2 text-sm text-violet-100/80">
                        Save a manual series alias for future imports when this title should collapse
                        into a more canonical series name.
                      </p>
                      <div className="mt-4 grid gap-3 md:grid-cols-[1fr_1fr_auto]">
                        <input
                          value={item.raw_title ?? ""}
                          readOnly
                          className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-slate-300"
                        />
                        <input
                          value={seriesAliasInputs[index] ?? ""}
                          onChange={(event) =>
                            setSeriesAliasInputs((current) => ({
                              ...current,
                              [index]: event.target.value,
                            }))
                          }
                          placeholder="Canonical series title"
                          className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-violet-300/40"
                        />
                        <button
                          type="button"
                          disabled={activeAliasKey === `series-${index}`}
                          onClick={() => void handleCreateMetadataAlias(index, item, "series")}
                          className="rounded-2xl bg-violet-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-violet-200 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {activeAliasKey === `series-${index}` ? "Saving..." : "Save Alias"}
                        </button>
                      </div>
                    </div>
                  ) : null}

                  {isOpsAdmin
                    ? (["writers", "artists", "cover_artists"] as const)
                        .map((role) => {
                          const aliasRows = zipCreatorSlots(item, role).filter((row) => row.raw.trim());
                          return aliasRows.length ? (
                            <div
                              key={`${index}-${role}-aliases`}
                              className="mt-4 rounded-2xl border border-fuchsia-400/20 bg-fuchsia-950/25 p-4"
                            >
                              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-fuchsia-100">
                                Create Creator Alias · {CREATOR_ROLE_LABELS[role]}
                              </p>
                              <p className="mt-2 text-sm text-fuchsia-50/85">
                                Map a raw OCR name to the canonical spelling you want future imports to
                                use. Applies on the next deterministic enrichment pass only.
                              </p>
                              <div className="mt-4 space-y-5">
                                {aliasRows.map((row) => {
                                  const rowKey = creatorAliasRowKey(index, role, row.slot);
                                  const activeKey = activeAliasKey === `creator:${rowKey}`;
                                  return (
                                    <div key={rowKey} className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
                                      <input
                                        value={row.raw}
                                        readOnly
                                        className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-slate-300"
                                      />
                                      <input
                                        value={creatorAliasInputs[rowKey] ?? ""}
                                        onChange={(event) =>
                                          setCreatorAliasInputs((current) => ({
                                            ...current,
                                            [rowKey]: event.target.value,
                                          }))
                                        }
                                        placeholder="Canonical creator name"
                                        className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-fuchsia-300/40"
                                      />
                                      <button
                                        type="button"
                                        disabled={activeKey}
                                        onClick={() =>
                                          void handleCreateCreatorAlias(
                                            rowKey,
                                            row.raw,
                                            creatorAliasInputs[rowKey] ?? row.canonical,
                                          )
                                        }
                                        className="rounded-2xl bg-fuchsia-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-fuchsia-200 disabled:cursor-not-allowed disabled:opacity-60"
                                      >
                                        {activeKey ? "Saving..." : "Save Alias"}
                                      </button>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          ) : null;
                        })
                    : null}

                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {shouldShowDraftEditor ? (
          <form className="mt-6 space-y-6" onSubmit={handleSubmit}>
            <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Retailer</span>
                  <input
                    value={retailer}
                    onChange={(event) => {
                      setRetailer(event.target.value);
                      setFormErrors((current) => ({ ...current, retailer: undefined }));
                    }}
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                    required
                  />
                  {formErrors.retailer ? (
                    <p className="text-sm text-rose-300">{formErrors.retailer}</p>
                  ) : null}
                </label>

                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Order Date</span>
                  <input
                    type="date"
                    value={orderDate}
                    onChange={(event) => {
                      setOrderDate(event.target.value);
                      setFormErrors((current) => ({ ...current, orderDate: undefined }));
                    }}
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                    required
                  />
                  {formErrors.orderDate ? (
                    <p className="text-sm text-rose-300">{formErrors.orderDate}</p>
                  ) : null}
                </label>

                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Source Type</span>
                  <input
                    value={sourceType}
                    readOnly
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  />
                </label>

                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Shipping Amount</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={shippingAmount}
                    onChange={(event) => {
                      setShippingAmount(event.target.value);
                      setFormErrors((current) => ({ ...current, shippingAmount: undefined }));
                    }}
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  />
                  {formErrors.shippingAmount ? (
                    <p className="text-sm text-rose-300">{formErrors.shippingAmount}</p>
                  ) : null}
                </label>

                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-300">Tax Amount</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={taxAmount}
                    onChange={(event) => {
                      setTaxAmount(event.target.value);
                      setFormErrors((current) => ({ ...current, taxAmount: undefined }));
                    }}
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  />
                  {formErrors.taxAmount ? (
                    <p className="text-sm text-rose-300">{formErrors.taxAmount}</p>
                  ) : null}
                </label>
              </div>
            </section>

            <section className="space-y-3">
              {items.map((item, index) => (
                <ImportReviewCard
                  key={`ai-order-item-${index}`}
                  item={item}
                  index={index}
                  isExpanded={Boolean(expandedItemIndexes[index])}
                  canRemove={items.length > 1}
                  isSubmitting={isSubmitting}
                  itemError={formErrors.items[index]}
                  lifecycleBadge={itemLifecycleBadge(item)}
                  cardSurfaceClassName={itemCardSurfaceClass(item)}
                  onToggleDetails={() => toggleItemDetails(index)}
                  onRemove={() => removeItem(index)}
                  onUpdate={(field, value) => updateItem(index, field, value)}
                  clearItemError={(field) => clearItemError(index, field)}
                />
              ))}

              <button
                type="button"
                disabled={isSubmitting}
                onClick={addItem}
                className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
              >
                Add item
              </button>
            </section>

            <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                  <p className="text-sm font-medium text-slate-400">Running Subtotal</p>
                  <p className="mt-3 text-2xl font-semibold text-white">
                    {formatCurrency(subtotal)}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                  <p className="text-sm font-medium text-slate-400">Shipping + Tax</p>
                  <p className="mt-3 text-2xl font-semibold text-white">
                    {formatCurrency(Number(shippingAmount || 0) + Number(taxAmount || 0))}
                  </p>
                </div>
                <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
                  <p className="text-sm font-medium text-cyan-100">Estimated All-In Total</p>
                  <p className="mt-3 text-2xl font-semibold text-white">
                    {formatCurrency(estimatedAllInTotal)}
                  </p>
                </div>
              </div>

                  {isSubmitting ? (
                <div className="mt-4">
                  <StatusBanner tone="info">
                    Confirming saved import and creating the order through the import confirm workflow.
                  </StatusBanner>
                </div>
              ) : null}

              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                <button
                  type="button"
                  disabled={
                    isSavingDraft || isSubmitting || (savedImportId !== null && importStatus !== "draft")
                  }
                  onClick={() => void saveDraftChanges()}
                  className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSavingDraft
                    ? savedImportId
                      ? "Saving draft..."
                      : "Creating manual draft..."
                    : savedImportId
                      ? "Save Draft Changes"
                      : "Create Manual Draft"}
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || importStatus !== "draft"}
                  className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSubmitting ? "Confirming import..." : "Confirm Import and Create Order"}
                </button>
                <button
                  type="button"
                  disabled={!savedImportId || isSavingDraft || isSubmitting || importStatus !== "draft"}
                  onClick={async () => {
                    if (!savedImportId) {
                      return;
                    }
                    setError(null);
                    try {
                      await apiClient.discardImport(savedImportId);
                      resetForm();
                    } catch (discardError) {
                      if (discardError instanceof ApiError) {
                        setError(discardError.message);
                      } else {
                        setError("Unable to discard import draft.");
                      }
                    }
                  }}
                  className="rounded-2xl border border-rose-400/20 bg-rose-400/10 px-5 py-3 text-sm font-semibold text-rose-200 transition hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Discard Draft
                </button>
                <Link
                  to="/dashboard"
                  className="rounded-2xl border border-white/10 px-5 py-3 text-center text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
                >
                  Back to Dashboard
                </Link>
              </div>
            </section>
          </form>
        ) : null}
      </div>
    </AppShell>
  );
}
