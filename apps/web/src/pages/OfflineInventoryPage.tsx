import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MobileDeviceListResponse,
  type OfflineInventoryChangeListResponse,
  type OfflineInventoryDashboardResponse,
  type OfflineSyncConflictListResponse,
  type OfflineSyncQueueListResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OfflineConflictViewer } from "../components/mobile/offline/OfflineConflictViewer";
import { OfflineInventoryEventTimeline } from "../components/mobile/offline/OfflineInventoryEventTimeline";
import { OfflineInventorySummaryPanel } from "../components/mobile/offline/OfflineInventorySummaryPanel";
import { OfflineInventoryTable } from "../components/mobile/offline/OfflineInventoryTable";
import { OfflineSyncQueueViewer } from "../components/mobile/offline/OfflineSyncQueueViewer";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function OfflineInventoryPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [dashboard, setDashboard] = useState<OfflineInventoryDashboardResponse | null>(null);
  const [changes, setChanges] = useState<OfflineInventoryChangeListResponse | null>(null);
  const [queue, setQueue] = useState<OfflineSyncQueueListResponse | null>(null);
  const [conflicts, setConflicts] = useState<OfflineSyncConflictListResponse | null>(null);
  const [devices, setDevices] = useState<MobileDeviceListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busyConflictId, setBusyConflictId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [localId, setLocalId] = useState("");
  const [deviceId, setDeviceId] = useState<number | null>(null);

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
      const [dash, changeList, queueList, conflictList, deviceList] = await Promise.all([
        apiClient.getOfflineInventoryDashboard(parsedOrganizationId),
        apiClient.listOfflineInventoryChanges(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listOfflineSyncQueue(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listOfflineSyncConflicts(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listMobileDevices(parsedOrganizationId, { limit: 100, offset: 0 }),
      ]);
      setDashboard(dash);
      setChanges(changeList);
      setQueue(queueList);
      setConflicts(conflictList);
      setDevices(deviceList);
      if (deviceList.items.length > 0 && deviceId === null) {
        setDeviceId(deviceList.items[0].id);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load offline inventory.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateRecord(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || !localId.trim()) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.createOfflineInventoryRecord(parsedOrganizationId, {
        local_record_identifier: localId.trim(),
        record_payload_json: { source: "offline_ui" },
      });
      setMessage("Offline inventory record saved.");
      setLocalId("");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to save offline record.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleQueueSync(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || deviceId === null) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.queueOfflineSyncOperation(parsedOrganizationId, {
        device_id: deviceId,
        queue_payload_json: { operation: "sync_inventory" },
      });
      setMessage("Sync operation queued.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to queue sync operation.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRegisterChange(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || deviceId === null) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.registerOfflineInventoryChange(parsedOrganizationId, {
        device_id: deviceId,
        change_type: "update",
        change_payload_json: { note: "offline_ui_change" },
      });
      setMessage("Inventory change registered.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to register change.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAcknowledgeConflict(conflictId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyConflictId(conflictId);
    setError(null);
    try {
      await apiClient.updateOfflineSyncConflict(parsedOrganizationId, conflictId, {
        conflict_status: "acknowledged",
      });
      setMessage("Conflict acknowledged.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to acknowledge conflict.");
    } finally {
      setBusyConflictId(null);
    }
  }

  const canView =
    dashboard?.permissions.can_view ?? (organization ? hasOrganizationPermission(organization, "organization:view") : false);
  const canManage =
    dashboard?.permissions.can_manage ?? (organization ? hasOrganizationPermission(organization, "organization:update") : false);

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
        eyebrow="P44-02"
        title={organization ? `${organization.display_name} offline inventory` : "Offline inventory"}
        description="Local inventory records, sync queue, conflict tracking, and replay-safe offline lineage."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to={`/organizations/${parsedOrganizationId}/mobile-ops`} className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100">
              Mobile ops
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/quick-sales`} className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100">
              Quick sales
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/convention-mode`} className="rounded-2xl border border-orange-400/30 px-4 py-2 text-sm font-semibold text-orange-100">
              Convention mode
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile-scanning`} className="rounded-2xl border border-violet-400/30 px-4 py-2 text-sm font-semibold text-violet-100">
              Mobile scanning
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile`} className="rounded-2xl border border-lime-400/30 px-4 py-2 text-sm font-semibold text-lime-100">
              Mobile foundation
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile-analytics`} className="rounded-2xl border border-indigo-400/30 px-4 py-2 text-sm font-semibold text-indigo-100">
              Mobile analytics
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}`} className="rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-200">
              Organization
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

      {loading ? <p className="mt-8 text-sm text-slate-400">Loading offline inventory…</p> : null}

      {!loading && organization && !canView ? (
        <OrganizationAccessDeniedState
          title="Offline inventory access denied"
          description="You need organization view permission to inspect offline inventory and sync state."
        />
      ) : null}

      {!loading && canView && dashboard ? (
        <div className="mt-8 space-y-10">
          <OfflineInventorySummaryPanel summary={dashboard.summary} runtimeRegistry={dashboard.runtime_registry} />

          <section>
            <h2 className="text-lg font-semibold text-slate-900">Offline inventory</h2>
            {canManage ? (
              <div className="mt-4 flex flex-wrap gap-2">
                <input
                  value={localId}
                  onChange={(e) => setLocalId(e.target.value)}
                  placeholder="Local record identifier"
                  className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                />
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => void handleCreateRecord()}
                  className="rounded-xl border border-lime-400/40 px-4 py-2 text-sm font-semibold text-lime-100 disabled:opacity-50"
                >
                  Save record
                </button>
              </div>
            ) : null}
            <div className="mt-4">
              <OfflineInventoryTable items={dashboard.recent_records} />
            </div>
          </section>

          {canManage ? (
            <section>
              <h2 className="text-lg font-semibold text-slate-900">Device operations</h2>
              <div className="mt-4 flex flex-wrap gap-2">
                <select
                  value={deviceId ?? ""}
                  onChange={(e) => setDeviceId(Number(e.target.value))}
                  className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                >
                  {(devices?.items ?? []).map((device) => (
                    <option key={device.id} value={device.id}>
                      {device.device_name} (#{device.id})
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={submitting || deviceId === null}
                  onClick={() => void handleRegisterChange()}
                  className="rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-200 disabled:opacity-50"
                >
                  Register change
                </button>
                <button
                  type="button"
                  disabled={submitting || deviceId === null}
                  onClick={() => void handleQueueSync()}
                  className="rounded-xl border border-sky-400/40 px-4 py-2 text-sm font-semibold text-sky-100 disabled:opacity-50"
                >
                  Queue sync
                </button>
              </div>
            </section>
          ) : null}

          <section>
            <h2 className="text-lg font-semibold text-slate-900">Sync queue</h2>
            <div className="mt-4">
              <OfflineSyncQueueViewer items={queue?.items ?? []} />
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">Changes</h2>
            <div className="mt-4 overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
              <table className="min-w-full text-left text-sm text-slate-800">
                <thead className="border-b border-white/10 bg-slate-950/60 text-[11px] uppercase tracking-[0.14em] text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Change</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Device</th>
                  </tr>
                </thead>
                <tbody>
                  {(changes?.items ?? []).map((row) => (
                    <tr key={row.id} className="border-b border-slate-100">
                      <td className="px-4 py-3 font-mono text-xs">#{row.id}</td>
                      <td className="px-4 py-3">{row.change_type}</td>
                      <td className="px-4 py-3">#{row.device_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">Conflicts</h2>
            <div className="mt-4">
              <OfflineConflictViewer
                items={conflicts?.items ?? []}
                canManage={canManage}
                busyConflictId={busyConflictId}
                onAcknowledge={(id) => void handleAcknowledgeConflict(id)}
              />
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-slate-900">Offline events</h2>
            <div className="mt-4">
              <OfflineInventoryEventTimeline events={dashboard.recent_events} />
            </div>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
