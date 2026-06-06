import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P78SellBundleRead } from "../api/client";
import { SellWorkflowNav } from "../components/sell/p78/SellWorkflowNav";
import { StatusBanner } from "../components/StatusBanner";

export function BundleOpportunitiesPage(): JSX.Element {
  const [items, setItems] = useState<P78SellBundleRead[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const body = await apiClient.listSellBundles();
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load bundles.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-4xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-amber-300">P78-01</p>
          <h1 className="text-xl font-semibold">Bundle opportunities</h1>
          <SellWorkflowNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-4 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        {items.length === 0 ? (
          <p className="text-slate-500">No bundle opportunities detected.</p>
        ) : (
          <ul className="space-y-3">
            {items.map((b) => (
              <li key={b.bundle_key} className="rounded-2xl border border-violet-500/30 bg-violet-950/20 p-4">
                <p className="font-medium text-white">{b.label}</p>
                <p className="text-xs text-violet-200/80">
                  {b.bundle_type} · {b.item_count} books
                </p>
                <p className="mt-2 text-sm text-slate-300">
                  Bundle FMV ${b.expected_bundle_fmv.toFixed(0)} · list ${b.suggested_list_price.toFixed(0)}
                </p>
                {b.signals.length ? (
                  <ul className="mt-2 space-y-1 text-xs text-slate-400">
                    {b.signals.map((s) => (
                      <li key={s}>• {s}</li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
