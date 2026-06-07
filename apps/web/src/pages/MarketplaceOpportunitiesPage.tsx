import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P82MarketplaceAcquisitionOpportunityRead } from "../api/client";
import { CollectorEmptyState } from "../components/CollectorEmptyState";
import { NavPageLoadBanner } from "../components/NavPageLoadBanner";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

export function MarketplaceOpportunitiesPage(): JSX.Element {
  const [items, setItems] = useState<P82MarketplaceAcquisitionOpportunityRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadStatus, setLoadStatus] = useState<string | undefined>();
  const [loadMessage, setLoadMessage] = useState<string | undefined>();

  const load = useCallback(async () => {
    setError(null);
    try {
      const body = await apiClient.listMarketplaceAcquisitionOpportunities({ refresh: false, limit: 50 });
      setItems(body.items ?? []);
      setLoadStatus(body.status);
      setLoadMessage(body.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load opportunities.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <PatriotPageLayout
      eyebrow="P82 · Marketplace"
      title="Marketplace opportunities"
      showExpansionNav
      error={error}
      onRetry={() => void load()}
    >
      <NavPageLoadBanner status={loadStatus} message={loadMessage} />
      {items.length === 0 && !error && loadStatus !== "ERROR" ? (
        <CollectorEmptyState
          title="No marketplace opportunities yet"
          description="Refresh deals from your inventory FMV spread or scan an eBay listing."
          actionLabel="Acquisition dashboard"
          actionTo="/marketplace-acquisition-dashboard"
        />
      ) : null}
      <ul className="space-y-2 text-sm">
        {items.map((o) => (
          <PatriotPanel key={o.id}>
            <Link to={`/marketplace-opportunity/${o.id}`} className="font-medium text-red-700 hover:underline">
              {o.title}
            </Link>
            <p className="mt-1 text-blue-900/80">
              {o.recommendation} · score {o.opportunity_score.toFixed(0)} · ${o.asking_price.toFixed(2)} vs FMV $
              {o.estimated_fmv.toFixed(2)}
            </p>
          </PatriotPanel>
        ))}
      </ul>
    </PatriotPageLayout>
  );
}
