import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type MarketplaceAcquisitionCandidateRead,
  type MarketplaceAcquisitionSummaryRead,
  type MarketplaceCandidateRecommendation,
  type MarketplaceCandidateStatus,
  type MarketplaceSourceRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const REC_FILTERS: { label: string; value: MarketplaceCandidateRecommendation | "" }[] = [
  { label: "All recommendations", value: "" },
  { label: "Buy", value: "BUY" },
  { label: "Watch", value: "WATCH" },
  { label: "Pass", value: "PASS" },
];

const STATUS_FILTERS: { label: string; value: MarketplaceCandidateStatus | "" }[] = [
  { label: "All statuses", value: "" },
  { label: "New", value: "NEW" },
  { label: "Reviewed", value: "REVIEWED" },
  { label: "Ignored", value: "IGNORED" },
  { label: "Acquired", value: "ACQUIRED" },
];

function money(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

export function MarketplaceAcquisitionPage(): JSX.Element {
  const [items, setItems] = useState<MarketplaceAcquisitionCandidateRead[]>([]);
  const [summary, setSummary] = useState<MarketplaceAcquisitionSummaryRead | null>(null);
  const [sources, setSources] = useState<MarketplaceSourceRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [recFilter, setRecFilter] = useState<MarketplaceCandidateRecommendation | "">("");
  const [statusFilter, setStatusFilter] = useState<MarketplaceCandidateStatus | "">("");
  const [publisherFilter, setPublisherFilter] = useState("");
  const [sourceTypeFilter, setSourceTypeFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    marketplace_source_id: "" as string,
    title: "",
    publisher: "",
    series_name: "",
    issue_number: "",
    total_price: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { recommendation?: string; status?: string; publisher?: string; source_type?: string } = {};
      if (recFilter) params.recommendation = recFilter;
      if (statusFilter) params.status = statusFilter;
      if (publisherFilter.trim()) params.publisher = publisherFilter.trim();
      if (sourceTypeFilter) params.source_type = sourceTypeFilter;
      const [list, sum] = await Promise.all([
        apiClient.getMarketplaceAcquisitions(params),
        apiClient.getMarketplaceAcquisitionSummary(),
      ]);
      setItems(list.items);
      setSummary(sum);
      setSources(sum.sources ?? []);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load marketplace acquisitions.");
    } finally {
      setLoading(false);
    }
  }, [publisherFilter, recFilter, sourceTypeFilter, statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onAddCandidate() {
    setMessage(null);
    setError(null);
    if (!form.title.trim()) {
      setError("Title is required.");
      return;
    }
    try {
      await apiClient.createMarketplaceAcquisition({
        marketplace_source_id: form.marketplace_source_id ? Number(form.marketplace_source_id) : undefined,
        title: form.title.trim(),
        publisher: form.publisher || undefined,
        series_name: form.series_name || undefined,
        issue_number: form.issue_number || undefined,
        total_price: form.total_price ? Number(form.total_price) : undefined,
      });
      setShowForm(false);
      setForm({ marketplace_source_id: "", title: "", publisher: "", series_name: "", issue_number: "", total_price: "" });
      setMessage("Candidate added.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to add candidate.");
    }
  }

  async function onEvaluate(id: number) {
    setMessage(null);
    try {
      await apiClient.evaluateMarketplaceAcquisition(id);
      setMessage("Candidate evaluated.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to evaluate candidate.");
    }
  }

  async function onStatus(id: number, status: MarketplaceCandidateStatus) {
    try {
      await apiClient.patchMarketplaceAcquisition(id, { status });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update status.");
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P55-04"
        title="Marketplace Acquisitions"
        description="Manual marketplace listing capture and advisory buy guidance (no live search or purchases)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      <div className="mt-6 flex flex-wrap items-end gap-3">
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100"
        >
          Add candidate
        </button>
        <select
          value={recFilter}
          onChange={(e) => setRecFilter(e.target.value as MarketplaceCandidateRecommendation | "")}
          className="rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
        >
          {REC_FILTERS.map((o) => (
            <option key={o.label} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as MarketplaceCandidateStatus | "")}
          className="rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
        >
          {STATUS_FILTERS.map((o) => (
            <option key={o.label} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select
          value={sourceTypeFilter}
          onChange={(e) => setSourceTypeFilter(e.target.value)}
          className="rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
        >
          <option value="">All sources</option>
          {sources.map((s) => (
            <option key={s.id} value={s.source_type}>
              {s.name}
            </option>
          ))}
        </select>
        <input
          placeholder="Publisher filter"
          value={publisherFilter}
          onChange={(e) => setPublisherFilter(e.target.value)}
          className="rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
        />
      </div>

      {showForm ? (
        <div className="mt-4 grid gap-3 rounded-3xl border border-white/10 bg-slate-900/65 p-4 sm:grid-cols-2 lg:grid-cols-3">
          <select
            value={form.marketplace_source_id}
            onChange={(e) => setForm((f) => ({ ...f, marketplace_source_id: e.target.value }))}
            className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white"
          >
            <option value="">Manual (default)</option>
            {sources.map((s) => (
              <option key={s.id} value={String(s.id)}>
                {s.name}
              </option>
            ))}
          </select>
          <input
            placeholder="Title *"
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white"
          />
          <input
            placeholder="Series"
            value={form.series_name}
            onChange={(e) => setForm((f) => ({ ...f, series_name: e.target.value }))}
            className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white"
          />
          <input
            placeholder="Issue #"
            value={form.issue_number}
            onChange={(e) => setForm((f) => ({ ...f, issue_number: e.target.value }))}
            className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white"
          />
          <input
            placeholder="Publisher"
            value={form.publisher}
            onChange={(e) => setForm((f) => ({ ...f, publisher: e.target.value }))}
            className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white"
          />
          <input
            placeholder="Total price"
            type="number"
            value={form.total_price}
            onChange={(e) => setForm((f) => ({ ...f, total_price: e.target.value }))}
            className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white"
          />
          <button
            type="button"
            onClick={() => void onAddCandidate()}
            className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 sm:col-span-2 lg:col-span-3"
          >
            Save candidate
          </button>
        </div>
      ) : null}

      {summary ? (
        <p className="mt-4 text-sm text-slate-400">{summary.total_candidates} candidate(s) tracked.</p>
      ) : null}

      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading…</p>
      ) : items.length === 0 ? (
        <p className="mt-6 text-sm text-slate-400">No marketplace candidates yet.</p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-3xl border border-white/10 bg-slate-900/65">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-white/10 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Price</th>
                <th className="px-4 py-3">Matched opp.</th>
                <th className="px-4 py-3">Match</th>
                <th className="px-4 py-3">Value</th>
                <th className="px-4 py-3">Rec.</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Rationale</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-b border-white/5">
                  <td className="px-4 py-3 text-white">{row.title}</td>
                  <td className="px-4 py-3 text-slate-300">{row.source_name ?? "—"}</td>
                  <td className="px-4 py-3 text-slate-200">{money(row.total_price)}</td>
                  <td className="px-4 py-3 text-slate-300">{row.acquisition_opportunity_id ?? "—"}</td>
                  <td className="px-4 py-3 text-slate-300">{(row.match_confidence * 100).toFixed(0)}%</td>
                  <td className="px-4 py-3 text-cyan-200">{row.value_score.toFixed(1)}</td>
                  <td className="px-4 py-3 font-medium text-slate-200">{row.recommendation}</td>
                  <td className="px-4 py-3 text-slate-300">{row.status}</td>
                  <td className="max-w-xs px-4 py-3 text-slate-400">{row.rationale}</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <button type="button" onClick={() => void onEvaluate(row.id)} className="text-cyan-300 hover:underline">
                      Evaluate
                    </button>
                    <button type="button" onClick={() => void onStatus(row.id, "REVIEWED")} className="ml-2 text-slate-300 hover:underline">
                      Reviewed
                    </button>
                    <button type="button" onClick={() => void onStatus(row.id, "IGNORED")} className="ml-2 text-rose-300 hover:underline">
                      Ignore
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}
