import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P78SellQueueItemRead } from "../api/client";
import { SellWorkflowNav } from "../components/sell/p78/SellWorkflowNav";
import { StatusBanner } from "../components/StatusBanner";

function priorityClass(p: string): string {
  if (p === "HIGH") return "border-rose-500/40 bg-rose-950/30";
  if (p === "MEDIUM") return "border-amber-500/40 bg-amber-950/20";
  return "border-slate-600 bg-slate-900/40";
}

export function SellQueuePage(): JSX.Element {
  const [items, setItems] = useState<P78SellQueueItemRead[]>([]);
  const [counts, setCounts] = useState({ high: 0, medium: 0, watch: 0 });
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const body = await apiClient.listSellQueue({ limit: 60, offset: 0 });
      setItems(body.items);
      setCounts({
        high: body.high_priority_count ?? 0,
        medium: body.medium_priority_count ?? 0,
        watch: body.watch_count ?? 0,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load sell queue.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createDraft(copyId: number): Promise<void> {
    setCreating(copyId);
    try {
      await apiClient.createListingDraft({ inventory_copy_id: copyId, status: "DRAFT" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create draft.");
    } finally {
      setCreating(null);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-4xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-amber-300">P78-01</p>
          <h1 className="text-xl font-semibold">Sell queue</h1>
          <SellWorkflowNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-4 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        <p className="text-sm text-slate-400">
          High {counts.high} · Medium {counts.medium} · Watch {counts.watch}
        </p>
        {items.length === 0 ? (
          <p className="text-slate-500">No sell candidates yet.</p>
        ) : (
          <ul className="space-y-3">
            {items.map((row) => (
              <li key={row.inventory_copy_id} className={`rounded-2xl border p-4 ${priorityClass(row.priority)}`}>
                <div className="flex flex-wrap justify-between gap-2">
                  <div>
                    <p className="font-medium text-white">{row.title}</p>
                    <p className="text-xs text-slate-400">
                      {row.priority} · sell {row.suggested_sell_quantity} of {row.owned_copies} (hold {row.target_hold_copies})
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="font-semibold text-emerald-200">${row.fmv.toFixed(0)} FMV</p>
                    <p className="text-slate-500">Liq {row.liquidity_score.toFixed(0)}</p>
                  </div>
                </div>
                {row.signals.length ? (
                  <ul className="mt-2 space-y-1 text-xs text-slate-300">
                    {row.signals.slice(0, 4).map((s) => (
                      <li key={s}>• {s}</li>
                    ))}
                  </ul>
                ) : null}
                <div className="mt-3 flex gap-2">
                  {row.listing_draft_id ? (
                    <span className="text-xs text-slate-400">Draft #{row.listing_draft_id}</span>
                  ) : (
                    <button
                      type="button"
                      disabled={creating === row.inventory_copy_id}
                      className="rounded-lg bg-amber-600/80 px-3 py-1 text-xs font-medium text-white hover:bg-amber-500 disabled:opacity-50"
                      onClick={() => void createDraft(row.inventory_copy_id)}
                    >
                      {creating === row.inventory_copy_id ? "Creating…" : "Create draft"}
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
