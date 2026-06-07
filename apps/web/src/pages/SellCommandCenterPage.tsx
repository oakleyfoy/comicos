import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P89SellCommandCenterRead } from "../api/client";
import { CollectorEmptyState } from "../components/CollectorEmptyState";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";
import { SellCommandCenterNav } from "../components/sell/SellCommandCenterNav";

function money(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function KpiCard({ label, value }: { label: string; value: string | number }): JSX.Element {
  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50/40 px-3 py-2">
      <p className="text-xs uppercase tracking-wide text-blue-600">{label}</p>
      <p className="text-xl font-semibold text-blue-950">{value}</p>
    </div>
  );
}

export function SellCommandCenterPage(): JSX.Element {
  const [data, setData] = useState<P89SellCommandCenterRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setData(await apiClient.getSellCommandCenter());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load Sell Command Center.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const empty =
    data &&
    data.sell_now.length === 0 &&
    data.grade_first.length === 0 &&
    data.drafts_needing_review.length === 0 &&
    data.active_listings.length === 0 &&
    data.sold_recently.length === 0;

  return (
    <PatriotPageLayout
      eyebrow="Sell"
      title="Sell Command Center"
      description="The books, listings, and seller actions ComicOS thinks deserve attention."
      error={error}
      onRetry={() => void load()}
      loading={loading && !data}
      maxWidthClass="max-w-5xl"
      headerExtra={<SellCommandCenterNav />}
    >
      {data ? (
        <>
          <PatriotPanel title="Seller KPIs">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <KpiCard label="Sell Now" value={data.kpis.sell_now_count} />
              <KpiCard label="Grade First" value={data.kpis.grade_first_count} />
              <KpiCard label="Drafts awaiting review" value={data.kpis.drafts_awaiting_review} />
              <KpiCard label="Active listings" value={data.kpis.active_listings} />
              <KpiCard label="Sold this month" value={data.kpis.sold_this_month} />
              <KpiCard label="Est. net profit" value={money(data.kpis.estimated_net_profit)} />
            </div>
          </PatriotPanel>

          <PatriotPanel title="Daily seller actions" className="mt-4">
            {data.daily_actions.length === 0 ? (
              <p className="text-sm text-blue-800">No ranked actions right now — generate sell candidates when ready.</p>
            ) : (
              <ol className="space-y-2">
                {data.daily_actions.map((action) => (
                  <li key={action.rank} className="rounded border border-blue-200 bg-white px-3 py-2 text-sm">
                    <p className="font-medium text-blue-950">
                      {action.rank}. {action.title}
                    </p>
                    <p className="text-blue-800">{action.detail}</p>
                    <Link to={action.route} className="mt-1 inline-block text-red-700 underline">
                      {action.action_label}
                    </Link>
                  </li>
                ))}
              </ol>
            )}
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
                title="No sell-side signals yet"
                description="Generate sell candidates and listing drafts to populate this dashboard."
              />
            </div>
          ) : null}

          <PatriotPanel title="Sell Now" className="mt-4">
            {data.sell_now.length === 0 ? (
              <p className="text-sm text-blue-800">No SELL NOW candidates cached.</p>
            ) : (
              <ul className="space-y-2">
                {data.sell_now.map((row) => (
                  <li key={row.sell_candidate_id} className="rounded border border-blue-200 bg-white px-3 py-2 text-sm">
                    <p className="font-medium">{row.comic_title}</p>
                    <p className="text-blue-800">
                      Score {row.sell_score ?? "—"} · Est. sale {money(row.estimated_sale_value)} · Profit{" "}
                      {money(row.estimated_profit)} · {row.confidence}
                    </p>
                    <p className="text-blue-700">{row.reason_summary}</p>
                    <Link to={row.cta_route} className="text-red-700 underline">
                      {row.cta_label}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </PatriotPanel>

          <PatriotPanel title="Grade First Before Selling" className="mt-4">
            {data.grade_first.length === 0 ? (
              <p className="text-sm text-blue-800">No grade-first candidates.</p>
            ) : (
              <ul className="space-y-2">
                {data.grade_first.map((row) => (
                  <li key={row.sell_candidate_id} className="rounded border border-blue-200 bg-white px-3 py-2 text-sm">
                    <p className="font-medium">{row.comic_title}</p>
                    <p className="text-blue-800">
                      Grade score {row.grade_first_score ?? "—"} · Upside{" "}
                      {row.potential_upside != null ? money(row.potential_upside) : "—"} · {row.confidence}
                    </p>
                    <Link to={row.cta_route} className="text-red-700 underline">
                      {row.cta_label}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </PatriotPanel>

          <PatriotPanel title="Hold or Monitor" className="mt-4">
            {data.hold_or_monitor.length === 0 ? (
              <p className="text-sm text-blue-800">No high-value hold/monitor picks.</p>
            ) : (
              <ul className="space-y-2">
                {data.hold_or_monitor.map((row) => (
                  <li key={row.sell_candidate_id} className="rounded border border-blue-200 bg-white px-3 py-2 text-sm">
                    <p className="font-medium">{row.comic_title}</p>
                    <p className="text-blue-800">
                      Hold {row.hold_score ?? "—"} · Market {money(row.market_price)} · Trend {row.trend_direction ?? "—"}
                    </p>
                    <Link to={row.cta_route} className="text-red-700 underline">
                      {row.cta_label}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </PatriotPanel>

          <PatriotPanel title="Listing drafts needing review" className="mt-4">
            {data.drafts_needing_review.length === 0 ? (
              <p className="text-sm text-blue-800">No drafts in DRAFT status.</p>
            ) : (
              <ul className="space-y-2">
                {data.drafts_needing_review.map((row) => (
                  <li key={row.draft_id} className="flex flex-wrap justify-between gap-2 rounded border border-blue-200 bg-white px-3 py-2 text-sm">
                    <div>
                      <p className="font-medium">{row.comic_title}</p>
                      <p className="text-blue-800">
                        {row.marketplace} · {money(row.suggested_price)} · {new Date(row.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <Link to={row.cta_route} className="self-center text-red-700 underline">
                      Review Draft
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </PatriotPanel>

          <PatriotPanel title="Active listings" className="mt-4">
            {data.active_listings.length === 0 ? (
              <p className="text-sm text-blue-800">No active managed listings.</p>
            ) : (
              <ul className="space-y-2">
                {data.active_listings.map((row) => (
                  <li key={row.listing_id} className="rounded border border-blue-200 bg-white px-3 py-2 text-sm">
                    <div className="flex flex-wrap justify-between gap-2">
                      <p className="font-medium">{row.comic_title}</p>
                      {row.needs_review ? (
                        <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900">Needs Review</span>
                      ) : null}
                    </div>
                    <p className="text-blue-800">
                      {row.marketplace} · Ask {money(row.asking_price)} · Min {money(row.minimum_price)} ·{" "}
                      {row.days_listed != null ? `${row.days_listed} days listed` : "Not listed yet"}
                    </p>
                    <Link to={row.cta_route} className="text-red-700 underline">
                      Manage Listing
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </PatriotPanel>

          <PatriotPanel title="Sold recently" className="mt-4">
            {data.sold_recently.length === 0 ? (
              <p className="text-sm text-blue-800">No sales in the last 30 days.</p>
            ) : (
              <ul className="space-y-2">
                {data.sold_recently.map((row) => (
                  <li key={row.listing_id} className="rounded border border-blue-200 bg-white px-3 py-2 text-sm">
                    <p className="font-medium">{row.comic_title}</p>
                    <p className="text-blue-800">
                      Sale {money(row.sale_price)} · Net{" "}
                      {row.profit_known ? money(row.net_profit) : "Unknown"} ·{" "}
                      {row.sold_at ? new Date(row.sold_at).toLocaleDateString() : "—"}
                    </p>
                    <Link to={row.cta_route} className="text-red-700 underline">
                      View Sale
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </PatriotPanel>

          <PatriotPanel title="Profit summary" className="mt-4">
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-blue-600">Gross sales</dt>
                <dd className="font-medium">{money(data.profit_summary.gross_sales)}</dd>
              </div>
              <div>
                <dt className="text-blue-600">Fees</dt>
                <dd>{money(data.profit_summary.fees)}</dd>
              </div>
              <div>
                <dt className="text-blue-600">Shipping costs</dt>
                <dd>{money(data.profit_summary.shipping_costs)}</dd>
              </div>
              <div>
                <dt className="text-blue-600">Net profit</dt>
                <dd className="font-medium">{money(data.profit_summary.net_profit)}</dd>
              </div>
              <div>
                <dt className="text-blue-600">Avg profit / sale</dt>
                <dd>{money(data.profit_summary.average_profit_per_sale)}</dd>
              </div>
              <div>
                <dt className="text-blue-600">Sold count</dt>
                <dd>{data.profit_summary.sold_count}</dd>
              </div>
            </dl>
            <p className="mt-2 text-xs text-blue-700">{data.profit_summary.period_label}</p>
          </PatriotPanel>

          <PatriotPanel title="Expired or stale listings" className="mt-4">
            {data.expired_or_stale.length === 0 ? (
              <p className="text-sm text-blue-800">Nothing expired or stale.</p>
            ) : (
              <ul className="space-y-2">
                {data.expired_or_stale.map((row, idx) => (
                  <li key={`${row.status}-${row.listing_id ?? row.draft_id ?? idx}`} className="rounded border border-blue-200 bg-white px-3 py-2 text-sm">
                    <p className="font-medium">{row.comic_title}</p>
                    <p className="text-blue-800">
                      {row.status} {row.marketplace ? `· ${row.marketplace}` : ""} · {row.reason}
                    </p>
                    <Link to={row.cta_route} className="text-red-700 underline">
                      Review Listing
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </PatriotPanel>
        </>
      ) : null}
    </PatriotPageLayout>
  );
}
