import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P80CollectorDashboardRead } from "../api/client";
import { StatusBanner } from "../components/StatusBanner";

export function CollectorDashboardPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<P80CollectorDashboardRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDashboard(await apiClient.getCollectorDashboard());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto flex max-w-2xl items-center justify-between">
          <div>
            <p className="text-[11px] uppercase tracking-[0.2em] text-emerald-300">P80-03</p>
            <h1 className="text-xl font-semibold">Collector Dashboard</h1>
          </div>
          <Link to="/collector-assistant" className="text-sm text-emerald-200 underline-offset-2 hover:underline">
            Scan
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-2xl space-y-6 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        {loading ? <p className="text-slate-400">Loading…</p> : null}

        {dashboard ? (
          <>
            <section className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
                <p className="text-xs text-slate-500">Collection gaps</p>
                <p className="text-2xl font-bold">{dashboard.gap_summary.total_gaps ?? 0}</p>
              </div>
              <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
                <p className="text-xs text-slate-500">Avg completion</p>
                <p className="text-2xl font-bold">{dashboard.gap_summary.average_completion_percent ?? 0}%</p>
              </div>
            </section>

            <DashboardList
              title="High priority gaps"
              empty="No gaps detected."
              items={dashboard.collection_gaps.slice(0, 8).map((gap) => (
                <li key={gap.id} className="text-sm text-slate-300">
                  {gap.series_name} #{gap.issue_number} · {gap.priority}
                </li>
              ))}
            />

            <DashboardList
              title="Recommended acquisitions"
              empty="No acquisition targets yet."
              items={dashboard.recommended_acquisitions.map((item) => (
                <li key={`${item.kind}-${item.title}`} className="text-sm text-slate-300">
                  {item.title}
                  {item.score != null ? ` · score ${item.score.toFixed(0)}` : ""}
                </li>
              ))}
            />

            <DashboardList
              title="Spec opportunities"
              empty="No spec signals right now."
              items={dashboard.spec_opportunities.map((item) => (
                <li key={`spec-${item.title}`} className="text-sm text-slate-300">
                  {item.title} · {item.recommendation}
                </li>
              ))}
            />

            <DashboardList
              title="Books to watch"
              empty="Nothing on watch list."
              items={dashboard.books_to_watch.map((item) => (
                <li key={`watch-${item.title}`} className="text-sm text-slate-300">
                  {item.title}
                </li>
              ))}
            />
          </>
        ) : null}
      </main>
    </div>
  );
}

function DashboardList({
  title,
  empty,
  items,
}: {
  title: string;
  empty: string;
  items: JSX.Element[];
}): JSX.Element {
  return (
    <section className="rounded-2xl border border-slate-700/80 bg-slate-900/40 p-4">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">{title}</h2>
      {items.length ? (
        <ul className="mt-3 space-y-2">{items}</ul>
      ) : (
        <p className="mt-3 text-sm text-slate-500">{empty}</p>
      )}
    </section>
  );
}
