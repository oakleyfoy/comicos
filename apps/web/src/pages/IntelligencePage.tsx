import { useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type IntelligenceDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

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

export function IntelligencePage(): JSX.Element {
  const [dashboard, setDashboard] = useState<IntelligenceDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getIntelligenceDashboard();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load collector intelligence.");
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
        eyebrow="Collector demand"
        title="Character, Franchise & Creator Intelligence"
        description="Deterministic popularity and demand signals for characters, franchises, and creators (P51-01). Advisory inputs only — no purchase automation."
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-400">Loading intelligence dashboard…</p> : null}

      {dashboard ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard label="Characters" value={String(dashboard.character_count)} />
            <StatCard label="Franchises" value={String(dashboard.franchise_count)} />
            <StatCard label="Creators" value={String(dashboard.creator_count)} />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Panel title="Top Characters">
              <ul className="space-y-2 text-sm text-slate-300">
                {dashboard.top_characters.map((row) => (
                  <li key={row.entity_id} className="flex justify-between gap-2">
                    <span>{row.entity_name}</span>
                    <span className="text-slate-400">{row.popularity_score.toFixed(1)}</span>
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Top Franchises">
              <ul className="space-y-2 text-sm text-slate-300">
                {dashboard.top_franchises.map((row) => (
                  <li key={row.entity_id} className="flex justify-between gap-2">
                    <span>{row.entity_name}</span>
                    <span className="text-slate-400">{row.popularity_score.toFixed(1)}</span>
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Top Creators">
              <ul className="space-y-2 text-sm text-slate-300">
                {dashboard.top_creators.map((row) => (
                  <li key={row.entity_id} className="flex justify-between gap-2">
                    <span>{row.entity_name}</span>
                    <span className="text-slate-400">{row.popularity_score.toFixed(1)}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Upcoming Popular Releases">
              {!dashboard.upcoming_releases_by_popularity.length ? (
                <p className="text-sm text-slate-500">No upcoming releases in the popularity window.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.upcoming_releases_by_popularity.map((row) => (
                    <li key={row.release_issue_id} className="flex justify-between gap-2">
                      <span>
                        {row.series_name} · {row.title}
                      </span>
                      <span className="text-slate-400">{row.combined_popularity_score.toFixed(1)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            <Panel title="Popularity Distribution">
              <ul className="space-y-2 text-sm text-slate-300">
                {dashboard.popularity_distribution.map((bucket) => (
                  <li key={bucket.bucket_label} className="flex justify-between gap-2">
                    <span>{bucket.bucket_label}</span>
                    <span className="text-slate-400">{bucket.entity_count}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
