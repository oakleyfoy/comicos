import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P72GradingOperationsDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

export function GradingOperationsDashboardPage(): JSX.Element {
  const [ops, setOps] = useState<P72GradingOperationsDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const dash = await apiClient.getGradingIntelligenceDashboard();
        if (!cancelled) setOps(dash.operations_engine ?? null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load grading operations dashboard.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const m = ops?.metrics;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Grading operations"
        title="Operations Dashboard"
        description="Queue depth, CGC turnaround, batch summary, and spend — manual workflow only (P72-02)."
      />
      <div className="mb-4 flex flex-wrap gap-3 text-sm">
        <Link className="text-indigo-600 hover:underline" to="/grading-queue">
          Grading queue
        </Link>
        <Link className="text-indigo-600 hover:underline" to="/grading-batches">
          Submission batches
        </Link>
      </div>
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading…</p> : null}
      {m ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Waiting" value={String(m.waiting_count)} />
            <Metric label="Submitted" value={String(m.submitted_count)} />
            <Metric label="At CGC" value={String(m.at_cgc_count)} />
            <Metric label="Returned" value={String(m.returned_count)} />
            <Metric label="Listed" value={String(m.listed_count)} />
            <Metric label="Sold" value={String(m.sold_count)} />
            <Metric label="Avg turnaround (days)" value={m.average_turnaround_days.toFixed(1)} />
            <Metric label="Total grading spend" value={`$${m.total_grading_spend.toFixed(0)}`} />
          </div>
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">Recent batches</h2>
            {!ops.batch_summary.length ? (
              <p className="mt-3 text-sm text-slate-500">No batches yet.</p>
            ) : (
              <ul className="mt-3 space-y-2 text-sm">
                {ops.batch_summary.map((b) => (
                  <li key={b.id} className="flex justify-between gap-2">
                    <span>{b.batch_name}</span>
                    <span className="text-slate-500">
                      {b.book_count} books · {b.batch_status}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      ) : !loading ? (
        <p className="text-sm text-slate-500">No operations data yet. Enqueue books from the grading queue.</p>
      ) : null}
    </AppShell>
  );
}
