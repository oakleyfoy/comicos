import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P85CollectorHomeRead } from "../api/client";
import { AppShell } from "../components/AppShell";
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
      <AppShell>
        <div className="rounded-lg bg-blue-950 px-4 py-8 text-white">
          <div className="mx-auto max-w-3xl">
            <CollectorErrorState message={error} onRetry={() => void load()} />
          </div>
        </div>
      </AppShell>
    );
  }

  if (!home) {
    return (
      <AppShell>
        <div className="rounded-lg bg-blue-950 px-4 py-8 text-blue-100">
          <p>Loading your collector home…</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="rounded-xl bg-blue-950 text-white">
        <header className="border-b border-red-700 bg-gradient-to-r from-blue-950 via-blue-900 to-red-900 px-4 py-6">
          <div className="mx-auto max-w-4xl">
            <p className="text-[11px] uppercase tracking-[0.2em] text-red-200">P85 · Home</p>
            <h1 className="mt-1 text-2xl font-semibold">{home.headline}</h1>
            <p className="mt-2 text-sm text-blue-100">
              Budget {String(home.budget_status.state ?? "—")} · Portfolio $
              {Number(home.portfolio_movement.current_value ?? 0).toFixed(0)}
            </p>
          </div>
        </header>
        <main className="mx-auto max-w-4xl space-y-8 px-4 py-6">
          <section>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-red-200">Today&apos;s actions</h2>
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
                  <li key={`${a.title}-${i}`} className="rounded border border-blue-700 bg-white/5 px-3 py-2">
                    <Link to={a.action_url || "/daily-actions"} className="text-red-200 hover:text-white hover:underline">
                      {a.title}
                    </Link>
                    <span className="ml-2 text-blue-200">
                      {a.action_type} · {a.priority_score.toFixed(0)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
          {home.sections.map((sec) => (
            <section key={sec.key} className="rounded-lg border border-blue-800 bg-white px-4 py-3 text-blue-950 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-sm font-semibold text-blue-950">{sec.title}</h2>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                  sec.status === "OK" ? "bg-blue-100 text-blue-800" : "bg-red-100 text-red-800"
                }`}>
                  {sec.status}
                </span>
              </div>
              {sec.count === 0 && sec.empty_hint ? (
                <p className="mt-2 text-sm text-blue-700">{sec.empty_hint}</p>
              ) : (
                <ul className="mt-2 space-y-1 text-sm text-blue-900">
                  {sec.items.map((item, idx) => (
                    <li key={idx}>{String(item.title ?? item.label ?? JSON.stringify(item))}</li>
                  ))}
                </ul>
              )}
            </section>
          ))}
          <p className="text-xs text-blue-200">
            <Link to="/collector-command-center" className="text-red-200 hover:text-white hover:underline">
              Command center
            </Link>
            {" · "}
            <Link to="/workflow-health" className="text-red-200 hover:text-white hover:underline">
              Workflow health
            </Link>
          </p>
        </main>
      </div>
    </AppShell>
  );
}
