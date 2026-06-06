import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P85CollectorHomeRead } from "../api/client";
import { CollectorEmptyState } from "../components/CollectorEmptyState";
import { CollectorErrorState } from "../components/CollectorErrorState";

export function CollectorHomePage(): JSX.Element {
  const [home, setHome] = useState<P85CollectorHomeRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setHome(await apiClient.getCollectorHome());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load collector home. Check your connection and try again.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
        <div className="mx-auto max-w-3xl">
          <CollectorErrorState message={error} onRetry={() => void load()} />
        </div>
      </div>
    );
  }

  if (!home) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-400">
        <p>Loading your collector home…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-6">
        <div className="mx-auto max-w-4xl">
          <p className="text-[11px] uppercase tracking-[0.2em] text-amber-300">P85 · Home</p>
          <h1 className="mt-1 text-2xl font-semibold">{home.headline}</h1>
          <p className="mt-2 text-sm text-slate-400">
            Budget {String(home.budget_status.state ?? "—")} · Portfolio $
            {Number(home.portfolio_movement.current_value ?? 0).toFixed(0)}
          </p>
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-8 px-4 py-6">
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Today&apos;s actions</h2>
          {home.todays_actions.length === 0 ? (
            <div className="mt-3">
              <CollectorEmptyState
                title="No actions queued yet"
                description="Daily actions combine recommendations, FOC, sell, and grade signals."
                actionLabel="Open daily actions"
                actionTo="/daily-actions"
              />
            </div>
          ) : (
            <ul className="mt-3 space-y-2 text-sm">
              {home.todays_actions.map((a, i) => (
                <li key={`${a.title}-${i}`} className="rounded border border-slate-800 px-3 py-2">
                  <Link to={a.action_url || "/daily-actions"} className="text-amber-200 hover:underline">
                    {a.title}
                  </Link>
                  <span className="ml-2 text-slate-500">
                    {a.action_type} · {a.priority_score.toFixed(0)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
        {home.sections.map((sec) => (
          <section key={sec.key}>
            <h2 className="text-sm font-semibold text-white">{sec.title}</h2>
            {sec.count === 0 && sec.empty_hint ? (
              <p className="mt-2 text-sm text-slate-500">{sec.empty_hint}</p>
            ) : (
              <ul className="mt-2 space-y-1 text-sm text-slate-300">
                {sec.items.map((item, idx) => (
                  <li key={idx}>{String(item.title ?? item.label ?? JSON.stringify(item))}</li>
                ))}
              </ul>
            )}
          </section>
        ))}
        <p className="text-xs text-slate-600">
          <Link to="/collector-command-center" className="text-violet-400 hover:underline">
            Command center
          </Link>
          {" · "}
          <Link to="/workflow-health" className="text-violet-400 hover:underline">
            Workflow health
          </Link>
        </p>
      </main>
    </div>
  );
}
