import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import {
  acceptIntakeItem,
  addAllHighConfidence,
  addIntakeItemToInventory,
  getIntakeReview,
  intakeImageUrl,
  rejectIntakeItem,
  requeueIntakeItem,
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
                <p className="truncate text-xs text-slate-500">
                  {item.normalized_barcode || item.raw_barcode || "No barcode read"}
                </p>
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
    </div>
  );
}
