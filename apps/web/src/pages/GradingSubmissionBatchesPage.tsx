import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P72GradingBatchRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function GradingSubmissionBatchesPage(): JSX.Element {
  const [batches, setBatches] = useState<P72GradingBatchRead[]>([]);
  const [name, setName] = useState("CGC Modern Batch");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setBatches(await apiClient.getGradingBatches());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load batches.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function createBatch() {
    setSaving(true);
    setError(null);
    try {
      await apiClient.createGradingBatch({ batch_name: name.trim(), queue_entry_ids: [] });
      setName("CGC Modern Batch");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create batch.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Grading operations"
        title="Submission Batches"
        description="Name batches, track costs and book counts — no automated CGC submit (P72-02)."
      />
      <div className="mb-4 flex flex-wrap gap-3 text-sm">
        <Link className="text-indigo-600 hover:underline" to="/grading-operations">
          Operations dashboard
        </Link>
        <Link className="text-indigo-600 hover:underline" to="/grading-queue">
          Grading queue
        </Link>
      </div>
      <div className="mb-6 flex flex-wrap items-end gap-2">
        <input
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Batch name"
        />
        <button
          type="button"
          disabled={saving || !name.trim()}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
          onClick={() => void createBatch()}
        >
          {saving ? "Creating…" : "Create batch"}
        </button>
      </div>
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading batches…</p> : null}
      {!loading && !batches.length ? <p className="text-sm text-slate-500">No batches yet.</p> : null}
      {batches.length ? (
        <ul className="space-y-3">
          {batches.map((b) => (
            <li key={b.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap justify-between gap-2">
                <span className="font-semibold text-slate-900">{b.batch_name}</span>
                <span className="text-sm text-slate-500">{b.batch_status}</span>
              </div>
              <p className="mt-2 text-sm text-slate-600">
                {b.book_count} books · Est. cost{" "}
                {b.estimated_cost != null ? `$${Number(b.estimated_cost).toFixed(0)}` : "—"} ·{" "}
                {b.target_grader}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
    </AppShell>
  );
}
