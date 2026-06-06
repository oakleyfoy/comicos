import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MarketplaceOpsDashboardResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { MarketplaceOpsDiagnosticsPanel } from "../components/marketplaces/ops/MarketplaceOpsDiagnosticsPanel";
import { MarketplaceOpsEventTimelineShell } from "../components/marketplaces/ops/MarketplaceOpsEventTimelineShell";
import { MarketplaceOpsMetricCards } from "../components/marketplaces/ops/MarketplaceOpsMetricCards";
import { MarketplaceOpsSnapshotPanel } from "../components/marketplaces/ops/MarketplaceOpsSnapshotPanel";
import { MarketplaceOpsSummaryPanels } from "../components/marketplaces/ops/MarketplaceOpsSummaryPanels";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function MarketplaceOpsDashboardPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [dashboard, setDashboard] = useState<MarketplaceOpsDashboardResponse | null>(null);
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
      const body = await apiClient.getMarketplaceOpsDashboard(parsedOrganizationId);
      setDashboard(body);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load marketplace ops dashboard.");
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateDiagnostics(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setGenerating(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.generateMarketplaceOpsDiagnostics(parsedOrganizationId);
      setMessage("Marketplace diagnostics generated.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to generate marketplace diagnostics.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleGenerateSnapshot(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setGenerating(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.generateMarketplaceOpsSnapshot(parsedOrganizationId);
      setMessage("Marketplace ops snapshot generated.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to generate marketplace ops snapshot.");
    } finally {
      setGenerating(false);
    }
  }

  const canView = dashboard?.permissions.can_view ?? (organization ? hasOrganizationPermission(organization, "organization:view") : false);
  const canManage = dashboard?.permissions.can_manage ?? (organization ? hasOrganizationPermission(organization, "organization:update") : false);
  const diagnosticsSummary = (dashboard?.summary["diagnostics"] ?? {}) as Record<string, unknown>;

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
        eyebrow="P43-09"
        title={organization ? `${organization.display_name} marketplace ops` : "Marketplace ops dashboard"}
        description="Deterministic marketplace operations visibility, diagnostics, snapshots, and replay-safe lineage."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to={`/organizations/${parsedOrganizationId}`} className="rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-200">
              Organization
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplaces`} className="rounded-2xl border border-indigo-400/30 px-4 py-2 text-sm font-semibold text-indigo-100">
              Accounts
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-listings`} className="rounded-2xl border border-fuchsia-400/30 px-4 py-2 text-sm font-semibold text-fuchsia-100">
              Listings
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-sync`} className="rounded-2xl border border-amber-400/30 px-4 py-2 text-sm font-semibold text-amber-100">
              Sync
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-orders`} className="rounded-2xl border border-teal-400/30 px-4 py-2 text-sm font-semibold text-teal-100">
              Orders
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-pricing`} className="rounded-2xl border border-violet-400/30 px-4 py-2 text-sm font-semibold text-violet-100">
              Pricing
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-events`} className="rounded-2xl border border-emerald-400/30 px-4 py-2 text-sm font-semibold text-emerald-100">
              Events
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/live-sales`} className="rounded-2xl border border-rose-400/30 px-4 py-2 text-sm font-semibold text-rose-100">
              Live sales
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-analytics`} className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100">
              Analytics
            </Link>
            {canManage ? (
              <>
                <button
                  type="button"
                  disabled={generating}
                  onClick={() => void handleGenerateDiagnostics()}
                  className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {generating ? "Generating..." : "Generate diagnostics"}
                </button>
                <button
                  type="button"
                  disabled={generating}
                  onClick={() => void handleGenerateSnapshot()}
                  className="rounded-2xl border border-emerald-400/30 px-4 py-2 text-sm font-semibold text-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {generating ? "Generating..." : "Generate snapshot"}
                </button>
              </>
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
          Loading marketplace ops dashboard...
        </section>
      ) : null}
      {!loading && organization && !canView ? (
        <div className="mt-6">
          <OrganizationAccessDeniedState
            title="Marketplace ops access denied"
            description="Marketplace ops visibility is deny-by-default and requires `organization:view`."
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
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Diagnostics</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">{String((diagnosticsSummary.warning ?? 0) as number)} warnings</p>
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
                This organization can view marketplace ops visibility, but only members with `organization:update` can generate diagnostics or snapshots.
              </StatusBanner>
            </div>
          ) : null}

          <section className="mt-6">
            <MarketplaceOpsMetricCards metrics={dashboard.metrics} summary={dashboard.summary} />
          </section>
          <section className="mt-6">
            <MarketplaceOpsSummaryPanels summary={dashboard.summary} />
          </section>
          <section className="mt-6 grid gap-4 xl:grid-cols-[1fr_1fr]">
            <MarketplaceOpsDiagnosticsPanel diagnostics={dashboard.diagnostics} />
            <MarketplaceOpsSnapshotPanel snapshot={dashboard.latest_snapshot ?? null} />
          </section>
          <section className="mt-6">
            <MarketplaceOpsEventTimelineShell events={dashboard.events} />
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
