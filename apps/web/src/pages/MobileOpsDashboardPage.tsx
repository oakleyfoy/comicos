import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MobileOpsDashboardResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { MobileOpsDiagnosticsPanel } from "../components/mobile/ops/MobileOpsDiagnosticsPanel";
import { MobileOpsEventTimeline } from "../components/mobile/ops/MobileOpsEventTimeline";
import { MobileOpsMetricCards } from "../components/mobile/ops/MobileOpsMetricCards";
import { MobileOpsSnapshotPanel } from "../components/mobile/ops/MobileOpsSnapshotPanel";
import { MobileOpsSummaryPanels } from "../components/mobile/ops/MobileOpsSummaryPanels";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function MobileOpsDashboardPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [dashboard, setDashboard] = useState<MobileOpsDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
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
        setDashboard(null);
        return;
      }
      const body = await apiClient.getMobileOpsDashboard(parsedOrganizationId);
      setDashboard(body);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load mobile ops dashboard.");
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerate(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setGenerating(true);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.generateMobileOpsDashboard(parsedOrganizationId);
      setDashboard(body);
      setMessage("Mobile ops snapshot, metrics, and diagnostics generated.");
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to generate mobile ops dashboard state.");
    } finally {
      setGenerating(false);
    }
  }

  const canView = dashboard?.permissions.can_view ?? (organization ? hasOrganizationPermission(organization, "organization:view") : false);
  const canManage = dashboard?.permissions.can_manage ?? (organization ? hasOrganizationPermission(organization, "organization:update") : false);
  const diagnosticSummary = (dashboard?.summary["workflow_health"] ?? {}) as Record<string, unknown>;

  if (!Number.isFinite(parsedOrganizationId)) {
    return (
      <AppShell>
        <p className="text-sm text-slate-600">Invalid organization id.</p>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P44-06"
        title={organization ? `${organization.display_name} mobile ops` : "Mobile ops dashboard"}
        description="Deterministic visibility across devices, offline state, scanning, convention operations, quick sales, and replay-safe mobile ops lineage."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to={`/organizations/${parsedOrganizationId}/mobile`} className="rounded-2xl border border-lime-400/30 px-4 py-2 text-sm font-semibold text-lime-100">
              Mobile foundation
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/offline-inventory`} className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100">
              Offline inventory
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile-scanning`} className="rounded-2xl border border-violet-400/30 px-4 py-2 text-sm font-semibold text-violet-100">
              Mobile scanning
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/convention-mode`} className="rounded-2xl border border-orange-400/30 px-4 py-2 text-sm font-semibold text-orange-100">
              Convention mode
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/quick-sales`} className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100">
              Quick sales
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile-security`} className="rounded-2xl border border-rose-400/30 px-4 py-2 text-sm font-semibold text-rose-100">
              Mobile security
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile-analytics`} className="rounded-2xl border border-indigo-400/30 px-4 py-2 text-sm font-semibold text-indigo-100">
              Mobile analytics
            </Link>
            {canManage ? (
              <button
                type="button"
                disabled={generating}
                onClick={() => void handleGenerate()}
                className="rounded-2xl border border-emerald-400/30 px-4 py-2 text-sm font-semibold text-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {generating ? "Generating..." : "Generate"}
              </button>
            ) : null}
          </div>
        }
      />

      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}
      {message ? (
        <div className="mt-4">
          <StatusBanner tone="success">{message}</StatusBanner>
        </div>
      ) : null}
      {loading ? (
        <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm text-sm text-slate-300">
          Loading mobile ops dashboard...
        </section>
      ) : null}
      {!loading && organization && !canView ? (
        <div className="mt-6">
          <OrganizationAccessDeniedState
            title="Mobile ops access denied"
            description="Mobile ops visibility is deny-by-default and requires `organization:view`."
          />
        </div>
      ) : null}
      {!loading && organization && canView && dashboard ? (
        <>
          <section className="mt-6 grid gap-4 md:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Dashboard status</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">visible</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Warnings</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">
                {String((((diagnosticSummary["diagnostics"] ?? {}) as Record<string, unknown>)["warning"] ?? 0) as number)}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Latest snapshot</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">{dashboard.latest_snapshot ? `#${dashboard.latest_snapshot.id}` : "none"}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Events</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">{dashboard.events.length}</p>
            </div>
          </section>

          {!canManage ? (
            <div className="mt-4">
              <StatusBanner tone="info">
                This organization can view mobile ops visibility, but only members with `organization:update` can generate metrics, diagnostics, and snapshots.
              </StatusBanner>
            </div>
          ) : null}

          <section className="mt-6">
            <MobileOpsMetricCards metrics={dashboard.metrics} />
          </section>
          <section className="mt-6">
            <MobileOpsSummaryPanels summary={dashboard.summary} />
          </section>
          <section className="mt-6 grid gap-4 xl:grid-cols-[1fr_1fr]">
            <MobileOpsDiagnosticsPanel diagnostics={dashboard.diagnostics} />
            <MobileOpsSnapshotPanel snapshot={dashboard.latest_snapshot ?? null} />
          </section>
          <section className="mt-6">
            <MobileOpsEventTimeline events={dashboard.events} />
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
