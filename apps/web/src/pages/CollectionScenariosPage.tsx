import { useState } from "react";

import { ApiError, apiClient } from "../api/client";
import { CollectorExpansionNav } from "../components/collector/CollectorExpansionNav";
import { StatusBanner } from "../components/StatusBanner";

const SCENARIOS = ["SELL_DUPLICATES", "GRADE_TOP_CANDIDATES", "MARKET_DROP", "MARKET_GAIN", "LIQUIDATE_SELL_QUEUE"];

export function CollectionScenariosPage(): JSX.Element {
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(type: string) {
    setError(null);
    try {
      const r = await apiClient.runCollectionScenario(type);
      setResult(`${r.scenario_type}: projected $${r.projected_value.toFixed(2)} — ${r.explanation}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Scenario failed.");
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-3xl space-y-3">
          <h1 className="text-xl font-semibold">Portfolio scenarios</h1>
          <CollectorExpansionNav />
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-4 px-4 py-6 text-sm">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        <div className="flex flex-wrap gap-2">
          {SCENARIOS.map((s) => (
            <button
              key={s}
              type="button"
              className="rounded bg-slate-800 px-3 py-1 hover:bg-slate-700"
              onClick={() => void run(s)}
            >
              {s}
            </button>
          ))}
        </div>
        {result ? <p className="text-slate-300">{result}</p> : null}
      </main>
    </div>
  );
}
