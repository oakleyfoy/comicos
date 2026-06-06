import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type LiveSaleClaimCreateRequest,
  type LiveSaleDetailResponse,
  type LiveSaleQueueItemCreateRequest,
  type LiveSaleQueueItemUpdateRequest,
  type LiveSaleQueueReorderRequest,
  type LiveSaleSessionCreateRequest,
  type LiveSaleSessionListResponse,
  type MarketplaceAccountListResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { LiveSaleClaimForm } from "../components/marketplaces/live-sales/LiveSaleClaimForm";
import { LiveSaleClaimTable } from "../components/marketplaces/live-sales/LiveSaleClaimTable";
import { LiveSaleDetailPanel } from "../components/marketplaces/live-sales/LiveSaleDetailPanel";
import { LiveSaleQueueItemForm } from "../components/marketplaces/live-sales/LiveSaleQueueItemForm";
import { LiveSaleQueueReorderShell } from "../components/marketplaces/live-sales/LiveSaleQueueReorderShell";
import { LiveSaleQueueTable } from "../components/marketplaces/live-sales/LiveSaleQueueTable";
import { LiveSaleSessionForm } from "../components/marketplaces/live-sales/LiveSaleSessionForm";
import { LiveSaleSessionTable } from "../components/marketplaces/live-sales/LiveSaleSessionTable";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

export function LiveSalesPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [accounts, setAccounts] = useState<MarketplaceAccountListResponse | null>(null);
  const [sessions, setSessions] = useState<LiveSaleSessionListResponse | null>(null);
  const [detail, setDetail] = useState<LiveSaleDetailResponse | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionSubmitting, setSessionSubmitting] = useState(false);
  const [queueSubmitting, setQueueSubmitting] = useState(false);
  const [claimSubmitting, setClaimSubmitting] = useState(false);
  const [busySessionAction, setBusySessionAction] = useState(false);
  const [busyQueueItemId, setBusyQueueItemId] = useState<number | null>(null);
  const [busyClaimId, setBusyClaimId] = useState<number | null>(null);

  useEffect(() => {
    if (Number.isFinite(parsedOrganizationId)) {
      void refresh();
    }
  }, [parsedOrganizationId]);

  useEffect(() => {
    if (selectedSessionId != null && Number.isFinite(parsedOrganizationId)) {
      void loadDetail(selectedSessionId);
    } else {
      setDetail(null);
    }
  }, [selectedSessionId, parsedOrganizationId]);

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
        setSessions(null);
        setDetail(null);
        return;
      }
      const [accountRows, sessionRows] = await Promise.all([
        apiClient.listMarketplaceAccounts(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listLiveSaleSessions(parsedOrganizationId, { limit: 100, offset: 0 }),
      ]);
      setAccounts(accountRows);
      setSessions(sessionRows);
      if (sessionRows.items.length === 0) {
        setSelectedSessionId(null);
        setDetail(null);
      } else if (selectedSessionId == null || !sessionRows.items.some((item) => item.id === selectedSessionId)) {
        setSelectedSessionId(sessionRows.items[0].id);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load live-sale workspace.");
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(sessionId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    try {
      const body = await apiClient.getLiveSaleSession(parsedOrganizationId, sessionId);
      setDetail(body);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load live-sale detail.");
    }
  }

  async function refreshDetail(sessionId?: number): Promise<void> {
    if (sessionId != null) {
      await loadDetail(sessionId);
    } else if (selectedSessionId != null) {
      await loadDetail(selectedSessionId);
    }
    await refresh();
  }

  async function handleCreateSession(payload: LiveSaleSessionCreateRequest): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setSessionSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.createLiveSaleSession(parsedOrganizationId, payload);
      setDetail(body);
      setSelectedSessionId(body.session.id);
      setMessage("Live-sale session created.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to create live-sale session.");
    } finally {
      setSessionSubmitting(false);
    }
  }

  async function handleStartSession(sessionId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusySessionAction(true);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.startLiveSaleSession(parsedOrganizationId, sessionId);
      setDetail(body);
      setMessage("Live-sale session started.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to start live-sale session.");
    } finally {
      setBusySessionAction(false);
    }
  }

  async function handleEndSession(sessionId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusySessionAction(true);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.endLiveSaleSession(parsedOrganizationId, sessionId);
      setDetail(body);
      setMessage("Live-sale session ended.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to end live-sale session.");
    } finally {
      setBusySessionAction(false);
    }
  }

  async function handleAddQueueItem(payload: LiveSaleQueueItemCreateRequest): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || selectedSessionId == null) {
      return;
    }
    setQueueSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.addLiveSaleQueueItem(parsedOrganizationId, selectedSessionId, payload);
      setMessage(`Queue item ${body.id} added.`);
      await refreshDetail(selectedSessionId);
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to add live-sale queue item.");
    } finally {
      setQueueSubmitting(false);
    }
  }

  async function handleReorderQueue(payload: LiveSaleQueueReorderRequest): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || selectedSessionId == null) {
      return;
    }
    setQueueSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.reorderLiveSaleQueue(parsedOrganizationId, selectedSessionId, payload);
      setDetail((current) => (current ? { ...current, queue_items: body.items } : current));
      setMessage("Queue reordered.");
      await refreshDetail(selectedSessionId);
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to reorder live-sale queue.");
    } finally {
      setQueueSubmitting(false);
    }
  }

  async function handleQueueStatus(
    queueItemId: number,
    itemStatus: "active" | "sold" | "passed" | "removed",
    actualSalePrice?: string | null,
  ): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || selectedSessionId == null) {
      return;
    }
    setBusyQueueItemId(queueItemId);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.updateLiveSaleQueueItemStatus(parsedOrganizationId, selectedSessionId, queueItemId, {
        item_status: itemStatus,
        actual_sale_price: actualSalePrice ?? null,
      });
      setDetail(body);
      setMessage(`Queue item updated to ${itemStatus}.`);
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to update queue item status.");
    } finally {
      setBusyQueueItemId(null);
    }
  }

  async function handleCreateClaim(payload: LiveSaleClaimCreateRequest): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || selectedSessionId == null) {
      return;
    }
    setClaimSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.createLiveSaleClaim(parsedOrganizationId, selectedSessionId, payload);
      setMessage(`Claim ${body.id} created.`);
      await refreshDetail(selectedSessionId);
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to create live-sale claim.");
    } finally {
      setClaimSubmitting(false);
    }
  }

  async function handleClaimStatus(claimId: number, claimStatus: "claimed" | "confirmed" | "cancelled"): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || selectedSessionId == null) {
      return;
    }
    setBusyClaimId(claimId);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.updateLiveSaleClaim(parsedOrganizationId, selectedSessionId, claimId, {
        claim_status: claimStatus,
      });
      setMessage(`Claim updated to ${claimStatus}.`);
      await refreshDetail(selectedSessionId);
      if (body.id) {
        setDetail((current) =>
          current
            ? {
                ...current,
                claims: current.claims.map((claim) => (claim.id === body.id ? body : claim)),
              }
            : current,
        );
      }
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to update live-sale claim.");
    } finally {
      setBusyClaimId(null);
    }
  }

  const canView = organization ? hasOrganizationPermission(organization, "organization:view") : false;
  const canManage = organization ? hasOrganizationPermission(organization, "organization:update") : false;

  const sessionItems = sessions?.items ?? [];
  const selectedDetail = detail;
  const currentClaims = selectedDetail?.claims ?? [];
  const currentQueue = selectedDetail?.queue_items ?? [];

  const selectedSession = useMemo(
    () => sessionItems.find((item) => item.id === selectedSessionId) ?? null,
    [sessionItems, selectedSessionId],
  );

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
        eyebrow="P43-07"
        title={organization ? `${organization.display_name} live-sales` : "Live-sales"}
        description="Deterministic Whatnot/live-sale workflow planning, queue ordering, claim tracking, and append-only live-sale lineage."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to={`/organizations/${parsedOrganizationId}`} className="rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-200">
              Organization
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplaces`} className="rounded-2xl border border-indigo-400/30 px-4 py-2 text-sm font-semibold text-indigo-100">
              Accounts
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-listings`} className="rounded-2xl border border-emerald-400/30 px-4 py-2 text-sm font-semibold text-emerald-100">
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
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-ops`} className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100">
              Ops dashboard
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-analytics`} className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100">
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
        <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm text-sm text-slate-300">
          Loading live-sale workspace...
        </section>
      ) : null}
      {!loading && organization && !canView ? (
        <div className="mt-6">
          <OrganizationAccessDeniedState
            title="Live-sale access denied"
            description="Live-sale visibility is deny-by-default and requires `organization:view`."
          />
        </div>
      ) : null}
      {!loading && organization && canView ? (
        <>
          <section className="mt-6 grid gap-4 md:grid-cols-4">
            <StatCard label="Sessions" value={String(sessions?.summary.total_sessions ?? 0)} />
            <StatCard label="Live" value={String(sessions?.summary.live_sessions ?? 0)} />
            <StatCard label="Planned" value={String(sessions?.summary.planned_sessions ?? 0)} />
            <StatCard label="Ended" value={String(sessions?.summary.ended_sessions ?? 0)} />
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <LiveSaleSessionForm accounts={accounts?.items ?? []} canManage={canManage} submitting={sessionSubmitting} onSubmit={handleCreateSession} />
            <LiveSaleDetailPanel detail={selectedDetail} canManage={canManage} busySessionAction={busySessionAction} onStart={handleStartSession} onEnd={handleEndSession} />
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <LiveSaleSessionTable items={sessionItems} selectedSessionId={selectedSessionId} onSelect={setSelectedSessionId} />
            <LiveSaleQueueItemForm canManage={canManage} submitting={queueSubmitting} onSubmit={handleAddQueueItem} />
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <LiveSaleQueueTable items={currentQueue} canManage={canManage} busyQueueItemId={busyQueueItemId} onUpdateStatus={handleQueueStatus} />
            <LiveSaleQueueReorderShell canManage={canManage} submitting={queueSubmitting} onSubmit={handleReorderQueue} />
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <LiveSaleClaimTable
              items={currentClaims}
              summary={selectedDetail ? { total_claims: selectedDetail.claims.length, claimed_claims: currentClaims.filter((claim) => claim.claim_status === "claimed").length, confirmed_claims: currentClaims.filter((claim) => claim.claim_status === "confirmed").length, cancelled_claims: currentClaims.filter((claim) => claim.claim_status === "cancelled").length } : null}
              canManage={canManage}
              busyClaimId={busyClaimId}
              onUpdateStatus={handleClaimStatus}
            />
            <LiveSaleClaimForm canManage={canManage} submitting={claimSubmitting} onSubmit={handleCreateClaim} />
          </section>

          {selectedSession ? (
            <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm text-sm text-slate-400">
              Selected session #{selectedSession.id} is {selectedSession.session_status}.
            </section>
          ) : null}
        </>
      ) : null}
    </AppShell>
  );
}
