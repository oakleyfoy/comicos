import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ConventionActivityListResponse,
  type ConventionBoothListResponse,
  type ConventionInventoryStageListResponse,
  type ConventionModeDashboardResponse,
  type ConventionSessionListResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { ConventionActivityTimeline } from "../components/mobile/convention/ConventionActivityTimeline";
import { ConventionBoothManager } from "../components/mobile/convention/ConventionBoothManager";
import { ConventionEventTimeline } from "../components/mobile/convention/ConventionEventTimeline";
import { ConventionSessionManager } from "../components/mobile/convention/ConventionSessionManager";
import { ConventionStagedInventoryViewer } from "../components/mobile/convention/ConventionStagedInventoryViewer";
import { ConventionSummaryCards } from "../components/mobile/convention/ConventionSummaryCards";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function ConventionModePage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [dashboard, setDashboard] = useState<ConventionModeDashboardResponse | null>(null);
  const [sessions, setSessions] = useState<ConventionSessionListResponse | null>(null);
  const [booths, setBooths] = useState<ConventionBoothListResponse | null>(null);
  const [staged, setStaged] = useState<ConventionInventoryStageListResponse | null>(null);
  const [activities, setActivities] = useState<ConventionActivityListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [sessionName, setSessionName] = useState("");
  const [boothName, setBoothName] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [inventoryItemId, setInventoryItemId] = useState("1001");

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
      const [dash, sessionList, boothList, stageList, activityList] = await Promise.all([
        apiClient.getConventionModeDashboard(parsedOrganizationId),
        apiClient.listConventionSessions(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listConventionBooths(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listConventionStagedInventory(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listConventionActivities(parsedOrganizationId, { limit: 100, offset: 0 }),
      ]);
      setDashboard(dash);
      setSessions(sessionList);
      setBooths(boothList);
      setStaged(stageList);
      setActivities(activityList);
      if (sessionList.items.length > 0 && selectedSessionId === null) {
        setSelectedSessionId(sessionList.items[0].id);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load convention mode.");
    } finally {
      setLoading(false);
    }
  }

  const canView =
    dashboard?.permissions.can_view ?? (organization ? hasOrganizationPermission(organization, "organization:view") : false);
  const canManage =
    dashboard?.permissions.can_manage ?? (organization ? hasOrganizationPermission(organization, "organization:update") : false);

  async function handleCreateSession(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || !sessionName.trim()) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.createConventionSession(parsedOrganizationId, { session_name: sessionName.trim() });
      setSessionName("");
      setMessage("Convention session created.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to create session.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStartSession(sessionId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setSubmitting(true);
    try {
      await apiClient.updateConventionSession(parsedOrganizationId, sessionId, { session_status: "active" });
      setMessage("Convention session started.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to start session.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCreateBooth(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || selectedSessionId === null || !boothName.trim()) {
      return;
    }
    setSubmitting(true);
    try {
      await apiClient.createConventionBooth(parsedOrganizationId, {
        convention_session_id: selectedSessionId,
        booth_name: boothName.trim(),
      });
      setBoothName("");
      setMessage("Booth created.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to create booth.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleOpenBooth(boothId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setSubmitting(true);
    try {
      await apiClient.updateConventionBooth(parsedOrganizationId, boothId, { booth_status: "active" });
      setMessage("Booth opened.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to open booth.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStageInventory(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || selectedSessionId === null) {
      return;
    }
    const itemId = Number(inventoryItemId);
    if (!Number.isFinite(itemId)) {
      return;
    }
    setSubmitting(true);
    try {
      await apiClient.stageConventionInventory(parsedOrganizationId, {
        convention_session_id: selectedSessionId,
        inventory_item_id: itemId,
      });
      setMessage("Inventory staged for convention.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to stage inventory.");
    } finally {
      setSubmitting(false);
    }
  }

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
        eyebrow="P44-04"
        title={organization ? `${organization.display_name} convention mode` : "Convention mode"}
        description="Convention sessions, booth operations, floor inventory staging, and replay-safe lineage."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to={`/organizations/${parsedOrganizationId}/mobile-ops`} className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100">
              Mobile ops
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/quick-sales`} className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100">
              Quick sales
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile-scanning`} className="rounded-2xl border border-violet-400/30 px-4 py-2 text-sm font-semibold text-violet-100">
              Scanning
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile`} className="rounded-2xl border border-lime-400/30 px-4 py-2 text-sm font-semibold text-lime-100">
              Mobile foundation
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile-analytics`} className="rounded-2xl border border-indigo-400/30 px-4 py-2 text-sm font-semibold text-indigo-100">
              Mobile analytics
            </Link>
          </div>
        }
      />

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}
      {message ? (
        <div className="mt-6">
          <StatusBanner tone="success">{message}</StatusBanner>
        </div>
      ) : null}

      {loading ? <p className="mt-8 text-sm text-slate-400">Loading convention mode…</p> : null}

      {!loading && organization && !canView ? (
        <OrganizationAccessDeniedState
          title="Convention access denied"
          description="You need organization view permission to inspect convention operations."
        />
      ) : null}

      {!loading && canView && dashboard ? (
        <div className="mt-8 space-y-10">
          <ConventionSummaryCards summary={dashboard.summary} />

          <section>
            <h2 className="text-lg font-semibold text-white">Sessions</h2>
            <div className="mt-4">
              <ConventionSessionManager
                sessions={sessions?.items ?? []}
                canManage={canManage}
                submitting={submitting}
                sessionName={sessionName}
                onSessionNameChange={setSessionName}
                onCreate={() => void handleCreateSession()}
                onStart={(id) => void handleStartSession(id)}
              />
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white">Booths</h2>
            <div className="mt-4">
              <ConventionBoothManager
                booths={booths?.items ?? []}
                canManage={canManage}
                submitting={submitting}
                boothName={boothName}
                sessionId={selectedSessionId}
                sessions={sessions?.items ?? []}
                onBoothNameChange={setBoothName}
                onSessionIdChange={setSelectedSessionId}
                onCreate={() => void handleCreateBooth()}
                onOpen={(id) => void handleOpenBooth(id)}
              />
            </div>
          </section>

          {canManage && selectedSessionId !== null ? (
            <section>
              <h2 className="text-lg font-semibold text-white">Stage inventory</h2>
              <div className="mt-4 flex flex-wrap gap-2">
                <input
                  value={inventoryItemId}
                  onChange={(e) => setInventoryItemId(e.target.value)}
                  className="w-32 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                />
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => void handleStageInventory()}
                  className="rounded-xl border border-amber-400/40 px-4 py-2 text-sm font-semibold text-amber-100 disabled:opacity-50"
                >
                  Stage item
                </button>
              </div>
            </section>
          ) : null}

          <section>
            <h2 className="text-lg font-semibold text-white">Staged inventory</h2>
            <div className="mt-4">
              <ConventionStagedInventoryViewer items={staged?.items ?? []} />
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white">Activities</h2>
            <div className="mt-4">
              <ConventionActivityTimeline activities={activities?.items ?? []} />
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white">Convention events</h2>
            <div className="mt-4">
              <ConventionEventTimeline events={dashboard.recent_events} />
            </div>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
