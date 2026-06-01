import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type IndustryScannerDashboardItemRead,
  type IndustryScannerDashboardRead,
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
  rows: IndustryScannerDashboardItemRead[];
  empty: string;
}): JSX.Element {
  return (
    <section className="mt-8">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">{title}</h2>
      {rows.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">{empty}</p>
      ) : (
        <div className="mt-3 overflow-x-auto rounded-xl border border-white/10">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-white/10 bg-slate-900/80 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2">Score</th>
                <th className="px-3 py-2">Publisher</th>
                <th className="px-3 py-2">Series</th>
                <th className="px-3 py-2">Issue</th>
                <th className="px-3 py-2">Signals</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${title}-${row.id}`} className="border-b border-white/5">
                  <td className="px-3 py-2 text-cyan-200">{row.opportunity_score.toFixed(1)}</td>
                  <td className="px-3 py-2 text-slate-300">{row.publisher_name}</td>
                  <td className="px-3 py-2 text-white">{row.series_name}</td>
                  <td className="px-3 py-2 text-slate-400">#{row.issue_number}</td>
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

export function IndustryScannerDashboardPage(): JSX.Element {
  const [dash, setDash] = useState<IndustryScannerDashboardRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await apiClient.getIndustryScannerDashboard(false);
      setDash(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load industry scanner dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  async function onRefreshScores() {
    setRefreshing(true);
    setError(null);
    try {
      const body = await apiClient.getIndustryScannerDashboard(true);
      setDash(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to refresh industry scanner dashboard.");
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void load();
  }, [load]);

  const summary = dash?.summary;

  const sections: { title: string; rows: IndustryScannerDashboardItemRead[]; empty: string }[] = dash
    ? [
        { title: "Top #1 Issues", rows: dash.top_number_one_issues, empty: "No #1 issues in the latest scan." },
        { title: "Ratio Variants", rows: dash.ratio_variants, empty: "No ratio variants detected." },
        { title: "Facsimiles", rows: dash.facsimiles, empty: "No facsimile releases detected." },
        {
          title: "Anniversary / Milestone Books",
          rows: dash.anniversary_milestone_books,
          empty: "No anniversary or milestone books detected.",
        },
        { title: "Key Events", rows: dash.key_events, empty: "No key event releases detected." },
        {
          title: "High Opportunity Score",
          rows: dash.high_opportunity_score,
          empty: "No high-score opportunities (≥70) yet.",
        },
        { title: "Watchlist", rows: dash.watchlist, empty: "No mid-tier watchlist opportunities yet." },
      ]
    : [];

  return (
    <AppShell>
      <PageHeader
        eyebrow="P59-05"
        title="Industry Scanner Dashboard"
        description="Best industry-wide release opportunities from supported publishers — aggregated from scan, signal, and opportunity scoring (not an AI Top 20)."
        actions={
          <button
            type="button"
            disabled={refreshing || loading}
            onClick={() => void onRefreshScores()}
            className="rounded-full border border-cyan-400/40 bg-cyan-400/15 px-4 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-400/25 disabled:opacity-50"
          >
            {refreshing ? "Refreshing…" : "Refresh scores"}
          </button>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

      {loading ? (
        <p className="mt-8 text-slate-400">Loading industry scanner dashboard…</p>
      ) : summary && dash ? (
        <>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { label: "Releases scanned", value: summary.releases_scanned },
              { label: "Signals detected", value: summary.signals_detected },
              { label: "High-score opportunities", value: summary.high_score_opportunities },
              { label: "#1 issues", value: summary.number_one_issues },
              { label: "Ratio variants", value: summary.ratio_variants },
              { label: "Key events", value: summary.key_events },
            ].map((card) => (
              <div key={card.label} className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">{card.label}</p>
                <p className="mt-1 text-2xl font-semibold text-white">{card.value}</p>
              </div>
            ))}
          </div>
          {dash.scan_run_id ? (
            <p className="mt-4 text-xs text-slate-500">Latest scan run ID: {dash.scan_run_id}</p>
          ) : null}
          {sections.map((section) => (
            <SectionBlock key={section.title} title={section.title} rows={section.rows} empty={section.empty} />
          ))}
        </>
      ) : null}
    </AppShell>
  );
}
