import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type AiParseOrderResponse,
  type DraftImport,
  type DraftSourceType,
  type ImportParseJobStatus,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

interface OrderItemDraft {
  publisher: string;
  title: string;
  issueNumber: string;
  coverName: string;
  printing: string;
  ratio: string;
  variantType: string;
  coverArtist: string;
  quantity: string;
  rawItemPrice: string;
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
  issueNumber: "",
  coverName: "",
  printing: "",
  ratio: "",
  variantType: "",
  coverArtist: "",
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

function normalizeOptional(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
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
        ? draft.items.map<OrderItemDraft>((item) => ({
            publisher: item.publisher ?? "",
            title: item.title ?? "",
            issueNumber: item.issue_number ?? "",
            coverName: item.cover_name ?? "",
            printing: item.printing ?? "",
            ratio: item.ratio ?? "",
            variantType: item.variant_type ?? "",
            coverArtist: item.cover_artist ?? "",
            quantity: item.quantity === null ? "" : String(item.quantity),
            rawItemPrice: item.raw_item_price ?? "",
          }))
        : [emptyItem()],
  };
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

export function OrderImportPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [editorMode, setEditorMode] = useState<DraftEditorMode>("ai");
  const [rawText, setRawText] = useState("");
  const [retailer, setRetailer] = useState("");
  const [orderDate, setOrderDate] = useState("");
  const [sourceType, setSourceType] = useState<DraftSourceType>("ai_draft");
  const [shippingAmount, setShippingAmount] = useState("0.00");
  const [taxAmount, setTaxAmount] = useState("0.00");
  const [items, setItems] = useState<OrderItemDraft[]>([emptyItem()]);
  const [formErrors, setFormErrors] = useState<FormErrors>(emptyFormErrors());
  const [error, setError] = useState<string | null>(null);
  const [parseWarnings, setParseWarnings] = useState<string[]>([]);
  const [confidenceScore, setConfidenceScore] = useState<number | null>(null);
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
    totalCopiesCreated: number;
    allInTotal: string;
  } | null>(null);

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
    setParseWarnings(savedImport.parsed_payload_json.warnings);
    setConfidenceScore(Number(savedImport.confidence_score));
    setHasDraft(true);
    setSavedImportId(savedImport.id);
    setImportStatus(savedImport.status);
  }

  function clearLoadedDraftState(): void {
    setRetailer("");
    setOrderDate("");
    setSourceType(editorMode === "manual" ? "manual_draft" : "ai_draft");
    setShippingAmount("0.00");
    setTaxAmount("0.00");
    setItems([emptyItem()]);
    setFormErrors(emptyFormErrors());
    setParseWarnings([]);
    setConfidenceScore(null);
    setHasDraft(false);
    setSavedImportId(null);
    setImportStatus(null);
    setSuccess(null);
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
        issue_number: item.issueNumber.trim() || null,
        cover_name: normalizeOptional(item.coverName),
        printing: normalizeOptional(item.printing),
        ratio: normalizeOptional(item.ratio),
        variant_type: normalizeOptional(item.variantType),
        cover_artist: normalizeOptional(item.coverArtist),
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
  }

  function removeItem(index: number): void {
    setItems((current) => current.filter((_, itemIndex) => itemIndex !== index));
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
        totalCopiesCreated: response.total_copies_created,
        allInTotal: response.all_in_total,
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

            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
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

            <section className="space-y-4">
              {items.map((item, index) => (
                <article
                  key={`ai-order-item-${index}`}
                  className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20"
                >
                  <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-sm uppercase tracking-[0.18em] text-slate-500">
                        Draft Item {index + 1}
                      </p>
                      <p className="mt-1 text-sm text-slate-400">
                        Review every field before confirming the draft.
                      </p>
                    </div>

                    {items.length > 1 ? (
                      <button
                        type="button"
                        disabled={isSubmitting}
                        onClick={() => removeItem(index)}
                        className="rounded-2xl border border-rose-400/20 bg-rose-400/10 px-4 py-2 text-sm font-semibold text-rose-200 transition hover:bg-rose-400/15"
                      >
                        Remove item
                      </button>
                    ) : null}
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <label className="space-y-2">
                      <span className="text-sm font-medium text-slate-300">Publisher</span>
                      <input
                        value={item.publisher}
                        onChange={(event) => {
                          updateItem(index, "publisher", event.target.value);
                          clearItemError(index, "publisher");
                        }}
                        className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      />
                      {formErrors.items[index]?.publisher ? (
                        <p className="text-sm text-rose-300">
                          {formErrors.items[index]?.publisher}
                        </p>
                      ) : !item.publisher.trim() ? (
                        <p className="text-sm text-slate-400">
                          Leave this blank only if unclear. Save the draft to let the server infer
                          obvious publishers safely.
                        </p>
                      ) : null}
                    </label>

                    <label className="space-y-2">
                      <span className="text-sm font-medium text-slate-300">Title</span>
                      <input
                        value={item.title}
                        onChange={(event) => {
                          updateItem(index, "title", event.target.value);
                          clearItemError(index, "title");
                        }}
                        className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      />
                      {formErrors.items[index]?.title ? (
                        <p className="text-sm text-rose-300">{formErrors.items[index]?.title}</p>
                      ) : null}
                    </label>

                    <label className="space-y-2">
                      <span className="text-sm font-medium text-slate-300">Issue Number</span>
                      <input
                        value={item.issueNumber}
                        onChange={(event) => {
                          updateItem(index, "issueNumber", event.target.value);
                          clearItemError(index, "issueNumber");
                        }}
                        className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      />
                      {formErrors.items[index]?.issueNumber ? (
                        <p className="text-sm text-rose-300">
                          {formErrors.items[index]?.issueNumber}
                        </p>
                      ) : null}
                    </label>

                    <label className="space-y-2">
                      <span className="text-sm font-medium text-slate-300">Cover Name</span>
                      <input
                        value={item.coverName}
                        onChange={(event) => updateItem(index, "coverName", event.target.value)}
                        className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      />
                    </label>

                    <label className="space-y-2">
                      <span className="text-sm font-medium text-slate-300">Printing</span>
                      <input
                        value={item.printing}
                        onChange={(event) => updateItem(index, "printing", event.target.value)}
                        className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      />
                    </label>

                    <label className="space-y-2">
                      <span className="text-sm font-medium text-slate-300">Ratio</span>
                      <input
                        value={item.ratio}
                        onChange={(event) => updateItem(index, "ratio", event.target.value)}
                        className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      />
                    </label>

                    <label className="space-y-2">
                      <span className="text-sm font-medium text-slate-300">Variant Type</span>
                      <input
                        value={item.variantType}
                        onChange={(event) => updateItem(index, "variantType", event.target.value)}
                        className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      />
                    </label>

                    <label className="space-y-2">
                      <span className="text-sm font-medium text-slate-300">Cover Artist</span>
                      <input
                        value={item.coverArtist}
                        onChange={(event) => updateItem(index, "coverArtist", event.target.value)}
                        className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      />
                    </label>

                    <label className="space-y-2">
                      <span className="text-sm font-medium text-slate-300">Quantity</span>
                      <input
                        type="number"
                        min="1"
                        step="1"
                        value={item.quantity}
                        onChange={(event) => {
                          updateItem(index, "quantity", event.target.value);
                          clearItemError(index, "quantity");
                        }}
                        className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      />
                      {formErrors.items[index]?.quantity ? (
                        <p className="text-sm text-rose-300">{formErrors.items[index]?.quantity}</p>
                      ) : null}
                    </label>

                    <label className="space-y-2">
                      <span className="text-sm font-medium text-slate-300">Raw Item Price</span>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={item.rawItemPrice}
                        onChange={(event) => {
                          updateItem(index, "rawItemPrice", event.target.value);
                          clearItemError(index, "rawItemPrice");
                        }}
                        className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      />
                      {formErrors.items[index]?.rawItemPrice ? (
                        <p className="text-sm text-rose-300">
                          {formErrors.items[index]?.rawItemPrice}
                        </p>
                      ) : null}
                    </label>
                  </div>
                </article>
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
