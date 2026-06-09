import { useEffect, useMemo, useState, type ChangeEvent, type DragEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ReceivingCompletionSummaryRead,
  type ReceivingSessionDetailRead,
  type ReceivingSessionItemRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

type QueueStatus = "VERIFIED" | "REVIEW" | "UNKNOWN" | "CONFIRMED" | "SKIPPED" | "PENDING";

const QUEUE_ORDER: QueueStatus[] = ["VERIFIED", "REVIEW", "UNKNOWN"];

function createPreviewUrl(file: File): string {
  if (typeof URL !== "undefined" && typeof URL.createObjectURL === "function") {
    return URL.createObjectURL(file);
  }
  return "";
}

function formatConfidence(value?: number | null): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}%`;
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function itemTitle(item: ReceivingSessionItemRead): string {
  const snapshot = item.recognition_snapshot_json ?? {};
  const series = typeof snapshot.series === "string" ? snapshot.series : "Unknown";
  const issue = typeof snapshot.issue_number === "string" && snapshot.issue_number ? `#${snapshot.issue_number}` : "";
  return `${series}${issue ? ` ${issue}` : ""}`.trim();
}

function candidateValue(candidate: Record<string, unknown>, key: string): string | null {
  const value = candidate[key];
  return typeof value === "string" && value.length ? value : null;
}

function statCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-3xl border border-white/10 bg-slate-950/75 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-950/75 p-4">
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function ReceivingStationPage(): JSX.Element {
  const [session, setSession] = useState<ReceivingSessionDetailRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null);
  const [selectedCandidateIndex, setSelectedCandidateIndex] = useState<number>(0);
  const [previewUrls, setPreviewUrls] = useState<Record<number, string>>({});
  const [completionOpen, setCompletionOpen] = useState(false);
  const [completionSummary, setCompletionSummary] = useState<ReceivingCompletionSummaryRead | null>(null);
  const [completionStep, setCompletionStep] = useState<1 | 2 | 3>(1);
  const [purchaseMode, setPurchaseMode] = useState<"existing" | "new">("new");
  const [existingOrderId, setExistingOrderId] = useState("");
  const [purchaseSourceType, setPurchaseSourceType] = useState<
    "FACEBOOK" | "WHATNOT" | "EBAY" | "CONVENTION" | "YARD_SALE" | "COLLECTION_BUY" | "LOCAL_COMIC_SHOP" | "OTHER"
  >("FACEBOOK");
  const [purchaseLabel, setPurchaseLabel] = useState("");
  const [sellerName, setSellerName] = useState("");
  const [purchaseDate, setPurchaseDate] = useState("");
  const [amountPaid, setAmountPaid] = useState("");
  const [shippingAmount, setShippingAmount] = useState("");
  const [taxAmount, setTaxAmount] = useState("");
  const [allocationMethod, setAllocationMethod] = useState<"equal" | "manual" | "key_weighted">("equal");
  const [manualAmounts, setManualAmounts] = useState<Record<number, string>>({});

  const currentItem = useMemo(() => {
    if (!session?.items.length) return null;
    return session.items.find((item) => item.id === selectedItemId) ?? session.items[0] ?? null;
  }, [selectedItemId, session]);

  const verifiedItems = useMemo(() => session?.items.filter((item) => item.status === "VERIFIED") ?? [], [session]);
  const reviewItems = useMemo(() => session?.items.filter((item) => item.status === "REVIEW") ?? [], [session]);
  const unknownItems = useMemo(() => session?.items.filter((item) => item.status === "UNKNOWN") ?? [], [session]);
  const confirmedItems = useMemo(() => session?.items.filter((item) => item.status === "CONFIRMED") ?? [], [session]);
  const skippedItems = useMemo(() => session?.items.filter((item) => item.status === "SKIPPED") ?? [], [session]);

  useEffect(() => {
    void startSession();
    // Intentionally create a fresh intake session when the page opens.
  }, []);

  useEffect(() => {
    if (!currentItem) {
      setSelectedCandidateIndex(0);
      return;
    }
    setSelectedCandidateIndex(currentItem.selected_candidate_index ?? 0);
  }, [currentItem?.id]);

  useEffect(() => {
    if (!session?.items.length) {
      setSelectedItemId(null);
      return;
    }
    setSelectedItemId((current) => {
      if (current && session.items.some((item) => item.id === current)) {
        return current;
      }
      return session.items.find((item) => QUEUE_ORDER.includes(item.status as QueueStatus))?.id ?? session.items[0]?.id ?? null;
    });
  }, [session?.items.length]);

  useEffect(() => {
    if (!completionOpen || !session) return;
    void loadCompletionSummary(session.id);
  }, [completionOpen, session?.id]);

  async function startSession(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const created = await apiClient.createReceivingSession();
      setSession({
        ...created,
        items: [],
      });
      setSelectedItemId(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to start a receiving session.");
    } finally {
      setBusy(false);
    }
  }

  async function uploadImages(files: File[]): Promise<void> {
    if (!files.length) return;
    setBusy(true);
    setError(null);
    try {
      const activeSession = session ?? (await apiClient.createReceivingSession());
      if (!session) {
        setSession({
          ...activeSession,
          items: [],
        });
      }
      const response = await apiClient.uploadReceivingSessionImages(activeSession.id, files);
      const next = response.session;
      const previewMap: Record<number, string> = {};
      const uploadedItems = next.items.slice(-files.length);
      uploadedItems.forEach((item, index) => {
        previewMap[item.id] = createPreviewUrl(files[index]);
      });
      setPreviewUrls((current) => ({ ...current, ...previewMap }));
      setSession(next);
      setSelectedItemId(uploadedItems[0]?.id ?? next.items[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to upload images.");
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm(item: ReceivingSessionItemRead, decision: "confirm" | "wrong_match"): Promise<void> {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const response = await apiClient.confirmReceivingSessionItem(session.id, {
        item_id: item.id,
        decision,
        selected_candidate_index: selectedCandidateIndex,
      });
      setSession(response.session);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to confirm item.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSkip(item: ReceivingSessionItemRead, reason?: string): Promise<void> {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const response = await apiClient.skipReceivingSessionItem(session.id, {
        item_id: item.id,
        reason,
      });
      setSession(response.session);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to skip item.");
    } finally {
      setBusy(false);
    }
  }

  async function loadCompletionSummary(sessionId: number): Promise<void> {
    try {
      const summary = await apiClient.getReceivingSessionSummary(sessionId);
      setCompletionSummary(summary);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load receiving summary.");
    }
  }

  function openCompletionModal(): void {
    setCompletionStep(1);
    setCompletionOpen(true);
  }

  function closeCompletionModal(): void {
    setCompletionOpen(false);
  }

  async function submitCompletion(): Promise<void> {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const confirmed = session.items.filter((item) => item.status === "CONFIRMED");
      const resolvedExistingOrderId = existingOrderId.trim().length ? Number(existingOrderId) : null;
      const manualAllocations =
        allocationMethod === "manual"
          ? confirmed
              .map((item) => ({
                item_id: item.id,
                amount: manualAmounts[item.id] ?? "",
              }))
              .filter((item) => item.amount.trim().length > 0)
          : [];
      await apiClient.assignReceivingPurchase(session.id, {
        mode: purchaseMode,
        existing_order_id: purchaseMode === "existing" ? resolvedExistingOrderId : null,
        source_type: purchaseSourceType,
        purchase_label: purchaseLabel || null,
        seller_name: sellerName || null,
        purchase_date: purchaseDate || null,
        amount_paid: amountPaid || "0",
        shipping_amount: shippingAmount || "0",
        tax_amount: taxAmount || "0",
        allocation_method: allocationMethod,
        manual_allocations,
      });
      await apiClient.completeReceivingSession(session.id);
      const refreshed = await apiClient.getReceivingSession(session.id);
      setSession(refreshed);
      setCompletionSummary(await apiClient.getReceivingSessionSummary(session.id));
      setCompletionOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to complete receiving session.");
    } finally {
      setBusy(false);
    }
  }

  function handleFileInput(event: ChangeEvent<HTMLInputElement>): void {
    const files = event.target.files;
    if (files) {
      void uploadImages(Array.from(files));
    }
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    setDragActive(false);
    if (event.dataTransfer.files.length > 0) {
      void uploadImages(Array.from(event.dataTransfer.files));
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P95-02"
        title="Receiving Station"
        description="Image-only intake workflow powered by recognition results and temporary session queues."
        actions={
          <div className="flex items-center gap-2">
            <Link
              to="/recognition-test"
              className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200"
            >
              Recognition Test
            </Link>
            <button
              type="button"
              onClick={openCompletionModal}
              disabled={!confirmedItems.length}
              className="rounded-2xl border border-emerald-400/30 px-4 py-2 text-sm font-semibold text-emerald-200 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Finish Receiving Session
            </button>
            <button
              type="button"
              onClick={() => void startSession()}
              className="rounded-2xl bg-teal-400 px-4 py-2 text-sm font-semibold text-slate-950"
            >
              New Session
            </button>
          </div>
        }
      />

      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        {statCard({ label: "Images Uploaded", value: String(session?.total_items ?? 0) })}
        {statCard({ label: "Verified Matches", value: String(session?.verified_items ?? 0) })}
        {statCard({ label: "Review Required", value: String(session?.review_items ?? 0) })}
        {statCard({ label: "Unknown", value: String(session?.unknown_items ?? 0) })}
        {statCard({ label: "Confirmed", value: String(session?.confirmed_items ?? 0) })}
        {statCard({ label: "Skipped", value: String(session?.skipped_items ?? 0) })}
      </section>

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-950/75 p-5">
        <div
          onDragEnter={() => setDragActive(true)}
          onDragOver={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          className={`rounded-3xl border border-dashed px-6 py-10 text-center transition ${
            dragActive ? "border-teal-400/60 bg-teal-400/10" : "border-white/15 bg-slate-900/40"
          }`}
        >
          <p className="text-sm font-semibold text-slate-100">Drop comic cover images here</p>
          <p className="mt-1 text-xs text-slate-400">The session will route each image through recognition and queue it immediately.</p>
          <label className="mt-4 inline-flex cursor-pointer rounded-2xl bg-teal-400 px-4 py-2 text-sm font-semibold text-slate-950">
            Add images
            <input type="file" accept="image/*" multiple className="hidden" onChange={handleFileInput} />
          </label>
          {busy ? <p className="mt-3 text-xs text-slate-400">Working…</p> : null}
        </div>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-[0.9fr,0.9fr,1.2fr]">
        <QueueColumn
          title="Verified Queue"
          tone="emerald"
          items={verifiedItems}
          selectedItemId={selectedItemId}
          onSelect={setSelectedItemId}
          previewUrls={previewUrls}
        />
        <QueueColumn
          title="Review Queue"
          tone="amber"
          items={reviewItems}
          selectedItemId={selectedItemId}
          onSelect={setSelectedItemId}
          previewUrls={previewUrls}
        />
        <QueueColumn
          title="Unknown Queue"
          tone="rose"
          items={unknownItems}
          selectedItemId={selectedItemId}
          onSelect={setSelectedItemId}
          previewUrls={previewUrls}
        />
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
        <div className="rounded-3xl border border-white/10 bg-slate-950/75 p-5">
          <h2 className="text-sm font-semibold text-white">Current Item</h2>
          {!currentItem ? (
            <p className="mt-3 text-sm text-slate-500">Upload a few images to start the queue.</p>
          ) : (
            <div className="mt-4 grid gap-4 lg:grid-cols-[0.95fr,1.05fr]">
              <div className="space-y-4">
                <img
                  src={previewUrls[currentItem.id] ?? ""}
                  alt={currentItem.source_filename ?? `Item ${currentItem.sequence_index + 1}`}
                  className="w-full rounded-2xl border border-white/10 object-cover"
                />
                <dl className="grid grid-cols-2 gap-2 text-xs text-slate-300">
                  <Info label="Status" value={currentItem.status} />
                  <Info label="Queue" value={currentItem.recognition_bucket} />
                  <Info label="Confidence" value={formatConfidence(currentItem.recognition_confidence)} />
                  <Info label="Uploaded" value={formatDate(currentItem.uploaded_at)} />
                </dl>
              </div>

              <div className="space-y-4">
                <Panel title="Identified comic">
                  <p className="text-lg font-semibold text-white">{itemTitle(currentItem)}</p>
                  <p className="mt-1 text-sm text-slate-300">
                    {typeof currentItem.recognition_snapshot_json.publisher === "string"
                      ? currentItem.recognition_snapshot_json.publisher
                      : "Unknown publisher"}{" "}
                    ·{" "}
                    {typeof currentItem.recognition_snapshot_json.variant === "string"
                      ? currentItem.recognition_snapshot_json.variant
                      : "No variant"}
                  </p>
                  <p className="mt-2 text-xs text-slate-400">
                    Recognition bucket: <span className="font-semibold text-white">{currentItem.recognition_bucket}</span>
                  </p>
                </Panel>

                <Panel title="Candidate choices">
                  {!currentItem.candidate_snapshot_json.length ? (
                    <p className="text-sm text-slate-500">No alternate candidates were returned.</p>
                  ) : (
                    <div className="space-y-2">
                      <label className="block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Selected candidate
                        <select
                          value={selectedCandidateIndex}
                          onChange={(event) => setSelectedCandidateIndex(Number(event.target.value))}
                          className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-900/70 px-3 py-2 text-sm text-white"
                        >
                          {currentItem.candidate_snapshot_json.map((candidate, index) => (
                            <option key={`${currentItem.id}-${index}`} value={index}>
                              {candidateValue(candidate, "series") ?? "Unknown"} #{candidateValue(candidate, "issue_number") ?? "?"} ·{" "}
                              {Math.round((Number(candidate.confidence) || 0) * 100)}%
                            </option>
                          ))}
                        </select>
                      </label>
                      {currentItem.candidate_snapshot_json.map((candidate, index) => (
                        <div
                          key={`${currentItem.id}-${index}`}
                          className="rounded-2xl border border-white/10 bg-slate-900/60 p-3 text-sm text-slate-200"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <span className="font-semibold text-white">
                              {candidateValue(candidate, "series") ?? "Unknown"} #{candidateValue(candidate, "issue_number") ?? "?"}
                            </span>
                            <span>{Math.round((Number(candidate.confidence) || 0) * 100)}%</span>
                          </div>
                          <p className="mt-1 text-xs text-slate-400">
                            {candidateValue(candidate, "publisher") ?? "Unknown publisher"} ·{" "}
                            {candidateValue(candidate, "variant") ?? "No variant"}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </Panel>

                <Panel title="Actions">
                  <div className="flex flex-wrap gap-2">
                    {currentItem.status === "VERIFIED" ? (
                      <>
                        <button
                          type="button"
                          onClick={() => void handleConfirm(currentItem, "confirm")}
                          className="rounded-2xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950"
                        >
                          Confirm
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleConfirm(currentItem, "wrong_match")}
                          className="rounded-2xl border border-amber-400/40 bg-amber-400/10 px-4 py-2 text-sm font-semibold text-amber-200"
                        >
                          Wrong Match
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleSkip(currentItem, "Skipped from verified queue")}
                          className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200"
                        >
                          Skip
                        </button>
                      </>
                    ) : null}
                    {currentItem.status === "REVIEW" ? (
                      <>
                        <button
                          type="button"
                          onClick={() => void handleConfirm(currentItem, "confirm")}
                          className="rounded-2xl bg-amber-400 px-4 py-2 text-sm font-semibold text-slate-950"
                        >
                          Confirm selected
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleConfirm(currentItem, "wrong_match")}
                          className="rounded-2xl border border-amber-400/40 bg-amber-400/10 px-4 py-2 text-sm font-semibold text-amber-200"
                        >
                          Wrong Match
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleSkip(currentItem, "Skipped from review queue")}
                          className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200"
                        >
                          Skip
                        </button>
                      </>
                    ) : null}
                    {currentItem.status === "UNKNOWN" ? (
                      <>
                        <Link
                          to="/recognition-test"
                          className="rounded-2xl border border-rose-400/40 bg-rose-400/10 px-4 py-2 text-sm font-semibold text-rose-200"
                        >
                          Search Catalog
                        </Link>
                        <button
                          type="button"
                          onClick={() => void handleSkip(currentItem, "Skip unknown item")}
                          className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200"
                        >
                          Skip
                        </button>
                        <button
                          type="button"
                          onClick={() => setError("Investigate later keeps the item in the unknown queue for now.")}
                          className="rounded-2xl bg-rose-400 px-4 py-2 text-sm font-semibold text-slate-950"
                        >
                          Investigate Later
                        </button>
                      </>
                    ) : null}
                    {currentItem.status === "CONFIRMED" || currentItem.status === "SKIPPED" ? (
                      <p className="text-sm text-slate-400">This item is already finalized.</p>
                    ) : null}
                  </div>
                </Panel>
              </div>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <Panel title="Session History">
            <div className="space-y-2">
              {!session?.items.length ? (
                <p className="text-sm text-slate-500">No items in this session yet.</p>
              ) : (
                session.items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setSelectedItemId(item.id)}
                    className={`w-full rounded-2xl border p-3 text-left transition ${
                      selectedItemId === item.id ? "border-teal-400/50 bg-teal-400/10" : "border-white/10 bg-slate-900/50"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-white">
                          {itemTitle(item)}
                        </p>
                        <p className="text-xs text-slate-400">
                          {item.source_filename ?? "upload"} · {item.status}
                        </p>
                      </div>
                      <span className="rounded-full border border-white/10 px-2 py-1 text-[11px] text-slate-300">
                        {item.recognition_bucket}
                      </span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </Panel>

          <Panel title="Finalized Items">
            <QueueSummary label="Confirmed" items={confirmedItems} />
            <QueueSummary label="Skipped" items={skippedItems} />
          </Panel>
        </div>
      </section>

      {completionOpen && session ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/75 p-4">
          <div className="w-full max-w-4xl rounded-3xl border border-white/10 bg-slate-950 p-5 shadow-2xl">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Receiving Summary</p>
                <h2 className="mt-1 text-2xl font-semibold text-white">
                  {completionSummary?.session.confirmed_items ?? session.confirmed_items} confirmed books
                </h2>
              </div>
              <button
                type="button"
                onClick={closeCompletionModal}
                className="rounded-2xl border border-white/10 px-3 py-2 text-sm text-slate-300"
              >
                Close
              </button>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {statCard({ label: "Confirmed Books", value: String(completionSummary?.session.confirmed_items ?? session.confirmed_items) })}
              {statCard({ label: "Review Needed", value: String(completionSummary?.session.review_items ?? session.review_items) })}
              {statCard({ label: "Unknown", value: String(completionSummary?.session.unknown_items ?? session.unknown_items) })}
            </div>

            <div className="mt-5 flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-slate-500">
              <span className={completionStep === 1 ? "text-white" : ""}>1. Purchase</span>
              <span>→</span>
              <span className={completionStep === 2 ? "text-white" : ""}>2. Allocation</span>
              <span>→</span>
              <span className={completionStep === 3 ? "text-white" : ""}>3. Review</span>
            </div>

            {completionStep === 1 ? (
              <section className="mt-4 grid gap-4 md:grid-cols-2">
                <Panel title="Purchase Source">
                  <div className="space-y-3">
                    <label className="block text-sm text-slate-300">
                      <span className="block text-xs uppercase tracking-[0.14em] text-slate-500">Mode</span>
                      <select
                        value={purchaseMode}
                        onChange={(event) => setPurchaseMode(event.target.value as "existing" | "new")}
                        className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-900/70 px-3 py-2 text-white"
                      >
                        <option value="new">Create New Purchase</option>
                        <option value="existing">Assign to Existing Purchase</option>
                      </select>
                    </label>
                    {purchaseMode === "existing" ? (
                      <label className="block text-sm text-slate-300">
                        <span className="block text-xs uppercase tracking-[0.14em] text-slate-500">Existing Order ID</span>
                        <input
                          value={existingOrderId}
                          onChange={(event) => setExistingOrderId(event.target.value)}
                          className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-900/70 px-3 py-2 text-white"
                        />
                      </label>
                    ) : (
                      <div className="grid gap-3 md:grid-cols-2">
                        <label className="block text-sm text-slate-300">
                          <span className="block text-xs uppercase tracking-[0.14em] text-slate-500">Source Type</span>
                          <select
                            value={purchaseSourceType}
                            onChange={(event) =>
                              setPurchaseSourceType(event.target.value as typeof purchaseSourceType)
                            }
                            className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-900/70 px-3 py-2 text-white"
                          >
                            <option value="FACEBOOK">Facebook</option>
                            <option value="WHATNOT">Whatnot</option>
                            <option value="EBAY">eBay</option>
                            <option value="CONVENTION">Convention</option>
                            <option value="YARD_SALE">Yard Sale</option>
                            <option value="COLLECTION_BUY">Collection Purchase</option>
                            <option value="LOCAL_COMIC_SHOP">Local Comic Shop</option>
                            <option value="OTHER">Other</option>
                          </select>
                        </label>
                        <label className="block text-sm text-slate-300">
                          <span className="block text-xs uppercase tracking-[0.14em] text-slate-500">Label</span>
                          <input
                            value={purchaseLabel}
                            onChange={(event) => setPurchaseLabel(event.target.value)}
                            className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-900/70 px-3 py-2 text-white"
                            placeholder="Facebook Lot, Whatnot Order #123"
                          />
                        </label>
                        <label className="block text-sm text-slate-300">
                          <span className="block text-xs uppercase tracking-[0.14em] text-slate-500">Seller</span>
                          <input
                            value={sellerName}
                            onChange={(event) => setSellerName(event.target.value)}
                            className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-900/70 px-3 py-2 text-white"
                          />
                        </label>
                        <label className="block text-sm text-slate-300">
                          <span className="block text-xs uppercase tracking-[0.14em] text-slate-500">Purchase Date</span>
                          <input
                            type="date"
                            value={purchaseDate}
                            onChange={(event) => setPurchaseDate(event.target.value)}
                            className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-900/70 px-3 py-2 text-white"
                          />
                        </label>
                      </div>
                    )}
                  </div>
                </Panel>
                <Panel title="Purchase Totals">
                  <div className="grid gap-3 md:grid-cols-3">
                    <label className="block text-sm text-slate-300">
                      <span className="block text-xs uppercase tracking-[0.14em] text-slate-500">Amount Paid</span>
                      <input
                        value={amountPaid}
                        onChange={(event) => setAmountPaid(event.target.value)}
                        className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-900/70 px-3 py-2 text-white"
                        placeholder="0.00"
                      />
                    </label>
                    <label className="block text-sm text-slate-300">
                      <span className="block text-xs uppercase tracking-[0.14em] text-slate-500">Shipping</span>
                      <input
                        value={shippingAmount}
                        onChange={(event) => setShippingAmount(event.target.value)}
                        className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-900/70 px-3 py-2 text-white"
                        placeholder="0.00"
                      />
                    </label>
                    <label className="block text-sm text-slate-300">
                      <span className="block text-xs uppercase tracking-[0.14em] text-slate-500">Tax</span>
                      <input
                        value={taxAmount}
                        onChange={(event) => setTaxAmount(event.target.value)}
                        className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-900/70 px-3 py-2 text-white"
                        placeholder="0.00"
                      />
                    </label>
                  </div>
                  <div className="mt-4 flex justify-end">
                    <button
                      type="button"
                      onClick={() => setCompletionStep(2)}
                      className="rounded-2xl bg-teal-400 px-4 py-2 text-sm font-semibold text-slate-950"
                    >
                      Next
                    </button>
                  </div>
                </Panel>
              </section>
            ) : null}

            {completionStep === 2 ? (
              <section className="mt-4 space-y-4">
                <Panel title="Cost Allocation">
                  <div className="grid gap-3 md:grid-cols-3">
                    <label className="block text-sm text-slate-300">
                      <span className="block text-xs uppercase tracking-[0.14em] text-slate-500">Method</span>
                      <select
                        value={allocationMethod}
                        onChange={(event) => setAllocationMethod(event.target.value as typeof allocationMethod)}
                        className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-900/70 px-3 py-2 text-white"
                      >
                        <option value="equal">Equal Allocation</option>
                        <option value="manual">Manual Allocation</option>
                        <option value="key_weighted">Key Weighted</option>
                      </select>
                    </label>
                  </div>
                  {allocationMethod === "manual" ? (
                    <div className="mt-4 grid gap-3">
                      {session.items.filter((item) => item.status === "CONFIRMED").map((item) => (
                        <label key={item.id} className="block text-sm text-slate-300">
                          <span className="block text-xs uppercase tracking-[0.14em] text-slate-500">
                            {itemTitle(item)}
                          </span>
                          <input
                            value={manualAmounts[item.id] ?? ""}
                            onChange={(event) =>
                              setManualAmounts((current) => ({ ...current, [item.id]: event.target.value }))
                            }
                            className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-900/70 px-3 py-2 text-white"
                            placeholder="0.00"
                          />
                        </label>
                      ))}
                    </div>
                  ) : null}
                  <div className="mt-4 flex justify-between">
                    <button
                      type="button"
                      onClick={() => setCompletionStep(1)}
                      className="rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-300"
                    >
                      Back
                    </button>
                    <button
                      type="button"
                      onClick={() => setCompletionStep(3)}
                      className="rounded-2xl bg-teal-400 px-4 py-2 text-sm font-semibold text-slate-950"
                    >
                      Review
                    </button>
                  </div>
                </Panel>
              </section>
            ) : null}

            {completionStep === 3 ? (
              <section className="mt-4 grid gap-4 md:grid-cols-2">
                <Panel title="Review">
                  <div className="space-y-2 text-sm text-slate-300">
                    <p>Mode: {purchaseMode === "existing" ? "Existing purchase" : "New purchase"}</p>
                    <p>Source: {purchaseSourceType}</p>
                    <p>Allocation: {allocationMethod}</p>
                    <p>Confirmed books: {session.confirmed_items}</p>
                    <p>Review and unknown items will remain unresolved.</p>
                  </div>
                  <div className="mt-4 flex justify-between">
                    <button
                      type="button"
                      onClick={() => setCompletionStep(2)}
                      className="rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-300"
                    >
                      Back
                    </button>
                    <button
                      type="button"
                      onClick={() => void submitCompletion()}
                      className="rounded-2xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950"
                    >
                      Create Inventory
                    </button>
                  </div>
                </Panel>
                <Panel title="Top Additions">
                  <div className="space-y-2">
                    {(completionSummary?.top_additions.length ? completionSummary.top_additions : confirmedItems.map(itemTitle)).map(
                      (title) => (
                        <div key={title} className="rounded-2xl border border-white/10 bg-slate-900/60 p-3 text-sm text-white">
                          {title}
                        </div>
                      ),
                    )}
                  </div>
                </Panel>
              </section>
            ) : null}
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}

function QueueColumn({
  title,
  tone,
  items,
  selectedItemId,
  onSelect,
  previewUrls,
}: {
  title: string;
  tone: "emerald" | "amber" | "rose";
  items: ReceivingSessionItemRead[];
  selectedItemId: number | null;
  onSelect: (itemId: number) => void;
  previewUrls: Record<number, string>;
}): JSX.Element {
  const toneClass =
    tone === "emerald"
      ? "border-emerald-500/35 bg-emerald-500/10"
      : tone === "amber"
        ? "border-amber-500/35 bg-amber-500/10"
        : "border-rose-500/35 bg-rose-500/10";
  return (
    <section className={`rounded-3xl border ${toneClass} p-4`}>
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <div className="mt-3 space-y-2">
        {!items.length ? (
          <p className="text-sm text-slate-400">No items in this queue.</p>
        ) : (
          items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item.id)}
              className={`w-full rounded-2xl border p-3 text-left transition ${
                selectedItemId === item.id ? "border-teal-400/50 bg-teal-400/10" : "border-white/10 bg-slate-900/50"
              }`}
            >
              <div className="flex gap-3">
                <img
                  src={previewUrls[item.id] ?? ""}
                  alt={item.source_filename ?? `Item ${item.sequence_index + 1}`}
                  className="h-16 w-12 rounded-lg border border-white/10 object-cover"
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-white">{itemTitle(item)}</p>
                  <p className="mt-1 text-xs text-slate-400">
                    {item.source_filename ?? "upload"} · {formatConfidence(item.recognition_confidence)}
                  </p>
                  <p className="mt-1 text-[11px] uppercase tracking-[0.14em] text-slate-500">{item.recognition_bucket}</p>
                </div>
              </div>
            </button>
          ))
        )}
      </div>
    </section>
  );
}

function QueueSummary({ label, items }: { label: string; items: ReceivingSessionItemRead[] }): JSX.Element {
  return (
    <div className="mt-3">
      <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <div className="mt-2 space-y-2">
        {!items.length ? (
          <p className="text-sm text-slate-400">None yet.</p>
        ) : (
          items.map((item) => (
            <div key={item.id} className="rounded-2xl border border-white/10 bg-slate-900/60 p-3 text-sm text-slate-200">
              {itemTitle(item)}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-3">
      <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <p className="mt-1 text-sm text-white">{value}</p>
    </div>
  );
}

