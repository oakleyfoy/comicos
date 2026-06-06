import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MobileAnalyticsDashboardResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { MobileAnalyticsEventTimeline } from "../components/mobile/analytics/MobileAnalyticsEventTimeline";
import { MobileAnalyticsKpiCards } from "../components/mobile/analytics/MobileAnalyticsKpiCards";
import { MobileAnalyticsMetricTable } from "../components/mobile/analytics/MobileAnalyticsMetricTable";
import { MobileAnalyticsOverviewPanels } from "../components/mobile/analytics/MobileAnalyticsOverviewPanels";
import { MobileAnalyticsSnapshotViewer } from "../components/mobile/analytics/MobileAnalyticsSnapshotViewer";
import { MobileAnalyticsTrendPanels } from "../components/mobile/analytics/MobileAnalyticsTrendPanels";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function MobileAnalyticsPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [dashboard, setDashboard] = useState<MobileAnalyticsDashboardResponse | null>(null);
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
      const body = await apiClient.getMobileAnalyticsDashboard(parsedOrganizationId);
      setDashboard(body);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load mobile analytics.");
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
      const body = await apiClient.generateMobileAnalytics(parsedOrganizationId);
      setDashboard(body);
      setMessage("Mobile analytics snapshot, metrics, and trends generated.");
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to generate mobile analytics.");
    } finally {
      setGenerating(false);
    }
  }

  const canView = dashboard?.permissions.can_view ?? (organization ? hasOrganizationPermission(organization, "organization:view") : false);
  const canManage = dashboard?.permissions.can_manage ?? (organization ? hasOrganizationPermission(organization, "organization:update") : false);

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
        eyebrow="P44-08"
        title={organization ? `${organization.display_name} mobile analytics` : "Mobile analytics"}
        description="Deterministic mobile KPI, trend, and performance snapshot infrastructure across devices, offline workflows, scanning, convention operations, quick sales, and security state."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to={`/organizations/${parsedOrganizationId}/mobile`} className="rounded-2xl border border-lime-400/30 px-4 py-2 text-sm font-semibold text-lime-100">
              Mobile foundation
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile-ops`} className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100">
              Mobile ops
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile-security`} className="rounded-2xl border border-rose-400/30 px-4 py-2 text-sm font-semibold text-rose-100">
              Mobile security
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
          Loading mobile analytics...
        </section>
      ) : null}
      {!loading && organization && !canView ? (
        <div className="mt-6">
          <OrganizationAccessDeniedState
            title="Mobile analytics access denied"
            description="Mobile analytics visibility is deny-by-default and requires `organization:view`."
          />
        </div>
      ) : null}
      {!loading && organization && canView && dashboard ? (
        <>
          {!canManage ? (
            <div className="mt-4">
              <StatusBanner tone="info">
                This organization can view mobile analytics, but only members with `organization:update` can generate new KPI, trend, and snapshot rows.
              </StatusBanner>
            </div>
          ) : null}

          <section className="mt-6">
            <MobileAnalyticsKpiCards metrics={dashboard.metrics} />
          </section>
          <section className="mt-6">
            <MobileAnalyticsOverviewPanels summary={dashboard.summary} />
          </section>
          <section className="mt-6">
            <MobileAnalyticsMetricTable metrics={dashboard.metrics} />
          </section>
          <section className="mt-6">
            <MobileAnalyticsTrendPanels trends={dashboard.trends} />
          </section>
          <section className="mt-6 grid gap-4 xl:grid-cols-[1fr_1fr]">
            <MobileAnalyticsSnapshotViewer snapshot={dashboard.latest_snapshot} />
            <MobileAnalyticsEventTimeline events={dashboard.events} />
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
