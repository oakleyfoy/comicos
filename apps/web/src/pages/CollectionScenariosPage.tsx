import { useState } from "react";

import { ApiError, apiClient } from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";
import { patriotPrimaryButtonClass } from "../components/patriotTheme";

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
    <PatriotPageLayout
      eyebrow="P83"
      title="Portfolio scenarios"
      showExpansionNav
      error={error}
      maxWidthClass="max-w-3xl"
    >
      <PatriotPanel>
        <div className="flex flex-wrap gap-2">
          {SCENARIOS.map((s) => (
            <button key={s} type="button" className={patriotPrimaryButtonClass} onClick={() => void run(s)}>
              {s}
            </button>
          ))}
        </div>
        {result ? <p className="mt-4 text-blue-900">{result}</p> : null}
      </PatriotPanel>
    </PatriotPageLayout>
  );
}
