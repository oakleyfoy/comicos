import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P82MarketplaceAcquisitionDashboardRead } from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

function Section({ title, items }: { title: string; items: { id: number; title: string; opportunity_score: number }[] }) {
  return (
    <PatriotPanel title={title}>
      <ul className="space-y-1 text-blue-900">
        {items.map((i) => (
          <li key={i.id}>
            <Link to={`/marketplace-opportunity/${i.id}`} className="font-medium text-blue-700 hover:text-red-700 hover:underline">
              {i.title}
            </Link>{" "}
            ({i.opportunity_score.toFixed(0)})
          </li>
        ))}
      </ul>
    </PatriotPanel>
  );
}

export function MarketplaceAcquisitionDashboardPage(): JSX.Element {
  const [dash, setDash] = useState<P82MarketplaceAcquisitionDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setDash(await apiClient.getMarketplaceAcquisitionDashboard({ refresh: true }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <PatriotPageLayout
      eyebrow="P82"
      title="Marketplace acquisition dashboard"
      showExpansionNav
      error={error}
      onRetry={() => void load()}
      loading={loading && !dash}
      maxWidthClass="max-w-4xl"
    >
      {dash ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Section title="Strong buys" items={dash.strong_buys} />
          <Section title="Good buys" items={dash.good_buys} />
          <Section title="Watch" items={dash.watch} />
          <Section title="Largest FMV spread" items={dash.largest_spread} />
          <Section title="Best grading upside" items={dash.best_grading_upside} />
          <Section title="Best profile matches" items={dash.best_profile_matches} />
        </div>
      ) : null}
    </PatriotPageLayout>
  );
}
