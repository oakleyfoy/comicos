import { useEffect, useState } from "react";

import { ApiError, apiClient, type P83CollectionValuationDashboardRead } from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

export function CollectionOptimizationPage(): JSX.Element {
  const [opt, setOpt] = useState<P83CollectionValuationDashboardRead["optimization"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const dash = await apiClient.getCollectionValuationDashboard();
        setOpt(dash.optimization);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load optimization.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <PatriotPageLayout
      eyebrow="P83"
      title="Portfolio optimization"
      showExpansionNav
      error={error}
      loading={loading && !opt}
      maxWidthClass="max-w-3xl"
    >
      {opt ? (
        <PatriotPanel>
          <p className="text-blue-900">Sell candidates: {opt.sell_candidates.length}</p>
          <p className="text-blue-900">Grade candidates: {opt.grade_candidates.length}</p>
          <p className="text-blue-900">Buy targets: {opt.buy_targets.length}</p>
        </PatriotPanel>
      ) : null}
    </PatriotPageLayout>
  );
}
