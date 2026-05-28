import { useEffect, useState } from "react";

import { ApiError, apiClient } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationBatchOpsPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    batches: 0,
    failed: 0,
    integrity: 0,
    storage: 0,
    orphanWarnings: 0,
    failures: 0,
  });

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [runs, failed, integrity, storage, issues] = await Promise.all([
          apiClient.listOpsAutomationBatchRuns({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationBatchRuns({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationIntegrityAudits({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationStorageAudits({ limit: 100, offset: 0 }),
          apiClient.listAutomationBatchIssues({ limit: 100, offset: 0 }),
        ]);
        if (ignore) return;
        setStats({
          batches: runs.pagination.total_count,
          failed: failed.failed_batch_count,
          integrity: integrity.pagination.total_count,
          storage: storage.pagination.total_count,
          orphanWarnings: issues.items.filter((row) => row.issue_type === "ORPHAN_ARTIFACT_DETECTED").length,
          failures: issues.items.filter((row) => row.issue_type === "MAINTENANCE_FAILURE" || row.issue_type === "BATCH_EXECUTION_FAILURE").length,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation batch ops data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section id="automation-batch-ops" className="mt-6 rounded-3xl border border-amber-400/35 bg-amber-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Automation batch ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Diagnostics for batch failures, maintenance failures, integrity audits, storage audit warnings, orphan artifact detection, and replay sweep visibility.
          </p>
        </div>
        <span className="rounded-full border border-amber-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-100/90">
          Ops / P41-05
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading automation batch ops…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <StatCard label="Batch runs" value={String(stats.batches)} />
          <StatCard label="Failed batches" value={String(stats.failed)} />
          <StatCard label="Integrity audits" value={String(stats.integrity)} />
          <StatCard label="Storage audits" value={String(stats.storage)} />
          <StatCard label="Orphan warnings" value={String(stats.orphanWarnings)} />
          <StatCard label="Execution failures" value={String(stats.failures)} />
        </div>
      )}
    </section>
  );
}
