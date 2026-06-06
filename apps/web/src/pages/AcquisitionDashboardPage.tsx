import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type AcquisitionDashboardItemRead, type AcquisitionDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function money(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function SectionTable({
  title,
  items,
  empty,
}: {
  title: string;
  items: AcquisitionDashboardItemRead[];
  empty: string;
}): JSX.Element {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-600">{title}</h3>
      {items.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">{empty}</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {items.map((item) => (
            <li key={`${item.item_type}-${item.item_id}`} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-medium text-slate-900">{item.title}</span>
                {item.recommendation ? (
                  <span className="font-medium text-teal-800">{item.recommendation}</span>
                ) : item.priority_label ? (
                  <span className="font-medium text-amber-800">{item.priority_label}</span>
                ) : null}
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {item.publisher ? `${item.publisher} · ` : ""}
                {item.priority_score != null ? `Score ${item.priority_score.toFixed(1)} · ` : ""}
                {item.total_price != null ? `Price ${money(item.total_price)} · ` : ""}
                {item.target_price != null ? `Target ${money(item.target_price)}` : ""}
              </p>
              {item.rationale ? <p className="mt-1 text-xs text-slate-400">{item.rationale}</p> : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function AcquisitionDashboardPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<AcquisitionDashboardRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [publisherFilter, setPublisherFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = publisherFilter.trim() ? { publisher: publisherFilter.trim() } : undefined;
      const body = await apiClient.getAcquisitionDashboard(params);
      setDashboard(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load acquisition dashboard.");
    } finally {
      setLoading(false);
    }
  }, [publisherFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const s = dashboard?.summary;

  return (
    <AppShell>
      <PageHeader
        eyebrow="P55-05"
        title="Acquisition Dashboard"
        description="Daily view of want-list targets, collection gaps, opportunities, and marketplace candidates (read-only aggregation)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      <div className="mt-4">
        <input
          placeholder="Publisher filter"
          value={publisherFilter}
          onChange={(e) => setPublisherFilter(e.target.value)}
          className="rounded-lg border border-white/10 bg-slate-900 px-3 py-1.5 text-sm text-white"
        />
      </div>
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading…</p>
      ) : s ? (
        <>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <div className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
              <p className="text-xs uppercase text-slate-500">Want list</p>
              <p className="mt-1 text-2xl font-semibold text-slate-900">{s.total_want_list_items}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
              <p className="text-xs uppercase text-slate-500">Critical targets</p>
              <p className="mt-1 text-2xl font-semibold text-rose-200">{s.critical_want_list_items}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
              <p className="text-xs uppercase text-slate-500">Open gaps</p>
              <p className="mt-1 text-2xl font-semibold text-slate-900">{s.open_collection_gaps}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
              <p className="text-xs uppercase text-slate-500">Buy candidates</p>
              <p className="mt-1 text-2xl font-semibold text-emerald-200">{s.buy_candidates}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
              <p className="text-xs uppercase text-slate-500">Below target</p>
              <p className="mt-1 text-2xl font-semibold text-cyan-200">{s.below_target_candidates}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/65 p-4">
              <p className="text-xs uppercase text-slate-500">Review required</p>
              <p className="mt-1 text-2xl font-semibold text-amber-800">{s.review_required_candidates}</p>
            </div>
          </div>
          <div className="mt-8 grid gap-4 lg:grid-cols-2">
            <SectionTable title="Top collection gaps" items={dashboard?.top_collection_gaps ?? []} empty="No gaps." />
            <SectionTable title="Top want-list items" items={dashboard?.top_want_list_items ?? []} empty="No critical/high want-list items." />
            <SectionTable title="Top opportunities" items={dashboard?.top_opportunities ?? []} empty="No opportunities." />
            <SectionTable title="Marketplace candidates" items={dashboard?.marketplace_candidates ?? []} empty="No candidates." />
            <SectionTable title="Below target price" items={dashboard?.below_target_price ?? []} empty="No below-target listings." />
            <SectionTable title="Review required" items={dashboard?.review_required ?? []} empty="Nothing flagged for review." />
          </div>
        </>
      ) : null}
    </AppShell>
  );
}
