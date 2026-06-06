import { useEffect, useState, type ReactNode } from "react";

import {
  ApiError,
  apiClient,
  type DealerCopilotDashboardRead,
  type DealerOpportunityScoreRead,
  type DealerRecommendationRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function statusTone(status: string): string {
  switch (status) {
    case "OPEN":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "REVIEWED":
    case "ACCEPTED":
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
    case "DISMISSED":
      return "border-rose-400/30 bg-rose-400/10 text-rose-100";
    default:
      return "border-white/10 bg-white/5 text-slate-200";
  }
}

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function RecommendationList({ rows }: { rows: DealerRecommendationRead[] }): JSX.Element {
  if (!rows.length) return <p className="text-sm text-slate-500">No recommendations available yet.</p>;
  return (
    <ul className="space-y-3">
      {rows.map((row) => (
        <li key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-white">{row.title}</p>
            <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${statusTone(row.recommendation_status)}`}>
              {row.recommendation_status}
            </span>
          </div>
          <p className="mt-2 text-sm text-slate-400">{row.description}</p>
          <p className="mt-2 text-xs text-slate-500">
            Priority {Math.round(row.priority_score * 100)} | Confidence {Math.round(row.confidence_score * 100)}
          </p>
        </li>
      ))}
    </ul>
  );
}

function OpportunityTable({ rows }: { rows: DealerOpportunityScoreRead[] }): JSX.Element {
  if (!rows.length) return <p className="text-sm text-slate-500">No opportunity scores are available yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-white/10 text-sm">
        <thead className="text-left text-xs uppercase tracking-[0.14em] text-slate-500">
          <tr>
            <th className="pb-3 pr-4">Asset</th>
            <th className="pb-3 pr-4">Opportunity</th>
            <th className="pb-3 pr-4">Risk</th>
            <th className="pb-3 pr-4">Forecast</th>
            <th className="pb-3 pr-4">Demand</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5 text-slate-200">
          {rows.map((row) => (
            <tr key={row.id}>
              <td className="py-3 pr-4">{row.asset_type} #{row.asset_id}</td>
              <td className="py-3 pr-4">{Math.round(row.opportunity_score * 100)}</td>
              <td className="py-3 pr-4">{Math.round(row.risk_score * 100)}</td>
              <td className="py-3 pr-4">{Math.round(row.forecast_score * 100)}</td>
              <td className="py-3 pr-4">{Math.round(row.demand_score * 100)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DealerCopilotPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<DealerCopilotDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadDashboard(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const body = await apiClient.getDealerCopilotDashboard();
      setDashboard(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load dealer copilot.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  async function handleRun(): Promise<void> {
    try {
      await apiClient.runDealerCopilot();
      await loadDashboard();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to run dealer copilot.");
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Dealer Copilot"
        title="Dealer Copilot"
        description="Advisory buy, sell, hold, grade, and watchlist recommendations backed by market intelligence."
        actions={
          <button
            type="button"
            onClick={() => void handleRun()}
            className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-100"
          >
            Run Copilot
          </button>
        }
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading dealer copilot…</p> : null}

      {!loading && dashboard ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Recommendations" value={String(dashboard.summary.total_recommendations)} />
            <StatCard label="Open Reviews" value={String(dashboard.summary.open_recommendations)} />
            <StatCard label="Opportunities" value={String(dashboard.opportunities.length)} />
            <StatCard label="Agent Activity" value={String(dashboard.executions.length)} />
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Top Buy Opportunities">
              <RecommendationList rows={dashboard.top_buys} />
            </Panel>
            <Panel title="Top Sell Opportunities">
              <RecommendationList rows={dashboard.top_sells} />
            </Panel>
            <Panel title="Top Hold Candidates">
              <RecommendationList rows={dashboard.top_holds} />
            </Panel>
            <Panel title="Top Grade Candidates">
              <RecommendationList rows={dashboard.top_grades} />
            </Panel>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Top Watchlist Items">
              <RecommendationList rows={dashboard.top_watchlist} />
            </Panel>
            <Panel title="Opportunity Scores">
              <OpportunityTable rows={dashboard.opportunities} />
            </Panel>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Recommendation Reviews">
              <RecommendationList rows={[...dashboard.top_buys, ...dashboard.top_sells, ...dashboard.top_holds].slice(0, 5)} />
            </Panel>
            <Panel title="Agent Activity">
              {dashboard.executions.length ? (
                <ul className="space-y-3">
                  {dashboard.executions.map((row) => (
                    <li key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-medium text-white">{row.agent_code}</p>
                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${statusTone(row.status)}`}>
                          {row.status}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-slate-500">Duration {row.duration_ms ?? 0} ms</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No agent activity yet.</p>
              )}
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
