import { FormEvent, useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type MarketUserDashboardRead, type UserPreferenceRead } from "../api/client";
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

export function MarketUserIntelligencePage(): JSX.Element {
  const [dashboard, setDashboard] = useState<MarketUserDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [prefType, setPrefType] = useState("FRANCHISE");
  const [prefLabel, setPrefLabel] = useState("");
  const [prefScore, setPrefScore] = useState("75");
  const [submitting, setSubmitting] = useState(false);

  async function loadDashboard() {
    setLoading(true);
    setError(null);
    try {
      await apiClient.postMarketUserIntelligenceRefresh();
      const body = await apiClient.getMarketUserIntelligenceDashboard();
      setDashboard(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load market & user intelligence.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  async function onSubmitManual(e: FormEvent) {
    e.preventDefault();
    if (!prefLabel.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiClient.createMarketUserPreference({
        preference_type: prefType,
        preference_label: prefLabel.trim(),
        preference_score: Number(prefScore) || undefined,
      });
      setPrefLabel("");
      await loadDashboard();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save manual preference.");
    } finally {
      setSubmitting(false);
    }
  }

  async function disablePreference(row: UserPreferenceRead) {
    if (!row.id) return;
    setError(null);
    try {
      await apiClient.disableMarketUserPreference(row.id);
      await loadDashboard();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to disable preference.");
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Market & user fit"
        title="Market & User Intelligence"
        description="Market demand baselines, inferred collector preferences, and combined fit signals (P51-03)."
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-400">Loading market & user intelligence…</p> : null}

      {dashboard ? (
        <div className="space-y-6">
          <p className="text-sm text-slate-400">
            {dashboard.total_market_profiles} market demand profiles · {dashboard.total_active_preferences} active user
            preferences
          </p>
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Top Market Demand">
              <ul className="space-y-2 text-sm text-slate-300">
                {dashboard.top_market_demand.map((row) => (
                  <li key={`${row.entity_type}-${row.entity_name}`} className="flex justify-between gap-2">
                    <span>
                      {row.entity_name} <span className="text-slate-500">({row.entity_type})</span>
                    </span>
                    <span className="text-slate-400">{row.demand_score.toFixed(1)}</span>
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Top User Preferences">
              <ul className="space-y-2 text-sm text-slate-300">
                {dashboard.top_user_preferences.map((row) => (
                  <li key={`${row.id}-${row.preference_key}`} className="flex justify-between gap-2">
                    <span>{row.preference_label}</span>
                    <span className="text-slate-400">{row.preference_score.toFixed(1)}</span>
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Preference Signals">
              <ul className="space-y-2 text-sm text-slate-300">
                {dashboard.preference_signals.length ? (
                  dashboard.preference_signals.map((row, idx) => (
                    <li key={`${row.source_type}-${idx}`}>
                      {row.preference_label || row.signal_type} · {row.source_type} ({row.signal_strength.toFixed(1)})
                    </li>
                  ))
                ) : (
                  <li className="text-slate-500">No preference signals yet.</li>
                )}
              </ul>
            </Panel>
            <Panel title="Market Demand Distribution">
              <ul className="space-y-2 text-sm text-slate-300">
                {dashboard.market_demand_distribution.map((row) => (
                  <li key={row.bucket} className="flex justify-between">
                    <span>{row.bucket}</span>
                    <span className="text-slate-400">{row.count}</span>
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Upcoming High-Fit Releases">
              <ul className="space-y-2 text-sm text-slate-300">
                {dashboard.upcoming_high_fit.length ? (
                  dashboard.upcoming_high_fit.map((row) => (
                    <li key={row.release_issue_id} className="flex justify-between gap-2">
                      <span>
                        {row.series_name} #{row.issue_number}
                      </span>
                      <span className="text-slate-400">{row.combined_market_user_score.toFixed(1)}</span>
                    </li>
                  ))
                ) : (
                  <li className="text-slate-500">No upcoming releases in the fit window.</li>
                )}
              </ul>
            </Panel>
            <Panel title="Manual Preferences">
              <form className="space-y-3 text-sm" onSubmit={onSubmitManual}>
                <label className="block">
                  <span className="text-slate-400">Type</span>
                  <select
                    className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-white"
                    value={prefType}
                    onChange={(e) => setPrefType(e.target.value)}
                  >
                    <option value="FRANCHISE">Franchise</option>
                    <option value="CHARACTER">Character</option>
                    <option value="CREATOR">Creator</option>
                    <option value="PUBLISHER">Publisher</option>
                    <option value="SERIES">Series</option>
                    <option value="VARIANT_TYPE">Variant type</option>
                    <option value="KEY_ISSUE_TYPE">Key issue type</option>
                  </select>
                </label>
                <label className="block">
                  <span className="text-slate-400">Label</span>
                  <input
                    className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-white"
                    value={prefLabel}
                    onChange={(e) => setPrefLabel(e.target.value)}
                    placeholder="e.g. Spider-Man"
                  />
                </label>
                <label className="block">
                  <span className="text-slate-400">Score (optional)</span>
                  <input
                    className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-white"
                    value={prefScore}
                    onChange={(e) => setPrefScore(e.target.value)}
                    type="number"
                    min={0}
                    max={100}
                  />
                </label>
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-full bg-indigo-500 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                >
                  {submitting ? "Saving…" : "Add preference"}
                </button>
              </form>
              <ul className="mt-4 space-y-2 text-sm text-slate-300">
                {dashboard.top_user_preferences
                  .filter((row) => row.status === "ACTIVE" && row.id > 0)
                  .map((row) => (
                    <li key={`manual-${row.id}`} className="flex items-center justify-between gap-2">
                      <span>{row.preference_label}</span>
                      <button
                        type="button"
                        className="text-xs text-rose-300 hover:text-rose-200"
                        onClick={() => void disablePreference(row)}
                      >
                        Disable
                      </button>
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
