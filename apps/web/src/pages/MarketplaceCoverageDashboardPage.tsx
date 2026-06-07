import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type P88MarketplaceCoverageRead,
  type P88MarketplaceDiagnosticsRead,
} from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

export function MarketplaceCoverageDashboardPage(): JSX.Element {
  const [coverage, setCoverage] = useState<P88MarketplaceCoverageRead | null>(null);
  const [diagnostics, setDiagnostics] = useState<P88MarketplaceDiagnosticsRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [cov, diag] = await Promise.all([
        apiClient.getAdminMarketplaceCoverage(),
        apiClient.getAdminMarketplaceDiagnostics(),
      ]);
      setCoverage(cov);
      setDiagnostics(diag);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load marketplace coverage.");
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
      title="Marketplace Coverage"
      description="Operational visibility for multi-marketplace listings, adapter support, and search health."
      showExpansionNav={false}
      error={error}
      onRetry={() => void load()}
      loading={loading && !coverage}
      maxWidthClass="max-w-5xl"
      headerExtra={
        <Link to="/ops/marketplace-search" className="text-blue-100 hover:text-white hover:underline">
          ← Search dashboard
        </Link>
      }
    >
      {coverage ? (
        <PatriotPanel>
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs uppercase text-blue-600">Total listings</dt>
              <dd className="text-lg font-semibold">{coverage.total_listings}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-blue-600">Search success</dt>
              <dd className="text-lg font-semibold">{coverage.search_success_rate_percent}%</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-blue-600">Supported</dt>
              <dd className="text-sm font-medium">{coverage.supported_marketplaces.join(", ") || "—"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-blue-600">Shell adapters</dt>
              <dd className="text-sm font-medium">{coverage.unsupported_marketplaces.join(", ") || "—"}</dd>
            </div>
          </dl>

          <div className="mt-6 overflow-x-auto">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-red-700">Listings by marketplace</h3>
            <table className="mt-2 w-full min-w-[640px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-blue-200 text-left text-xs uppercase text-blue-600">
                  <th className="py-2 pr-3">Marketplace</th>
                  <th className="py-2 pr-3">Listings</th>
                  <th className="py-2 pr-3">Search</th>
                  <th className="py-2 pr-3">Lookup</th>
                  <th className="py-2 pr-3">Tracking</th>
                  <th className="py-2">Refresh</th>
                </tr>
              </thead>
              <tbody>
                {coverage.listings_by_marketplace.map((row) => (
                  <tr key={row.marketplace} className="border-b border-blue-100">
                    <td className="py-2 pr-3 font-medium">{row.marketplace_name}</td>
                    <td className="py-2 pr-3">{row.listing_count}</td>
                    <td className="py-2 pr-3">{row.supports_search ? "Yes" : "—"}</td>
                    <td className="py-2 pr-3">{row.supports_listing_lookup ? "Yes" : "—"}</td>
                    <td className="py-2 pr-3">{row.supports_price_tracking ? "Yes" : "—"}</td>
                    <td className="py-2">{row.supports_refresh ? "Yes" : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </PatriotPanel>
      ) : null}

      {diagnostics ? (
        <PatriotPanel className="mt-6">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-red-700">Marketplace diagnostics</h3>
          <p className="mt-1 text-xs text-blue-700">Read-only adapter and refresh status (no live searches).</p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-blue-200 text-left text-xs uppercase text-blue-600">
                  <th className="py-2 pr-3">Marketplace</th>
                  <th className="py-2 pr-3">Adapter</th>
                  <th className="py-2 pr-3">Support</th>
                  <th className="py-2 pr-3">Listings</th>
                  <th className="py-2">Last refresh</th>
                </tr>
              </thead>
              <tbody>
                {diagnostics.adapters.map((row) => (
                  <tr key={row.marketplace} className="border-b border-blue-100">
                    <td className="py-2 pr-3 font-medium">{row.marketplace_name}</td>
                    <td className="py-2 pr-3">{row.adapter_status}</td>
                    <td className="py-2 pr-3">{row.marketplace_support_status}</td>
                    <td className="py-2 pr-3">{row.listing_count}</td>
                    <td className="py-2">{row.last_successful_refresh ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {diagnostics.recent_errors.length > 0 ? (
            <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-blue-900">
              {diagnostics.recent_errors.map((err) => (
                <li key={err}>{err}</li>
              ))}
            </ul>
          ) : null}
        </PatriotPanel>
      ) : null}
    </PatriotPageLayout>
  );
}
