import type { MobileDeviceResponse, MobileDeviceTrustStateResponse } from "../../../api/client";

interface MobileDeviceTrustTableProps {
  devices: MobileDeviceResponse[];
  trustStates: MobileDeviceTrustStateResponse[];
  canManage: boolean;
  busyTrustStateId: number | null;
  onSuspend: (trustState: MobileDeviceTrustStateResponse) => void;
  onUnsuspend: (trustState: MobileDeviceTrustStateResponse) => void;
}

export function MobileDeviceTrustTable({
  devices,
  trustStates,
  canManage,
  busyTrustStateId,
  onSuspend,
  onUnsuspend,
}: MobileDeviceTrustTableProps): JSX.Element {
  const deviceNameById = new Map<number, string>(devices.map((device) => [device.id, device.device_name]));

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Device trust states</h2>
          <p className="mt-1 text-sm text-slate-400">Current trust posture per registered mobile device.</p>
        </div>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-sm text-slate-300">
          <thead className="text-xs uppercase tracking-[0.16em] text-slate-500">
            <tr>
              <th className="pb-3 pr-4 font-medium">Device</th>
              <th className="pb-3 pr-4 font-medium">Status</th>
              <th className="pb-3 pr-4 font-medium">Reason</th>
              <th className="pb-3 pr-4 font-medium">Updated</th>
              <th className="pb-3 font-medium">Controls</th>
            </tr>
          </thead>
          <tbody>
            {trustStates.map((trustState) => (
              <tr key={trustState.id} className="border-t border-white/5">
                <td className="py-3 pr-4">
                  <p className="font-medium text-white">{deviceNameById.get(trustState.mobile_device_id) ?? `Device #${trustState.mobile_device_id}`}</p>
                  <p className="text-xs text-slate-500">#{trustState.mobile_device_id}</p>
                </td>
                <td className="py-3 pr-4">{trustState.trust_status}</td>
                <td className="py-3 pr-4">{trustState.trust_reason ?? "No reason recorded"}</td>
                <td className="py-3 pr-4">{new Date(trustState.updated_at).toLocaleString()}</td>
                <td className="py-3">
                  {canManage ? (
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        disabled={busyTrustStateId === trustState.id || trustState.trust_status === "suspended"}
                        onClick={() => onSuspend(trustState)}
                        className="rounded-xl border border-rose-400/30 px-3 py-1.5 text-xs font-semibold text-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Suspend
                      </button>
                      <button
                        type="button"
                        disabled={busyTrustStateId === trustState.id || trustState.trust_status !== "suspended"}
                        onClick={() => onUnsuspend(trustState)}
                        className="rounded-xl border border-emerald-400/30 px-3 py-1.5 text-xs font-semibold text-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Unsuspend
                      </button>
                    </div>
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
