import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P81DiscoveryFeedRead, type P81DiscoveryOpportunityRead } from "../api/client";
import { DiscoveryNav } from "../components/discovery/p81/DiscoveryNav";
import { StatusBanner } from "../components/StatusBanner";

function OppList({ items, empty }: { items: P81DiscoveryOpportunityRead[]; empty: string }) {
  if (!items.length) return <p className="text-sm text-slate-500">{empty}</p>;
  return (
    <ul className="space-y-2">
      {items.map((o) => (
        <li key={o.id}>
          <Link
            to={`/discovery-opportunity/${o.id}`}
            className="block rounded-xl border border-slate-700 bg-slate-900/40 px-3 py-2 hover:border-amber-500/40"
          >
            <div className="flex justify-between gap-2">
              <span className="text-sm font-medium text-white">{o.title}</span>
              <span className="text-xs text-amber-200">{o.discovery_score.toFixed(0)}</span>
            </div>
            <p className="text-[10px] uppercase tracking-wider text-slate-500">
              {o.score_category} · {o.opportunity_type}
            </p>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function DiscoveryFeedPage(): JSX.Element {
  const [feed, setFeed] = useState<P81DiscoveryFeedRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setFeed(await apiClient.getDiscoveryFeed({ refresh: false }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load discovery feed.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!feed) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : <p className="text-slate-400">Loading…</p>}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-4xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-violet-300">P81-01</p>
          <h1 className="text-xl font-semibold">Discovery feed</h1>
          <DiscoveryNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        <section>
          <h2 className="text-sm font-semibold text-white">Top opportunities</h2>
          <div className="mt-2">
            <OppList items={feed.top_opportunities} empty="No scored opportunities yet." />
          </div>
        </section>
        <section className="grid gap-6 sm:grid-cols-2">
          <div>
            <h2 className="text-sm font-semibold text-white">New #1 issues</h2>
            <div className="mt-2">
              <OppList items={feed.new_number_ones} empty="None" />
            </div>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white">Milestones</h2>
            <div className="mt-2">
              <OppList items={feed.milestone_issues} empty="None" />
            </div>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white">Creator projects</h2>
            <div className="mt-2">
              <OppList items={feed.creator_projects} empty="None" />
            </div>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white">New variants</h2>
            <div className="mt-2">
              <OppList items={feed.new_variants} empty="None" />
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
