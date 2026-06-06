import { useEffect, useMemo, useState, type ReactNode } from "react";

import { ApiError, apiClient, type PullListDecisionRead, type PullListDecisionType } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const DECISION_FILTERS: { label: string; value: PullListDecisionType | "" }[] = [
  { label: "All", value: "" },
  { label: "Start Run", value: "START_RUN" },
  { label: "Continue Run", value: "CONTINUE_RUN" },
  { label: "Watch", value: "WATCH" },
  { label: "Pass", value: "PASS" },
];

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

export function PullListDecisionsPage(): JSX.Element {
  const [items, setItems] = useState<PullListDecisionRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [decisionFilter, setDecisionFilter] = useState<PullListDecisionType | "">("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const params = decisionFilter ? { decision_type: decisionFilter } : undefined;
        const body = await apiClient.getPullListDecisions(params);
        if (!cancelled) setItems(body.items);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load pull list decisions.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [decisionFilter]);

  const counts = useMemo(() => {
    const map: Record<string, number> = {};
    for (const row of items) {
      map[row.decision_type] = (map[row.decision_type] ?? 0) + 1;
    }
    return map;
  }, [items]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P52-02"
        title="Pull List Decisions"
        description="Deterministic collector actions from Release Intelligence and Recommendation V2 (read-only)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      <div className="mt-4 flex flex-wrap gap-2">
        {DECISION_FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={() => setDecisionFilter(f.value)}
            className={`rounded-full border px-3 py-1 text-xs font-medium ${
              decisionFilter === f.value
                ? "border-cyan-400/40 bg-cyan-400/15 text-cyan-100"
                : "border-white/10 bg-white/5 text-slate-300"
            }`}
          >
            {f.label}
            {f.value && counts[f.value] != null ? ` (${counts[f.value]})` : ""}
          </button>
        ))}
      </div>
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading decisions…</p>
      ) : (
        <div className="mt-6 space-y-6">
          <Panel title="Decisions">
            {items.length === 0 ? (
              <p className="text-sm text-slate-600">
                No decisions yet. Run decision generation for your catalog to populate this view.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm text-slate-800">
                  <thead className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                    <tr>
                      <th className="pb-3 pr-4 font-medium">Decision</th>
                      <th className="pb-3 pr-4 font-medium">Comic</th>
                      <th className="pb-3 pr-4 font-medium">Release</th>
                      <th className="pb-3 pr-4 font-medium">FOC</th>
                      <th className="pb-3 pr-4 font-medium">Confidence</th>
                      <th className="pb-3 font-medium">Reasons</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((row) => (
                      <tr key={row.id} className="border-t border-white/5 align-top">
                        <td className="py-3 pr-4 font-semibold text-white">{row.decision_type.replace("_", " ")}</td>
                        <td className="py-3 pr-4">
                          <div className="font-medium text-white">{row.comic_title || row.series_name}</div>
                          <div className="text-xs text-slate-500">
                            {row.publisher} · #{row.issue_number}
                          </div>
                        </td>
                        <td className="py-3 pr-4">{formatDate(row.release_date)}</td>
                        <td className="py-3 pr-4">{formatDate(row.foc_date)}</td>
                        <td className="py-3 pr-4">{row.confidence_score.toFixed(2)}</td>
                        <td className="py-3 text-xs text-slate-400">{row.reasons.join(" · ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>
      )}
    </AppShell>
  );
}
