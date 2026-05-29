import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MarketplaceAnalyticsDashboardResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { MarketplaceAnalyticsEventTimelineShell } from "../components/marketplaces/analytics/MarketplaceAnalyticsEventTimelineShell";
import { MarketplaceAnalyticsKpiCards } from "../components/marketplaces/analytics/MarketplaceAnalyticsKpiCards";
import { MarketplaceAnalyticsMetricTable } from "../components/marketplaces/analytics/MarketplaceAnalyticsMetricTable";
import { MarketplaceAnalyticsSnapshotPanel } from "../components/marketplaces/analytics/MarketplaceAnalyticsSnapshotPanel";
import { MarketplaceAnalyticsSummaryCards } from "../components/marketplaces/analytics/MarketplaceAnalyticsSummaryCards";
import { MarketplaceAnalyticsTrendPanels } from "../components/marketplaces/analytics/MarketplaceAnalyticsTrendPanels";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function MarketplaceAnalyticsPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [dashboard, setDashboard] = useState<MarketplaceAnalyticsDashboardResponse | null>(null);
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
      const body = await apiClient.getMarketplaceAnalyticsDashboard(parsedOrganizationId);
      setDashboard(body);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load marketplace analytics.");
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateAnalytics(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setGenerating(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.generateMarketplaceAnalyticsSnapshot(parsedOrganizationId);
      setMessage("Marketplace analytics generated.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to generate marketplace analytics.");
    } finally {
      setGenerating(false);
    }
  }

  const canView = dashboard?.permissions.can_view ?? (organization ? hasOrganizationPermission(organization, "organization:view") : false);
  const canManage = dashboard?.permissions.can_manage ?? (organization ? hasOrganizationPermission(organization, "organization:update") : false);

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
        eyebrow="P43-10"
        title={organization ? `${organization.display_name} marketplace analytics` : "Marketplace analytics"}
        description="Deterministic KPI snapshots, performance trends, and replay-safe marketplace analytics lineage."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to={`/organizations/${parsedOrganizationId}`} className="rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-200">
              Organization
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-ops`} className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100">
              Ops dashboard
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplaces`} className="rounded-2xl border border-indigo-400/30 px-4 py-2 text-sm font-semibold text-indigo-100">
              Accounts
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-listings`} className="rounded-2xl border border-fuchsia-400/30 px-4 py-2 text-sm font-semibold text-fuchsia-100">
              Listings
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
            <Link to={`/organizations/${parsedOrganizationId}/shopify`} className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100">
              Shopify sync
            </Link>
            {canManage ? (
              <button
                type="button"
                disabled={generating}
                onClick={() => void handleGenerateAnalytics()}
                className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {generating ? "Generating..." : "Generate analytics"}
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
        <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5 text-sm text-slate-300">
          Loading marketplace analytics...
        </section>
      ) : null}
      {!loading && organization && !canView ? (
        <div className="mt-6">
          <OrganizationAccessDeniedState
            title="Marketplace analytics access denied"
            description="Marketplace analytics visibility is deny-by-default and requires `organization:view`."
          />
        </div>
      ) : null}
      {!loading && organization && canView && dashboard ? (
        <>
          <section className="mt-6 grid gap-4 md:grid-cols-4">
            <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Analytics status</p>
              <p className="mt-2 text-2xl font-semibold text-white">visible</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Snapshots</p>
              <p className="mt-2 text-2xl font-semibold text-white">{dashboard.snapshots.length}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Metrics</p>
              <p className="mt-2 text-2xl font-semibold text-white">{dashboard.metrics.length}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Trends</p>
              <p className="mt-2 text-2xl font-semibold text-white">{dashboard.trends.length}</p>
            </div>
          </section>

          {!canManage ? (
            <div className="mt-4">
              <StatusBanner tone="info">
                This organization can view analytics, but only members with `organization:update` can generate snapshots.
              </StatusBanner>
            </div>
          ) : null}

          <section className="mt-6">
            <MarketplaceAnalyticsKpiCards metrics={dashboard.metrics} summary={dashboard.summary} />
          </section>
          <section className="mt-6">
            <MarketplaceAnalyticsMetricTable metrics={dashboard.metrics} />
          </section>
          <section className="mt-6">
            <MarketplaceAnalyticsTrendPanels trends={dashboard.trends} />
          </section>
          <section className="mt-6">
            <MarketplaceAnalyticsSummaryCards summary={dashboard.summary} />
          </section>
          <section className="mt-6 grid gap-4 xl:grid-cols-[1fr_1fr]">
            <MarketplaceAnalyticsSnapshotPanel snapshot={dashboard.latest_snapshot ?? null} />
            <MarketplaceAnalyticsEventTimelineShell events={dashboard.events} />
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
