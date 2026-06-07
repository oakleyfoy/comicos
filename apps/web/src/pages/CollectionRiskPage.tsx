import { useEffect, useState } from "react";

import { ApiError, apiClient, type P83CollectionRiskRead } from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

export function CollectionRiskPage(): JSX.Element {
  const [risk, setRisk] = useState<P83CollectionRiskRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        setRisk(await apiClient.getCollectionRisk());
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load risk.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <PatriotPageLayout
      eyebrow="P83"
      title="Collection risk"
      showExpansionNav
      error={error}
      loading={loading && !risk}
      maxWidthClass="max-w-3xl"
    >
      {risk ? (
        <PatriotPanel>
          <p className="text-blue-900">
            {risk.risk_category} — score {risk.risk_score.toFixed(1)}
          </p>
        </PatriotPanel>
      ) : null}
    </PatriotPageLayout>
  );
}
