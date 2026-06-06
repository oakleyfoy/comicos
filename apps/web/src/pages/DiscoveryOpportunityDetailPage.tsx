import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, apiClient, type P81DiscoveryOpportunityRead } from "../api/client";
import { DiscoveryNav } from "../components/discovery/p81/DiscoveryNav";
import { StatusBanner } from "../components/StatusBanner";

export function DiscoveryOpportunityDetailPage(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const [opp, setOpp] = useState<P81DiscoveryOpportunityRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setError(null);
    try {
      setOpp(await apiClient.getDiscoveryOpportunity(Number(id)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load opportunity.");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!opp) {
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
          <h1 className="text-xl font-semibold">{opp.title}</h1>
          <DiscoveryNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-4 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        <p className="text-sm text-amber-200">
          Score {opp.discovery_score.toFixed(0)} · {opp.score_category} · {opp.opportunity_type}
        </p>
        <p className="text-sm text-slate-300">
          {opp.publisher} · {opp.series_name} #{opp.issue_number}
          {opp.release_date ? ` · Release ${opp.release_date}` : null}
        </p>
        {opp.summary ? <p className="text-sm text-slate-400 whitespace-pre-wrap">{opp.summary}</p> : null}
        {opp.signals.length ? (
          <ul className="list-disc pl-5 text-sm text-slate-400">
            {opp.signals.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        ) : null}
        <Link to="/discovery-opportunities" className="text-sm text-violet-300 hover:underline">
          ← Back to opportunities
        </Link>
      </main>
    </div>
  );
}
