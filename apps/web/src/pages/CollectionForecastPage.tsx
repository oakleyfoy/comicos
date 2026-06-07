import { useEffect, useState } from "react";

import { ApiError, apiClient, type P83CollectionForecastRead } from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

export function CollectionForecastPage(): JSX.Element {
  const [forecast, setForecast] = useState<P83CollectionForecastRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        setForecast(await apiClient.getCollectionForecast());
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load forecast.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <PatriotPageLayout
      eyebrow="P83"
      title="Collection forecast"
      showExpansionNav
      error={error}
      loading={loading && !forecast}
      maxWidthClass="max-w-3xl"
    >
      {forecast ? (
        <PatriotPanel title="Horizons">
          <ul className="space-y-2 text-blue-900">
            {forecast.horizons.map((h) => (
              <li key={h.horizon}>
                {h.horizon}: ${h.forecast_value.toFixed(2)} ({h.forecast_change >= 0 ? "+" : ""}
                {h.forecast_change.toFixed(2)})
              </li>
            ))}
          </ul>
        </PatriotPanel>
      ) : null}
    </PatriotPageLayout>
  );
}
