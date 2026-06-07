import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P88MarketplaceSearchDashboardRead } from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

export function MarketplaceSearchDashboardPage(): JSX.Element {
  const [data, setData] = useState<P88MarketplaceSearchDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const body = await apiClient.getAdminMarketplaceSearchDashboard();
      setData(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load marketplace search dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <PatriotPageLayout
      eyebrow="Admin"
      title="Marketplace Search Dashboard"
      description="Read-only metrics for live eBay Browse searches and stored marketplace listings."
      showExpansionNav={false}
      error={error}
      onRetry={() => void load()}
      loading={loading && !data}
      maxWidthClass="max-w-4xl"
      headerExtra={
        <Link to="/settings/integrations" className="text-blue-100 hover:text-white hover:underline">
          ← Integrations
        </Link>
      }
    >
      {data ? (
        <PatriotPanel>
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-xs uppercase text-blue-600">Search runs</dt>
              <dd className="text-lg font-semibold">{data.total_search_runs}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-blue-600">Recent searches</dt>
              <dd className="text-lg font-semibold">{data.recent_searches_run}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-blue-600">Success rate</dt>
              <dd className="text-lg font-semibold">{data.success_rate_percent}%</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-blue-600">Listings found</dt>
              <dd className="text-lg font-semibold">{data.listings_found_total}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-blue-600">New listings</dt>
              <dd className="text-lg font-semibold">{data.new_listings_total}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-blue-600">Updated listings</dt>
              <dd className="text-lg font-semibold">{data.updated_listings_total}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-blue-600">Failed searches</dt>
              <dd className="text-lg font-semibold">{data.failed_searches_total}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-blue-600">Active listings</dt>
              <dd className="text-lg font-semibold">{data.active_listings}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-blue-600">Ended listings</dt>
              <dd className="text-lg font-semibold">{data.ended_listings}</dd>
            </div>
          </dl>
          {data.recent_errors.length > 0 ? (
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-red-700">Recent errors</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-blue-900">
                {data.recent_errors.map((err) => (
                  <li key={err}>{err}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </PatriotPanel>
      ) : null}
    </PatriotPageLayout>
  );
}
