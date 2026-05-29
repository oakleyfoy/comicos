import { useMemo, useState } from "react";

import type {
  OrganizationMemberResponse,
  OrganizationMembershipRoleResponse,
  OrganizationRoleResponse,
} from "../../../api/client";
import { roleTone, sortRoleKeys } from "../../../lib/organizationPermissions";

export function OrganizationRoleAssignmentsPanel({
  members,
  roles,
  memberRoleAssignments,
  canManageRoles,
  busyKey,
  onAssign,
  onRemove,
}: {
  members: OrganizationMemberResponse[];
  roles: OrganizationRoleResponse[];
  memberRoleAssignments: Record<number, OrganizationMembershipRoleResponse[]>;
  canManageRoles: boolean;
  busyKey: string | null;
  onAssign: (memberId: number, roleKey: string) => Promise<void>;
  onRemove: (memberId: number, roleId: number) => Promise<void>;
}): JSX.Element {
  const [selectedRoleByMember, setSelectedRoleByMember] = useState<Record<number, string>>({});

  const sortedRoles = useMemo(() => [...roles].sort((left, right) => left.role_key.localeCompare(right.role_key)), [roles]);

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Role assignments</p>
        <h2 className="mt-1 text-lg font-semibold text-white">Member role shell</h2>
        <p className="mt-1 text-sm text-slate-400">The backend remains authoritative. This shell reflects the deterministic role registry and assignment APIs only.</p>
      </div>
      <div className="mt-4 space-y-4">
        {members.map((member) => {
          const assignments = memberRoleAssignments[member.id] ?? [];
          const assignedRoleKeys = new Set(assignments.map((assignment) => assignment.role_key));
          const availableRoles = sortedRoles.filter((role) => !assignedRoleKeys.has(role.role_key));
          const selectedRoleKey = selectedRoleByMember[member.id] ?? availableRoles[0]?.role_key ?? "";
          return (
            <div key={member.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-white">{member.user_email}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {sortRoleKeys(member.role_keys).map((roleKey) => (
                      <span key={roleKey} className={`rounded-full border px-3 py-1 text-xs font-semibold ${roleTone(roleKey)}`}>
                        {roleKey}
                      </span>
                    ))}
                  </div>
                </div>
                {canManageRoles && !member.is_owner ? (
                  <div className="flex flex-wrap gap-2">
                    <select
                      value={selectedRoleKey}
                      onChange={(event) =>
                        setSelectedRoleByMember((current) => ({
                          ...current,
                          [member.id]: event.target.value,
                        }))
                      }
                      className="rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                    >
                      {availableRoles.map((role) => (
                        <option key={role.id} value={role.role_key}>
                          {role.display_name}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      disabled={!selectedRoleKey || availableRoles.length === 0 || busyKey === `assign:${member.id}`}
                      onClick={() => void onAssign(member.id, selectedRoleKey)}
                      className="rounded-2xl bg-fuchsia-500 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {busyKey === `assign:${member.id}` ? "Assigning..." : "Assign"}
                    </button>
                  </div>
                ) : null}
              </div>
              {canManageRoles && assignments.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {assignments.map((assignment) => (
                    <button
                      key={assignment.id}
                      type="button"
                      onClick={() => void onRemove(member.id, assignment.organization_role_id)}
                      disabled={busyKey === `remove:${member.id}:${assignment.organization_role_id}` || assignment.role_key === "owner"}
                      className="rounded-full border border-rose-400/25 bg-rose-400/10 px-3 py-1 text-xs text-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Remove {assignment.role_key}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}
