import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type OrganizationArchiveRequest,
  type OrganizationEventResponse,
  type OrganizationInvitationResponse,
  type OrganizationMemberResponse,
  type OrganizationMembershipRoleResponse,
  type OrganizationRoleResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationEventsPanel } from "../components/organizations/OrganizationEventsPanel";
import { OrganizationInvitePanel } from "../components/organizations/OrganizationInvitePanel";
import { OrganizationMembersPanel } from "../components/organizations/OrganizationMembersPanel";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { OrganizationRoleAssignmentsPanel } from "../components/organizations/permissions/OrganizationRoleAssignmentsPanel";
import { OrganizationRoleMatrixPanel } from "../components/organizations/permissions/OrganizationRoleMatrixPanel";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function OrganizationDetailPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [members, setMembers] = useState<OrganizationMemberResponse[]>([]);
  const [events, setEvents] = useState<OrganizationEventResponse[]>([]);
  const [roles, setRoles] = useState<OrganizationRoleResponse[]>([]);
  const [memberRoleAssignments, setMemberRoleAssignments] = useState<Record<number, OrganizationMembershipRoleResponse[]>>({});
  const [lastInvitation, setLastInvitation] = useState<OrganizationInvitationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [inviting, setInviting] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [busyRoleKey, setBusyRoleKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      const canViewMembers = hasOrganizationPermission(org, "members:view");
      const canViewAudit = hasOrganizationPermission(org, "audit:view");
      const [memberList, eventList, roleList] = await Promise.all([
        canViewMembers ? apiClient.listOrganizationMembers(parsedOrganizationId, { limit: 100, offset: 0 }) : Promise.resolve({ items: [], pagination: { total_count: 0, limit: 0, offset: 0, has_next: false, next_cursor: null } }),
        canViewAudit ? apiClient.listOrganizationEvents(parsedOrganizationId, { limit: 100, offset: 0 }) : Promise.resolve({ items: [], pagination: { total_count: 0, limit: 0, offset: 0, has_next: false, next_cursor: null } }),
        canViewMembers ? apiClient.listOrganizationRoles(parsedOrganizationId, { limit: 50, offset: 0 }) : Promise.resolve({ items: [], pagination: { total_count: 0, limit: 0, offset: 0, has_next: false, next_cursor: null } }),
      ]);
      setOrganization(org);
      setMembers(memberList.items);
      setEvents(eventList.items);
      setRoles(roleList.items);
      if (canViewMembers && memberList.items.length > 0) {
        const roleAssignments = await Promise.all(
          memberList.items.map(async (member) => ({
            memberId: member.id,
            assignments: (await apiClient.listOrganizationMemberRoles(parsedOrganizationId, member.id, { limit: 50, offset: 0 })).items,
          })),
        );
        setMemberRoleAssignments(
          roleAssignments.reduce<Record<number, OrganizationMembershipRoleResponse[]>>((accumulator, row) => {
            accumulator[row.memberId] = row.assignments;
            return accumulator;
          }, {}),
        );
      } else {
        setMemberRoleAssignments({});
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load organization workspace.");
    } finally {
      setLoading(false);
    }
  }

  async function handleInvite(email: string): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setInviting(true);
    setError(null);
    try {
      const invitation = await apiClient.inviteOrganizationMember(parsedOrganizationId, { email });
      setLastInvitation(invitation);
      await refresh();
    } catch (inviteErr) {
      setError(inviteErr instanceof ApiError ? inviteErr.message : "Unable to create invitation.");
    } finally {
      setInviting(false);
    }
  }

  async function handleAssignRole(memberId: number, roleKey: string): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyRoleKey(`assign:${memberId}`);
    setError(null);
    try {
      await apiClient.assignOrganizationMemberRole(parsedOrganizationId, memberId, { role_key: roleKey });
      await refresh();
    } catch (roleErr) {
      setError(roleErr instanceof ApiError ? roleErr.message : "Unable to assign organization role.");
    } finally {
      setBusyRoleKey(null);
    }
  }

  async function handleRemoveRole(memberId: number, roleId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyRoleKey(`remove:${memberId}:${roleId}`);
    setError(null);
    try {
      await apiClient.removeOrganizationMemberRole(parsedOrganizationId, memberId, roleId);
      await refresh();
    } catch (roleErr) {
      setError(roleErr instanceof ApiError ? roleErr.message : "Unable to remove organization role.");
    } finally {
      setBusyRoleKey(null);
    }
  }

  async function handleArchive(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setArchiving(true);
    setError(null);
    try {
      const payload: OrganizationArchiveRequest = { reason: "Archived from organization detail shell." };
      const archived = await apiClient.archiveOrganization(parsedOrganizationId, payload);
      setOrganization(archived);
      await refresh();
    } catch (archiveErr) {
      setError(archiveErr instanceof ApiError ? archiveErr.message : "Unable to archive organization.");
    } finally {
      setArchiving(false);
    }
  }

  if (!Number.isFinite(parsedOrganizationId)) {
    return (
      <AppShell>
        <EmptyState title="Invalid organization" description="The organization identifier in the URL is not valid." />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P42-01"
        title={organization?.display_name ?? "Organization detail"}
        description="Member lineage, invitation shell, and append-only event history for the initial multi-tenant organization foundation."
        actions={
          <div className="flex gap-2">
            <Link to="/organizations" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              All organizations
            </Link>
            {organization && hasOrganizationPermission(organization, "inventory:view") ? (
              <Link
                to={`/organizations/${organization.id}/inventory`}
                className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100"
              >
                Shared inventory
              </Link>
            ) : null}
            {organization && hasOrganizationPermission(organization, "organization:view") ? (
              <Link
                to={`/organizations/${organization.id}/activity`}
                className="rounded-2xl border border-emerald-400/30 px-4 py-2 text-sm font-semibold text-emerald-100"
              >
                Activity feed
              </Link>
            ) : null}
            {organization && hasOrganizationPermission(organization, "audit:view") ? (
              <Link
                to={`/organizations/${organization.id}/audit`}
                className="rounded-2xl border border-rose-400/30 px-4 py-2 text-sm font-semibold text-rose-100"
              >
                Audit ledger
              </Link>
            ) : null}
            {organization && hasOrganizationPermission(organization, "operations:view") ? (
              <Link
                to={`/organizations/${organization.id}/dashboard`}
                className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100"
              >
                Operations dashboard
              </Link>
            ) : null}
            {organization && hasOrganizationPermission(organization, "operations:view") ? (
              <Link
                to={`/organizations/${organization.id}/reviews`}
                className="rounded-2xl border border-violet-400/30 px-4 py-2 text-sm font-semibold text-violet-100"
              >
                Team reviews
              </Link>
            ) : null}
            {organization && hasOrganizationPermission(organization, "organization:update") ? (
              <Link
                to={`/organizations/${organization.id}/storefront`}
                className="rounded-2xl border border-amber-400/30 px-4 py-2 text-sm font-semibold text-amber-100"
              >
                Storefront settings
              </Link>
            ) : null}
            <button
              type="button"
              onClick={() => void handleArchive()}
              disabled={archiving || organization?.status === "ARCHIVED" || !hasOrganizationPermission(organization, "organization:archive")}
              className="rounded-2xl border border-rose-400/35 px-4 py-2 text-sm font-semibold text-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {organization?.status === "ARCHIVED" ? "Archived" : archiving ? "Archiving..." : "Archive"}
            </button>
          </div>
        }
      />
      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}
      {loading || !organization ? (
        <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5 text-sm text-slate-300">Loading organization workspace...</section>
      ) : (
        <>
          <section className="mt-6 grid gap-4 md:grid-cols-4">
            <StatCard label="Status" value={organization.status} />
            <StatCard label="Members" value={String(organization.active_member_count)} />
            <StatCard label="Pending invites" value={String(organization.pending_invitation_count)} />
            <StatCard label="Updated" value={formatDateTime(organization.updated_at)} />
          </section>
          <div className="mt-4 grid gap-4 xl:grid-cols-[0.9fr,1.1fr]">
            <OrganizationInvitePanel
              submitting={inviting}
              lastInvitation={lastInvitation}
              onInvite={handleInvite}
              disabled={!hasOrganizationPermission(organization, "members:invite")}
              disabledMessage="Your current organization role cannot create new invitations."
            />
            {hasOrganizationPermission(organization, "members:view") ? (
              <OrganizationMembersPanel members={members} />
            ) : (
              <OrganizationAccessDeniedState
                title="Members hidden"
                description="Your current organization role does not include `members:view`."
              />
            )}
          </div>
          <div className="mt-4 grid gap-4 xl:grid-cols-[0.95fr,1.05fr]">
            {hasOrganizationPermission(organization, "members:view") ? (
              <OrganizationRoleMatrixPanel roles={roles} />
            ) : (
              <OrganizationAccessDeniedState
                title="Roles hidden"
                description="Your current organization role cannot inspect the organization role registry."
              />
            )}
            {hasOrganizationPermission(organization, "members:view") ? (
              <OrganizationRoleAssignmentsPanel
                members={members}
                roles={roles}
                memberRoleAssignments={memberRoleAssignments}
                canManageRoles={hasOrganizationPermission(organization, "members:roles:update")}
                busyKey={busyRoleKey}
                onAssign={handleAssignRole}
                onRemove={handleRemoveRole}
              />
            ) : (
              <OrganizationAccessDeniedState
                title="Role assignments hidden"
                description="Your current organization role cannot inspect organization member assignments."
              />
            )}
          </div>
          <div className="mt-4">
            {hasOrganizationPermission(organization, "audit:view") ? (
              <OrganizationEventsPanel events={events} />
            ) : (
              <OrganizationAccessDeniedState
                title="Audit events hidden"
                description="Your current organization role does not include `audit:view`, so append-only audit lineage stays fail-closed."
              />
            )}
          </div>
        </>
      )}
    </AppShell>
  );
}
