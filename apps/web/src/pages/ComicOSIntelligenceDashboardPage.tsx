import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type AutoWatchlistBundleRead,
  type BuyQueueListRead,
  type CollectorAlertsRead,
  type CollectorBriefingRead,
  type CollectorDashboardRead,
  type CollectorHealthRead,
  type CollectorRecommendationsRead,
  type FOCAlertListRead,
  type MarketSignalListRead,
  type PortfolioPerformanceSnapshotRead,
  type PullForecastListRead,
  type SellSignalListRead,
  type AcquisitionListRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const LANE_ORDER = ["BUY", "HOLD", "SELL", "GRADE", "ACQUIRE", "WATCH"] as const;

function money(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }): JSX.Element {
  return (
    <section className="rounded-2xl border border-slate-700 bg-slate-900/80 p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">{title}</h2>
      {children}
    </section>
  );
}

function LaneList({
  lanes,
  lane,
  limit = 8,
}: {
  lanes: CollectorRecommendationsRead["lanes"];
  lane: (typeof LANE_ORDER)[number];
  limit?: number;
}): JSX.Element {
  const items = lanes[lane] ?? [];
  if (items.length === 0) {
    return <p className="text-sm text-slate-500">No {lane.toLowerCase()} recommendations in the latest run.</p>;
  }
  return (
    <ul className="space-y-2">
      {items.slice(0, limit).map((item) => (
        <li key={item.id} className="rounded-xl border border-white/5 bg-slate-950/60 px-3 py-2 text-sm text-white">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="font-medium">{item.title}</span>
            <span className="text-xs text-slate-400">
              score {item.priority_score.toFixed(1)} · {item.confidence}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            {item.publisher} #{item.issue_number} · {item.recommended_action}
          </p>
          {item.explanation ? <p className="mt-1 text-xs text-slate-300">{item.explanation}</p> : null}
        </li>
      ))}
    </ul>
  );
}

export function ComicOSIntelligenceDashboardPage(): JSX.Element {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [briefing, setBriefing] = useState<CollectorBriefingRead | null>(null);
  const [recommendations, setRecommendations] = useState<CollectorRecommendationsRead | null>(null);
  const [dashboard, setDashboard] = useState<CollectorDashboardRead | null>(null);
  const [health, setHealth] = useState<CollectorHealthRead | null>(null);
  const [alerts, setAlerts] = useState<CollectorAlertsRead | null>(null);
  const [buyQueue, setBuyQueue] = useState<BuyQueueListRead | null>(null);
  const [foc, setFoc] = useState<FOCAlertListRead | null>(null);
  const [pullForecast, setPullForecast] = useState<PullForecastListRead | null>(null);
  const [watchlists, setWatchlists] = useState<AutoWatchlistBundleRead | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioPerformanceSnapshotRead | null>(null);
  const [sellSignals, setSellSignals] = useState<SellSignalListRead | null>(null);
  const [acquisition, setAcquisition] = useState<AcquisitionListRead | null>(null);
  const [marketSignals, setMarketSignals] = useState<MarketSignalListRead | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        briefingRes,
        recsRes,
        dashRes,
        healthRes,
        alertsRes,
        buyRes,
        focRes,
        forecastRes,
        watchRes,
        portRes,
        sellRes,
        acqRes,
        sigRes,
      ] = await Promise.all([
        apiClient.getCollectorAssistantBriefingLatest(),
        apiClient.getCollectorAssistantRecommendationsLatest(),
        apiClient.getCollectorAssistantDashboardLatest(),
        apiClient.getCollectorAssistantHealthLatest(),
        apiClient.getCollectorAssistantAlertsLatest(),
        apiClient.getRecommendationIntelligenceBuyQueueLatest(),
        apiClient.getRecommendationIntelligenceFocLatest(),
        apiClient.getRecommendationIntelligencePullForecastLatest(),
        apiClient.getRecommendationIntelligenceWatchlistsLatest(),
        apiClient.getMarketIntelligencePortfolioLatest(),
        apiClient.getMarketIntelligenceSellSignalsLatest(),
        apiClient.getMarketIntelligenceAcquisitionLatest(),
        apiClient.getMarketIntelligenceSignalsLatest(),
      ]);
      setBriefing(briefingRes);
      setRecommendations(recsRes);
      setDashboard(dashRes);
      setHealth(healthRes);
      setAlerts(alertsRes);
      setBuyQueue(buyRes);
      setFoc(focRes);
      setPullForecast(forecastRes);
      setWatchlists(watchRes);
      setPortfolio(portRes);
      setSellSignals(sellRes);
      setAcquisition(acqRes);
      setMarketSignals(sigRes);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load intelligence dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const lanes = recommendations?.lanes ?? {};

  return (
    <AppShell>
      <PageHeader
        eyebrow="P50–P64"
        title="ComicOS Intelligence"
        description="Read-only view of collector assistant lanes, P63 market intelligence, and P62 buy queue / FOC / watchlists."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-400">Loading intelligence…</p> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title="Collector briefing">
          {briefing ? (
            <>
              <p className="text-lg font-semibold text-white">{briefing.headline || "—"}</p>
              <p className="mt-1 text-xs text-slate-400">Status: {briefing.readiness_status}</p>
              {briefing.briefing_markdown ? (
                <pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap text-xs text-slate-300">
                  {briefing.briefing_markdown}
                </pre>
              ) : null}
            </>
          ) : null}
        </SectionCard>

        <SectionCard title="Portfolio health">
          {health ? (
            <div className="grid gap-2 sm:grid-cols-2">
              <div>
                <p className="text-xs text-slate-500">Health score</p>
                <p className="text-xl font-semibold text-white">{health.health_score.toFixed(0)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Band</p>
                <p className="text-xl font-semibold text-white">{health.health_band}</p>
              </div>
            </div>
          ) : null}
          {dashboard?.platform_ready ? (
            <p className="mt-2 text-xs text-emerald-400">Executive dashboard ready</p>
          ) : (
            <p className="mt-2 text-xs text-amber-400">Executive dashboard not ready — run platform build in ops.</p>
          )}
        </SectionCard>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {LANE_ORDER.map((lane) => (
          <SectionCard key={lane} title={`${lane} recommendations`}>
            <LaneList lanes={lanes} lane={lane} />
          </SectionCard>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <SectionCard title="P63 portfolio snapshot">
          {portfolio ? (
            <div className="grid gap-2 text-sm text-white sm:grid-cols-2">
              <p>Items: {portfolio.total_items}</p>
              <p>Cost basis: {money(portfolio.total_cost_basis)}</p>
              <p>Current value: {money(portfolio.total_current_value)}</p>
              <p>Unrealized: {money(portfolio.total_unrealized_gain)} ({portfolio.total_unrealized_gain_pct.toFixed(1)}%)</p>
            </div>
          ) : null}
        </SectionCard>

        <SectionCard title="Opportunity alerts">
          {alerts && alerts.alerts.length > 0 ? (
            <ul className="space-y-2 text-sm">
              {alerts.alerts.slice(0, 6).map((a) => (
                <li key={a.id} className="rounded-lg border border-white/5 px-2 py-1 text-white">
                  <span className="text-xs uppercase text-amber-400">{a.severity}</span> {a.title}
                  <p className="text-xs text-slate-400">{a.message}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">No critical alerts.</p>
          )}
        </SectionCard>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <SectionCard title="P63 market signals">
          {marketSignals ? (
            <p className="text-sm text-white">
              {marketSignals.total_items} signals
              {marketSignals.items.length > 0
                ? ` · top: ${marketSignals.items[0].title} (${marketSignals.items[0].signal_type}, score ${marketSignals.items[0].market_score})`
                : ""}
            </p>
          ) : null}
        </SectionCard>

        <SectionCard title="P63 sell / acquire">
          {sellSignals ? <p className="text-sm text-white">Sell signals: {sellSignals.total_items}</p> : null}
          {acquisition ? <p className="mt-1 text-sm text-white">Acquisition opportunities: {acquisition.total_items}</p> : null}
        </SectionCard>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <SectionCard title="P62 buy queue">
          {buyQueue ? (
            <p className="text-sm text-white">
              {buyQueue.total_items} items
              {buyQueue.snapshot ? ` · snapshot ${buyQueue.snapshot.snapshot_date}` : ""}
            </p>
          ) : null}
          {buyQueue?.items.slice(0, 5).map((item) => (
            <p key={item.id} className="mt-1 text-xs text-slate-300">
              {item.title} · qty {item.quantity_recommended}
            </p>
          ))}
        </SectionCard>

        <SectionCard title="FOC alerts">
          {foc ? <p className="text-sm text-white">{foc.total_items} FOC alerts</p> : null}
        </SectionCard>

        <SectionCard title="Pull forecast & watchlists">
          {pullForecast ? <p className="text-sm text-white">Forecast items: {pullForecast.total_items}</p> : null}
          {watchlists ? (
            <p className="mt-1 text-sm text-white">
              Auto watchlists: {watchlists.watchlists.length}
              {watchlists.watchlists[0] ? ` · ${watchlists.watchlists[0].item_count} items in ${watchlists.watchlists[0].watchlist_type}` : ""}
            </p>
          ) : null}
        </SectionCard>
      </div>
    </AppShell>
  );
}
