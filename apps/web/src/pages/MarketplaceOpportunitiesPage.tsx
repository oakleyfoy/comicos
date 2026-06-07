import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, apiClient, type P82MarketplaceAcquisitionOpportunityRead } from "../api/client";
import { BuyMarketplaceNav } from "../components/buy/BuyMarketplaceNav";
import { CollectorEmptyState } from "../components/CollectorEmptyState";
import { NavPageLoadBanner } from "../components/NavPageLoadBanner";
import { PatriotPageLayout } from "../components/PatriotPageLayout";
import { BuyOpportunityCard } from "../features/buyOpportunities/BuyOpportunityCard";
import { buildBuyOpportunityDisplayCards } from "../features/buyOpportunities/buyOpportunityPresentation";
import { ImportMarketplaceUrlModal } from "../features/buyOpportunities/ImportMarketplaceUrlModal";

export function MarketplaceOpportunitiesPage(): JSX.Element {
  const [items, setItems] = useState<P82MarketplaceAcquisitionOpportunityRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadStatus, setLoadStatus] = useState<string | undefined>();
  const [loadMessage, setLoadMessage] = useState<string | undefined>();
  const [importOpen, setImportOpen] = useState(false);
  const [importSuccess, setImportSuccess] = useState<string | null>(null);

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
      headerExtra={<BuyMarketplaceNav />}
      error={error}
      onRetry={() => void load()}
      headerActions={
        <button
          type="button"
          className="rounded-md bg-white px-3 py-1.5 text-sm font-medium text-red-800 hover:bg-blue-50"
          onClick={() => setImportOpen(true)}
        >
          Import Marketplace URL
        </button>
      }
    >
      <NavPageLoadBanner status={loadStatus} message={loadMessage} />
      {importSuccess ? (
        <p className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">{importSuccess}</p>
      ) : null}
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
      <ImportMarketplaceUrlModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onSuccess={() => setImportSuccess("Marketplace imported successfully.")}
      />
    </PatriotPageLayout>
  );
}
