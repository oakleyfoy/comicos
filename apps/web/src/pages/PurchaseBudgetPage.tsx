import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type PurchaseBudgetAllocationRead,
  type PurchaseBudgetSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function money(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

export function PurchaseBudgetPage(): JSX.Element {
  const [summary, setSummary] = useState<PurchaseBudgetSummaryRead | null>(null);
  const [items, setItems] = useState<PurchaseBudgetAllocationRead[]>([]);
  const [monthlyInput, setMonthlyInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [budget, sum, alloc] = await Promise.all([
        apiClient.getPurchaseBudget(),
        apiClient.getPurchaseBudgetSummary(),
        apiClient.getPurchaseBudgetAllocations(),
      ]);
      setSummary(sum);
      setItems(alloc.items);
      setMonthlyInput(String(budget.monthly_budget));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load purchase budget.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function saveBudget() {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const monthly = Number(monthlyInput);
      if (Number.isNaN(monthly) || monthly < 0) {
        setError("Enter a valid monthly budget.");
        return;
      }
      await apiClient.patchPurchaseBudget({ monthly_budget: monthly });
      setMessage("Budget saved.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save budget.");
    } finally {
      setSaving(false);
    }
  }

  async function onGenerate() {
    setGenerating(true);
    setMessage(null);
    setError(null);
    try {
      const result = await apiClient.generatePurchaseBudgetAllocations();
      setMessage(`Generated ${result.created_count} new allocation(s).`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to generate allocations.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P53-04"
        title="Budget Allocation"
        description="Prioritized spending plan from purchase intelligence (advisory only — no orders or retailer contact)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}
      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">
          Monthly budget
          <input
            type="number"
            min={0}
            step={1}
            value={monthlyInput}
            onChange={(e) => setMonthlyInput(e.target.value)}
            className="mt-1 block w-36 rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          />
        </label>
        <button
          type="button"
          disabled={saving}
          onClick={() => void saveBudget()}
          className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 disabled:opacity-50"
        >
          Save budget
        </button>
        <button
          type="button"
          disabled={generating}
          onClick={() => void onGenerate()}
          className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 disabled:opacity-50"
        >
          Generate allocations
        </button>
      </div>
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading…</p>
      ) : summary ? (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <div className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
              <p className="text-xs uppercase text-slate-500">Monthly budget</p>
              <p className="mt-2 text-2xl font-semibold text-white">{money(summary.total_budget)}</p>
            </div>
            <div className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
              <p className="text-xs uppercase text-slate-500">Allocated budget</p>
              <p className="mt-2 text-2xl font-semibold text-cyan-100">{money(summary.allocated_budget)}</p>
              <p className="mt-1 text-xs text-slate-500">{summary.allocation_percentage.toFixed(1)}% utilized</p>
            </div>
            <div className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
              <p className="text-xs uppercase text-slate-500">Remaining budget</p>
              <p className="mt-2 text-2xl font-semibold text-emerald-200">{money(summary.remaining_budget)}</p>
            </div>
          </div>
          {items.length === 0 ? (
            <p className="mt-6 text-sm text-slate-400">
              No allocations yet. Set a budget, generate quantities/variants, then generate allocations.
            </p>
          ) : (
            <div className="mt-6 overflow-x-auto rounded-3xl border border-white/10 bg-slate-900/65">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-white/10 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Comic</th>
                    <th className="px-4 py-3">Tier</th>
                    <th className="px-4 py-3">Allocation</th>
                    <th className="px-4 py-3">Priority</th>
                    <th className="px-4 py-3">Rationale</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr key={row.id} className="border-b border-white/5 text-slate-200">
                      <td className="px-4 py-3">
                        <div className="font-medium text-white">{row.title || row.series_name}</div>
                        <div className="text-xs text-slate-500">
                          {row.publisher} · #{row.issue_number}
                        </div>
                      </td>
                      <td className="px-4 py-3">{row.recommendation_tier}</td>
                      <td className="px-4 py-3 font-semibold text-cyan-100">{money(row.allocated_amount)}</td>
                      <td className="px-4 py-3">{row.priority_rank}</td>
                      <td className="max-w-md px-4 py-3 text-slate-400">{row.rationale}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
    </AppShell>
  );
}
