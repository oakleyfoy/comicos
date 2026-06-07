import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type P88MarketplaceAlertRead,
  type P88MarketplaceMonitoringRunRead,
  type P88MarketplaceSavedSearchRead,
} from "../api/client";
import { BuyMarketplaceNav } from "../components/buy/BuyMarketplaceNav";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";
import { isSafeMarketplaceListingUrl } from "../features/buyOpportunities/buyOpportunityPresentation";

const ALERT_LABELS: Record<string, string> = {
  NEW_LISTING: "New Listing",
  PRICE_DROP: "Price Drop",
  BELOW_FMV: "Below FMV",
  WATCHLIST_MATCH: "Watchlist Match",
  RARE_MATCH: "Rare Match",
};

export function MarketplaceMonitoringPage(): JSX.Element {
  const [searches, setSearches] = useState<P88MarketplaceSavedSearchRead[]>([]);
  const [alerts, setAlerts] = useState<P88MarketplaceAlertRead[]>([]);
  const [runs, setRuns] = useState<P88MarketplaceMonitoringRunRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    query: "",
    series: "",
    issue_number: "",
    max_price: "",
    min_discount_to_fmv: "15",
    is_active: true,
  });

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [searchList, alertList, runList] = await Promise.all([
        apiClient.listMarketplaceSavedSearches(),
        apiClient.listMarketplaceMonitoringAlerts({ status: "NEW" }),
        apiClient.listMarketplaceMonitoringRuns({ limit: 10 }),
      ]);
      setSearches(searchList.items ?? []);
      setAlerts(alertList.items ?? []);
      setRuns(runList.items ?? []);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load marketplace monitoring.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await apiClient.createMarketplaceSavedSearch({
      name: form.name,
      marketplace: "EBAY",
      query: form.query,
      series: form.series,
      issue_number: form.issue_number,
      max_price: form.max_price ? Number(form.max_price) : undefined,
      min_discount_to_fmv: form.min_discount_to_fmv ? Number(form.min_discount_to_fmv) : undefined,
      is_active: form.is_active,
    });
    setFormOpen(false);
    setForm({ name: "", query: "", series: "", issue_number: "", max_price: "", min_discount_to_fmv: "15", is_active: true });
    await load();
  }

  async function runNow(id: number) {
    await apiClient.runMarketplaceSavedSearch(id);
    await load();
  }

  async function dismissAlert(id: number) {
    await apiClient.updateMarketplaceAlert(id, { status: "DISMISSED" });
    await load();
  }

  async function reviewAlert(id: number) {
    await apiClient.updateMarketplaceAlert(id, { status: "ACKNOWLEDGED" });
    await load();
  }

  return (
    <PatriotPageLayout
      eyebrow="Buy"
      title="Marketplace Monitoring"
      description="Saved eBay searches, live alerts for new listings, price drops, and below-FMV opportunities."
      showExpansionNav
      error={error}
      onRetry={() => void load()}
      loading={loading && searches.length === 0 && alerts.length === 0}
      headerExtra={<BuyMarketplaceNav />}
      headerActions={
        <button
          type="button"
          className="rounded-md bg-white px-3 py-1.5 text-sm font-medium text-red-800 hover:bg-blue-50"
          onClick={() => setFormOpen((v) => !v)}
        >
          {formOpen ? "Cancel" : "New Saved Search"}
        </button>
      }
    >
      {formOpen ? (
        <PatriotPanel>
          <form className="grid gap-3 text-sm sm:grid-cols-2" onSubmit={(e) => void handleCreate(e)}>
            <label className="block sm:col-span-2">
              <span className="text-xs uppercase text-blue-600">Name</span>
              <input
                className="mt-1 w-full rounded border border-blue-300 px-2 py-1"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </label>
            <label className="block">
              <span className="text-xs uppercase text-blue-600">Query</span>
              <input
                className="mt-1 w-full rounded border border-blue-300 px-2 py-1"
                value={form.query}
                onChange={(e) => setForm({ ...form, query: e.target.value })}
              />
            </label>
            <label className="block">
              <span className="text-xs uppercase text-blue-600">Series</span>
              <input
                className="mt-1 w-full rounded border border-blue-300 px-2 py-1"
                value={form.series}
                onChange={(e) => setForm({ ...form, series: e.target.value })}
              />
            </label>
            <label className="block">
              <span className="text-xs uppercase text-blue-600">Issue</span>
              <input
                className="mt-1 w-full rounded border border-blue-300 px-2 py-1"
                value={form.issue_number}
                onChange={(e) => setForm({ ...form, issue_number: e.target.value })}
              />
            </label>
            <label className="block">
              <span className="text-xs uppercase text-blue-600">Max price</span>
              <input
                className="mt-1 w-full rounded border border-blue-300 px-2 py-1"
                value={form.max_price}
                onChange={(e) => setForm({ ...form, max_price: e.target.value })}
              />
            </label>
            <label className="block">
              <span className="text-xs uppercase text-blue-600">Min discount to FMV (%)</span>
              <input
                className="mt-1 w-full rounded border border-blue-300 px-2 py-1"
                value={form.min_discount_to_fmv}
                onChange={(e) => setForm({ ...form, min_discount_to_fmv: e.target.value })}
              />
            </label>
            <div className="sm:col-span-2">
              <button type="submit" className="rounded-md bg-red-700 px-3 py-1.5 text-sm font-medium text-white">
                Save search
              </button>
            </div>
          </form>
        </PatriotPanel>
      ) : null}

      <PatriotPanel>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-red-700">Saved searches</h2>
        {searches.length === 0 ? (
          <p className="mt-2 text-sm text-blue-800">No saved searches yet. Create one to start monitoring eBay.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {searches.map((s) => (
              <li key={s.id} className="rounded border border-blue-200 px-3 py-2 text-sm">
                <p className="font-medium">{s.name}</p>
                <p className="text-blue-700">
                  {s.marketplace} · {s.series} {s.issue_number} {s.query ? `· ${s.query}` : ""}
                </p>
                <p className="text-xs text-blue-600">
                  {s.is_active ? "Active" : "Disabled"}
                  {s.last_run_at ? ` · Last run ${new Date(s.last_run_at).toLocaleString()}` : ""}
                  {s.last_error ? ` · Error: ${s.last_error}` : ""}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="rounded border border-blue-800 px-2 py-1 text-xs font-medium"
                    onClick={() => void runNow(s.id)}
                  >
                    Run Now
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </PatriotPanel>

      <PatriotPanel>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-red-700">Marketplace alerts</h2>
        {alerts.length === 0 ? (
          <p className="mt-2 text-sm text-blue-800">No new alerts.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {alerts.map((a) => {
              const listingSafe =
                a.listing_url &&
                isSafeMarketplaceListingUrl({
                  listing_url: a.listing_url,
                  external_listing_id: a.external_item_id ?? "",
                  marketplace: a.marketplace ?? "EBAY",
                });
              return (
                <li key={a.id} className="rounded border border-blue-200 bg-blue-50/40 px-3 py-2 text-sm">
                  <p className="text-xs font-semibold uppercase text-red-700">
                    {ALERT_LABELS[a.alert_type] ?? a.alert_type}
                  </p>
                  <p className="font-medium">{a.title}</p>
                  <p>{a.message}</p>
                  {a.price != null ? (
                    <p>
                      ${a.price.toFixed(2)}
                      {a.shipping_cost ? ` +$${a.shipping_cost.toFixed(2)} shipping` : ""}
                      {a.estimated_fmv ? ` · FMV $${a.estimated_fmv.toFixed(2)}` : ""}
                    </p>
                  ) : null}
                  <p className="text-xs text-blue-600">{new Date(a.created_at).toLocaleString()}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {a.opportunity_id ? (
                      <Link
                        to={`/marketplace-opportunity/${a.opportunity_id}`}
                        className="rounded bg-red-700 px-2 py-1 text-xs text-white"
                      >
                        View Opportunity
                      </Link>
                    ) : null}
                    {listingSafe ? (
                      <a
                        href={a.listing_url!}
                        className="rounded border border-blue-800 px-2 py-1 text-xs"
                        target="_blank"
                        rel="noreferrer"
                      >
                        View Marketplace Listing
                      </a>
                    ) : null}
                    <button type="button" className="text-xs underline" onClick={() => void reviewAlert(a.id)}>
                      Mark reviewed
                    </button>
                    <button type="button" className="text-xs underline" onClick={() => void dismissAlert(a.id)}>
                      Dismiss
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </PatriotPanel>

      <PatriotPanel>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-red-700">Recent runs</h2>
        {runs.length === 0 ? (
          <p className="mt-2 text-sm text-blue-800">No monitoring runs yet.</p>
        ) : (
          <ul className="mt-3 space-y-2 text-sm">
            {runs.map((r) => (
              <li key={r.id} className="rounded border border-blue-200 px-3 py-2">
                {new Date(r.created_at).toLocaleString()} · found {r.listings_found} · new {r.new_listings} · drops{" "}
                {r.price_drops} · below FMV {r.below_fmv_alerts}
              </li>
            ))}
          </ul>
        )}
      </PatriotPanel>
    </PatriotPageLayout>
  );
}
