import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P77CollectorBudgetRead } from "../api/client";
import { CollectorProfileNav } from "../components/collector/p77/CollectorProfileNav";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";
import { patriotInputClass, patriotPrimaryButtonClass } from "../components/patriotTheme";

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

  return (
    <PatriotPageLayout
      eyebrow="P77-01 · Settings"
      title="Budget settings"
      subNav={<CollectorProfileNav />}
      error={error}
      onRetry={() => void load()}
      loading={!budget}
      maxWidthClass="max-w-2xl"
    >
      {budget ? (
        <PatriotPanel>
          <div className="space-y-3">
            <label className="block text-sm">
              Monthly budget ($)
              <input
                type="number"
                className={`mt-1 w-full ${patriotInputClass}`}
                value={budget.monthly_budget}
                onChange={(e) => setBudget({ ...budget, monthly_budget: Number(e.target.value) })}
              />
            </label>
            <label className="block text-sm">
              Budget period
              <select
                className={`mt-1 w-full ${patriotInputClass}`}
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
                className={`mt-1 w-full min-h-[100px] ${patriotInputClass} font-mono text-xs`}
                value={publisherLines}
                onChange={(e) => setPublisherLines(e.target.value)}
              />
            </label>
            <label className="block text-sm">
              Category budgets
              <textarea
                className={`mt-1 w-full min-h-[100px] ${patriotInputClass} font-mono text-xs`}
                value={categoryLines}
                onChange={(e) => setCategoryLines(e.target.value)}
              />
            </label>
            <button type="button" disabled={saving} onClick={() => void save()} className={`w-full ${patriotPrimaryButtonClass} py-3`}>
              {saving ? "Saving…" : "Save budget"}
            </button>
          </div>
        </PatriotPanel>
      ) : null}
    </PatriotPageLayout>
  );
}
