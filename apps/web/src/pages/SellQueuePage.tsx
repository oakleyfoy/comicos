import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P78SellQueueItemRead } from "../api/client";
import { PatriotPanel } from "../components/PatriotPageLayout";
import { SellWorkflowPageLayout } from "../components/sell/p78/SellWorkflowPageLayout";

function priorityClass(p: string): string {
  if (p === "HIGH") return "border-red-300 bg-red-50";
  if (p === "MEDIUM") return "border-blue-300 bg-blue-50";
  return "border-blue-200 bg-white";
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
    <SellWorkflowPageLayout title="Sell queue" eyebrow="P78-01 · Sell" error={error} onRetry={() => void load()}>
      <PatriotPanel>
        <p className="text-blue-900">
          High {counts.high} · Medium {counts.medium} · Watch {counts.watch}
        </p>
      </PatriotPanel>
      {items.length === 0 ? (
        <PatriotPanel>
          <p className="text-blue-800/80">No sell candidates yet.</p>
        </PatriotPanel>
      ) : (
        <ul className="space-y-3">
          {items.map((row) => (
            <li key={row.inventory_copy_id} className={`rounded-2xl border p-4 text-blue-950 ${priorityClass(row.priority)}`}>
              <div className="flex flex-wrap justify-between gap-2">
                <div>
                  <p className="font-medium">{row.title}</p>
                  <p className="text-xs text-blue-800/80">
                    {row.priority} · sell {row.suggested_sell_quantity} of {row.owned_copies} (hold {row.target_hold_copies})
                  </p>
                </div>
                <div className="text-right text-sm">
                  <p className="font-semibold text-blue-950">${row.fmv.toFixed(0)} FMV</p>
                  <p className="text-blue-800/70">Liq {row.liquidity_score.toFixed(0)}</p>
                </div>
              </div>
              {row.signals.length ? (
                <ul className="mt-2 space-y-1 text-xs text-blue-900/80">
                  {row.signals.slice(0, 4).map((s) => (
                    <li key={s}>• {s}</li>
                  ))}
                </ul>
              ) : null}
              <div className="mt-3 flex gap-2">
                {row.listing_draft_id ? (
                  <span className="text-xs text-blue-800/70">Draft #{row.listing_draft_id}</span>
                ) : (
                  <button
                    type="button"
                    disabled={creating === row.inventory_copy_id}
                    onClick={() => void createDraft(row.inventory_copy_id)}
                    className="rounded-lg bg-red-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-50"
                  >
                    {creating === row.inventory_copy_id ? "Creating…" : "Create draft"}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </SellWorkflowPageLayout>
  );
}
