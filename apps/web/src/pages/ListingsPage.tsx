import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P78SellingDashboardRead } from "../api/client";
import { NavPageLoadBanner } from "../components/NavPageLoadBanner";
import { PatriotPanel } from "../components/PatriotPageLayout";
import { SellWorkflowPageLayout } from "../components/sell/p78/SellWorkflowPageLayout";

function ListingRow({ title, status, price, extra }: { title: string; status: string; price: number; extra?: string }) {
  return (
    <li className="rounded-lg border border-blue-200 bg-white px-3 py-2 text-blue-950">
      <div className="flex flex-wrap justify-between gap-2">
        <div>
          <p className="text-sm font-medium">{title}</p>
          <p className="text-[10px] uppercase tracking-wider text-red-700">{status}</p>
        </div>
        <p className="text-sm font-semibold text-blue-900">${price.toFixed(2)}</p>
      </div>
      {extra ? <p className="mt-1 text-xs text-blue-800/70">{extra}</p> : null}
    </li>
  );
}

export function ListingsPage(): JSX.Element {
  const [dash, setDash] = useState<P78SellingDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setDash(await apiClient.getSellingDashboard());
    } catch (err) {
      setDash(null);
      setError(err instanceof ApiError ? err.message : "Failed to load listings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onSync = async () => {
    setSyncing(true);
    setError(null);
    try {
      await apiClient.syncListings();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sync failed.");
    } finally {
      setSyncing(false);
    }
  };

  const syncButton = (
    <button
      type="button"
      disabled={syncing}
      onClick={() => void onSync()}
      className="rounded-lg border border-white/30 bg-red-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-50"
    >
      {syncing ? "Syncing…" : "Sync marketplace"}
    </button>
  );

  return (
    <SellWorkflowPageLayout
      title="Listings"
      eyebrow="P78-02 · Sell"
      error={error}
      onRetry={() => void load()}
      loading={loading && !dash}
      headerActions={syncButton}
    >
      {dash ? (
        <>
          <NavPageLoadBanner status={dash.status ?? dash.analytics.status} message={dash.message ?? dash.analytics.message} />
          <PatriotPanel title="Active listings">
            <ul className="mt-2 space-y-2">
              {dash.active_listings.length === 0 ? (
                <p className="text-blue-800/80">None</p>
              ) : (
                dash.active_listings.map((l) => (
                  <ListingRow
                    key={l.id}
                    title={l.title}
                    status={`${l.lifecycle_status} · ${l.sync_state}`}
                    price={l.asking_price}
                    extra={l.listing_url ?? l.external_listing_id ?? undefined}
                  />
                ))
              )}
            </ul>
          </PatriotPanel>
          <PatriotPanel title="Draft listings">
            <ul className="mt-2 space-y-2">
              {dash.draft_listings.length === 0 ? (
                <p className="text-blue-800/80">None — create drafts from the sell queue.</p>
              ) : (
                dash.draft_listings.map((d) => (
                  <ListingRow
                    key={String(d.id)}
                    title={String(d.title ?? "Draft")}
                    status={String(d.status ?? "DRAFT")}
                    price={Number(d.market_price ?? 0)}
                  />
                ))
              )}
            </ul>
          </PatriotPanel>
          <PatriotPanel title="Sold listings">
            <ul className="mt-2 space-y-2">
              {dash.sold_listings.length === 0 ? (
                <p className="text-blue-800/80">None</p>
              ) : (
                dash.sold_listings.map((l) => (
                  <ListingRow key={l.id} title={l.title} status={l.lifecycle_status} price={l.sold_price ?? l.asking_price} />
                ))
              )}
            </ul>
          </PatriotPanel>
          <PatriotPanel title="Completed sales">
            <ul className="mt-2 space-y-2">
              {dash.recent_sales.length === 0 ? (
                <p className="text-blue-800/80">None</p>
              ) : (
                dash.recent_sales.map((s) => (
                  <li key={s.id} className="rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm text-blue-950">
                    <span className="font-medium">${s.sale_price.toFixed(2)}</span>
                    <span className="text-blue-800/70">
                      {" "}
                      · profit ${s.profit.toFixed(2)} · ROI {s.roi_pct}%
                    </span>
                  </li>
                ))
              )}
            </ul>
          </PatriotPanel>
        </>
      ) : null}
    </SellWorkflowPageLayout>
  );
}
