import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P77BudgetStatusRead } from "../api/client";
import { CollectorProfileNav } from "../components/collector/p77/CollectorProfileNav";
import { StatusBanner } from "../components/StatusBanner";

function stateTone(state: string): string {
  if (state === "GREEN") return "text-emerald-300 border-emerald-500/40";
  if (state === "YELLOW") return "text-amber-300 border-amber-500/40";
  return "text-rose-300 border-rose-500/40";
}

export function CollectorBudgetDashboardPage(): JSX.Element {
  const [status, setStatus] = useState<P77BudgetStatusRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setStatus(await apiClient.getCollectorBudgetStatus());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load budget status.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!status) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : <p className="text-slate-400">Loading…</p>}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-2xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-sky-300">P77-02</p>
          <h1 className="text-xl font-semibold">Budget dashboard</h1>
          <CollectorProfileNav />
        </div>
      </header>
      <main className="mx-auto max-w-2xl space-y-4 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        <section className={`rounded-2xl border p-4 ${stateTone(status.budget_state)}`}>
          <p className="text-[10px] uppercase tracking-wider opacity-80">Budget state</p>
          <p className="mt-1 text-3xl font-bold">{status.budget_state}</p>
          <p className="mt-2 text-sm">{status.utilization_percent.toFixed(0)}% of monthly budget used</p>
        </section>
        <section className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-3">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Monthly budget</p>
            <p className="text-lg font-semibold">${status.monthly_budget.toFixed(2)}</p>
          </div>
          <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-3">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Spent</p>
            <p className="text-lg font-semibold">${status.monthly_spend.toFixed(2)}</p>
          </div>
          <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-3">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Remaining</p>
            <p className="text-lg font-semibold">${status.remaining_budget.toFixed(2)}</p>
          </div>
          <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-3">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Projected</p>
            <p className="text-lg font-semibold">${status.projected_spend.toFixed(2)}</p>
          </div>
        </section>
      </main>
    </div>
  );
}
