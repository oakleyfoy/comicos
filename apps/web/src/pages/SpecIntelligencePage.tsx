import { useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type SpecDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { VariantList } from "../components/VariantList";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function SpecIntelligencePage(): JSX.Element {
  const [dashboard, setDashboard] = useState<SpecDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getSpecIntelligenceDashboard();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load spec intelligence dashboard.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const latestBuyList = dashboard?.weekly_buy_lists[0] ?? null;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Spec advisory"
        title="Spec Intelligence"
        description="Spec scoring, personalized recommendations, and weekly buy lists for upcoming releases — advisory only (P50-03)."
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-400">Loading spec intelligence…</p> : null}

      {dashboard ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Must Buy" value={String(latestBuyList?.items.filter((row) => row.buy_category === "Must Buy").length ?? 0)} />
            <StatCard label="Strong Buy" value={String(latestBuyList?.items.filter((row) => row.buy_category === "Strong Buy").length ?? 0)} />
            <StatCard label="Watch" value={String(latestBuyList?.items.filter((row) => row.buy_category === "Watch").length ?? 0)} />
            <StatCard label="Pass" value={String(latestBuyList?.items.filter((row) => row.buy_category === "Pass").length ?? 0)} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Variant Count" value={String(dashboard.variant_count)} />
            <StatCard label="Ratio Variants" value={String(dashboard.ratio_variant_count)} />
            <StatCard label="Top Ratio Variants" value={String(dashboard.top_ratio_variants.length)} />
            <StatCard label="Upcoming Incentives" value={String(dashboard.upcoming_incentive_variants.length)} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Weekly Buy List">
              {!latestBuyList?.items.length ? (
                <p className="text-sm text-slate-500">No weekly buy list generated yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {latestBuyList.items.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span>{row.buy_category}</span>
                      <span className="text-slate-400">{row.ranking_score.toFixed(1)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Top Spec Opportunities">
              {!dashboard.top_spec_opportunities.length ? (
                <p className="text-sm text-slate-500">No opportunities yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.top_spec_opportunities.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span>{row.recommendation_type}</span>
                      <span className="text-slate-400">{row.recommendation_score.toFixed(1)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Variant Opportunities">
              {!dashboard.variant_opportunities.length ? (
                <p className="text-sm text-slate-500">No variant-driven opportunities.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.variant_opportunities.map((row) => (
                    <li key={row.id}>{row.recommendation_type}</li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Top Variant Opportunities">
              <VariantList items={dashboard.top_ratio_variants} />
            </Panel>

            <Panel title="Upcoming Incentive Variants">
              <VariantList items={dashboard.upcoming_incentive_variants} />
            </Panel>

            <Panel title="New #1 Opportunities">
              {!dashboard.new_number_one_opportunities.length ? (
                <p className="text-sm text-slate-500">No #1 opportunities.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.new_number_one_opportunities.map((row) => (
                    <li key={row.id}>{row.recommendation_type}</li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Key Issue Opportunities">
              {!dashboard.key_issue_opportunities.length ? (
                <p className="text-sm text-slate-500">No key issue opportunities.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.key_issue_opportunities.map((row) => (
                    <li key={row.id}>{row.recommendation_type}</li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Recommendation Reviews">
              {!dashboard.recommendation_reviews.length ? (
                <p className="text-sm text-slate-500">No reviews recorded yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.recommendation_reviews.map((row) => (
                    <li key={row.id}>
                      {row.review_status}
                      {row.review_notes ? ` - ${row.review_notes}` : ""}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Agent Activity">
              {!dashboard.agent_activity.length ? (
                <p className="text-sm text-slate-500">No spec agent runs recorded.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.agent_activity.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span>{row.agent_code}</span>
                      <span className="text-slate-400">{row.status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
