import { useEffect, useState } from "react";

import { ApiError, apiClient, type P83CollectionForecastRead } from "../api/client";
import { CollectorExpansionNav } from "../components/collector/CollectorExpansionNav";
import { StatusBanner } from "../components/StatusBanner";

export function CollectionForecastPage(): JSX.Element {
  const [forecast, setForecast] = useState<P83CollectionForecastRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setForecast(await apiClient.getCollectionForecast());
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load forecast.");
      }
    })();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-3xl space-y-3">
          <h1 className="text-xl font-semibold">Collection forecast</h1>
          <CollectorExpansionNav />
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-6 text-sm">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        {forecast ? (
          <ul className="space-y-2">
            {forecast.horizons.map((h) => (
              <li key={h.horizon}>
                {h.horizon}: ${h.forecast_value.toFixed(2)} ({h.forecast_change >= 0 ? "+" : ""}
                {h.forecast_change.toFixed(2)})
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-slate-400">Loading…</p>
        )}
      </main>
    </div>
  );
}
