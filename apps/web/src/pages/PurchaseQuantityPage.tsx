import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  apiClient,
  type PurchaseQuantityRecommendationRead,
  type PurchaseQuantityTier,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const TIER_FILTERS: { label: string; value: PurchaseQuantityTier | "" }[] = [
  { label: "All tiers", value: "" },
  { label: "Must Buy", value: "MUST_BUY" },
  { label: "Strong Buy", value: "STRONG_BUY" },
  { label: "Buy", value: "BUY" },
  { label: "Watch", value: "WATCH" },
  { label: "Pass", value: "PASS" },
];

const QTY_FILTERS: { label: string; value: number | "" }[] = [
  { label: "All quantities", value: "" },
  { label: "0", value: 0 },
  { label: "1", value: 1 },
  { label: "2", value: 2 },
  { label: "3", value: 3 },
  { label: "5", value: 5 },
];

export function PurchaseQuantityPage(): JSX.Element {
  const [items, setItems] = useState<PurchaseQuantityRecommendationRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [tierFilter, setTierFilter] = useState<PurchaseQuantityTier | "">("");
  const [qtyFilter, setQtyFilter] = useState<number | "">("");
  const [publisherFilter, setPublisherFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { tier?: string; quantity?: number; publisher?: string } = {};
      if (tierFilter) params.tier = tierFilter;
      if (qtyFilter !== "") params.quantity = qtyFilter;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      const body = await apiClient.getPurchaseQuantities(params);
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load purchase quantities.");
    } finally {
      setLoading(false);
    }
  }, [tierFilter, qtyFilter, publisherFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onGenerate() {
    setGenerating(true);
    setMessage(null);
    setError(null);
    try {
      const result = await apiClient.generatePurchaseQuantities();
      setMessage(`Generated ${result.created_count} new recommendation(s).`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to generate quantities.");
    } finally {
      setGenerating(false);
    }
  }

  const summary = useMemo(() => {
    const byQty: Record<number, number> = {};
    for (const row of items) {
      byQty[row.quantity_recommended] = (byQty[row.quantity_recommended] ?? 0) + 1;
    }
    return byQty;
  }, [items]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P53-02"
        title="Purchase Quantities"
        description="Profile-aware copy-count guidance from Recommendation V2 (advisory only — no orders or budget allocation)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}
      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">
          Tier
          <select
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value as PurchaseQuantityTier | "")}
            className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          >
            {TIER_FILTERS.map((f) => (
              <option key={f.label} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-400">
          Quantity
          <select
            value={qtyFilter === "" ? "" : String(qtyFilter)}
            onChange={(e) => {
              const v = e.target.value;
              setQtyFilter(v === "" ? "" : Number(v));
            }}
            className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          >
            {QTY_FILTERS.map((f) => (
              <option key={f.label} value={f.value === "" ? "" : String(f.value)}>
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
          Generate quantities
        </button>
      </div>
      {!loading && Object.keys(summary).length > 0 ? (
        <p className="mt-4 text-xs text-slate-500">
          Showing {items.length} release(s)
          {Object.entries(summary)
            .map(([q, n]) => `${n}× qty ${q}`)
            .join(" · ")}
        </p>
      ) : null}
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading…</p>
      ) : items.length === 0 ? (
        <p className="mt-6 text-sm text-slate-400">No quantity recommendations yet. Run generate after V2 scores exist.</p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-3xl border border-white/10 bg-slate-900/65">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-white/10 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Decision</th>
                <th className="px-4 py-3">Tier</th>
                <th className="px-4 py-3">Quantity</th>
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
                  <td className="px-4 py-3">{row.pull_list_decision ?? "—"}</td>
                  <td className="px-4 py-3">{row.recommendation_tier}</td>
                  <td className="px-4 py-3 font-semibold text-cyan-100">{row.quantity_recommended}</td>
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
