import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P81DiscoveryFeedRead, type P81DiscoveryOpportunityRead } from "../api/client";
import { DiscoveryPageLayout, PatriotPanel } from "../components/discovery/p81/DiscoveryPageLayout";

function OppList({ items, empty }: { items: P81DiscoveryOpportunityRead[]; empty: string }) {
  if (!items.length) return <p className="text-sm text-blue-800/80">{empty}</p>;
  return (
    <ul className="space-y-2">
      {items.map((o) => (
        <li key={o.id}>
          <Link
            to={`/discovery-opportunity/${o.id}`}
            className="block rounded-lg border border-blue-200 bg-white px-3 py-2 hover:border-red-400"
          >
            <div className="flex justify-between gap-2">
              <span className="text-sm font-medium text-blue-950">{o.title}</span>
              <span className="text-xs font-semibold text-red-700">{o.discovery_score.toFixed(0)}</span>
            </div>
            <p className="text-[10px] uppercase tracking-wider text-blue-800/70">
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
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setFeed(await apiClient.getDiscoveryFeed({ refresh: false }));
    } catch (err) {
      setFeed(null);
      setError(err instanceof ApiError ? err.message : "Failed to load discovery feed.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <DiscoveryPageLayout
      title="Discovery feed"
      eyebrow="P81-01 · Discovery"
      error={error}
      onRetry={() => void load()}
      loading={loading && !feed}
    >
      {feed ? (
        <>
          <PatriotPanel title="Top opportunities">
            <OppList items={feed.top_opportunities} empty="No scored opportunities yet." />
          </PatriotPanel>
          <section className="grid gap-6 sm:grid-cols-2">
            <PatriotPanel title="New #1 issues">
              <OppList items={feed.new_number_ones} empty="None" />
            </PatriotPanel>
            <PatriotPanel title="Milestones">
              <OppList items={feed.milestone_issues} empty="None" />
            </PatriotPanel>
            <PatriotPanel title="Creator projects">
              <OppList items={feed.creator_projects} empty="None" />
            </PatriotPanel>
            <PatriotPanel title="New variants">
              <OppList items={feed.new_variants} empty="None" />
            </PatriotPanel>
          </section>
        </>
      ) : null}
    </DiscoveryPageLayout>
  );
}
