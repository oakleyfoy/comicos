import { useEffect, useState } from "react";

import { ApiError, apiClient, type P80OperationsDashboardRead } from "../api/client";
import { MobileOpsShell } from "../components/mobile/p80/MobileOpsShell";
import { StatusBanner } from "../components/StatusBanner";

function Stat({ label, value }: { label: string; value: string | number }): JSX.Element {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-950/50 p-3">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="text-xl font-semibold">{value}</p>
    </div>
  );
}

export function MobileOperationsPage(): JSX.Element {
  const [dash, setDash] = useState<P80OperationsDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void apiClient
      .getMobileOperationsDashboard()
      .then(setDash)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load dashboard."));
  }, []);

  return (
    <MobileOpsShell title="Operations">
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {dash ? (
        <div className="grid grid-cols-2 gap-3">
          <Stat label="Received today" value={dash.intake_received_today} />
          <Stat label="Received week" value={dash.intake_received_this_week} />
          <Stat label="Pending receipts" value={dash.intake_pending_receipts} />
          <Stat label="Assigned today" value={dash.storage_assigned_today} />
          <Stat label="Unassigned" value={dash.storage_unassigned_inventory} />
          <Stat label="Open audits" value={dash.audit_open_sessions} />
          <Stat label="Audit accuracy" value={`${dash.audit_average_accuracy_pct}%`} />
          <Stat label="Recent audits" value={dash.audit_recent_completed} />
        </div>
      ) : (
        <p className="text-sm text-slate-500">Loading…</p>
      )}
    </MobileOpsShell>
  );
}
