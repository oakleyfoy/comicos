import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MarketplaceInventoryConflictResponse,
  type MarketplaceInventoryReconciliationReportResponse,
  type MarketplaceInventoryStateResponse,
  type MarketplaceInventorySyncRunResponse,
  type MarketplaceInventorySyncSummaryResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { MarketplaceConflictViewer } from "../components/marketplaces/sync/MarketplaceConflictViewer";
import { MarketplaceInventoryStateTable } from "../components/marketplaces/sync/MarketplaceInventoryStateTable";
import {
  MarketplaceReconciliationReportPanel,
  MarketplaceSyncDiagnostics,
} from "../components/marketplaces/sync/MarketplaceReconciliationReportPanel";
import { MarketplaceSyncRunTable } from "../components/marketplaces/sync/MarketplaceSyncRunTable";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function MarketplaceInventorySyncPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [summary, setSummary] = useState<MarketplaceInventorySyncSummaryResponse | null>(null);
  const [runs, setRuns] = useState<MarketplaceInventorySyncRunResponse[]>([]);
  const [states, setStates] = useState<MarketplaceInventoryStateResponse[]>([]);
  const [conflicts, setConflicts] = useState<MarketplaceInventoryConflictResponse[]>([]);
  const [report, setReport] = useState<MarketplaceInventoryReconciliationReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (Number.isFinite(parsedOrganizationId)) {
      void refresh();
    }
  }, [parsedOrganizationId]);

  async function refresh(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const org = await apiClient.getOrganization(parsedOrganizationId);
      setOrganization(org);
      if (!hasOrganizationPermission(org, "organization:view")) {
        setSummary(null);
        setRuns([]);
        setStates([]);
        setConflicts([]);
        return;
      }
      const [summaryBody, runBody, stateBody, conflictBody] = await Promise.all([
        apiClient.getMarketplaceSyncSummary(parsedOrganizationId),
        apiClient.listMarketplaceSyncRuns(parsedOrganizationId, { limit: 25, offset: 0 }),
        apiClient.listMarketplaceSyncStates(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listMarketplaceSyncConflicts(parsedOrganizationId, { limit: 50, offset: 0 }),
      ]);
      setSummary(summaryBody);
      setRuns(runBody.items);
      setStates(stateBody.items);
      setConflicts(conflictBody.items);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load marketplace sync workspace.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRunSync(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.runMarketplaceSync(parsedOrganizationId, { sync_run_type: "manual_sync" });
      setMessage(`Marketplace sync run #${body.id} completed.`);
      setReport(null);
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Marketplace sync run failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleReconcile(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.reconcileMarketplaceSync(parsedOrganizationId, {});
      setReport(body);
      setMessage("Marketplace reconciliation report generated.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Marketplace reconciliation failed.");
    } finally {
      setBusy(false);
    }
  }

  const canView = summary?.permissions.can_view ?? (organization ? hasOrganizationPermission(organization, "organization:view") : false);
  const canManage =
    summary?.permissions.can_manage ?? (organization ? hasOrganizationPermission(organization, "organization:update") : false);

  if (!Number.isFinite(parsedOrganizationId)) {
    return (
      <AppShell>
        <p className="text-sm text-slate-400">Invalid organization id.</p>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P43-03"
        title={organization ? `${organization.display_name} marketplace sync` : "Marketplace inventory sync"}
        description="Deterministic inventory state tracking, reconciliation, conflict detection, and append-only sync lineage."
        actions={
          <div className="flex gap-2">
            <Link to={`/organizations/${parsedOrganizationId}`} className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Organization
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-listings`}
              className="rounded-2xl border border-fuchsia-400/30 px-4 py-2 text-sm font-semibold text-fuchsia-100"
            >
              Listings
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-orders`}
              className="rounded-2xl border border-teal-400/30 px-4 py-2 text-sm font-semibold text-teal-100"
            >
              Orders
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-pricing`}
              className="rounded-2xl border border-violet-400/30 px-4 py-2 text-sm font-semibold text-violet-100"
            >
              Pricing
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-events`}
              className="rounded-2xl border border-emerald-400/30 px-4 py-2 text-sm font-semibold text-emerald-100"
            >
              Events
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/live-sales`}
              className="rounded-2xl border border-rose-400/30 px-4 py-2 text-sm font-semibold text-rose-100"
            >
              Live sales
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-ops`}
              className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100"
            >
              Ops dashboard
            </Link>
          </div>
        }
      />
      {error ? <div className="mt-4"><StatusBanner tone="error">{error}</StatusBanner></div> : null}
      {message ? <div className="mt-4"><StatusBanner tone="success">{message}</StatusBanner></div> : null}
      {loading ? <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5 text-sm text-slate-300">Loading marketplace sync workspace...</section> : null}
      {!loading && organization && !canView ? (
        <div className="mt-6">
          <OrganizationAccessDeniedState
            title="Marketplace sync access denied"
            description="Marketplace sync visibility is permission-aware and deny-by-default."
          />
        </div>
      ) : null}
      {!loading && summary && canView ? (
        <>
          <section className="mt-6">
            <MarketplaceSyncDiagnostics diagnostics={summary.diagnostics} />
          </section>
          <section className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy || !canManage}
              onClick={() => void handleRunSync()}
              className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100 disabled:opacity-50"
            >
              Run sync
            </button>
            <button
              type="button"
              disabled={busy || !canManage}
              onClick={() => void handleReconcile()}
              className="rounded-2xl border border-amber-400/30 px-4 py-2 text-sm font-semibold text-amber-100 disabled:opacity-50"
            >
              Generate reconciliation
            </button>
          </section>
          <div className="mt-6 grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
            <section className="space-y-6">
              <MarketplaceSyncRunTable runs={runs} loading={false} />
              <MarketplaceInventoryStateTable states={states} loading={false} />
            </section>
            <section className="space-y-6">
              <MarketplaceReconciliationReportPanel report={report} />
              <MarketplaceConflictViewer conflicts={conflicts} loading={false} />
            </section>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}
