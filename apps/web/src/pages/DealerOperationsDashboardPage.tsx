import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type OrganizationDealerDashboardSnapshotResponse,
  type OrganizationDealerDashboardSummaryResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { DealerDashboardMetricCards } from "../components/dashboard/DealerDashboardMetricCards";
import { DealerDashboardSectionPanels } from "../components/dashboard/DealerDashboardSectionPanels";
import { DealerDashboardTimelineShell } from "../components/dashboard/DealerDashboardTimelineShell";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { hasOrganizationPermission } from "../lib/organizationPermissions";
import { formatDateTime } from "../components/dashboard/dealerDashboardLabels";

export function DealerOperationsDashboardPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [summary, setSummary] = useState<OrganizationDealerDashboardSummaryResponse | null>(null);
  const [snapshots, setSnapshots] = useState<OrganizationDealerDashboardSnapshotResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(
    async (options?: { refreshMetrics?: boolean }): Promise<void> => {
      if (!Number.isFinite(parsedOrganizationId)) {
        return;
      }
      setError(null);
      try {
        const org = await apiClient.getOrganization(parsedOrganizationId);
        setOrganization(org);
        if (!hasOrganizationPermission(org, "operations:view")) {
          setSummary(null);
          setSnapshots([]);
          return;
        }
        const [dashboard, snapshotList] = await Promise.all([
          apiClient.getOrganizationDealerDashboard(parsedOrganizationId, {
            refresh: options?.refreshMetrics ?? true,
          }),
          apiClient.listOrganizationDealerDashboardSnapshots(parsedOrganizationId, { limit: 20, offset: 0 }),
        ]);
        setSummary(dashboard);
        setSnapshots(snapshotList.items);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Unable to load dealer operations dashboard.");
      }
    },
    [parsedOrganizationId],
  );

  useEffect(() => {
    setLoading(true);
    void refresh().finally(() => setLoading(false));
  }, [refresh]);

  async function handleRefresh(): Promise<void> {
    setRefreshing(true);
    try {
      await refresh({ refreshMetrics: true });
    } finally {
      setRefreshing(false);
    }
  }

  if (!Number.isFinite(parsedOrganizationId)) {
    return (
      <AppShell>
        <EmptyState title="Invalid organization" description="The organization id in the URL is not valid." />
      </AppShell>
    );
  }

  const canView = organization ? hasOrganizationPermission(organization, "operations:view") : false;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Organization workspace"
        title="Dealer operations dashboard"
        description="Unified operational visibility for inventory, reviews, storefront, activity, notifications, and security signals."
        actions={
          organization ? (
            <div className="flex flex-wrap gap-2">
              {canView ? (
                <button
                  type="button"
                  disabled={refreshing}
                  onClick={() => void handleRefresh()}
                  className="rounded-2xl border border-cyan-400/35 px-4 py-2 text-sm font-semibold text-cyan-100 disabled:opacity-50"
                >
                  {refreshing ? "Refreshing…" : "Refresh metrics"}
                </button>
              ) : null}
              <Link
                to={`/organizations/${organization.id}`}
                className="rounded-2xl border border-white/15 px-4 py-2 text-sm font-semibold text-slate-200"
              >
                Back to organization
              </Link>
              <Link
                to={`/organizations/${organization.id}/shopify`}
                className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100"
              >
                Shopify sync
              </Link>
            </div>
          ) : null
        }
      />
      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}
      {loading || !organization ? (
        <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5 text-sm text-slate-300">
          Loading dealer operations dashboard…
        </section>
      ) : !canView ? (
        <div className="mt-6">
          <OrganizationAccessDeniedState
            title="Dashboard unavailable"
            description="You do not have permission to view organization operational metrics (`operations:view`)."
          />
        </div>
      ) : summary ? (
        <div className="mt-6 space-y-6">
          <section className="rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900/80 to-slate-950/80 p-5">
            <p className="text-[11px] uppercase tracking-[0.16em] text-emerald-200/80">Overview</p>
            <h2 className="mt-1 text-xl font-semibold text-white">{organization.display_name}</h2>
            <p className="mt-2 text-sm text-slate-400">
              Backend-authoritative snapshot generated {formatDateTime(summary.generated_at)}
              {summary.snapshot ? ` · snapshot #${summary.snapshot.id}` : ""}.
            </p>
          </section>
          <DealerDashboardMetricCards sections={summary.sections} />
          <DealerDashboardSectionPanels organizationId={organization.id} sections={summary.sections} />
          <DealerDashboardTimelineShell snapshots={snapshots} />
        </div>
      ) : (
        <EmptyState title="Dashboard unavailable" description="Operational summary could not be loaded for this organization." />
      )}
    </AppShell>
  );
}
