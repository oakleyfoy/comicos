import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P78SellingDashboardRead } from "../api/client";
import { SellWorkflowNav } from "../components/sell/p78/SellWorkflowNav";
import { StatusBanner } from "../components/StatusBanner";

function ListingRow({ title, status, price, extra }: { title: string; status: string; price: number; extra?: string }) {
  return (
    <li className="rounded-xl border border-slate-700 bg-slate-900/40 px-3 py-2">
      <div className="flex flex-wrap justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-white">{title}</p>
          <p className="text-[10px] uppercase tracking-wider text-slate-500">{status}</p>
        </div>
        <p className="text-sm text-emerald-200">${price.toFixed(2)}</p>
      </div>
      {extra ? <p className="mt-1 text-xs text-slate-500">{extra}</p> : null}
    </li>
  );
}

export function ListingsPage(): JSX.Element {
  const [dash, setDash] = useState<P78SellingDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setDash(await apiClient.getSellingDashboard());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load listings.");
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

  if (!dash) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : <p className="text-slate-400">Loading…</p>}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-4xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-amber-300">P78-02</p>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h1 className="text-xl font-semibold">Listings</h1>
            <button
              type="button"
              disabled={syncing}
              onClick={() => void onSync()}
              className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-50"
            >
              {syncing ? "Syncing…" : "Sync marketplace"}
            </button>
          </div>
          <SellWorkflowNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

        <section>
          <h2 className="text-sm font-semibold text-white">Active listings</h2>
          <ul className="mt-2 space-y-2">
            {dash.active_listings.length === 0 ? (
              <p className="text-sm text-slate-500">None</p>
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
        </section>

        <section>
          <h2 className="text-sm font-semibold text-white">Draft listings</h2>
          <ul className="mt-2 space-y-2">
            {dash.draft_listings.length === 0 ? (
              <p className="text-sm text-slate-500">None — create drafts from the sell queue.</p>
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
        </section>

        <section>
          <h2 className="text-sm font-semibold text-white">Sold listings</h2>
          <ul className="mt-2 space-y-2">
            {dash.sold_listings.length === 0 ? (
              <p className="text-sm text-slate-500">None</p>
            ) : (
              dash.sold_listings.map((l) => (
                <ListingRow
                  key={l.id}
                  title={l.title}
                  status={l.lifecycle_status}
                  price={l.sold_price ?? l.asking_price}
                />
              ))
            )}
          </ul>
        </section>

        <section>
          <h2 className="text-sm font-semibold text-white">Completed sales</h2>
          <ul className="mt-2 space-y-2">
            {dash.recent_sales.length === 0 ? (
              <p className="text-sm text-slate-500">None</p>
            ) : (
              dash.recent_sales.map((s) => (
                <li key={s.id} className="rounded-xl border border-slate-700 bg-slate-900/40 px-3 py-2 text-sm">
                  <span className="text-white">${s.sale_price.toFixed(2)}</span>
                  <span className="text-slate-500"> · profit ${s.profit.toFixed(2)} · ROI {s.roi_pct}%</span>
                </li>
              ))
            )}
          </ul>
        </section>
      </main>
    </div>
  );
}
