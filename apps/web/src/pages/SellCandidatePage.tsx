import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type SellCandidateAction,
  type SellCandidateRecommendationRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const REC_FILTERS: { label: string; value: SellCandidateAction | "" }[] = [
  { label: "All recommendations", value: "" },
  { label: "Strong Sell", value: "STRONG_SELL" },
  { label: "Sell", value: "SELL" },
  { label: "Hold", value: "HOLD" },
  { label: "Review", value: "REVIEW" },
];

function money(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function recClass(rec: SellCandidateAction): string {
  if (rec === "STRONG_SELL" || rec === "SELL") return "text-rose-800";
  if (rec === "REVIEW") return "text-amber-800";
  return "text-slate-300";
}

export function SellCandidatePage(): JSX.Element {
  const [items, setItems] = useState<SellCandidateRecommendationRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [recFilter, setRecFilter] = useState<SellCandidateAction | "">("");
  const [publisherFilter, setPublisherFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { recommendation?: string; publisher?: string } = {};
      if (recFilter) params.recommendation = recFilter;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const body = await apiClient.getSellCandidates(params);
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load sell candidates.");
    } finally {
      setLoading(false);
    }
  }, [recFilter, publisherFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onGenerate() {
    setGenerating(true);
    setMessage(null);
    setError(null);
    try {
      const result = await apiClient.generateSellCandidates();
      setMessage(`Generated ${result.created_count} new recommendation(s).`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to generate sell candidates.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P54-05"
        title="Sell Candidates"
        description="Hold vs sell guidance from duplicates, profit, grading, and portfolio concentration (no listings or sales)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}
      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">
          Recommendation
          <select
            value={recFilter}
            onChange={(e) => setRecFilter(e.target.value as SellCandidateAction | "")}
            className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          >
            {REC_FILTERS.map((f) => (
              <option key={f.label} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-400">
          Publisher
          <input
            value={publisherFilter}
            onChange={(e) => setPublisherFilter(e.target.value)}
            placeholder="Filter publisher"
            className="mt-1 block w-40 rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          />
        </label>
        <button
          type="button"
          disabled={generating}
          onClick={() => void onGenerate()}
          className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 disabled:opacity-50"
        >
          Generate sell candidates
        </button>
      </div>
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading…</p>
      ) : items.length === 0 ? (
        <p className="mt-6 text-sm text-slate-400">No sell candidates yet. Add inventory and run generation.</p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-3xl border border-white/10 bg-slate-900/65">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-white/10 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Comic</th>
                <th className="px-4 py-3">Recommendation</th>
                <th className="px-4 py-3">FMV</th>
                <th className="px-4 py-3">Est. Profit</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-b border-white/5 text-slate-200">
                  <td className="px-4 py-3">
                    <div className="font-medium text-white">
                      {row.title} #{row.issue_number}
                    </div>
                    <div className="text-xs text-slate-500">{row.publisher}</div>
                  </td>
                  <td className={`px-4 py-3 font-semibold ${recClass(row.recommendation)}`}>{row.recommendation.replace("_", " ")}</td>
                  <td className="px-4 py-3">{money(row.estimated_fmv)}</td>
                  <td className="px-4 py-3">{money(row.estimated_profit)}</td>
                  <td className="px-4 py-3">{row.confidence_score.toFixed(2)}</td>
                  <td className="max-w-md px-4 py-3 text-slate-400">{row.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}
