import type { OrganizationRoleResponse } from "../../../api/client";

export function OrganizationRoleMatrixPanel({ roles }: { roles: OrganizationRoleResponse[] }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Role registry</p>
        <h2 className="mt-1 text-lg font-semibold text-white">Organization roles</h2>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {roles.map((role) => (
          <div key={role.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-medium text-white">{role.display_name}</p>
                <p className="mt-1 text-sm text-slate-400">`{role.role_key}`</p>
              </div>
              {role.system_managed ? (
                <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300">System</span>
              ) : null}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {role.permission_keys.map((permissionKey) => (
                <span key={permissionKey} className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-100">
                  {permissionKey}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
