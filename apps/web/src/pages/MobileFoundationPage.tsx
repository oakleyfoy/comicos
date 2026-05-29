import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MobileDeviceListResponse,
  type MobileFoundationDashboardResponse,
  type MobileSessionListResponse,
  type OfflineSyncContractListResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { MobileDeviceRegistryTable } from "../components/mobile/MobileDeviceRegistryTable";
import { MobileFoundationEventTimeline } from "../components/mobile/MobileFoundationEventTimeline";
import { MobileSessionViewer } from "../components/mobile/MobileSessionViewer";
import { MobileStatusDashboard } from "../components/mobile/MobileStatusDashboard";
import { OfflineContractViewer } from "../components/mobile/OfflineContractViewer";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function MobileFoundationPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [dashboard, setDashboard] = useState<MobileFoundationDashboardResponse | null>(null);
  const [devices, setDevices] = useState<MobileDeviceListResponse | null>(null);
  const [sessions, setSessions] = useState<MobileSessionListResponse | null>(null);
  const [contracts, setContracts] = useState<OfflineSyncContractListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [deviceIdentifier, setDeviceIdentifier] = useState("");
  const [deviceName, setDeviceName] = useState("");
  const [deviceType, setDeviceType] = useState("tablet");
  const [contractType, setContractType] = useState("metadata");

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
        setDevices(null);
        setSessions(null);
        setContracts(null);
        return;
      }
      const [dash, deviceList, sessionList, contractList] = await Promise.all([
        apiClient.getMobileFoundationDashboard(parsedOrganizationId),
        apiClient.listMobileDevices(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listMobileSessions(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listOfflineSyncContracts(parsedOrganizationId, { limit: 100, offset: 0 }),
      ]);
      setDashboard(dash);
      setDevices(deviceList);
      setSessions(sessionList);
      setContracts(contractList);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load mobile foundation.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRegisterDevice(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || !deviceIdentifier.trim() || !deviceName.trim()) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.registerMobileDevice(parsedOrganizationId, {
        device_identifier: deviceIdentifier.trim(),
        device_name: deviceName.trim(),
        device_type: deviceType.trim() || "tablet",
      });
      setMessage("Device registered.");
      setDeviceIdentifier("");
      setDeviceName("");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to register device.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCreateContract(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.createOfflineSyncContract(parsedOrganizationId, {
        contract_type: contractType,
        contract_payload_json: { schema_version: 1, source: "mobile_foundation_ui" },
      });
      setMessage("Offline sync contract created.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to create contract.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStartSession(deviceId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.createMobileSession(parsedOrganizationId, { device_id: deviceId });
      setMessage("Mobile session started.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to start session.");
    } finally {
      setSubmitting(false);
    }
  }

  const canView =
    dashboard?.permissions.can_view ?? (organization ? hasOrganizationPermission(organization, "organization:view") : false);
  const canManage =
    dashboard?.permissions.can_manage ?? (organization ? hasOrganizationPermission(organization, "organization:update") : false);

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
        eyebrow="P44-01"
        title={organization ? `${organization.display_name} mobile foundation` : "Mobile foundation"}
        description="Device registry, offline runtime sessions, sync contracts, and append-only foundation lineage."
        actions={
          <div className="flex flex-wrap gap-2">
            {canView ? (
              <Link
                to={`/organizations/${parsedOrganizationId}/mobile-ops`}
                className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100"
              >
                Mobile ops
              </Link>
            ) : null}
            {canView ? (
              <Link
                to={`/organizations/${parsedOrganizationId}/mobile-security`}
                className="rounded-2xl border border-rose-400/30 px-4 py-2 text-sm font-semibold text-rose-100"
              >
                Mobile security
              </Link>
            ) : null}
            {canView ? (
              <Link
                to={`/organizations/${parsedOrganizationId}/mobile-analytics`}
                className="rounded-2xl border border-indigo-400/30 px-4 py-2 text-sm font-semibold text-indigo-100"
              >
                Mobile analytics
              </Link>
            ) : null}
            {canView ? (
              <Link
                to={`/organizations/${parsedOrganizationId}/mobile-scanning`}
                className="rounded-2xl border border-violet-400/30 px-4 py-2 text-sm font-semibold text-violet-100"
              >
                Mobile scanning
              </Link>
            ) : null}
            {canView ? (
              <Link
                to={`/organizations/${parsedOrganizationId}/offline-inventory`}
                className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100"
              >
                Offline inventory
              </Link>
            ) : null}
            <Link
              to={`/organizations/${parsedOrganizationId}`}
              className="rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-200"
            >
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

      {loading ? <p className="mt-8 text-sm text-slate-400">Loading mobile foundation…</p> : null}

      {!loading && organization && !canView ? (
        <OrganizationAccessDeniedState
          title="Mobile foundation access denied"
          description="You need organization view permission to inspect mobile devices and offline runtime state."
        />
      ) : null}

      {!loading && canView && dashboard ? (
        <div className="mt-8 space-y-10">
          <MobileStatusDashboard summary={dashboard.summary} runtimeRegistry={dashboard.runtime_registry} />

          <section>
            <h2 className="text-lg font-semibold text-white">Device registry</h2>
            {canManage ? (
              <div className="mt-4 flex flex-wrap gap-2">
                <input
                  value={deviceIdentifier}
                  onChange={(e) => setDeviceIdentifier(e.target.value)}
                  placeholder="Device identifier"
                  className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                />
                <input
                  value={deviceName}
                  onChange={(e) => setDeviceName(e.target.value)}
                  placeholder="Device name"
                  className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                />
                <input
                  value={deviceType}
                  onChange={(e) => setDeviceType(e.target.value)}
                  placeholder="Type"
                  className="w-28 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                />
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => void handleRegisterDevice()}
                  className="rounded-xl border border-lime-400/40 px-4 py-2 text-sm font-semibold text-lime-100 disabled:opacity-50"
                >
                  Register device
                </button>
              </div>
            ) : null}
            <div className="mt-4">
              <MobileDeviceRegistryTable items={devices?.items ?? []} />
            </div>
            {canManage && devices?.items.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {devices.items.map((device) => (
                  <button
                    key={device.id}
                    type="button"
                    disabled={submitting}
                    onClick={() => void handleStartSession(device.id)}
                    className="rounded-xl border border-white/10 px-3 py-1.5 text-xs text-slate-200 disabled:opacity-50"
                  >
                    Start session on {device.device_name}
                  </button>
                ))}
              </div>
            ) : null}
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white">Mobile sessions</h2>
            <div className="mt-4">
              <MobileSessionViewer items={sessions?.items ?? []} />
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white">Offline sync contracts</h2>
            {canManage ? (
              <div className="mt-4 flex flex-wrap gap-2">
                <select
                  value={contractType}
                  onChange={(e) => setContractType(e.target.value)}
                  className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                >
                  <option value="inventory">inventory</option>
                  <option value="transaction">transaction</option>
                  <option value="lookup">lookup</option>
                  <option value="metadata">metadata</option>
                </select>
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => void handleCreateContract()}
                  className="rounded-xl border border-sky-400/40 px-4 py-2 text-sm font-semibold text-sky-100 disabled:opacity-50"
                >
                  Create contract
                </button>
              </div>
            ) : null}
            <div className="mt-4">
              <OfflineContractViewer items={contracts?.items ?? []} />
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white">Foundation events</h2>
            <div className="mt-4">
              <MobileFoundationEventTimeline events={dashboard.recent_events} />
            </div>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
