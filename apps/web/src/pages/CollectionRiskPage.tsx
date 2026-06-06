import { useEffect, useState } from "react";

import { ApiError, apiClient, type P83CollectionRiskRead } from "../api/client";
import { CollectorExpansionNav } from "../components/collector/CollectorExpansionNav";
import { StatusBanner } from "../components/StatusBanner";

export function CollectionRiskPage(): JSX.Element {
  const [risk, setRisk] = useState<P83CollectionRiskRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setRisk(await apiClient.getCollectionRisk());
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load risk.");
      }
    })();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-3xl space-y-3">
          <h1 className="text-xl font-semibold">Collection risk</h1>
          <CollectorExpansionNav />
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-6 text-sm">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        {risk ? (
          <p>
            {risk.risk_category} — score {risk.risk_score.toFixed(1)}
          </p>
        ) : (
          <p className="text-slate-400">Loading…</p>
        )}
      </main>
    </div>
  );
}
