import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P77CollectorBudgetRead } from "../api/client";
import { CollectorProfileNav } from "../components/collector/p77/CollectorProfileNav";
import { StatusBanner } from "../components/StatusBanner";

export function CollectorBudgetPage(): JSX.Element {
  const [budget, setBudget] = useState<P77CollectorBudgetRead | null>(null);
  const [publisherLines, setPublisherLines] = useState("");
  const [categoryLines, setCategoryLines] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const row = await apiClient.getCollectorProfileBudget();
      setBudget(row);
      setPublisherLines(row.publisher_allocations.map((a) => `${a.name}:${a.amount}`).join("\n"));
      setCategoryLines(row.category_allocations.map((a) => `${a.name}:${a.amount}`).join("\n"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load budget.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function parseLines(text: string): { name: string; amount: number }[] {
    return text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [name, amount] = line.split(":");
        return { name: (name ?? "").trim(), amount: Number.parseFloat((amount ?? "0").trim()) || 0 };
      })
      .filter((row) => row.name);
  }

  async function save(): Promise<void> {
    if (!budget) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await apiClient.updateCollectorProfileBudget({
        monthly_budget: budget.monthly_budget,
        budget_period: budget.budget_period,
        publisher_allocations: parseLines(publisherLines),
        category_allocations: parseLines(categoryLines),
      });
      setBudget(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  if (!budget) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 px-4 py-8">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : <p className="text-slate-400">Loading…</p>}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-2xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-sky-300">P77-01</p>
          <h1 className="text-xl font-semibold">Budget Settings</h1>
          <CollectorProfileNav />
        </div>
      </header>
      <main className="mx-auto max-w-2xl space-y-4 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        <section className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4 space-y-3">
          <label className="block text-sm">
            Monthly budget ($)
            <input
              type="number"
              className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2"
              value={budget.monthly_budget}
              onChange={(e) => setBudget({ ...budget, monthly_budget: Number(e.target.value) })}
            />
          </label>
          <label className="block text-sm">
            Budget period
            <select
              className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2"
              value={budget.budget_period}
              onChange={(e) => setBudget({ ...budget, budget_period: e.target.value })}
            >
              <option value="MONTHLY">Monthly</option>
              <option value="QUARTERLY">Quarterly</option>
            </select>
          </label>
          <label className="block text-sm">
            Publisher budgets (one per line: Name:Amount)
            <textarea
              className="mt-1 w-full min-h-[100px] rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 font-mono text-xs"
              value={publisherLines}
              onChange={(e) => setPublisherLines(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            Category budgets
            <textarea
              className="mt-1 w-full min-h-[100px] rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 font-mono text-xs"
              value={categoryLines}
              onChange={(e) => setCategoryLines(e.target.value)}
            />
          </label>
          <button
            type="button"
            disabled={saving}
            onClick={() => void save()}
            className="w-full rounded-xl bg-sky-600 py-3 font-semibold disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save budget"}
          </button>
        </section>
      </main>
    </div>
  );
}
