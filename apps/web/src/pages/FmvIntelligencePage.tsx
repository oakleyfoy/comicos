import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P90FmvIntelligenceDashboardRead } from "../api/client";
import { CollectorEmptyState } from "../components/CollectorEmptyState";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

function money(value: number): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}

function SnapTable({ title, rows }: { title: string; rows: P90FmvIntelligenceDashboardRead["highest_value"] }): JSX.Element {
  return (
    <PatriotPanel title={title} className="mt-4">
      {rows.length === 0 ? (
        <p className="text-sm text-blue-800">No cached FMV V2 snapshots yet. Run the FMV V2 runner to populate data.</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((row) => (
            <li key={row.id} className="rounded border border-blue-200 bg-white px-3 py-2 text-sm">
              <p className="font-medium text-blue-950">
                {row.series} {row.issue_number ? `#${row.issue_number}` : ""}
              </p>
              <p className="text-blue-800">
                Market {money(row.market_value)} · Quick {money(row.quick_sale_value)} · Premium {money(row.premium_value)}
              </p>
              <p className="text-xs text-blue-600">
                {row.valuation_confidence} confidence · Trend {row.trend_direction} ({row.trend_score}) · {row.sales_velocity}
              </p>
            </li>
          ))}
        </ul>
      )}
    </PatriotPanel>
  );
}

export function FmvIntelligencePage(): JSX.Element {
  const [data, setData] = useState<P90FmvIntelligenceDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setData(await apiClient.getFmvIntelligence());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load FMV Intelligence.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const portfolio = data?.portfolio;

  return (
    <PatriotPageLayout
      eyebrow="Portfolio"
      title="FMV Intelligence"
      description="Market-driven valuations with confidence, trend, and velocity — from cached marketplace and pricing snapshots."
      error={error}
      onRetry={() => void load()}
      loading={loading && !data}
      maxWidthClass="max-w-5xl"
    >
      {data && portfolio ? (
        <>
          <PatriotPanel title="Portfolio FMV V2">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-blue-200 bg-blue-50/40 px-3 py-2">
                <p className="text-xs uppercase text-blue-600">Quick liquidation</p>
                <p className="text-xl font-semibold text-blue-950">{money(portfolio.quick_liquidation_total as number)}</p>
              </div>
              <div className="rounded-lg border border-blue-200 bg-blue-50/40 px-3 py-2">
                <p className="text-xs uppercase text-blue-600">Market portfolio</p>
                <p className="text-xl font-semibold text-blue-950">{money(portfolio.market_portfolio_value as number)}</p>
              </div>
              <div className="rounded-lg border border-blue-200 bg-blue-50/40 px-3 py-2">
                <p className="text-xs uppercase text-blue-600">Portfolio trend</p>
                <p className="text-xl font-semibold text-blue-950">{String(portfolio.portfolio_trend ?? "FLAT")}</p>
              </div>
            </div>
            <p className="mt-2 text-xs text-blue-700">
              High confidence copies: {portfolio.confidence_high as number} · Medium: {portfolio.confidence_medium as number} · Low:{" "}
              {portfolio.confidence_low as number}
            </p>
          </PatriotPanel>

          {!data.highest_value.length ? (
            <div className="mt-4">
              <CollectorEmptyState
                title="No FMV V2 snapshots"
                description="Generate snapshots with the FMV V2 runner; legacy FMV remains available until market data fills in."
              />
            </div>
          ) : null}

          <SnapTable title="Highest value books" rows={data.highest_value} />
          <SnapTable title="Largest movers" rows={data.largest_movers} />
          <SnapTable title="Strongest uptrends" rows={data.strongest_uptrends} />
          <SnapTable title="Strongest downtrends" rows={data.strongest_downtrends} />
          <SnapTable title="Highest confidence values" rows={data.highest_confidence} />
          <SnapTable title="Lowest confidence values" rows={data.lowest_confidence} />
        </>
      ) : null}
    </PatriotPageLayout>
  );
}
