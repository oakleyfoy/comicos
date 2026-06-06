import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type WeeklySpecDashboardItemRead,
  type WeeklySpecDashboardRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function SectionBlock({
  title,
  rows,
  empty,
}: {
  title: string;
  rows: WeeklySpecDashboardItemRead[];
  empty: string;
}): JSX.Element {
  return (
    <section className="mt-8">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">{title}</h2>
      {rows.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">{empty}</p>
      ) : (
        <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-800 text-xs uppercase text-slate-200">
              <tr>
                <th className="px-3 py-2">Rank</th>
                <th className="px-3 py-2">Final</th>
                <th className="px-3 py-2">Conf.</th>
                <th className="px-3 py-2">Risk</th>
                <th className="px-3 py-2">FOC</th>
                <th className="px-3 py-2">Comic</th>
                <th className="px-3 py-2">Signals</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${title}-${row.id}`} className="border-b border-slate-100">
                  <td className="px-3 py-2 text-white">#{row.rank}</td>
                  <td className="px-3 py-2 text-cyan-200">{row.final_score.toFixed(1)}</td>
                  <td className="px-3 py-2 text-slate-300">{row.confidence_score.toFixed(3)}</td>
                  <td className="px-3 py-2 text-slate-400">{row.risk_level}</td>
                  <td className="px-3 py-2 text-xs text-amber-800/90">{row.foc_urgency_label}</td>
                  <td className="px-3 py-2 text-white">{row.title || row.publisher}</td>
                  <td className="px-3 py-2 text-xs text-slate-500">{row.signal_types.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function WeeklySpecDashboardPage(): JSX.Element {
  const [dash, setDash] = useState<WeeklySpecDashboardRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await apiClient.getWeeklySpecDashboard();
      setDash(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load weekly spec dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const summary = dash?.summary;

  const sections: { title: string; rows: WeeklySpecDashboardItemRead[]; empty: string }[] = dash
    ? [
        { title: "Top 20 Preorder", rows: dash.top_20_preorder, empty: "Generate Top 20 spec picks to populate this section." },
        { title: "Preorder Now", rows: dash.preorder_now, empty: "No preorder-now timing signals in the current Top 20." },
        { title: "High Confidence", rows: dash.high_confidence, empty: "No high-confidence picks in the current Top 20." },
        {
          title: "High Risk / High Reward",
          rows: dash.high_risk_high_reward,
          empty: "No high-risk high-reward picks in the current Top 20.",
        },
        { title: "#1 Issues", rows: dash.number_one_issues, empty: "No #1 issue picks in the current Top 20." },
        { title: "Ratio Variants", rows: dash.ratio_variants, empty: "No ratio variant picks in the current Top 20." },
        { title: "First Appearances", rows: dash.first_appearances, empty: "No first appearance picks in the current Top 20." },
        { title: "Milestones", rows: dash.milestones, empty: "No milestone picks in the current Top 20." },
      ]
    : [];

  return (
    <AppShell>
      <PageHeader
        eyebrow="P60-05"
        title="Weekly Spec Dashboard"
        description="Top 20 preorder shortlist with FOC urgency, confidence, risk, publisher and signal breakdowns — presentation only (no new scoring)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

      {loading ? (
        <p className="mt-8 text-slate-400">Loading weekly spec dashboard…</p>
      ) : summary && dash ? (
        <>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { label: "Top picks", value: summary.top_picks_count },
              { label: "Preorder now", value: summary.preorder_now_count },
              { label: "Avg confidence", value: summary.average_confidence.toFixed(3) },
              { label: "High risk", value: summary.high_risk_count },
              { label: "#1 issues", value: summary.number_one_issues_count },
              { label: "Ratio variants", value: summary.ratio_variant_count },
              { label: "First appearances", value: summary.first_appearance_count },
              { label: "FOC approaching", value: summary.foc_approaching_count },
            ].map((card) => (
              <div key={card.label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs uppercase tracking-wide text-slate-500">{card.label}</p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">{card.value}</p>
              </div>
            ))}
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">Publisher breakdown</h2>
              {Object.keys(dash.publisher_breakdown).length === 0 ? (
                <p className="mt-2 text-sm text-slate-500">No publisher data yet.</p>
              ) : (
                <ul className="mt-3 space-y-1 text-sm text-slate-300">
                  {Object.entries(dash.publisher_breakdown).map(([publisher, count]) => (
                    <li key={publisher} className="flex justify-between gap-4">
                      <span>{publisher}</span>
                      <span className="font-medium text-teal-800">{count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">Signal breakdown</h2>
              {Object.keys(dash.signal_breakdown).length === 0 ? (
                <p className="mt-2 text-sm text-slate-500">No signals tagged on current picks.</p>
              ) : (
                <ul className="mt-3 space-y-1 text-sm text-slate-300">
                  {Object.entries(dash.signal_breakdown).map(([signal, count]) => (
                    <li key={signal} className="flex justify-between gap-4">
                      <span>{signal}</span>
                      <span className="font-medium text-teal-800">{count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {sections.map((section) => (
            <SectionBlock key={section.title} title={section.title} rows={section.rows} empty={section.empty} />
          ))}
        </>
      ) : (
        <p className="mt-8 text-sm text-slate-500">No weekly spec dashboard data yet.</p>
      )}
    </AppShell>
  );
}
