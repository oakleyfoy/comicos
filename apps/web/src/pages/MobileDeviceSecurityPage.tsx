import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MobileDeviceResponse,
  type MobileDeviceSecurityDashboardResponse,
  type MobileDeviceSecurityPolicyResponse,
  type MobileDeviceTrustStateResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { MobileDeviceTrustTable } from "../components/mobile/security/MobileDeviceTrustTable";
import { MobileSecurityAccessLogViewer } from "../components/mobile/security/MobileSecurityAccessLogViewer";
import { MobileSecurityEventTimeline } from "../components/mobile/security/MobileSecurityEventTimeline";
import { MobileSecurityPolicyTable } from "../components/mobile/security/MobileSecurityPolicyTable";
import { MobileSecuritySummaryPanel } from "../components/mobile/security/MobileSecuritySummaryPanel";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

const POLICY_KEYS = [
  "require_trusted_device",
  "block_suspended_device",
  "require_active_session",
  "allow_offline_actions",
];

export function MobileDeviceSecurityPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [dashboard, setDashboard] = useState<MobileDeviceSecurityDashboardResponse | null>(null);
  const [devices, setDevices] = useState<MobileDeviceResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyTrustStateId, setBusyTrustStateId] = useState<number | null>(null);
  const [busyPolicyId, setBusyPolicyId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [trustForm, setTrustForm] = useState({ mobileDeviceId: "", trustStatus: "trusted", trustReason: "" });
  const [policyForm, setPolicyForm] = useState({ policyKey: "require_trusted_device", policyStatus: "active" });

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
        setDevices([]);
        return;
      }
      const [mobileDevices, body] = await Promise.all([
        apiClient.listMobileDevices(parsedOrganizationId, { limit: 200, offset: 0 }),
        apiClient.getMobileDeviceSecurityDashboard(parsedOrganizationId),
      ]);
      setDevices(mobileDevices.items);
      setDashboard(body);
      setTrustForm((current) => ({
        ...current,
        mobileDeviceId: current.mobileDeviceId || String(mobileDevices.items[0]?.id ?? ""),
      }));
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load mobile device security.");
    } finally {
      setLoading(false);
    }
  }

  const trustStateIds = useMemo(() => new Set((dashboard?.trust_states ?? []).map((row) => row.mobile_device_id)), [dashboard]);
  const availableDevices = devices.filter((device) => !trustStateIds.has(device.id));
  const canView = dashboard?.permissions.can_view ?? (organization ? hasOrganizationPermission(organization, "organization:view") : false);
  const canManage = dashboard?.permissions.can_manage ?? (organization ? hasOrganizationPermission(organization, "organization:update") : false);

  async function handleCreateTrustState(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!Number.isFinite(parsedOrganizationId) || !trustForm.mobileDeviceId) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.createMobileDeviceTrustState(parsedOrganizationId, {
        mobile_device_id: Number(trustForm.mobileDeviceId),
        trust_status: trustForm.trustStatus,
        trust_reason: trustForm.trustReason || null,
      });
      setMessage("Device trust state saved.");
      setTrustForm({ mobileDeviceId: "", trustStatus: "trusted", trustReason: "" });
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to save device trust state.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCreatePolicy(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.createMobileDeviceSecurityPolicy(parsedOrganizationId, {
        policy_key: policyForm.policyKey,
        policy_status: policyForm.policyStatus,
        policy_payload_json: {},
      });
      setMessage("Device security policy saved.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to save device security policy.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSuspend(trustState: MobileDeviceTrustStateResponse): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyTrustStateId(trustState.id);
    setError(null);
    setMessage(null);
    try {
      await apiClient.updateMobileDeviceTrustState(parsedOrganizationId, trustState.id, {
        trust_status: "suspended",
        trust_reason: "Suspended from mobile security workspace",
      });
      setMessage("Device suspended.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to suspend device.");
    } finally {
      setBusyTrustStateId(null);
    }
  }

  async function handleUnsuspend(trustState: MobileDeviceTrustStateResponse): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyTrustStateId(trustState.id);
    setError(null);
    setMessage(null);
    try {
      await apiClient.updateMobileDeviceTrustState(parsedOrganizationId, trustState.id, {
        trust_status: "trusted",
        trust_reason: "Unsuspended from mobile security workspace",
      });
      setMessage("Device unsuspended.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to unsuspend device.");
    } finally {
      setBusyTrustStateId(null);
    }
  }

  async function handleTogglePolicy(policy: MobileDeviceSecurityPolicyResponse): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyPolicyId(policy.id);
    setError(null);
    setMessage(null);
    try {
      await apiClient.updateMobileDeviceSecurityPolicy(parsedOrganizationId, policy.id, {
        policy_status: policy.policy_status === "active" ? "inactive" : "active",
        policy_payload_json: policy.policy_payload_json,
      });
      setMessage("Policy updated.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to update policy.");
    } finally {
      setBusyPolicyId(null);
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
        eyebrow="P44-07"
        title={organization ? `${organization.display_name} mobile security` : "Mobile device security"}
        description="Deterministic trust-state management, device suspension controls, access auditing, and replay-safe security lineage for mobile operations."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to={`/organizations/${parsedOrganizationId}/mobile`} className="rounded-2xl border border-lime-400/30 px-4 py-2 text-sm font-semibold text-lime-100">
              Mobile foundation
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile-ops`} className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100">
              Mobile ops
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile-analytics`} className="rounded-2xl border border-indigo-400/30 px-4 py-2 text-sm font-semibold text-indigo-100">
              Mobile analytics
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
          Loading mobile device security...
        </section>
      ) : null}
      {!loading && organization && !canView ? (
        <div className="mt-6">
          <OrganizationAccessDeniedState
            title="Mobile security access denied"
            description="Mobile device security visibility is deny-by-default and requires `organization:view`."
          />
        </div>
      ) : null}
      {!loading && organization && canView && dashboard ? (
        <>
          <section className="mt-6">
            <MobileSecuritySummaryPanel dashboard={dashboard} />
          </section>

          {canManage ? (
            <section className="mt-6 grid gap-4 xl:grid-cols-2">
              <form onSubmit={(event) => void handleCreateTrustState(event)} className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
                <h2 className="text-lg font-semibold text-white">Register trust state</h2>
                <div className="mt-4 grid gap-3">
                  <label className="text-sm text-slate-300">
                    Device
                    <select
                      value={trustForm.mobileDeviceId}
                      onChange={(event) => setTrustForm((current) => ({ ...current, mobileDeviceId: event.target.value }))}
                      className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                    >
                      <option value="">Select device</option>
                      {availableDevices.map((device) => (
                        <option key={device.id} value={device.id}>
                          {device.device_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-sm text-slate-300">
                    Status
                    <select
                      value={trustForm.trustStatus}
                      onChange={(event) => setTrustForm((current) => ({ ...current, trustStatus: event.target.value }))}
                      className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                    >
                      <option value="trusted">trusted</option>
                      <option value="untrusted">untrusted</option>
                      <option value="suspended">suspended</option>
                    </select>
                  </label>
                  <label className="text-sm text-slate-300">
                    Reason
                    <input
                      value={trustForm.trustReason}
                      onChange={(event) => setTrustForm((current) => ({ ...current, trustReason: event.target.value }))}
                      className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                    />
                  </label>
                  <button
                    type="submit"
                    disabled={submitting || !trustForm.mobileDeviceId}
                    className="rounded-2xl border border-emerald-400/30 px-4 py-2 text-sm font-semibold text-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Save trust state
                  </button>
                </div>
              </form>

              <form onSubmit={(event) => void handleCreatePolicy(event)} className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
                <h2 className="text-lg font-semibold text-white">Create policy</h2>
                <div className="mt-4 grid gap-3">
                  <label className="text-sm text-slate-300">
                    Policy key
                    <select
                      value={policyForm.policyKey}
                      onChange={(event) => setPolicyForm((current) => ({ ...current, policyKey: event.target.value }))}
                      className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                    >
                      {POLICY_KEYS.map((policyKey) => (
                        <option key={policyKey} value={policyKey}>
                          {policyKey}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-sm text-slate-300">
                    Status
                    <select
                      value={policyForm.policyStatus}
                      onChange={(event) => setPolicyForm((current) => ({ ...current, policyStatus: event.target.value }))}
                      className="mt-1 w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                    >
                      <option value="active">active</option>
                      <option value="inactive">inactive</option>
                    </select>
                  </label>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Save policy
                  </button>
                </div>
              </form>
            </section>
          ) : null}

          <section className="mt-6">
            <MobileDeviceTrustTable
              devices={devices}
              trustStates={dashboard.trust_states}
              canManage={canManage}
              busyTrustStateId={busyTrustStateId}
              onSuspend={(trustState) => void handleSuspend(trustState)}
              onUnsuspend={(trustState) => void handleUnsuspend(trustState)}
            />
          </section>
          <section className="mt-6">
            <MobileSecurityPolicyTable
              policies={dashboard.policies}
              canManage={canManage}
              busyPolicyId={busyPolicyId}
              onToggle={(policy) => void handleTogglePolicy(policy)}
            />
          </section>
          <section className="mt-6 grid gap-4 xl:grid-cols-[1fr_1fr]">
            <MobileSecurityAccessLogViewer logs={dashboard.access_logs} />
            <MobileSecurityEventTimeline events={dashboard.events} />
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
