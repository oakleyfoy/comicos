import type { OrganizationResponse, OrganizationSecurityContextRead } from "../../api/client";

export function SecurityContextPanel({
  organizations,
  securityContext,
  switching,
  onSwitch,
}: {
  organizations: OrganizationResponse[];
  securityContext: OrganizationSecurityContextRead | null;
  switching: boolean;
  onSwitch: (organizationId: number) => Promise<void>;
}): JSX.Element {
  const activeOrganizationId = securityContext?.active_organization_id ?? null;

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Security context</p>
        <h2 className="mt-1 text-lg font-semibold text-white">Active organization</h2>
        <p className="mt-1 text-sm text-slate-400">Organization selection is backend-authoritative and persisted through the session security context.</p>
      </div>
      <div className="mt-4 space-y-3">
        <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
          <p className="text-sm text-slate-300">
            Active org: <span className="font-semibold text-white">{securityContext?.active_organization_display_name ?? "None selected"}</span>
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Session status: {securityContext?.session_status ?? "UNKNOWN"} • roles {(securityContext?.role_keys ?? []).join(", ") || "none"}
          </p>
        </div>
        <div className="grid gap-2">
          {organizations.map((organization) => (
            <button
              key={organization.id}
              type="button"
              disabled={switching || activeOrganizationId === organization.id}
              onClick={() => void onSwitch(organization.id)}
              className="flex items-center justify-between rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-left text-sm text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span>{organization.display_name}</span>
              <span>{activeOrganizationId === organization.id ? "Active" : switching ? "Switching..." : "Switch"}</span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
