import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MarketplaceAccountListResponse,
  type MarketplaceEventDetailResponse,
  type MarketplaceEventIngestRequest,
  type MarketplaceEventProcessingRunListResponse,
  type MarketplaceEventListResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { MarketplaceEventDetailPanel } from "../components/marketplaces/events/MarketplaceEventDetailPanel";
import { MarketplaceEventIngestShell } from "../components/marketplaces/events/MarketplaceEventIngestShell";
import { MarketplaceEventLineageViewer } from "../components/marketplaces/events/MarketplaceEventLineageViewer";
import { MarketplaceEventProcessingRunTable } from "../components/marketplaces/events/MarketplaceEventProcessingRunTable";
import { MarketplaceEventTable } from "../components/marketplaces/events/MarketplaceEventTable";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function MarketplaceEventsPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [accounts, setAccounts] = useState<MarketplaceAccountListResponse | null>(null);
  const [events, setEvents] = useState<MarketplaceEventListResponse | null>(null);
  const [runs, setRuns] = useState<MarketplaceEventProcessingRunListResponse | null>(null);
  const [detail, setDetail] = useState<MarketplaceEventDetailResponse | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busyEventId, setBusyEventId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (Number.isFinite(parsedOrganizationId)) {
      void refresh();
    }
  }, [parsedOrganizationId]);

  useEffect(() => {
    if (selectedEventId != null && Number.isFinite(parsedOrganizationId)) {
      void loadDetail(selectedEventId);
    } else {
      setDetail(null);
    }
  }, [selectedEventId, parsedOrganizationId]);

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
        setAccounts(null);
        setEvents(null);
        setRuns(null);
        return;
      }
      const [accountRows, eventRows, runRows] = await Promise.all([
        apiClient.listMarketplaceAccounts(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listMarketplaceEvents(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listMarketplaceEventRuns(parsedOrganizationId, { limit: 100, offset: 0 }),
      ]);
      setAccounts(accountRows);
      setEvents(eventRows);
      setRuns(runRows);
      if (eventRows.items.length === 0) {
        setSelectedEventId(null);
      } else if (selectedEventId == null || !eventRows.items.some((item) => item.id === selectedEventId)) {
        setSelectedEventId(eventRows.items[0].id);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load marketplace events.");
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(eventId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    try {
      const body = await apiClient.getMarketplaceEvent(parsedOrganizationId, eventId);
      setDetail(body);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load marketplace event detail.");
    }
  }

  async function handleIngest(payload: MarketplaceEventIngestRequest): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.ingestMarketplaceEvent(parsedOrganizationId, payload);
      setDetail(body);
      setSelectedEventId(body.event.id);
      setMessage(body.event.event_status === "failed" ? "Event ingested with validation errors." : "Marketplace event ingested.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to ingest marketplace event.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleProcess(eventId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyEventId(eventId);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.processMarketplaceEvent(parsedOrganizationId, { marketplace_event_id: eventId });
      setDetail(body);
      setMessage("Marketplace event processed.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to process marketplace event.");
    } finally {
      setBusyEventId(null);
    }
  }

  const canView = organization ? hasOrganizationPermission(organization, "organization:view") : false;
  const canManage = organization ? hasOrganizationPermission(organization, "organization:update") : false;

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
        eyebrow="P43-06"
        title={organization ? `${organization.display_name} marketplace events` : "Marketplace events"}
        description="Deterministic webhook/event ingestion, validation, processing runs, and append-only event lineage for organization-scoped integrations."
        actions={
          <div className="flex gap-2">
            <Link to={`/organizations/${parsedOrganizationId}`} className="rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-200">
              Organization
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplaces`}
              className="rounded-2xl border border-indigo-400/30 px-4 py-2 text-sm font-semibold text-indigo-100"
            >
              Accounts
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-pricing`}
              className="rounded-2xl border border-violet-400/30 px-4 py-2 text-sm font-semibold text-violet-100"
            >
              Pricing
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-orders`}
              className="rounded-2xl border border-teal-400/30 px-4 py-2 text-sm font-semibold text-teal-100"
            >
              Orders
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
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-analytics`}
              className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100"
            >
              Analytics
            </Link>
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
          Loading marketplace event workspace...
        </section>
      ) : null}
      {!loading && organization && !canView ? (
        <div className="mt-6">
          <OrganizationAccessDeniedState
            title="Marketplace events access denied"
            description="Event visibility is deny-by-default and requires `organization:view`."
          />
        </div>
      ) : null}
      {!loading && organization && canView ? (
        <>
          <section className="mt-6 grid gap-4 md:grid-cols-4">
            <StatCard label="Events" value={String(events?.items.length ?? 0)} />
            <StatCard label="Received" value={String(events?.summary.received_events ?? 0)} />
            <StatCard label="Processed" value={String(events?.summary.processed_events ?? 0)} />
            <StatCard label="Failed" value={String(events?.summary.failed_events ?? 0)} />
          </section>
          <section className="mt-4 grid gap-6 xl:grid-cols-[0.96fr,1.04fr]">
            <div className="space-y-6">
              <MarketplaceEventIngestShell
                accounts={accounts?.items ?? []}
                canManage={canManage}
                submitting={submitting}
                onSubmit={handleIngest}
              />
              <MarketplaceEventTable
                items={events?.items ?? []}
                selectedEventId={selectedEventId}
                onSelect={setSelectedEventId}
              />
            </div>
            <div className="space-y-6">
              <MarketplaceEventDetailPanel
                detail={detail}
                canManage={canManage}
                busy={busyEventId === detail?.event.id}
                onProcess={handleProcess}
              />
              <MarketplaceEventLineageViewer lineage={detail?.lineage ?? []} />
            </div>
          </section>
          <section className="mt-6">
            <MarketplaceEventProcessingRunTable items={runs?.items ?? []} />
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
