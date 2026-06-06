import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P77AnalyticsDashboardRead } from "../api/client";
import { CollectorProfileNav } from "../components/collector/p77/CollectorProfileNav";
import { StatusBanner } from "../components/StatusBanner";

export function CollectorAnalyticsPage(): JSX.Element {
  const [dash, setDash] = useState<P77AnalyticsDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setDash(await apiClient.getCollectorAnalyticsDashboard());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load analytics.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!dash) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : <p className="text-slate-400">Loading…</p>}
      </div>
    );
  }

  const inf = dash.profile_influence;
  const budget = dash.budget;
  const impact = dash.recommendation_impact;
  const perf = dash.personalization_performance;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-4xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-sky-300">P77-03</p>
          <h1 className="text-xl font-semibold">Collector analytics</h1>
          <CollectorProfileNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

        <section className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
          <h2 className="text-sm font-semibold text-white">Profile summary</h2>
          <p className="mt-2 text-sm text-slate-300">
            {dash.profile_summary.collector_type} · {dash.profile_summary.risk_profile} ·{" "}
            {dash.profile_summary.time_horizon}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Publishers: {dash.profile_summary.preferred_publishers.join(", ") || "—"}
          </p>
        </section>

        <section className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
          <h2 className="text-sm font-semibold text-white">Profile influence</h2>
          <ul className="mt-3 grid grid-cols-2 gap-2 text-sm text-slate-300">
            <li>Publisher matches: {inf.publisher_match_pct}%</li>
            <li>Character matches: {inf.character_match_pct}%</li>
            <li>Creator matches: {inf.creator_match_pct}%</li>
            <li>Goal matches: {inf.goal_match_pct}%</li>
          </ul>
        </section>

        <section className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
          <h2 className="text-sm font-semibold text-white">Budget analytics</h2>
          <p className="mt-2 text-sm text-slate-300">
            ${budget.current_spend.toFixed(0)} / ${budget.monthly_budget.toFixed(0)} ({budget.utilization_percent}% ·{" "}
            {budget.budget_state})
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Forecast: ${budget.forecast.projected_month_end_spend.toFixed(0)} — {budget.forecast.status}
          </p>
          {budget.category_breakdown.length ? (
            <ul className="mt-3 space-y-1 text-sm text-slate-400">
              {budget.category_breakdown.slice(0, 6).map((c) => (
                <li key={c.name}>
                  {c.name}: ${c.spend.toFixed(0)}
                </li>
              ))}
            </ul>
          ) : null}
        </section>

        <section className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
          <h2 className="text-sm font-semibold text-white">Goal progress</h2>
          {dash.goals.goals.length === 0 ? (
            <p className="mt-2 text-sm text-slate-500">No goals yet.</p>
          ) : (
            <ul className="mt-3 space-y-2 text-sm">
              {dash.goals.goals.map((g) => (
                <li key={g.goal_id} className="text-slate-300">
                  {g.title}: {g.progress_value} / {g.target_value} ({g.completion_percent.toFixed(0)}%)
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-xs text-slate-500">
            Goal-influenced recommendations: {dash.goals.goal_influenced_recommendation_pct}%
          </p>
        </section>

        <section className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
          <h2 className="text-sm font-semibold text-white">Recommendation impact</h2>
          <p className="mt-2 text-sm text-slate-300">
            Evaluated {impact.recommendations_evaluated} · adjusted {impact.recommendations_adjusted} (
            {impact.adjustment_rate_pct}%)
          </p>
        </section>

        <section className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
          <h2 className="text-sm font-semibold text-white">Personalization performance</h2>
          <p className="mt-2 text-sm text-slate-300">
            Global ROI {perf.global_recommendation_roi_pct}% · Personalized {perf.personalized_recommendation_roi_pct}%
            (Δ {perf.roi_improvement_pct}%)
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Quantity adjustments: {perf.quantity_adjustment_count} · Budget compliance {perf.budget_compliance_pct}%
          </p>
        </section>

        <section className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
          <h2 className="text-sm font-semibold text-white">Collector assistant (sample)</h2>
          <p className="mt-2 text-sm text-slate-300">
            BUY {dash.collector_assistant.buy_count} · PASS {dash.collector_assistant.pass_count} · alignment{" "}
            {dash.collector_assistant.action_alignment_pct}%
          </p>
        </section>
      </main>
    </div>
  );
}
