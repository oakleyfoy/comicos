import { EmptyState } from "../EmptyState";
import type { OrganizationMemberResponse } from "../../api/client";
import { roleTone, sortRoleKeys } from "../../lib/organizationPermissions";

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function tone(status: string): string {
  return status === "ACTIVE"
    ? "border-emerald-400/35 bg-emerald-400/10 text-emerald-100"
    : "border-slate-400/35 bg-slate-400/10 text-slate-200";
}

export function OrganizationMembersPanel({ members }: { members: OrganizationMemberResponse[] }): JSX.Element {
  if (!members.length) {
    return <EmptyState title="No members" description="Active members will appear here after invitations are accepted." />;
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Membership</p>
        <h2 className="mt-1 text-lg font-semibold text-white">Organization members</h2>
      </div>
      <div className="mt-4 space-y-3">
        {members.map((member) => (
          <div key={member.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-medium text-white">{member.user_email}</p>
                <p className="mt-1 text-sm text-slate-400">
                  Joined {formatDateTime(member.joined_at)}{member.is_owner ? " • Owner" : ""}
                </p>
                {member.role_keys.length ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {sortRoleKeys(member.role_keys).map((roleKey) => (
                      <span key={roleKey} className={`rounded-full border px-3 py-1 text-xs font-semibold ${roleTone(roleKey)}`}>
                        {roleKey}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
              <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${tone(member.membership_status)}`}>
                {member.membership_status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
