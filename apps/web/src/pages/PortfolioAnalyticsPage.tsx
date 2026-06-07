import { useCallback, useEffect, useState } from "react";

import { apiClient, type P89ManagedListingPortfolioSummaryRead, type P89MarketPricingPortfolioTotalsRead } from "../api/client";
import {
  p67Api,
  p68Api,
  type P68SnapshotRow,
  type P67CollectionLatest,
  type P67GradingLatest,
  type P67InvestorLatest,
  type P67PortfolioLatest,
  type P67RecommendationLatest,
} from "../api/p67PortfolioAnalytics";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function money(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function Section({ title, children }: { title: string; children: React.ReactNode }): JSX.Element {
  return (
    <section className="rounded-2xl border border-slate-700 bg-slate-900/80 p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">{title}</h2>
      {children}
    </section>
  );
}

export function PortfolioAnalyticsPage(): JSX.Element {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [buildError, setBuildError] = useState<string | null>(null);
  const [building, setBuilding] = useState(false);
  const [portfolio, setPortfolio] = useState<P67PortfolioLatest | null>(null);
  const [collection, setCollection] = useState<P67CollectionLatest | null>(null);
  const [recommendation, setRecommendation] = useState<P67RecommendationLatest | null>(null);
  const [grading, setGrading] = useState<P67GradingLatest | null>(null);
  const [investor, setInvestor] = useState<P67InvestorLatest | null>(null);
  const [pricing, setPricing] = useState<P68SnapshotRow[]>([]);
  const [marketPricingTotals, setMarketPricingTotals] = useState<P89MarketPricingPortfolioTotalsRead | null>(null);
  const [listingSales, setListingSales] = useState<P89ManagedListingPortfolioSummaryRead | null>(null);

  const loadLatest = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, c, r, g, i, pr, mkt, salesSummary] = await Promise.all([
        p67Api.portfolioLatest(),
        p67Api.collectionLatest(),
        p67Api.recommendationLatest(),
        p67Api.gradingLatest(),
        p67Api.investorLatest(),
        p68Api.latestSnapshots(),
        apiClient.getMarketPricingPortfolioTotals().catch(() => null),
        apiClient.getManagedListingPortfolioSummary().catch(() => null),
      ]);
      setPortfolio(p);
      setCollection(c);
      setRecommendation(r);
      setGrading(g);
      setInvestor(i);
      setPricing(pr.items ?? []);
      setMarketPricingTotals(mkt);
      setListingSales(salesSummary);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load portfolio analytics");
    } finally {
      setLoading(false);
    }
  }, []);

  const runRefreshBuild = useCallback(async () => {
    setBuilding(true);
    setBuildError(null);
    const errors: string[] = [];
    const [p68, p67] = await Promise.all([p68Api.buildSnapshots(), p67Api.buildPlatform()]);
    if (!p68.ok) {
      errors.push(p68.error ? `Market pricing: ${p68.error}` : "Market pricing build failed.");
    }
    if (!p67.ok) {
      errors.push(p67.error ? `Platform: ${p67.error}` : "Platform analytics build failed.");
    }
    if (errors.length) {
      setBuildError(errors.join(" "));
    }
    await loadLatest();
    setBuilding(false);
  }, [loadLatest]);

  useEffect(() => {
    void loadLatest();
  }, [loadLatest]);

  const snap = portfolio?.snapshot;
  const hasInvestorData = investor && investor.status !== "EMPTY";

  return (
    <AppShell>
      <PageHeader
        eyebrow="P67"
        title="Portfolio Analytics"
        description="Investment view — cached snapshots only on load; use Refresh build to recompute."
        actions={
          <button
            type="button"
            className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            disabled={building || loading}
            onClick={() => void runRefreshBuild()}
          >
            {building ? "Building…" : "Refresh build"}
          </button>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {buildError ? <StatusBanner tone="error">{buildError}</StatusBanner> : null}
      {loading ? <p className="text-slate-400">Loading cached analytics…</p> : null}

      {!loading ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <Section title="Realized sales (P89)">
            {listingSales ? (
              <dl className="grid grid-cols-1 gap-3 text-sm text-white sm:grid-cols-2">
                <div>
                  <dt className="text-slate-400">Realized sales</dt>
                  <dd className="text-lg font-semibold">{money(listingSales.realized_sales_total)}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Total net profit</dt>
                  <dd className="text-lg font-semibold">{money(listingSales.total_net_profit)}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Active listing value</dt>
                  <dd>{money(listingSales.active_listing_value)}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Sold this month</dt>
                  <dd>
                    {listingSales.sold_this_month_count} · {money(listingSales.sold_this_month_net_profit)} profit
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="text-sm text-slate-400">No managed listing sales yet.</p>
            )}
          </Section>

          <Section title="Market pricing (P89)">
            {marketPricingTotals ? (
              <dl className="grid grid-cols-1 gap-3 text-sm text-white sm:grid-cols-3">
                <div>
                  <dt className="text-slate-400">Quick liquidation total</dt>
                  <dd className="text-lg font-semibold">{money(marketPricingTotals.quick_liquidation_total)}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Market value total</dt>
                  <dd className="text-lg font-semibold">{money(marketPricingTotals.market_value_total)}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Premium value total</dt>
                  <dd className="text-lg font-semibold">{money(marketPricingTotals.premium_value_total)}</dd>
                </div>
              </dl>
            ) : (
              <p className="text-sm text-slate-400">No cached market pricing totals yet.</p>
            )}
          </Section>

          <Section title="Investor Dashboard">
            {hasInvestorData ? (
              <dl className="grid grid-cols-2 gap-3 text-sm text-white">
                <div>
                  <dt className="text-slate-400">Collection value</dt>
                  <dd className="text-lg font-semibold">{money(investor.collection_value)}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Cost basis</dt>
                  <dd>{money(investor.cost_basis)}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Unrealized gain</dt>
                  <dd>{money(investor.unrealized_gain)}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Portfolio health</dt>
                  <dd>{investor.portfolio_health_score.toFixed(1)}</dd>
                </div>
              </dl>
            ) : (
              <p className="text-sm text-slate-500">{investor?.message ?? "No investor dashboard snapshot yet."}</p>
            )}
          </Section>

          <Section title="Portfolio Performance">
            {snap ? (
              <dl className="grid grid-cols-2 gap-2 text-sm text-white">
                <div>
                  <dt className="text-slate-400">Avg ROI</dt>
                  <dd>{snap.average_roi_pct.toFixed(1)}%</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Unrealized %</dt>
                  <dd>{snap.total_unrealized_gain_pct.toFixed(1)}%</dd>
                </div>
                <div className="col-span-2">
                  <dt className="text-slate-400">Best / worst</dt>
                  <dd className="text-xs">
                    {snap.best_performer_title || "—"} / {snap.worst_performer_title || "—"}
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="text-slate-500">No portfolio snapshot.</p>
            )}
          </Section>

          <Section title="Collection Analytics">
            {collection && collection.status !== "EMPTY" ? (
              <p className="text-sm text-white">
                {collection.total_holdings} holdings · concentration {collection.concentration_score.toFixed(1)} ·
                diversification {String(collection.metadata_json.diversification_score ?? "—")}
              </p>
            ) : (
              <p className="text-sm text-slate-500">{collection?.message ?? "No collection analytics snapshot yet."}</p>
            )}
          </Section>

          <Section title="Recommendation Performance">
            {recommendation?.snapshot ? (
              <p className="text-sm text-white">
                Hit rate {recommendation.snapshot.hit_rate_pct}% · avg return {recommendation.snapshot.average_return_pct}%
                · confidence accuracy {recommendation.snapshot.confidence_accuracy_pct}%
              </p>
            ) : (
              <p className="text-slate-500">No recommendation scorecard yet.</p>
            )}
          </Section>

          <Section title="Market Pricing (P68)">
            {pricing.length ? (
              <ul className="space-y-2 text-sm text-white">
                {pricing.slice(0, 8).map((row) => (
                  <li key={`${row.title}-${row.primary_provider}`} className="rounded-lg border border-white/5 bg-slate-950/50 p-2">
                    <div className="font-medium">{row.title}</div>
                    <div className="text-xs text-slate-400">
                      Computed FMV {money(row.blended_fmv)} · conf {(row.confidence * 100).toFixed(0)}% · sales {row.sales_count}{" "}
                      · {row.primary_provider || "—"}
                      {row.primary_provider === "STUB" || row.metadata_json?.label_stub ? " (stub/manual — not live market)" : ""}
                    </div>
                    <div className="text-xs text-slate-500">
                      Low {money(row.low_sale)} / Median {money(row.median_sale)} / High {money(row.high_sale)} · liquidity{" "}
                      {row.liquidity_score.toFixed(0)} · trend {row.price_trend_30d}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">No computed FMV snapshots yet. Use Refresh build to generate P68 pricing.</p>
            )}
          </Section>

          <Section title="Grading Opportunities">
            {grading?.items?.length ? (
              <ul className="space-y-1 text-sm text-white">
                {grading.items.slice(0, 6).map((row) => (
                  <li key={`${row.title}-${row.submission_priority}`}>
                    #{row.submission_priority} {row.title} — est. ROI {row.estimated_roi_pct.toFixed(1)}%
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-500">No grading candidates.</p>
            )}
          </Section>
        </div>
      ) : null}
    </AppShell>
  );
}
