import { useEffect, useState, type ReactNode } from "react";

import {
  ApiError,
  apiClient,
  type ForecastPlatformDashboardRead,
  type ForecastPlatformHealthComponentRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function statusTone(status: string): string {
  switch (status) {
    case "PASS":
    case "HEALTHY":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "WARNING":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "FAIL":
    case "FAILED":
      return "border-rose-400/30 bg-rose-400/10 text-rose-100";
    case "DISABLED":
      return "border-slate-500/30 bg-slate-500/10 text-slate-200";
    default:
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
  }
}

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

function StatusBadge({ value }: { value: string }): JSX.Element {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${statusTone(value)}`}>
      {value}
    </span>
  );
}

function HealthList({ rows }: { rows: ForecastPlatformHealthComponentRead[] }): JSX.Element {
  if (!rows.length) return <p className="text-sm text-slate-500">No health components are visible yet.</p>;
  return (
    <ul className="space-y-3">
      {rows.map((row) => (
        <li key={row.component_code} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-white">{row.title}</p>
            <StatusBadge value={row.health_status} />
          </div>
          <p className="mt-2 text-sm text-slate-400">{row.summary}</p>
        </li>
      ))}
    </ul>
  );
}

function SimpleList({ items }: { items: string[] }): JSX.Element {
  if (!items.length) return <p className="text-sm text-slate-500">No entries available yet.</p>;
  return (
    <ul className="space-y-2 text-sm text-slate-300">
      {items.map((item) => (
        <li key={item} className="rounded-2xl border border-white/10 bg-slate-950/40 p-3">
          {item}
        </li>
      ))}
    </ul>
  );
}

export function ForecastPlatformPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<ForecastPlatformDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getForecastPlatformDashboard();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load forecast platform.");
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

  return (
    <AppShell>
      <PageHeader
        eyebrow="Forecast Platform"
        title="Forecast Platform"
        description="Closeout, readiness, validation, health, and certification for the P47 decision-intelligence layer."
        actions={
          dashboard ? (
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge value={dashboard.validation.overall_status} />
              <StatusBadge value={dashboard.health.overall_status} />
              <StatusBadge value={dashboard.certification.platform_certified ? "CERTIFIED" : "NOT CERTIFIED"} />
            </div>
          ) : null
        }
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-400">Loading forecast platform…</p> : null}

      {!loading && dashboard ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <StatCard label="Market Score" value={dashboard.summary.market_score.toFixed(1)} />
            <StatCard label="Forecast Count" value={String(dashboard.summary.forecast_count)} />
            <StatCard label="Risk Count" value={String(dashboard.summary.risk_count)} />
            <StatCard label="Recommendation Count" value={String(dashboard.summary.recommendation_count)} />
            <StatCard label="Forecast Accuracy" value={`${Math.round(dashboard.summary.forecast_accuracy * 100)}%`} />
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Market Intelligence Status">
              <HealthList rows={dashboard.health.components.filter((row) => row.component_code === "market_intelligence_health")} />
            </Panel>
            <Panel title="Forecasting Status">
              <HealthList rows={dashboard.health.components.filter((row) => ["forecast_generation_health", "risk_assessment_health"].includes(row.component_code))} />
            </Panel>
            <Panel title="Dealer Copilot Status">
              <HealthList rows={dashboard.health.components.filter((row) => row.component_code === "dealer_copilot_health")} />
            </Panel>
            <Panel title="Validation/Learning Status">
              <HealthList rows={dashboard.health.components.filter((row) => ["validation_learning_health", "agent_execution_health"].includes(row.component_code))} />
            </Panel>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Top Opportunities">
              <SimpleList
                items={[
                  ...dashboard.summary.top_buy_recommendations.map((row) => `Buy: ${row.title}`),
                  ...dashboard.summary.top_sell_recommendations.map((row) => `Sell: ${row.title}`),
                  ...dashboard.summary.top_grade_candidates.map((row) => `Grade: ${row.title}`),
                ]}
              />
            </Panel>
            <Panel title="Top Risks">
              <SimpleList items={dashboard.summary.top_risks.map((row) => `${row.risk_type} (${Math.round(row.risk_score * 100) / 100})`)} />
            </Panel>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Certification Status">
              <div className="space-y-3">
                <StatusBadge value={dashboard.certification.platform_certified ? "CERTIFIED" : "NOT CERTIFIED"} />
                <p className="text-sm text-slate-300">{dashboard.certification.summary}</p>
                <SimpleList items={dashboard.certification.certification_notes} />
              </div>
            </Panel>
            <Panel title="Validation Checks">
              <SimpleList items={dashboard.validation.checks.map((row) => `${row.title}: ${row.status}`)} />
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
