import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type OrganizationAuditAccessLogResponse,
  type OrganizationAuditCategory,
  type OrganizationAuditLedgerResponse,
  type OrganizationComplianceEventResponse,
  type OrganizationComplianceSeverity,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAuditAccessLogPanel } from "../components/organizations/audit/OrganizationAuditAccessLogPanel";
import { OrganizationAuditDetailViewer } from "../components/organizations/audit/OrganizationAuditDetailViewer";
import { OrganizationAuditFilters } from "../components/organizations/audit/OrganizationAuditFilters";
import { OrganizationAuditTimeline } from "../components/organizations/audit/OrganizationAuditTimeline";
import { OrganizationCompliancePanel } from "../components/organizations/audit/OrganizationCompliancePanel";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function OrganizationAuditPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [auditEntries, setAuditEntries] = useState<OrganizationAuditLedgerResponse[]>([]);
  const [complianceEvents, setComplianceEvents] = useState<OrganizationComplianceEventResponse[]>([]);
  const [accessLogs, setAccessLogs] = useState<OrganizationAuditAccessLogResponse[]>([]);
  const [selectedEntryId, setSelectedEntryId] = useState<number | null>(null);
  const [category, setCategory] = useState<OrganizationAuditCategory | null>(null);
  const [severity, setSeverity] = useState<OrganizationComplianceSeverity | null>(null);
  const [actorFilter, setActorFilter] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (): Promise<void> => {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const org = await apiClient.getOrganization(parsedOrganizationId);
      setOrganization(org);
      if (!hasOrganizationPermission(org, "audit:view")) {
        setAuditEntries([]);
        setComplianceEvents([]);
        setAccessLogs([]);
        return;
      }
      const actorId = actorFilter.trim() ? Number(actorFilter.trim()) : undefined;
      const [audit, compliance, logs] = await Promise.all([
        apiClient.listOrganizationAudit(parsedOrganizationId, {
          limit: 100,
          offset: 0,
          category: category ?? undefined,
          actor: Number.isFinite(actorId) ? actorId : undefined,
          resource_type: resourceType.trim() || undefined,
        }),
        apiClient.listOrganizationComplianceEvents(parsedOrganizationId, {
          limit: 100,
          offset: 0,
          severity: severity ?? undefined,
        }),
        apiClient.listOrganizationAuditAccessLogs(parsedOrganizationId, {
          limit: 100,
          offset: 0,
          actor: Number.isFinite(actorId) ? actorId : undefined,
          resource_type: resourceType.trim() || undefined,
        }),
      ]);
      setAuditEntries(audit.items);
      setComplianceEvents(compliance.items);
      setAccessLogs(logs.items);
      setSelectedEntryId((current) => {
        if (!audit.items.length) {
          return null;
        }
        if (current === null || !audit.items.some((row) => row.id === current)) {
          return audit.items[0].id;
        }
        return current;
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load organization audit ledger.");
    } finally {
      setLoading(false);
    }
  }, [parsedOrganizationId, category, severity, actorFilter, resourceType]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const selectedEntry = useMemo(
    () => auditEntries.find((entry) => entry.id === selectedEntryId) ?? null,
    [auditEntries, selectedEntryId],
  );

  if (!Number.isFinite(parsedOrganizationId)) {
    return (
      <AppShell>
        <EmptyState title="Invalid organization" description="The organization id in the URL is not valid." />
      </AppShell>
    );
  }

  const canViewAudit = organization ? hasOrganizationPermission(organization, "audit:view") : false;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Organization workspace"
        title="Audit ledger"
        description="Immutable organization audit history, compliance events, and audit-access traceability."
        actions={
          organization ? (
            <Link
              to={`/organizations/${organization.id}`}
              className="rounded-2xl border border-white/15 px-4 py-2 text-sm font-semibold text-slate-200"
            >
              Back to organization
            </Link>
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
          Loading audit workspace...
        </section>
      ) : !canViewAudit ? (
        <div className="mt-6">
          <OrganizationAccessDeniedState
            title="Audit ledger unavailable"
            description="You do not have permission to view organization audit and compliance data."
          />
        </div>
      ) : (
        <>
          <div className="mt-6">
            <OrganizationAuditFilters
              category={category}
              severity={severity}
              actorFilter={actorFilter}
              resourceType={resourceType}
              onCategoryChange={setCategory}
              onSeverityChange={setSeverity}
              onActorFilterChange={setActorFilter}
              onResourceTypeChange={setResourceType}
            />
          </div>
          <div className="mt-4 grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
            <OrganizationAuditTimeline
              entries={auditEntries}
              selectedEntryId={selectedEntryId}
              onSelect={setSelectedEntryId}
            />
            <OrganizationAuditDetailViewer entry={selectedEntry} />
          </div>
          <div className="mt-4 grid gap-4 xl:grid-cols-[0.95fr,1.05fr]">
            <OrganizationCompliancePanel events={complianceEvents} />
            <OrganizationAuditAccessLogPanel rows={accessLogs} />
          </div>
        </>
      )}
    </AppShell>
  );
}
