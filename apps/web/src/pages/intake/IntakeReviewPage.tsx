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

const COUNT_CARDS: {
  key: keyof IntakeCounts;
  label: string;
  border: string;
  value: string;
}[] = [
  { key: "scanned", label: "Scanned", border: "border-l-slate-500", value: "text-slate-50" },
  { key: "queued", label: "Queued", border: "border-l-violet-400", value: "text-violet-200" },
  { key: "processing", label: "Processing", border: "border-l-amber-400", value: "text-amber-100" },
  { key: "auto_matched", label: "Auto matched", border: "border-l-teal-400", value: "text-teal-100" },
  { key: "ready_for_review", label: "Ready for review", border: "border-l-sky-400", value: "text-sky-100" },
  { key: "needs_review", label: "Needs review", border: "border-l-orange-400", value: "text-orange-100" },
  {
    key: "added_to_inventory",
    label: "Added to inventory",
    border: "border-l-emerald-400",
    value: "text-emerald-100",
  },
  { key: "failed", label: "Failed", border: "border-l-rose-400", value: "text-rose-100" },
];

function intakeBarcode(item: IntakeItem): string {
  const br = item.barcode_read;
  const fromRead =
    br && typeof br.reconstructed_full === "string" && br.reconstructed_full.length >= 12
      ? br.reconstructed_full
      : "";
  return item.normalized_barcode || fromRead || item.raw_barcode || "";
}

function isLocalCatalogBarcodeMatch(item: IntakeItem): boolean {
  return (
    item.status === "auto_matched" &&
    (item.match_source === "catalog_upc" || item.match_source === "learned_barcode") &&
    Boolean(item.selected_catalog_issue_id)
  );
}

function isVerifiedLocalBarcodeMatch(item: IntakeItem): boolean {
  return isLocalCatalogBarcodeMatch(item);
}

function intakeBarcodeGap(item: IntakeItem): Record<string, unknown> | null {
  const gap = item.barcode_read?.barcode_gap;
  return gap && typeof gap === "object" ? (gap as Record<string, unknown>) : null;
}

function intakeHeadline(item: IntakeItem): string {
  const gap = intakeBarcodeGap(item);
  const gapSeries = typeof gap?.gcd_series === "string" ? gap.gcd_series.trim() : "";
  const gapNum = typeof gap?.gcd_issue_number === "string" ? gap.gcd_issue_number.trim() : "";
  const gapAuthoritative =
    gap?.action === "auto_import_available" ||
    (typeof gap?.gcd_match_count === "number" && gap.gcd_match_count === 1);
  const series = gapAuthoritative
    ? gapSeries || item.matched_series?.trim() || ""
    : item.matched_series?.trim() || gapSeries;
  const num = gapAuthoritative
    ? gapNum || item.matched_issue_number?.trim() || ""
    : item.matched_issue_number?.trim() || gapNum;
  if (series) {
    return [series, num ? `#${num.replace(/^#/, "")}` : null].filter(Boolean).join(" ");
  }
  return "Unidentified";
}

function intakeSubtitle(item: IntakeItem): string {
  const parts: string[] = [];
  const gap = intakeBarcodeGap(item);
  const pub =
    item.matched_publisher?.trim() ||
    (typeof gap?.gcd_publisher === "string" ? gap.gcd_publisher.trim() : "");
  if (pub) parts.push(pub);
  if (item.matched_year?.trim()) parts.push(item.matched_year.trim());
  return parts.join(" · ");
}

function intakeInfoMessage(item: IntakeItem): Array<{ tone: "success" | "info" | "warn"; text: string }> {
  const lines: Array<{ tone: "success" | "info" | "warn"; text: string }> = [];
  if (isVerifiedLocalBarcodeMatch(item)) {
    lines.push({ tone: "success", text: "Barcode verified against local catalog." });
    const note = item.reason?.trim();
    if (note && /printed supplement OCR/i.test(note)) {
      lines.push({ tone: "info", text: note });
    }
    if (note && /Cover fingerprint favors another issue/i.test(note)) {
      lines.push({ tone: "info", text: note });
    }
    return lines;
  }
  if (item.status === "auto_matched" && item.match_source === "learned_barcode") {
    lines.push({ tone: "success", text: "Barcode linked to your catalog for future scans." });
  }
  return lines;
}

function intakeUserReason(item: IntakeItem): string | null {
  if (isVerifiedLocalBarcodeMatch(item)) {
    return null;
  }
  const raw = item.reason?.trim();
  if (!raw) return null;
  if (/printed supplement OCR/i.test(raw)) {
    return null;
  }
  if (/Cover fingerprint favors another issue/i.test(raw)) {
    return null;
  }
  if (/Cover fingerprint strongly suggests/i.test(raw) && item.status === "auto_matched") {
    return null;
  }
  if (raw.startsWith("Match failed validation: ")) {
    const detail = raw.slice("Match failed validation: ".length);
    if (/expects dc/i.test(detail) && /unknown/i.test(detail)) {
      return "We read the barcode but couldn’t tie it to a catalog record yet. Use Import & Accept or pick the issue.";
    }
    if (/encodes issue #/i.test(detail)) {
      return "Barcode issue number doesn’t match the catalog hit — pick the correct issue.";
    }
    return detail;
  }
  if (raw.startsWith("No catalog or ComicVine match")) {
    return "No match in catalog yet — import from ComicVine or search manually.";
  }
  if (raw.startsWith("Not in your catalog yet") && raw.includes("GCD match found")) {
    return raw;
  }
  if (raw.startsWith("Not in your catalog yet") && raw.includes("ready to auto-import from GCD")) {
    return raw;
  }
  if (raw.startsWith("Not in your catalog yet")) {
    return raw;
  }
  if (raw.includes("5-digit supplement")) {
    return "Couldn’t read the full barcode — rescan with the supplement visible.";
  }
  if (raw.startsWith("Barcode match needs cover confirmation")) {
    return "Barcode matched but cover didn’t confirm — review or pick the issue.";
  }
  return raw;
}

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
  const label =
    status === "auto_matched" ? "Ready to add" : (STATUS_LABEL[status] ?? status);
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${tone}`}>
      {label}
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
        <h1 className="text-xl font-semibold text-white">Intake Review</h1>
        <p className="mt-1 text-sm text-slate-300">
          Books identify in the background — review and add to inventory while scanning continues.
        </p>
      </header>

      {counts ? (
        <div className="mx-auto mb-5 grid max-w-3xl grid-cols-2 gap-2.5 sm:grid-cols-4" data-testid="intake-counts">
          {COUNT_CARDS.map((card) => (
            <div
              key={card.key}
              className={`rounded-xl border border-slate-800 bg-slate-900/90 px-3 py-3 text-center shadow-sm shadow-black/20 border-l-4 ${card.border}`}
            >
              <div className={`text-2xl font-bold tabular-nums ${card.value}`} data-testid={`count-${card.key}`}>
                {counts[card.key]}
              </div>
              <div className="mt-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                {card.label}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <div className="mx-auto mb-4 flex max-w-3xl items-center justify-between gap-3">
        <span className="text-sm font-medium text-slate-300">{items.length} items</span>
        <button
          type="button"
          onClick={() => void onAddAll()}
          disabled={!counts || counts.auto_matched === 0}
          className="rounded-lg bg-emerald-500 px-3 py-2 text-sm font-semibold text-slate-950 shadow-sm shadow-emerald-950/30 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500 disabled:shadow-none"
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
          const canConfirm = item.selected_catalog_issue_id != null;
          const localMatch = isLocalCatalogBarcodeMatch(item);
          const reviewable =
            item.status === "ready_for_review" ||
            item.status === "needs_review" ||
            item.status === "auto_matched";
          const gap = intakeBarcodeGap(item);
          const gapAutoImport =
            gap?.action === "auto_import_available" || gap?.ready_to_auto_import === true;
          const canImport =
            !canConfirm &&
            reviewable &&
            item.status !== "auto_matched" &&
            (item.matched_series != null || item.normalized_barcode != null || gapAutoImport);
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
                </div>
                <p className="text-base font-semibold text-slate-50">{intakeHeadline(item)}</p>
                {intakeSubtitle(item) ? (
                  <p className="text-sm text-slate-400">{intakeSubtitle(item)}</p>
                ) : null}
                {intakeBarcode(item) ? (
                  <p className="mt-1 font-mono text-xs text-slate-500">{intakeBarcode(item)}</p>
                ) : null}
                {intakeInfoMessage(item).map((info) => (
                  <p
                    key={info.text}
                    className={`mt-2 text-sm ${
                      info.tone === "success"
                        ? "text-sky-200"
                        : info.tone === "info"
                          ? "text-slate-400"
                          : "text-orange-200/90"
                    }`}
                  >
                    {info.text}
                  </p>
                ))}
                {!localMatch &&
                item.barcode_read?.supplement_disagreement &&
                item.barcode_read.decoded_supplement !== item.barcode_read.final_supplement ? (
                  <p className="mt-1 text-xs text-amber-300/90">
                    Barcode and printed supplement disagree — confirm before adding.
                  </p>
                ) : null}
                {gapAutoImport && !canConfirm ? (
                  <p className="mt-2 text-sm text-indigo-200/90">
                    GCD barcode match — use Import &amp; Accept to add to your catalog.
                  </p>
                ) : null}
                {intakeUserReason(item) ? (
                  <p className="mt-2 text-sm text-orange-200/90">{intakeUserReason(item)}</p>
                ) : null}
                {item.error ? <p className="mt-1 text-sm text-rose-300/90">{item.error}</p> : null}

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
                        className={`rounded-lg px-3 py-1.5 text-xs font-semibold disabled:opacity-50 ${
                          localMatch ? "bg-emerald-500 text-slate-950" : "bg-sky-700"
                        }`}
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
          <p className="rounded-xl border border-dashed border-slate-600 bg-slate-900/40 py-10 text-center text-sm text-slate-400">
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
