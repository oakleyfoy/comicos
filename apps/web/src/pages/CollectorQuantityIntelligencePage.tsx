import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P77PersonalizedQuantityRead } from "../api/client";
import { CollectorProfileNav } from "../components/collector/p77/CollectorProfileNav";
import { StatusBanner } from "../components/StatusBanner";

export function CollectorQuantityIntelligencePage(): JSX.Element {
  const [items, setItems] = useState<P77PersonalizedQuantityRead[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const body = await apiClient.listPersonalizedQuantities({ limit: 50, offset: 0 });
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load quantities.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-3xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-sky-300">P77-02</p>
          <h1 className="text-xl font-semibold">Quantity intelligence</h1>
          <CollectorProfileNav />
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-4 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        {items.length === 0 ? (
          <p className="text-slate-400">No quantity recommendations yet.</p>
        ) : (
          <ul className="space-y-3">
            {items.map((row, idx) => (
              <li
                key={`${row.release_id ?? "x"}-${row.title}-${idx}`}
                className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <p className="font-medium text-white">{row.title}</p>
                    <p className="text-sm text-slate-400">
                      {[row.series_name, row.publisher].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-emerald-200">{row.personalized_quantity}</p>
                    <p className="text-xs text-slate-500">was {row.global_quantity}</p>
                  </div>
                </div>
                {row.reasons.length ? (
                  <ul className="mt-2 space-y-1 text-sm text-slate-300">
                    {row.reasons.map((r) => (
                      <li key={r}>• {r}</li>
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
