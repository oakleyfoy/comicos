import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import {
  acceptIntakeItem,
  addAllHighConfidence,
  addIntakeItemToInventory,
  chooseIntakeItemIssue,
  getIntakeReview,
  importAndAcceptIntakeItem,
  intakeImageUrl,
  rejectIntakeItem,
  requeueIntakeItem,
  searchCatalogIssues,
  type IntakeCatalogSearchResult,
  type IntakeCounts,
  type IntakeItem,
  type IntakeReview,
} from "../../api/intake";

const COUNT_CARDS: { key: keyof IntakeCounts; label: string; tone: string }[] = [
  { key: "scanned", label: "Scanned", tone: "text-slate-100" },
  { key: "queued", label: "Queued", tone: "text-slate-300" },
  { key: "processing", label: "Processing", tone: "text-amber-300" },
  { key: "auto_matched", label: "Auto matched", tone: "text-emerald-400" },
  { key: "ready_for_review", label: "Ready for review", tone: "text-sky-400" },
  { key: "needs_review", label: "Needs review", tone: "text-orange-400" },
  { key: "added_to_inventory", label: "Added to inventory", tone: "text-emerald-300" },
  { key: "failed", label: "Failed", tone: "text-rose-400" },
];

const STATUS_LABEL: Record<string, string> = {
  queued: "Queued",
  processing: "Processing",
  auto_matched: "Auto matched",
  ready_for_review: "Ready for review",
  needs_review: "Needs review",
  added_to_inventory: "Added to inventory",
  rejected: "Rejected",
  failed: "Failed",
};

function StatusBadge({ status }: { status: string }): JSX.Element {
  const tone =
    status === "auto_matched" || status === "added_to_inventory"
      ? "bg-emerald-600/25 text-emerald-200"
      : status === "ready_for_review"
        ? "bg-sky-600/25 text-sky-200"
        : status === "needs_review"
          ? "bg-orange-600/25 text-orange-200"
          : status === "failed" || status === "rejected"
            ? "bg-rose-600/25 text-rose-200"
            : "bg-slate-700/50 text-slate-300";
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${tone}`}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

export function IntakeReviewPage(): JSX.Element {
  const { token = "" } = useParams();
  const [review, setReview] = useState<IntakeReview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [pickerItem, setPickerItem] = useState<IntakeItem | null>(null);
  const [pickerQuery, setPickerQuery] = useState("");
  const [pickerResults, setPickerResults] = useState<IntakeCatalogSearchResult[]>([]);
  const [pickerBusy, setPickerBusy] = useState(false);
  const pollRef = useRef<number | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const data = await getIntakeReview(token);
      setReview(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load review");
    }
  }, [token]);

  useEffect(() => {
    void load();
    pollRef.current = window.setInterval(() => void load(), 2000);
    return () => {
      if (pollRef.current != null) window.clearInterval(pollRef.current);
    };
  }, [load]);

  const applyItem = (updated: IntakeItem) => {
    setReview((prev) =>
      prev ? { ...prev, items: prev.items.map((it) => (it.id === updated.id ? updated : it)) } : prev,
    );
  };

  const runAction = async (id: number, fn: () => Promise<IntakeItem>) => {
    setBusyId(id);
    setError(null);
    try {
      applyItem(await fn());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusyId(null);
      void load();
    }
  };

  const onAddAll = async () => {
    setError(null);
    try {
      await addAllHighConfidence(token);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Add all failed");
    }
  };

  const openPicker = (item: IntakeItem) => {
    setPickerItem(item);
    setPickerQuery(item.matched_series ?? "");
    setPickerResults([]);
  };

  const runPickerSearch = async () => {
    if (!pickerQuery.trim()) return;
    setPickerBusy(true);
    setError(null);
    try {
      const data = await searchCatalogIssues(
        pickerQuery,
        pickerItem?.matched_issue_number ?? undefined,
      );
      setPickerResults(data.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setPickerBusy(false);
    }
  };

  const choosePickerResult = async (catalogIssueId: number) => {
    if (!pickerItem) return;
    const itemId = pickerItem.id;
    setPickerBusy(true);
    setError(null);
    try {
      applyItem(await chooseIntakeItemIssue(itemId, catalogIssueId));
      setPickerItem(null);
      setPickerResults([]);
      void load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not choose issue");
    } finally {
      setPickerBusy(false);
    }
  };

  const counts = review?.counts;
  const items = review?.items ?? [];

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100">
      <header className="mx-auto mb-5 max-w-3xl">
        <h1 className="text-xl font-semibold">Intake Review</h1>
        <p className="text-xs text-slate-400">
          Books identify in the background — review and add to inventory while scanning continues.
        </p>
      </header>

      {counts ? (
        <div className="mx-auto mb-5 grid max-w-3xl grid-cols-2 gap-2 sm:grid-cols-4" data-testid="intake-counts">
          {COUNT_CARDS.map((card) => (
            <div key={card.key} className="rounded-xl bg-slate-900 px-3 py-3 text-center">
              <div className={`text-2xl font-bold ${card.tone}`} data-testid={`count-${card.key}`}>
                {counts[card.key]}
              </div>
              <div className="text-[11px] uppercase tracking-wide text-slate-500">{card.label}</div>
            </div>
          ))}
        </div>
      ) : null}

      <div className="mx-auto mb-4 flex max-w-3xl items-center justify-between">
        <span className="text-sm text-slate-400">{items.length} items</span>
        <button
          type="button"
          onClick={() => void onAddAll()}
          disabled={!counts || counts.auto_matched === 0}
          className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold hover:bg-emerald-500 disabled:opacity-40"
        >
          Add all high-confidence ({counts?.auto_matched ?? 0})
        </button>
      </div>

      {error ? (
        <p className="mx-auto mb-3 max-w-3xl rounded-lg bg-rose-600/20 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      ) : null}

      <div className="mx-auto max-w-3xl space-y-3">
        {items.map((item) => {
          const busy = busyId === item.id;
          const title = [item.matched_series, item.matched_issue_number ? `#${item.matched_issue_number}` : null]
            .filter(Boolean)
            .join(" ");
          const canConfirm = item.selected_catalog_issue_id != null;
          const reviewable =
            item.status === "ready_for_review" ||
            item.status === "needs_review" ||
            item.status === "auto_matched";
          const canImport =
            !canConfirm &&
            reviewable &&
            (item.matched_series != null || item.normalized_barcode != null);
          return (
            <article key={item.id} className="flex gap-3 rounded-xl border border-slate-800 bg-slate-900/60 p-3">
              <img
                src={intakeImageUrl(item)}
                alt="scan"
                className="h-24 w-20 shrink-0 rounded-lg object-cover"
                loading="lazy"
              />
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex items-center gap-2">
                  <StatusBadge status={item.status} />
                  {item.match_source ? (
                    <span className="text-[11px] text-slate-500">{item.match_source}</span>
                  ) : null}
                  {item.confidence > 0 ? (
                    <span className="text-[11px] text-slate-500">
                      {Math.round(item.confidence * 100)}%
                    </span>
                  ) : null}
                </div>
                <p className="truncate text-sm font-medium text-slate-100">
                  {title || item.matched_publisher || "Unidentified"}
                </p>
                <div className="mt-1 space-y-0.5 text-xs text-slate-500">
                  <p>Raw scan: {item.raw_barcode || "—"}</p>
                  <p>Normalized: {item.normalized_barcode || "—"}</p>
                  {item.base_upc ? <p>Base UPC: {item.base_upc}</p> : null}
                  {item.extension ? <p>Supplement: {item.extension}</p> : null}
                  {item.possible_corrected_barcode ? (
                    <p className="text-amber-300/90">
                      Possible correction: {item.possible_corrected_barcode}
                    </p>
                  ) : null}
                  {item.barcode_read ? (
                    <>
                      <p>Reconstructed: {String(item.barcode_read.reconstructed_full ?? "—")}</p>
                      <p>Decoded supplement (bars): {String(item.barcode_read.decoded_supplement ?? "—")}</p>
                      <p>OCR supplement (left text): {String(item.barcode_read.ocr_supplement ?? item.barcode_read.left_supplement_ocr ?? "—")}</p>
                      {item.barcode_read.corrected_supplement ? (
                        <p>Corrected supplement: {String(item.barcode_read.corrected_supplement)}</p>
                      ) : null}
                      {item.barcode_read.region_ocr_debug &&
                      typeof item.barcode_read.region_ocr_debug === "object" &&
                      (
                        (item.barcode_read.region_ocr_debug as Record<string, unknown>)
                          .left_supplement as Record<string, unknown> | undefined
                      )?.supplement_consensus ? (
                        <p className="text-slate-400">
                          Multi-frame OCR consensus:{" "}
                          {String(
                            (
                              (
                                (item.barcode_read.region_ocr_debug as Record<string, unknown>)
                                  .left_supplement as Record<string, unknown>
                              ).supplement_consensus as Record<string, unknown>
                            ).digits || "—",
                          )}
                        </p>
                      ) : null}
                      <p>
                        Final supplement: {String(item.barcode_read.final_supplement || "—")}
                        {item.barcode_read.catalog_confirmed ? " (catalog ✓)" : ""}
                        {item.barcode_read.fingerprint_confirmed ? " (fingerprint ✓)" : ""}
                      </p>
                      <p>
                        Detection method: {String(item.barcode_read.detection_method ?? "percentage")}
                        {item.barcode_read.detection_method === "percentage" &&
                        item.barcode_read.fallback_reason ? (
                          <>
                            <br />
                            Fallback reason: {String(item.barcode_read.fallback_reason)}
                          </>
                        ) : null}
                        {item.barcode_read.geometry_rejection_reason ? (
                          <>
                            <br />
                            Geometry rejection: {String(item.barcode_read.geometry_rejection_reason)}
                          </>
                        ) : null}
                        {item.barcode_read.opencv_available === false ? (
                          <>
                            <br />
                            OpenCV: unavailable
                          </>
                        ) : null}
                      </p>
                      <p>
                        Confidence: main {Math.round(Number(item.barcode_read.confidence_main ?? 0) * 100)}%,
                        supplement {Math.round(Number(item.barcode_read.confidence_left ?? 0) * 100)}%
                      </p>
                      {Array.isArray(item.barcode_read.supplement_candidates) &&
                      item.barcode_read.supplement_candidates.length > 0 ? (
                        <p className="text-slate-400">
                          OCR candidates:{" "}
                          {(item.barcode_read.supplement_candidates as Array<Record<string, unknown>>)
                            .slice(0, 3)
                            .map(
                              (c) =>
                                `${String(c.digits)}×${String(c.repeat_count ?? 0)}${
                                  c.catalog_exists ? "(cat)" : ""
                                }`,
                            )
                            .join(", ")}
                        </p>
                      ) : null}
                      {Array.isArray(item.barcode_read.ocr_attempts) &&
                      item.barcode_read.ocr_attempts.length > 0 ? (
                        <details className="text-slate-500">
                          <summary className="cursor-pointer">
                            Raw OCR attempts ({(item.barcode_read.ocr_attempts as unknown[]).length})
                          </summary>
                          <ul className="mt-1 space-y-0.5">
                            {(item.barcode_read.ocr_attempts as Array<Record<string, unknown>>)
                              .filter((a) => String(a.digits ?? "").length > 0)
                              .slice(0, 12)
                              .map((a, idx) => (
                                <li key={idx}>
                                  {String(a.variant)}: {String(a.digits) || "∅"} (
                                  {Math.round(Number(a.confidence ?? 0) * 100)}%)
                                </li>
                              ))}
                          </ul>
                        </details>
                      ) : null}
                      {item.barcode_read.supplement_disagreement ? (
                        <p className="text-amber-300/90">
                          Supplement mismatch: bar decode vs left OCR — confirm final supplement.
                        </p>
                      ) : null}
                      {item.barcode_read.inferred_supplement ? (
                        <p className="text-amber-300/90">Supplement inferred/corrected (not raw OCR).</p>
                      ) : null}
                      {item.barcode_read.correction_reason ? (
                        <p className="text-amber-300/90">{String(item.barcode_read.correction_reason)}</p>
                      ) : null}
                      {item.barcode_read.review_reason &&
                      item.barcode_read.review_reason !== item.barcode_read.correction_reason ? (
                        <p className="text-amber-300/90">{String(item.barcode_read.review_reason)}</p>
                      ) : null}
                      {item.barcode_read.region_ocr_debug &&
                      typeof item.barcode_read.region_ocr_debug === "object" &&
                      (item.barcode_read.region_ocr_debug as Record<string, unknown>).geometry_viz ? (
                        <p className="text-slate-400">
                          Geometry OCR viz:{" "}
                          {String(
                            (
                              (item.barcode_read.region_ocr_debug as Record<string, unknown>)
                                .geometry_viz as Record<string, unknown>
                            ).intended_vs_detected_note ?? "",
                          )}
                          {(item.barcode_read.region_debug_path as string | undefined)
                            ? ` See ${String(item.barcode_read.region_debug_path)}/overlay_labeled.jpg`
                            : ""}
                        </p>
                      ) : null}
                    </>
                  ) : null}
                </div>
                {item.candidates.length > 0 ? (
                  <ul className="mt-2 space-y-1 text-xs text-slate-400">
                    {item.candidates.slice(0, 5).map((c) => (
                      <li key={c.id}>
                        Candidate: {c.series ?? "Unknown"} #{c.issue_number ?? "?"} ({c.source},{" "}
                        {Math.round(c.score * 100)}%)
                      </li>
                    ))}
                  </ul>
                ) : null}
                {item.reason ? <p className="mt-1 text-xs text-orange-300/80">{item.reason}</p> : null}
                {item.error ? <p className="mt-1 text-xs text-rose-300/80">{item.error}</p> : null}

                {item.status !== "added_to_inventory" && item.status !== "rejected" ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {item.status === "ready_for_review" && canConfirm ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void runAction(item.id, () => acceptIntakeItem(item.id))}
                        className="rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
                      >
                        Accept match
                      </button>
                    ) : null}
                    {canImport ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void runAction(item.id, () => importAndAcceptIntakeItem(item.id))}
                        className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
                      >
                        Import &amp; Accept
                      </button>
                    ) : null}
                    {reviewable ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => openPicker(item)}
                        className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs font-medium disabled:opacity-50"
                      >
                        Choose different issue
                      </button>
                    ) : null}
                    {canConfirm ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void runAction(item.id, () => addIntakeItemToInventory(item.id))}
                        className="rounded-lg bg-sky-700 px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
                      >
                        Add to inventory
                      </button>
                    ) : null}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void runAction(item.id, () => requeueIntakeItem(item.id))}
                      className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs font-medium disabled:opacity-50"
                    >
                      Rescan
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void runAction(item.id, () => rejectIntakeItem(item.id))}
                      className="rounded-lg border border-rose-600/60 px-3 py-1.5 text-xs font-medium text-rose-200 disabled:opacity-50"
                    >
                      Reject
                    </button>
                  </div>
                ) : null}
              </div>
            </article>
          );
        })}
        {items.length === 0 ? (
          <p className="rounded-xl border border-dashed border-slate-700 py-10 text-center text-sm text-slate-500">
            No scans yet. Start scanning on your phone — items appear here as they process.
          </p>
        ) : null}
      </div>

      {pickerItem ? (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 p-4">
          <div className="mt-10 w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-base font-semibold">Choose different issue</h2>
              <button
                type="button"
                onClick={() => setPickerItem(null)}
                className="rounded-lg border border-slate-600 px-2 py-1 text-xs"
              >
                Close
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void runPickerSearch();
              }}
              className="mb-3 flex gap-2"
            >
              <input
                value={pickerQuery}
                onChange={(e) => setPickerQuery(e.target.value)}
                placeholder="Search series, e.g. Superman"
                className="flex-1 rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm"
                aria-label="Catalog search"
              />
              <button
                type="submit"
                disabled={pickerBusy}
                className="rounded-lg bg-sky-700 px-3 py-2 text-sm font-semibold disabled:opacity-50"
              >
                Search
              </button>
            </form>
            <div className="max-h-80 space-y-2 overflow-y-auto">
              {pickerResults.map((res) => (
                <button
                  key={res.catalog_issue_id}
                  type="button"
                  disabled={pickerBusy}
                  onClick={() => void choosePickerResult(res.catalog_issue_id)}
                  className="flex w-full items-center gap-3 rounded-lg border border-slate-700 bg-slate-800/50 p-2 text-left hover:border-sky-500 disabled:opacity-50"
                >
                  {res.cover_url ? (
                    <img src={res.cover_url} alt="" className="h-14 w-10 rounded object-cover" loading="lazy" />
                  ) : (
                    <div className="h-14 w-10 rounded bg-slate-700" />
                  )}
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      {[res.series, res.issue_number ? `#${res.issue_number}` : null].filter(Boolean).join(" ") ||
                        "Untitled"}
                    </p>
                    <p className="truncate text-xs text-slate-500">{res.publisher || ""}</p>
                  </div>
                </button>
              ))}
              {pickerResults.length === 0 ? (
                <p className="py-6 text-center text-sm text-slate-500">
                  {pickerBusy ? "Searching…" : "Search the catalog to pick the correct issue."}
                </p>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
