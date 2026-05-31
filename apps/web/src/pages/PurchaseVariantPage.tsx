import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type PurchaseVariantAction,
  type PurchaseVariantRecommendationRead,
  type PurchaseVariantType,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const REC_FILTERS: { label: string; value: PurchaseVariantAction | "" }[] = [
  { label: "All recommendations", value: "" },
  { label: "Buy", value: "BUY" },
  { label: "Watch", value: "WATCH" },
  { label: "Avoid", value: "AVOID" },
];

const TYPE_FILTERS: { label: string; value: PurchaseVariantType | "" }[] = [
  { label: "All types", value: "" },
  { label: "Cover A", value: "COVER_A" },
  { label: "Open order", value: "OPEN_ORDER" },
  { label: "Incentive", value: "INCENTIVE" },
  { label: "Ratio", value: "RATIO" },
  { label: "Store exclusive", value: "STORE_EXCLUSIVE" },
  { label: "Unknown", value: "UNKNOWN" },
];

function recTone(rec: PurchaseVariantAction): string {
  if (rec === "BUY") return "text-emerald-300";
  if (rec === "WATCH") return "text-amber-200";
  return "text-rose-300";
}

export function PurchaseVariantPage(): JSX.Element {
  const [items, setItems] = useState<PurchaseVariantRecommendationRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [recFilter, setRecFilter] = useState<PurchaseVariantAction | "">("");
  const [typeFilter, setTypeFilter] = useState<PurchaseVariantType | "">("");
  const [publisherFilter, setPublisherFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { recommendation?: string; variant_type?: string; publisher?: string } = {};
      if (recFilter) params.recommendation = recFilter;
      if (typeFilter) params.variant_type = typeFilter;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const body = await apiClient.getPurchaseVariants(params);
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load purchase variants.");
    } finally {
      setLoading(false);
    }
  }, [recFilter, typeFilter, publisherFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onGenerate() {
    setGenerating(true);
    setMessage(null);
    setError(null);
    try {
      const result = await apiClient.generatePurchaseVariants();
      setMessage(`Generated ${result.created_count} new variant recommendation(s).`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to generate variants.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P53-03"
        title="Purchase Variants"
        description="Cover-level BUY / WATCH / AVOID guidance from quantity recommendations and profile (no marketplace pricing or orders)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}
      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">
          Recommendation
          <select
            value={recFilter}
            onChange={(e) => setRecFilter(e.target.value as PurchaseVariantAction | "")}
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
          Variant type
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as PurchaseVariantType | "")}
            className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          >
            {TYPE_FILTERS.map((f) => (
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
          Generate variants
        </button>
      </div>
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading…</p>
      ) : items.length === 0 ? (
        <p className="mt-6 text-sm text-slate-400">
          No variant recommendations yet. Generate purchase quantities first, then run variant generation.
        </p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-3xl border border-white/10 bg-slate-900/65">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-white/10 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Comic</th>
                <th className="px-4 py-3">Cover</th>
                <th className="px-4 py-3">Variant Type</th>
                <th className="px-4 py-3">Recommendation</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-b border-white/5 text-slate-200">
                  <td className="px-4 py-3">
                    <div className="font-medium text-white">{row.title || row.series_name}</div>
                    <div className="text-xs text-slate-500">
                      {row.publisher} · #{row.issue_number}
                    </div>
                  </td>
                  <td className="px-4 py-3">{row.cover_label}</td>
                  <td className="px-4 py-3">{row.variant_type.replace(/_/g, " ")}</td>
                  <td className={`px-4 py-3 font-semibold ${recTone(row.recommendation)}`}>{row.recommendation}</td>
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
