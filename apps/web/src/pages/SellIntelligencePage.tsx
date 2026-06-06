import { useCallback, useEffect, useState } from "react";

import {
  p71Api,
  type P71Dashboard,
  type P71ExitItem,
  type P71LiquidityItem,
  type P71ListingItem,
  type P71QueueItem,
} from "../api/p71SellIntelligence";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
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

export function SellIntelligencePage(): JSX.Element {
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSnapshots, setHasSnapshots] = useState(false);
  const [exits, setExits] = useState<P71ExitItem[]>([]);
  const [queue, setQueue] = useState<P71QueueItem[]>([]);
  const [listings, setListings] = useState<P71ListingItem[]>([]);
  const [liquidity, setLiquidity] = useState<P71LiquidityItem[]>([]);
  const [dashboard, setDashboard] = useState<P71Dashboard | null>(null);

  const loadSnapshots = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [e, q, l, liq, dash] = await Promise.all([
        p71Api.exitRecommendations(),
        p71Api.exitQueue(),
        p71Api.listingIntelligence(),
        p71Api.liquidity(),
        p71Api.dashboard(),
      ]);
      const anySnapshot = Boolean(e ?? q ?? l ?? liq ?? dash);
      setHasSnapshots(anySnapshot);
      setExits(e?.items ?? []);
      setQueue(q?.items ?? []);
      setListings(l?.items ?? []);
      setLiquidity(liq?.items ?? []);
      setDashboard(dash);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sell intelligence");
    } finally {
      setLoading(false);
    }
  }, []);

  const rebuildSnapshots = useCallback(async () => {
    setBuilding(true);
    setError(null);
    try {
      await p71Api.buildPlatform();
      await loadSnapshots();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to build sell intelligence snapshots");
    } finally {
      setBuilding(false);
    }
  }, [loadSnapshots]);

  useEffect(() => {
    void loadSnapshots();
  }, [loadSnapshots]);

  const cards = dashboard?.cards_json ?? {};

  return (
    <AppShell>
      <PageHeader
        eyebrow="P71"
        title="Sell Intelligence"
        description="Exit recommendations from P61–P69 intelligence — advisory only, no auto-listing."
        actions={
          <button
            type="button"
            disabled={building || loading}
            className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm text-white disabled:opacity-60"
            onClick={() => void rebuildSnapshots()}
          >
            {building ? "Building snapshots…" : "Build snapshots"}
          </button>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-slate-400">Loading sell intelligence…</p> : null}

      {!loading && !hasSnapshots ? (
        <div className="mt-6">
          <EmptyState
            title="No sell intelligence snapshots yet"
            description="Run a one-time snapshot build to score exits, listing guidance, liquidity, and the investor dashboard. Page loads read existing snapshots only."
            action={
              <button
                type="button"
                disabled={building}
                className="rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white"
                onClick={() => void rebuildSnapshots()}
              >
                {building ? "Building…" : "Build snapshots"}
              </button>
            }
          />
        </div>
      ) : null}

      {!loading && dashboard ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <Section title="Investor Sell Dashboard">
            <p className="text-sm text-white">
              Expected realized profit (queue): <strong>{money(dashboard.expected_realized_profit)}</strong>
            </p>
            <p className="mt-2 text-xs text-slate-400">
              Queue: {String((cards.exit_queue_summary as { queued?: number })?.queued ?? 0)} items
            </p>
          </Section>

          <Section title="Exit Recommendations">
            {exits.length ? (
              <ul className="space-y-2 text-sm text-white">
                {exits.slice(0, 8).map((row) => (
                  <li key={`${row.title}-${row.recommendation}`} className="rounded-lg border border-white/5 bg-slate-950/50 p-2">
                    <div className="font-medium">{row.title}</div>
                    <div className="text-xs text-slate-400">
                      {row.recommendation} · score {row.exit_score.toFixed(0)} · conf {(row.exit_confidence * 100).toFixed(0)}%
                    </div>
                    <div className="text-xs text-slate-500">{row.primary_reason}</div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-500">No holdings to score.</p>
            )}
          </Section>

          <Section title="Exit Queue">
            {queue.length ? (
              <ol className="list-decimal space-y-1 pl-4 text-sm text-white">
                {queue.slice(0, 10).map((row) => (
                  <li key={`${row.priority}-${row.title}`}>
                    {row.title} — {row.recommended_action} · {money(row.expected_profit)} @ {money(row.target_price)} · ~
                    {row.expected_days.toFixed(0)}d
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-slate-500">No prioritized exits (hold-heavy portfolio).</p>
            )}
          </Section>

          <Section title="Listing Intelligence">
            {listings.length ? (
              <ul className="space-y-1 text-sm text-white">
                {listings.slice(0, 6).map((row) => (
                  <li key={row.title}>
                    {row.title} — {row.listing_recommendation} BIN {money(row.suggested_bin)} · profit {money(row.expected_profit)} · ~
                    {row.expected_days_to_sell.toFixed(0)}d
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-500">No FMV-backed listing guidance.</p>
            )}
          </Section>

          <Section title="Liquidity Analysis">
            {liquidity.length ? (
              <ul className="space-y-1 text-sm text-white">
                {liquidity.slice(0, 8).map((row) => (
                  <li key={row.title}>
                    {row.title} — {row.liquidity_band} ({row.liquidity_score.toFixed(0)}) · ~{row.days_to_sell_estimate.toFixed(0)} days
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-500">No liquidity rows in the latest snapshot.</p>
            )}
          </Section>
        </div>
      ) : null}
    </AppShell>
  );
}
