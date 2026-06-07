import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, apiClient, type P82MarketplaceAcquisitionOpportunityRead } from "../api/client";
import { CollectorEmptyState } from "../components/CollectorEmptyState";
import { NavPageLoadBanner } from "../components/NavPageLoadBanner";
import { PatriotPageLayout } from "../components/PatriotPageLayout";
import { BuyOpportunityCard } from "../features/buyOpportunities/BuyOpportunityCard";
import { buildBuyOpportunityDisplayCards } from "../features/buyOpportunities/buyOpportunityPresentation";

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
      setError(
        err instanceof ApiError ? err.message : "Unable to load buy opportunities right now.",
      );
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const cards = useMemo(() => buildBuyOpportunityDisplayCards(items), [items]);
  const showEmpty = cards.length === 0 && !error && loadStatus !== "ERROR";

  return (
    <PatriotPageLayout
      eyebrow="Buy"
      title="Buy Opportunities"
      description="Comics identified by ComicOS as strong purchase opportunities based on value, demand, release intelligence, and collector signals."
      showExpansionNav
      error={error}
      onRetry={() => void load()}
    >
      <NavPageLoadBanner status={loadStatus} message={loadMessage} />
      {showEmpty ? (
        <CollectorEmptyState
          title="No buy opportunities found right now."
          description="ComicOS will surface undervalued books, marketplace deals, and acquisition targets here when new opportunities are available."
          actionLabel="Acquisition dashboard"
          actionTo="/marketplace-acquisition-dashboard"
        />
      ) : null}
      {!error && cards.length > 0 ? (
        <ul className="space-y-4">
          {cards.map((card) => (
            <li key={card.groupKey}>
              <BuyOpportunityCard card={card} />
            </li>
          ))}
        </ul>
      ) : null}
    </PatriotPageLayout>
  );
}
