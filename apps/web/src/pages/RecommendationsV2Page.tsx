import { useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type RecommendationV2DashboardRead, type RecommendationV2DetailRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function TierList({
  items,
  onSelect,
}: {
  items: RecommendationV2DashboardRead["must_buy"];
  onSelect: (id: number) => void;
}) {
  if (!items.length) {
    return <p className="text-sm text-slate-500">None in this bucket.</p>;
  }
  return (
    <ul className="space-y-2 text-sm text-slate-300">
      {items.map((row) => (
        <li key={row.id}>
          <button type="button" className="flex w-full justify-between gap-2 text-left hover:text-white" onClick={() => onSelect(row.id)}>
            <span>
              {row.series_name} #{row.issue_number} · {row.recommendation_type}
            </span>
            <span className="text-slate-400">{row.total_score.toFixed(1)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export function RecommendationsV2Page(): JSX.Element {
  const [dashboard, setDashboard] = useState<RecommendationV2DashboardRead | null>(null);
  const [detail, setDetail] = useState<RecommendationV2DetailRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      await apiClient.postRecommendationsV2Run();
      const body = await apiClient.getRecommendationsV2Dashboard();
      setDashboard(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load Recommendations V2.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function selectRecommendation(id: number) {
    try {
      const body = await apiClient.getRecommendationV2Detail(id);
      setDetail(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load recommendation detail.");
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Buy advisory"
        title="Recommendations V2"
        description="Explainable scoring from character, key issue, market, and user intelligence (P51-04). Advisory only."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-400">Running Recommendation Engine V2…</p> : null}
      {dashboard ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="Must Buy">
            <TierList items={dashboard.must_buy} onSelect={selectRecommendation} />
          </Panel>
          <Panel title="Strong Buy">
            <TierList items={dashboard.strong_buy} onSelect={selectRecommendation} />
          </Panel>
          <Panel title="Buy">
            <TierList items={dashboard.buy} onSelect={selectRecommendation} />
          </Panel>
          <Panel title="Watch">
            <TierList items={dashboard.watch} onSelect={selectRecommendation} />
          </Panel>
          <Panel title="Pass">
            <TierList items={dashboard.pass_tier} onSelect={selectRecommendation} />
          </Panel>
          <Panel title="Investment #1s">
            <TierList items={dashboard.investment_number_ones} onSelect={selectRecommendation} />
          </Panel>
          <Panel title="Start Run Opportunities">
            <TierList items={dashboard.start_run} onSelect={selectRecommendation} />
          </Panel>
          <Panel title="Key Issues">
            <TierList items={dashboard.key_issues} onSelect={selectRecommendation} />
          </Panel>
          <Panel title="Ratio Variants">
            <TierList items={dashboard.ratio_variants} onSelect={selectRecommendation} />
          </Panel>
          <Panel title="User Preference Matches">
            <TierList items={dashboard.user_preference_matches} onSelect={selectRecommendation} />
          </Panel>
          {detail ? (
            <Panel title="Score Breakdown & Explanation">
              <p className="text-sm text-slate-300">{detail.decision?.decision_summary}</p>
              <p className="mt-2 text-sm text-slate-400">{detail.decision?.primary_reason}</p>
              <p className="mt-2 text-sm text-amber-200/90">{detail.decision?.risk_note}</p>
              <ul className="mt-4 space-y-1 text-xs text-slate-400">
                {detail.components.map((c) => (
                  <li key={c.component_name}>
                    {c.component_name}: {c.component_score.toFixed(1)} — {c.explanation}
                  </li>
                ))}
              </ul>
            </Panel>
          ) : null}
        </div>
      ) : null}
    </AppShell>
  );
}
