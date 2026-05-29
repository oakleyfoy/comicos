import type { MobileDeviceSecurityPolicyResponse } from "../../../api/client";

interface MobileSecurityPolicyTableProps {
  policies: MobileDeviceSecurityPolicyResponse[];
  canManage: boolean;
  busyPolicyId: number | null;
  onToggle: (policy: MobileDeviceSecurityPolicyResponse) => void;
}

export function MobileSecurityPolicyTable({
  policies,
  canManage,
  busyPolicyId,
  onToggle,
}: MobileSecurityPolicyTableProps): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <h2 className="text-lg font-semibold text-white">Security policies</h2>
        <p className="mt-1 text-sm text-slate-400">Organization-scoped device access controls with deterministic status toggles.</p>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-sm text-slate-300">
          <thead className="text-xs uppercase tracking-[0.16em] text-slate-500">
            <tr>
              <th className="pb-3 pr-4 font-medium">Policy</th>
              <th className="pb-3 pr-4 font-medium">Status</th>
              <th className="pb-3 pr-4 font-medium">Payload</th>
              <th className="pb-3 font-medium">Controls</th>
            </tr>
          </thead>
          <tbody>
            {policies.map((policy) => (
              <tr key={policy.id} className="border-t border-white/5">
                <td className="py-3 pr-4 font-medium text-white">{policy.policy_key}</td>
                <td className="py-3 pr-4">{policy.policy_status}</td>
                <td className="py-3 pr-4 text-xs text-slate-400">{JSON.stringify(policy.policy_payload_json)}</td>
                <td className="py-3">
                  {canManage ? (
                    <button
                      type="button"
                      disabled={busyPolicyId === policy.id}
                      onClick={() => onToggle(policy)}
                      className="rounded-xl border border-sky-400/30 px-3 py-1.5 text-xs font-semibold text-sky-100 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {policy.policy_status === "active" ? "Disable" : "Enable"}
                    </button>
                  ) : (
                    <span className="text-xs text-slate-500">View only</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
