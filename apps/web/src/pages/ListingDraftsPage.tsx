import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P78ListingDraftRead } from "../api/client";
import { NavPageLoadBanner } from "../components/NavPageLoadBanner";
import { PatriotPanel } from "../components/PatriotPageLayout";
import { SellWorkflowPageLayout } from "../components/sell/p78/SellWorkflowPageLayout";

export function ListingDraftsPage(): JSX.Element {
  const [items, setItems] = useState<P78ListingDraftRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadStatus, setLoadStatus] = useState<string | undefined>();
  const [loadMessage, setLoadMessage] = useState<string | undefined>();

  const load = useCallback(async () => {
    setError(null);
    try {
      const body = await apiClient.listListingDrafts({ limit: 50, offset: 0 });
      setItems(body.items);
      setLoadStatus(body.status);
      setLoadMessage(body.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load drafts.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <SellWorkflowPageLayout title="Listing drafts" eyebrow="P78-01 · Sell" error={error} onRetry={() => void load()}>
      <NavPageLoadBanner status={loadStatus} message={loadMessage} />
      {items.length === 0 ? (
        <PatriotPanel>
          <p className="text-blue-800/80">No listing drafts yet. Create one from the sell queue.</p>
        </PatriotPanel>
      ) : (
        <ul className="space-y-3">
          {items.map((d) => (
            <PatriotPanel key={d.id}>
              <div className="flex flex-wrap justify-between gap-2">
                <div>
                  <p className="font-medium text-blue-950">{d.title}</p>
                  <p className="text-xs uppercase tracking-wider text-red-700">{d.status}</p>
                </div>
                <p className="text-sm font-semibold text-blue-900">${d.market_price.toFixed(2)} market</p>
              </div>
              <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-blue-900/80">{d.description}</p>
              <p className="mt-2 text-xs text-blue-800/70">
                Quick ${d.quick_sale_price.toFixed(2)} · Premium ${d.premium_price.toFixed(2)} · Qty {d.suggested_sell_quantity}
              </p>
            </PatriotPanel>
          ))}
        </ul>
      )}
    </SellWorkflowPageLayout>
  );
}
