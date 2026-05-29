import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type IntakeStagingListResponse,
  type MobileDeviceListResponse,
  type MobileScanningDashboardResponse,
  type ScanCaptureListResponse,
  type ScanCaptureDetailResponse,
  type ScanLookupListResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { IntakeStagingViewer } from "../components/mobile/scanning/IntakeStagingViewer";
import { ScanCaptureForm } from "../components/mobile/scanning/ScanCaptureForm";
import { ScanEventTimeline } from "../components/mobile/scanning/ScanEventTimeline";
import { ScanHistoryTable } from "../components/mobile/scanning/ScanHistoryTable";
import { ScanLookupResultViewer } from "../components/mobile/scanning/ScanLookupResultViewer";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function MobileScanningPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [dashboard, setDashboard] = useState<MobileScanningDashboardResponse | null>(null);
  const [scans, setScans] = useState<ScanCaptureListResponse | null>(null);
  const [lookups, setLookups] = useState<ScanLookupListResponse | null>(null);
  const [staging, setStaging] = useState<IntakeStagingListResponse | null>(null);
  const [devices, setDevices] = useState<MobileDeviceListResponse | null>(null);
  const [lastCapture, setLastCapture] = useState<ScanCaptureDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busyStagingId, setBusyStagingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [scanType, setScanType] = useState("upc");
  const [scanValue, setScanValue] = useState("");
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
      const [dash, scanList, lookupList, stagingList, deviceList] = await Promise.all([
        apiClient.getMobileScanningDashboard(parsedOrganizationId),
        apiClient.listScanCaptures(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listScanLookupResults(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listIntakeStagingRecords(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listMobileDevices(parsedOrganizationId, { limit: 100, offset: 0 }),
      ]);
      setDashboard(dash);
      setScans(scanList);
      setLookups(lookupList);
      setStaging(stagingList);
      setDevices(deviceList);
      if (deviceList.items.length > 0 && deviceId === null) {
        setDeviceId(deviceList.items[0].id);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load mobile scanning.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCapture(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || deviceId === null || !scanValue.trim()) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const detail = await apiClient.captureMobileScan(parsedOrganizationId, {
        device_id: deviceId,
        scan_type: scanType,
        scan_value: scanValue.trim(),
      });
      setLastCapture(detail);
      setMessage("Scan captured and lookup completed.");
      setScanValue("");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to capture scan.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStageLastCapture(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || !lastCapture) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await apiClient.createIntakeStagingRecord(parsedOrganizationId, {
        scan_capture_id: lastCapture.capture.id,
        staging_payload_json: { source: "mobile_scanning_ui" },
      });
      setMessage("Intake staging record created.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to create staging record.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleApproveStaging(stagingId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyStagingId(stagingId);
    try {
      await apiClient.updateIntakeStagingRecord(parsedOrganizationId, stagingId, { staging_status: "approved" });
      setMessage("Intake record approved.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to approve staging record.");
    } finally {
      setBusyStagingId(null);
    }
  }

  async function handleArchiveStaging(stagingId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyStagingId(stagingId);
    try {
      await apiClient.updateIntakeStagingRecord(parsedOrganizationId, stagingId, { staging_status: "archived" });
      setMessage("Intake record archived.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to archive staging record.");
    } finally {
      setBusyStagingId(null);
    }
  }

  const canView =
    dashboard?.permissions.can_view ?? (organization ? hasOrganizationPermission(organization, "organization:view") : false);
  const canManage =
    dashboard?.permissions.can_manage ?? (organization ? hasOrganizationPermission(organization, "organization:update") : false);

  const summary = dashboard?.summary ?? {};
  const scansSummary = (summary["scans"] ?? {}) as Record<string, number>;
  const stagingSummary = (summary["staging"] ?? {}) as Record<string, number>;
  const lookupsSummary = (summary["lookups"] ?? {}) as Record<string, number>;

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
        eyebrow="P44-03"
        title={organization ? `${organization.display_name} mobile scanning` : "Mobile scanning"}
        description="Manual scan capture, deterministic lookup, intake staging, and append-only scan lineage."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link
              to={`/organizations/${parsedOrganizationId}/mobile-ops`}
              className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100"
            >
              Mobile ops
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/quick-sales`}
              className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100"
            >
              Quick sales
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/mobile`}
              className="rounded-2xl border border-lime-400/30 px-4 py-2 text-sm font-semibold text-lime-100"
            >
              Mobile foundation
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/convention-mode`}
              className="rounded-2xl border border-orange-400/30 px-4 py-2 text-sm font-semibold text-orange-100"
            >
              Convention mode
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/offline-inventory`}
              className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100"
            >
              Offline inventory
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/mobile-analytics`}
              className="rounded-2xl border border-indigo-400/30 px-4 py-2 text-sm font-semibold text-indigo-100"
            >
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

      {loading ? <p className="mt-8 text-sm text-slate-400">Loading mobile scanning…</p> : null}

      {!loading && organization && !canView ? (
        <OrganizationAccessDeniedState
          title="Mobile scanning access denied"
          description="You need organization view permission to inspect scan history and intake staging."
        />
      ) : null}

      {!loading && canView && dashboard ? (
        <div className="mt-8 space-y-10">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="Scans" value={String(scansSummary.total ?? 0)} />
            <StatCard label="Lookups" value={String(lookupsSummary.total ?? 0)} />
            <StatCard label="Pending intake" value={String(stagingSummary.pending ?? 0)} />
          </div>

          {canManage && (devices?.items.length ?? 0) > 0 ? (
            <section>
              <h2 className="text-lg font-semibold text-white">Scan capture</h2>
              <p className="mt-1 text-sm text-slate-400">Manual entry simulates device capture until camera integration lands.</p>
              <div className="mt-4">
                <ScanCaptureForm
                  scanType={scanType}
                  scanValue={scanValue}
                  deviceId={deviceId}
                  devices={devices?.items ?? []}
                  submitting={submitting}
                  onScanTypeChange={setScanType}
                  onScanValueChange={setScanValue}
                  onDeviceIdChange={setDeviceId}
                  onSubmit={() => void handleCapture()}
                />
              </div>
              {lastCapture ? (
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => void handleStageLastCapture()}
                  className="mt-3 rounded-xl border border-amber-400/40 px-4 py-2 text-sm font-semibold text-amber-100 disabled:opacity-50"
                >
                  Stage last capture for intake
                </button>
              ) : null}
            </section>
          ) : null}

          <section>
            <h2 className="text-lg font-semibold text-white">Scan history</h2>
            <div className="mt-4">
              <ScanHistoryTable items={scans?.items ?? []} />
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white">Lookup results</h2>
            <div className="mt-4">
              <ScanLookupResultViewer items={lookups?.items ?? []} />
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white">Intake staging</h2>
            <div className="mt-4">
              <IntakeStagingViewer
                items={staging?.items ?? []}
                canManage={canManage}
                busyStagingId={busyStagingId}
                onApprove={(id) => void handleApproveStaging(id)}
                onArchive={(id) => void handleArchiveStaging(id)}
              />
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white">Scan events</h2>
            <div className="mt-4">
              <ScanEventTimeline events={dashboard.recent_events} />
            </div>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
