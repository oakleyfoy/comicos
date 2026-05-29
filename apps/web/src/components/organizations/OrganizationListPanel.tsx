import { Link } from "react-router-dom";

import { EmptyState } from "../EmptyState";
import type { OrganizationResponse } from "../../api/client";

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function OrganizationListPanel({ organizations }: { organizations: OrganizationResponse[] }): JSX.Element {
  if (!organizations.length) {
    return <EmptyState title="No organizations yet" description="Create your first organization to establish dealer membership and invitation lineage." />;
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Organization index</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Current memberships</h2>
        </div>
        <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300">{organizations.length} visible</span>
      </div>
      <div className="mt-4 space-y-3">
        {organizations.map((organization) => (
          <Link
            key={organization.id}
            to={`/organizations/${organization.id}`}
            className="block rounded-2xl border border-white/10 bg-slate-950/40 p-4 transition hover:border-fuchsia-400/40"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-white">{organization.display_name}</h3>
                <p className="mt-1 text-sm text-slate-400">
                  `{organization.slug}` • {organization.organization_type} • {organization.status}
                </p>
              </div>
              <div className="text-right text-xs text-slate-400">
                <p>{organization.active_member_count} members</p>
                <p>{organization.pending_invitation_count} pending invites</p>
                <p className="mt-1">Updated {formatDateTime(organization.updated_at)}</p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
