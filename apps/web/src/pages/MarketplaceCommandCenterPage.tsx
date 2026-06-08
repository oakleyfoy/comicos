import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P88MarketplaceCommandCenterRead } from "../api/client";
import { BuyMarketplaceNav } from "../components/buy/BuyMarketplaceNav";
import { CollectorEmptyState } from "../components/CollectorEmptyState";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

function BestDealAction({ row }: { row: P88MarketplaceCommandCenterRead["best_deals_today"][number] }): JSX.Element {
  const label = row.has_verified_listing ? "Buy Now" : "Review Opportunity";
  if (row.has_verified_listing && row.action_url?.startsWith("http")) {
    return (
      <a
        href={row.action_url}
        target="_blank"
        rel="noreferrer"
        className="font-semibold text-red-700 hover:underline"
      >
        {label}
      </a>
    );
  }
  const href = row.action_url?.startsWith("/") ? row.action_url : `/marketplace-opportunity/${row.opportunity_id}`;
  return (
    <Link to={href} className="font-semibold text-blue-900 hover:underline">
      {label}
    </Link>
  );
}

function KpiCard({ label, value }: { label: string; value: number }): JSX.Element {
  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50/40 px-3 py-2">
      <p className="text-xs uppercase tracking-wide text-blue-600">{label}</p>
      <p className="text-xl font-semibold text-blue-950">{value}</p>
    </div>
  );
}

export function MarketplaceCommandCenterPage(): JSX.Element {
  const [data, setData] = useState<P88MarketplaceCommandCenterRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setData(await apiClient.getMarketplaceCommandCenter());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load Marketplace Command Center.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const empty =
    data &&
    data.best_deals_today.length === 0 &&
    data.price_drops.length === 0 &&
    data.collection_gaps.length === 0 &&
    data.watchlist_matches.length === 0 &&
    data.upcoming_releases.length === 0 &&
    data.top_recommendations.length === 0;

  return (
    <PatriotPageLayout
      eyebrow="Buy"
      title="Marketplace Command Center"
      description="The best buying opportunities across all marketplaces and ComicOS intelligence systems."
      error={error}
      onRetry={() => void load()}
      loading={loading && !data}
      maxWidthClass="max-w-5xl"
      headerExtra={<BuyMarketplaceNav />}
    >
      {data ? (
        <>
          <PatriotPanel title="Today's snapshot">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <KpiCard label="Active opportunities" value={data.kpis.active_opportunities} />
              <KpiCard label="Marketplace alerts" value={data.kpis.marketplace_alerts} />
              <KpiCard label="Price drops" value={data.kpis.price_drops} />
              <KpiCard label="Watchlist matches" value={data.kpis.watchlist_matches} />
              <KpiCard label="Collection gaps" value={data.kpis.collection_gaps} />
              <KpiCard label="Upcoming releases" value={data.kpis.upcoming_releases} />
            </div>
          </PatriotPanel>

          <PatriotPanel title="Quick actions" className="mt-4">
            <ul className="flex flex-wrap gap-2">
              {data.quick_actions.map((action) => (
                <li key={action.action_type}>
                  <Link
                    to={action.route}
                    className="inline-block rounded-md border border-blue-800 px-3 py-1.5 text-sm font-medium text-blue-900 hover:bg-blue-50"
                  >
                    {action.label}
                  </Link>
                </li>
              ))}
            </ul>
          </PatriotPanel>

          {empty ? (
            <div className="mt-4">
              <CollectorEmptyState
                title="No marketplace signals yet"
                description="Run marketplace monitoring or import buy opportunities to populate this dashboard."
              />
            </div>
          ) : null}

          <PatriotPanel title="ComicOS top recommendations" className="mt-4">
            {data.top_recommendations.length === 0 ? (
              <p className="text-sm text-blue-800">No recommendations cached yet.</p>
            ) : (
              <ul className="space-y-3">
                {data.top_recommendations.map((row) => (
                  <li
                    key={row.opportunity_id}
                    className="flex gap-3 rounded border border-blue-200 bg-white px-3 py-2"
                  >
                    {row.cover_image_url ? (
                      <img
                        src={row.cover_image_url}
                        alt=""
                        className="h-16 w-12 shrink-0 rounded object-cover"
                      />
                    ) : (
                      <div className="flex h-16 w-12 shrink-0 items-center justify-center rounded bg-blue-100 text-xs text-blue-700">
                        Comic
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <Link
                        to={`/marketplace-opportunity/${row.opportunity_id}`}
                        className="font-medium text-red-700 hover:underline"
                      >
                        {row.title}
                      </Link>
                      <p className="text-sm text-blue-800">
                        Score {Math.round(row.score)} · {row.reason_summary}
                      </p>
                      {row.best_marketplace_name ? (
                        <p className="text-sm text-blue-900">
                          Best: {row.best_marketplace_name}
                          {row.best_price != null ? ` · $${row.best_price.toFixed(2)}` : null}
                        </p>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </PatriotPanel>

          <PatriotPanel title="Best deals today" className="mt-4">
            {data.best_deals_today.length === 0 ? (
              <p className="text-sm text-blue-800">No best deals in cache.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-blue-200 text-left text-xs uppercase text-blue-600">
                      <th className="py-2 pr-3">Comic</th>
                      <th className="py-2 pr-3">Marketplace</th>
                      <th className="py-2 pr-3">Price</th>
                      <th className="py-2 pr-3">FMV</th>
                      <th className="py-2 pr-3">Upside</th>
                      <th className="py-2 pr-3">Savings</th>
                      <th className="py-2">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.best_deals_today.map((row) => (
                      <tr key={row.opportunity_id} className="border-b border-blue-100">
                        <td className="py-2 pr-3">
                          <Link
                            to={`/marketplace-opportunity/${row.opportunity_id}`}
                            className="font-medium text-red-700 hover:underline"
                          >
                            {row.title}
                          </Link>
                        </td>
                        <td className="py-2 pr-3">{row.marketplace_name ?? row.marketplace ?? "—"}</td>
                        <td className="py-2 pr-3">${row.price.toFixed(2)}</td>
                        <td className="py-2 pr-3">${row.fmv.toFixed(2)}</td>
                        <td className="py-2 pr-3">
                          {row.upside_percent != null ? `+${Math.round(row.upside_percent)}%` : "—"}
                        </td>
                        <td className="py-2 pr-3">
                          {row.savings_vs_highest != null
                            ? `$${row.savings_vs_highest.toFixed(2)}`
                            : "—"}
                        </td>
                        <td className="py-2">
                          <BestDealAction row={row} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </PatriotPanel>

          <PatriotPanel title="Recent price drops" className="mt-4">
            {data.price_drops.length === 0 ? (
              <p className="text-sm text-blue-800">No recent price drops.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {data.price_drops.map((row) => (
                  <li key={`${row.listing_id}-${row.title}`} className="rounded border border-blue-100 px-3 py-2">
                    <p className="font-medium">{row.title}</p>
                    <p className="text-blue-800">
                      {row.marketplace_name} · ${row.old_price.toFixed(2)} → ${row.new_price.toFixed(2)} · Drop{" "}
                      {row.drop_percent}%
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </PatriotPanel>

          <PatriotPanel title="Watchlist matches" className="mt-4">
            {data.watchlist_matches.length === 0 ? (
              <p className="text-sm text-blue-800">No watchlist matches.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {data.watchlist_matches.map((row) => (
                  <li key={row.alert_id} className="rounded border border-blue-100 px-3 py-2">
                    <p className="font-medium">{row.title}</p>
                    <p className="text-blue-800">
                      {row.saved_search_name}
                      {row.marketplace_name ? ` · ${row.marketplace_name}` : null}
                      {row.price != null ? ` · $${row.price.toFixed(2)}` : null}
                    </p>
                    <p className="text-xs text-blue-700">{row.message}</p>
                  </li>
                ))}
              </ul>
            )}
          </PatriotPanel>

          <PatriotPanel title="Collection gaps" className="mt-4">
            {data.collection_gaps.length === 0 ? (
              <p className="text-sm text-blue-800">No collection gaps cached.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {data.collection_gaps.map((row) => (
                  <li key={row.gap_id} className="rounded border border-blue-100 px-3 py-2">
                    <p className="font-medium">{row.title}</p>
                    <p className="text-blue-800">{row.reason}</p>
                  </li>
                ))}
              </ul>
            )}
          </PatriotPanel>

          <PatriotPanel title="Upcoming releases worth buying" className="mt-4">
            {data.upcoming_releases.length === 0 ? (
              <p className="text-sm text-blue-800">No upcoming releases in your pull list.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {data.upcoming_releases.map((row) => (
                  <li key={row.item_id} className="rounded border border-blue-100 px-3 py-2">
                    <p className="font-medium">{row.title}</p>
                    <p className="text-blue-800">
                      {row.recommendation}
                      {row.release_date ? ` · Release ${row.release_date}` : null}
                      {row.foc_date ? ` · FOC ${row.foc_date}` : null}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </PatriotPanel>

          {data.marketplace_activity.length > 0 ? (
            <PatriotPanel title="Marketplace activity" className="mt-4">
              <ul className="space-y-2 text-sm">
                {data.marketplace_activity.map((row, idx) => (
                  <li key={`${row.activity_type}-${idx}`} className="border-b border-blue-100 pb-2">
                    <p className="font-medium">{row.title}</p>
                    <p className="text-xs text-blue-700">{row.message}</p>
                  </li>
                ))}
              </ul>
            </PatriotPanel>
          ) : null}
        </>
      ) : null}
    </PatriotPageLayout>
  );
}
